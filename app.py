import os, sqlite3, time, random, json, uuid, hashlib, re, urllib.request, urllib.parse, secrets, html as html_mod
from flask import Flask, g, render_template, session, request, jsonify, Response, redirect, url_for
from functools import wraps
try:
    from pymemcache.client import base as memcache
    MC = memcache.Client(('127.0.0.1', 11211))
except:
    MC = None

RECAPTCHA_SECRET = os.environ.get("RECAPTCHA_SECRET", "6Ldd32IsAAAAAKrY5NSlh8D3Mzefb4sxqWL6G-Od")
RECAPTCHA_SITE_KEY = os.environ.get("RECAPTCHA_SITE_KEY", "6Ldd32IsAAAAAC0k5zVL2qCkOkvl2BmS4uD9vm45")

# Generate a persistent secret key - stored in .secret_key file
_secret_key_path = os.path.join(os.path.dirname(__file__), ".secret_key")
if os.environ.get("SECRET_KEY"):
    _app_secret = os.environ["SECRET_KEY"]
else:
    if os.path.exists(_secret_key_path):
        with open(_secret_key_path, "r") as f:
            _app_secret = f.read().strip()
    else:
        _app_secret = secrets.token_hex(32)
        with open(_secret_key_path, "w") as f:
            f.write(_app_secret)

app = Flask(__name__)
app.secret_key = _app_secret
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SECURE_COOKIES", "").lower() == "true"

BOT_USER_AGENTS = ['bot', 'crawler', 'spider', 'scraper', 'curl', 'wget', 'python-requests', 'httpx', 'aiohttp', 'go-http', 'java', 'perl', 'ruby']
RATE_LIMITS = {}
db_path = os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "data.db"))
booted = False

def hash_pw(pw):
    return hashlib.sha256((pw + app.secret_key).encode()).hexdigest()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if is_ip_banned():
            session.clear()
            return jsonify({"ok": False, "error": "Access denied"}), 403
        if "user_id" not in session:
            return redirect(url_for("landing_page"))
        d = db()
        acc = d.execute("select id, session_token, ban_until from accounts where id=?", (session["user_id"],)).fetchone()
        if not acc:
            session.clear()
            return redirect(url_for("landing_page"))
        # Temp bans: keep user logged in but block actions via ban-check overlay
        # (no longer clear session for temp bans)
        if acc["session_token"] and session.get("token") != acc["session_token"]:
            session.clear()
            return redirect(url_for("landing_page"))
        now = int(time.time())
        if now - session.get("_last_ip_update", 0) > 60:
            d.execute("update accounts set last_ip=? where id=?", (get_client_ip(), session["user_id"]))
            d.commit()
            session["_last_ip_update"] = now
        return f(*args, **kwargs)
    return decorated

def db():
    if "db" not in g:
        g.db = sqlite3.connect(db_path, check_same_thread=False)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close(err):
    d = g.pop("db", None)
    if d:
        d.close()

def get_client_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr or '').split(',')[0].strip()

def is_rate_limited(key, limit, window):
    if MC:
        try:
            k = f"rl:{key}".encode()
            val = MC.get(k)
            count = int(val) if val else 0
            if count >= limit:
                return True
            MC.set(k, str(count + 1).encode(), expire=window)
            return False
        except:
            pass
    now = time.time()
    if key not in RATE_LIMITS:
        RATE_LIMITS[key] = []
    RATE_LIMITS[key] = [t for t in RATE_LIMITS[key] if now - t < window]
    if len(RATE_LIMITS[key]) >= limit:
        return True
    RATE_LIMITS[key].append(now)
    return False

def is_bot_request():
    ua = request.headers.get('User-Agent', '').lower()
    if not ua or len(ua) < 10:
        return True
    for bot in BOT_USER_AGENTS:
        if bot in ua:
            return True
    return False

def is_ip_banned():
    # IP banning disabled
    return False

def log_tx(user_id, action, amount, bal_before, bal_after):
    d = db()
    d.execute("insert into tx_log(user_id, action, amount, balance_before, balance_after, ts, ip) values(?,?,?,?,?,?,?)",
              (user_id, action, amount, bal_before, bal_after, int(time.time()), get_client_ip()))
    d.commit()

def check_suspicious(user_id):
    return False
    d = db()
    now = int(time.time())
    recent = d.execute("select sum(amount) as total from tx_log where user_id=? and amount>0 and ts>?", (user_id, now-3600)).fetchone()
    if recent and recent["total"] and recent["total"] > 10000000:
        d.execute("insert or replace into banned_ips(ip, banned_until, reason) values(?,?,?)", 
                  (get_client_ip(), now + 86400, "Suspicious earnings"))
        return True
    return False

def validate_session():
    if "user_id" not in session:
        return False
    d = db()
    acc = d.execute("select id, session_token from accounts where id=?", (session["user_id"],)).fetchone()
    if not acc:
        return False
    if acc["session_token"] and session.get("token") != acc["session_token"]:
        session.clear()
        return False
    return True

@app.before_request
def global_rate_limit():
    if request.endpoint and not request.endpoint.startswith('static'):
        ip = get_client_ip()
        if is_rate_limited(f"global:{ip}", 120, 60):
            return jsonify({"ok": False, "error": "Too many requests"}), 429

@app.before_request
def boot():
    global booted
    if booted:
        return
    init()
    seed()
    booted = True

@app.after_request
def set_device_id(response):
    if 'device_id' not in request.cookies:
        response.set_cookie('device_id', str(uuid.uuid4()), max_age=60*60*24*365, httponly=True, samesite='Lax')
    return response

@app.before_request
def update_last_seen():
    if "user_id" in session:
        try:
            d = db()
            d.execute("update users set last_seen=? where id=?", (int(time.time()), session["user_id"]))
            d.commit()
        except:
            pass

def init():
    d = db()
    d.executescript("""
    create table if not exists accounts(id text primary key, username text unique, password text, created integer, last_ip text, session_token text);
    create table if not exists device_signups(device_id text primary key, last_signup integer);
    create table if not exists banned_ips(ip text primary key, banned_until integer, reason text);
    create table if not exists tx_log(id integer primary key autoincrement, user_id text, action text, amount real, balance_before real, balance_after real, ts integer, ip text);
    create table if not exists shoes(id integer primary key, name text unique, rarity text, base real);
    create table if not exists users(id text primary key, balance real);
    create table if not exists global_state(id integer primary key, last_stock integer, last_price integer);
    create table if not exists market(shoe_id integer primary key, stock integer, price real, base real, news text, news_val real, news_until integer, trend real default 0, news2 text default '', news_val2 real default 0, news_until2 integer default 0);
    create table if not exists user_stock(user_id text, shoe_id integer, stock_cycle integer, bought integer, primary key(user_id, shoe_id, stock_cycle));
    create table if not exists hold(user_id text, shoe_id integer, qty integer, cost_basis real default 0, primary key(user_id, shoe_id));
    create table if not exists history(shoe_id integer, ts integer, price real);
    create table if not exists appraised(id integer primary key autoincrement, user_id text, shoe_id integer, rating real, multiplier real, ts integer);
    create table if not exists favorites(user_id text, shoe_id integer, appraisal_id integer, primary key(user_id, shoe_id, appraisal_id));
    create index if not exists idx_hist on history(shoe_id, ts);
    create index if not exists idx_appraised on appraised(user_id, shoe_id);
    create table if not exists trades(
        id integer primary key autoincrement,
        from_user text, to_user text,
        offer_shoes text, offer_cash real,
        want_shoes text, want_cash real,
        status text default 'pending',
        created integer, updated integer
    );
    create index if not exists idx_trades on trades(from_user, to_user, status);
    create table if not exists active_hanging(id integer primary key, victim text, started integer);
    create table if not exists notifications(id integer primary key autoincrement, user_id text, message text, ts integer);
    create table if not exists announcements(id integer primary key autoincrement, message text, ts integer, expires integer);
    create table if not exists shoe_index(user_id text, shoe_id integer, discovered integer, collected integer, primary key(user_id, shoe_id));
    create table if not exists court_session(id integer primary key, defendant text, accusation text, status text, started integer, ended integer);
    create table if not exists court_messages(id integer primary key autoincrement, session_id integer, username text, message text, is_system integer, ts integer);
    create table if not exists court_votes(session_id integer, voter text, vote text, primary key(session_id, voter));
    create table if not exists global_chat(id integer primary key autoincrement, user_id text, username text, message text, ts integer);
    create index if not exists idx_chat on global_chat(ts);
    create table if not exists gambling_pots(id integer primary key autoincrement, market_cap real, total_value real default 0, status text default 'open', winner_id text, winner_name text, created integer, ended integer, spin_start integer);
    create table if not exists pot_entries(id integer primary key autoincrement, pot_id integer, user_id text, username text, shoe_id integer, appraisal_id integer, rating real, multiplier real, variant text default '', value real, ts integer);
    insert or ignore into global_state(id, last_stock, last_price) values(1, 0, 0);
    insert or ignore into court_session(id, status) values(1, 'inactive');
    """)
    try:
        d.execute("alter table users add column last_income integer default 0")
    except:
        pass
    try:
        d.execute("alter table accounts add column ban_until integer default 0")
    except:
        pass
    try:
        d.execute("alter table accounts add column ban_reason text default ''")
    except:
        pass
    try:
        d.execute("alter table users add column last_seen integer default 0")
    except:
        pass
    try:
        d.execute("alter table accounts add column profile_picture text default ''")
    except:
        pass
    try:
        d.execute("alter table appraised add column variant text default ''")
    except:
        pass
    try:
        d.execute("alter table pot_entries add column variant text default ''")
    except:
        pass
    try:
        d.execute("alter table hold add column cost_basis real default 0")
    except:
        pass
    try:
        d.execute("alter table market add column trend real default 0")
    except:
        pass
    try:
        d.execute("alter table market add column news2 text default ''")
    except:
        pass
    try:
        d.execute("alter table market add column news_val2 real default 0")
    except:
        pass
    try:
        d.execute("alter table market add column news_until2 integer default 0")
    except:
        pass
    d.execute("update shoes set rarity='godly' where rarity='secret'")
    d.execute("update shoes set rarity='divine' where rarity='dexies'")
    d.execute("update shoes set rarity='grails' where rarity='lebos'")
    # Rename old divine shoe names to new ones
    old_divine = ["Dexies Phantom Protocol","Dexies Neural Apex","Dexies Quantum Flux","Dexies Void Walker","Dexies Neon Genesis","Dexies Cyber Nexus","Dexies Hologram Prime","Dexies Infinity Core","Dexies Plasma Edge","Dexies Dark Matter","Dexies Stellar Drift","Dexies Zero Gravity",
                  "Phantom Protocol","Neural Apex","Quantum Flux","Void Walker","Neon Genesis","Cyber Nexus","Hologram Prime","Infinity Core","Plasma Edge","Dark Matter","Stellar Drift","Zero Gravity",
                  "Divine Phantom Protocol","Divine Neural Apex","Divine Quantum Flux","Divine Void Walker","Divine Neon Genesis","Divine Cyber Nexus","Divine Hologram Prime","Divine Infinity Core","Divine Plasma Edge","Divine Dark Matter","Divine Stellar Drift","Divine Zero Gravity"]
    new_divine = ["Phantom Runner V","Nexus Stride Pro","Quantum Glider X","Void Step Eclipse","Genesis Boost NX","Cyber Kick Prime","Holo Glide Ultra","Infinity Runner Max","Plasma Stride Edge","Eclipse Walker GT","Stellar Dash Drift","Zero-G Sole XR"]
    for i, old in enumerate(old_divine):
        d.execute("update shoes set name=? where name=? and rarity='divine'", (new_divine[i % len(new_divine)], old))
    # Rename old grails shoe names to new ones
    old_grails = ["Lebos Divine Ascension","Lebos Eternal Crown","Lebos Celestial One","Lebos Golden Throne","Lebos Supreme Omega","Lebos Apex Deity","Lebos Immortal Reign","Lebos Cosmic Emperor","Lebos Ultimate Genesis",
                  "Divine Ascension","Eternal Crown","Celestial One","Golden Throne","Supreme Omega","Apex Deity","Immortal Reign","Cosmic Emperor","Ultimate Genesis",
                  "Grails Divine Ascension","Grails Eternal Crown","Grails Celestial One","Grails Golden Throne","Grails Supreme Omega","Grails Apex Deity","Grails Immortal Reign","Grails Cosmic Emperor","Grails Ultimate Genesis",
                  "Eternal Ascension","Celestial Crown","Golden Throne","Supreme Omega","Apex Deity","Immortal Reign","Cosmic Emperor","Ultimate Genesis","Astral Monarch"]
    new_grails = ["Eternal Air One","Crown Stride Supreme","Throne Runner Gold","Omega Kick Elite","Deity Glider Apex","Reign Step Immortal","Emperor Dash Cosmic","Genesis Runner Ultra","Monarch Stride Astral"]
    for i, old in enumerate(old_grails):
        d.execute("update shoes set name=? where name=? and rarity='grails'", (new_grails[i % len(new_grails)], old))
    d.execute("delete from shoes where name='leia luvs femboys'")
    d.execute("update shoes set name='The one??' where name='Aurora Stride Celestial' and rarity='heavenly'")
    for name in HEAVENLY_SHOES:
        existing = d.execute("select id from shoes where name=?", (name,)).fetchone()
        if not existing:
            lo, hi = BASE_PRICES["heavenly"]
            d.execute("insert into shoes(name, rarity, base) values(?,?,?)", (name, "heavenly", round(random.uniform(lo, hi), 2)))
    
    space_users = d.execute("select id from accounts where trim(username)=''").fetchall()
    for user in space_users:
        uid = user["id"]
        d.execute("delete from hold where user_id=?", (uid,))
        d.execute("delete from appraised where user_id=?", (uid,))
        d.execute("delete from favorites where user_id=?", (uid,))
        d.execute("delete from notifications where user_id=?", (uid,))
        d.execute("delete from shoe_index where user_id=?", (uid,))
        d.execute("delete from user_stock where user_id=?", (uid,))
        d.execute("delete from tx_log where user_id=?", (uid,))
        d.execute("delete from pot_entries where user_id=?", (uid,))
        d.execute("delete from global_chat where user_id=?", (uid,))
        d.execute("delete from trades where from_user=? or to_user=?", (uid, uid))
        d.execute("delete from users where id=?", (uid,))
        d.execute("delete from accounts where id=?", (uid,))
    
    d.commit()

def pick(w):
    r = random.random() * sum(w)
    s = 0
    for i, v in enumerate(w):
        s += v
        if r <= s:
            return i
    return len(w) - 1

RARITIES = ["common","uncommon","rare","epic","legendary","mythic","godly","divine","grails","heavenly"]
WEIGHTS = [40,22,14,10,6,4,2,1.5,0.5,0.1]
BASE_PRICES = {
    "common": (500, 1500),
    "uncommon": (1200, 3500),
    "rare": (3000, 8000),
    "epic": (7000, 18000),
    "legendary": (15000, 40000),
    "mythic": (35000, 90000),
    "godly": (80000, 250000),
    "divine": (200000, 500000),
    "grails": (500000, 2000000),
    "heavenly": (8000000, 12000000),
}
VOLATILITY = {
    "common": 1.2,
    "uncommon": 1.4,
    "rare": 1.6,
    "epic": 1.9,
    "legendary": 2.3,
    "mythic": 2.5,
    "godly": 2.8,
    "divine": 3.0,
    "grails": 3.2,
    "heavenly": 3.2,
}
ADMIN_USERS = ["lebodapotato"]
ADMIN_IPS = []
MAX_BALANCE = 100000000

DIVINE_SHOES = [
    "Phantom Runner V", "Nexus Stride Pro", "Quantum Glider X",
    "Void Step Eclipse", "Genesis Boost NX", "Cyber Kick Prime",
    "Holo Glide Ultra", "Infinity Runner Max", "Plasma Stride Edge",
    "Eclipse Walker GT", "Stellar Dash Drift", "Zero-G Sole XR"
]
GRAILS_SHOES = [
    "Eternal Air One", "Crown Stride Supreme", "Throne Runner Gold",
    "Omega Kick Elite", "Deity Glider Apex", "Reign Step Immortal",
    "Emperor Dash Cosmic", "Genesis Runner Ultra", "Monarch Stride Astral"
]
HEAVENLY_SHOES = [
    "The one??"
]

def seed():
    d = db()
    c = d.execute("select count(*) c from shoes").fetchone()["c"]
    if c >= 120:
        return
    a = ["Apex","Blur","Chroma","Cipher","Cobalt","Crux","Dawn","Drift","Echo","Flux","Forge","Frost","Gale","Glint","Halo","Haze","Ion","Jade","Kite","Luxe","Mako","Nova","Onyx","Pulse","Quill","Rift","Rune","Sable","Surge","Tempest","Umber","Vex","Warden","Xenon","Yonder","Zephyr"]
    b = ["Runner","Stride","Stomp","Sprint","Glider","Walker","Skimmer","Shadow","Bolt","Wave","Rider","Trace","Shift","Drive","Glide","Step","Leap","Slide","Vapor","Grind","Dash","Hover","Reverb","Arc","Shard","Crest","Spire","Trace","Vigor","Bloom","Shard","Drift","Fable","Strike","Quake"]
    c = ["One","II","III","IV","V","Prime","Edge","Core","Zero","Plus","Max","Ultra","Lite","Pro","XR","GT","NX","MK","FX","VX"]
    names = set()
    rows = []
    normal_rarities = ["common","uncommon","rare","epic","legendary","mythic","godly"]
    normal_weights = [40,22,14,10,6,4,2]
    while len(rows) < 120:
        name = f"{random.choice(a)} {random.choice(b)} {random.choice(c)}"
        if name in names:
            continue
        names.add(name)
        rr = normal_rarities[pick(normal_weights)]
        lo, hi = BASE_PRICES[rr]
        rows.append((name, rr, round(random.uniform(lo, hi), 2)))
    for name in DIVINE_SHOES:
        lo, hi = BASE_PRICES["divine"]
        rows.append((name, "divine", round(random.uniform(lo, hi), 2)))
    for name in GRAILS_SHOES:
        lo, hi = BASE_PRICES["grails"]
        rows.append((name, "grails", round(random.uniform(lo, hi), 2)))
    for name in HEAVENLY_SHOES:
        lo, hi = BASE_PRICES["heavenly"]
        rows.append((name, "heavenly", round(random.uniform(lo, hi), 2)))
    d.executemany("insert or ignore into shoes(name, rarity, base) values(?,?,?)", rows)
    d.commit()

def uid():
    if "user_id" not in session:
        return None
    u = session["user_id"]
    d = db()
    row = d.execute("select id from users where id=?", (u,)).fetchone()
    if not row:
        d.execute("insert into users(id, balance, last_income) values(?,?,?)", (u, 10000, 0))
        d.commit()
    return u

def stock_amt(r):
    return {
        "common": (15, 50),
        "uncommon": (10, 35),
        "rare": (6, 20),
        "epic": (4, 12),
        "legendary": (2, 8),
        "mythic": (1, 5),
        "godly": (1, 3),
        "divine": (1, 2),
        "grails": (1, 1),
        "heavenly": (1, 1),
    }[r]

def refresh(force=False):
    d = db()
    now = int(time.time())
    gs = d.execute("select last_stock from global_state where id=1").fetchone()
    last = gs["last_stock"] if gs else 0
    n = d.execute("select count(*) c from market").fetchone()["c"]
    if not force and now - last < 300 and n == 15:
        return
    d.execute("delete from market")
    picked = set()
    rows = []
    normal_rarities = ["common","uncommon","rare","epic","legendary","mythic","godly"]
    normal_weights = [40,22,14,10,6,4,2]
    while len(rows) < 14:
        rr = normal_rarities[pick(normal_weights)]
        shoe = d.execute("select * from shoes where rarity=? order by random() limit 1", (rr,)).fetchone()
        if not shoe or shoe["id"] in picked:
            continue
        picked.add(shoe["id"])
        lo, hi = stock_amt(rr)
        stock = random.randint(lo, hi)
        base = shoe["base"]
        vol = VOLATILITY[rr]
        price = round(base * (1 + random.uniform(-0.15, 0.15) * vol), 2)
        rows.append((shoe["id"], stock, price, base, "", 0.0, 0))
        d.execute("insert into history(shoe_id, ts, price) values(?,?,?)", (shoe["id"], now, price))
    if random.random() < 0.001:
        rr = "heavenly"
        shoe = d.execute("select * from shoes where rarity=? order by random() limit 1", (rr,)).fetchone()
        if shoe and shoe["id"] not in picked:
            picked.add(shoe["id"])
            stock = 1
            vol = VOLATILITY[rr]
            price = round(shoe["base"] * (1 + random.uniform(-0.15, 0.15) * vol), 2)
            rows.append((shoe["id"], stock, price, shoe["base"], "", 0.0, 0))
            d.execute("insert into history(shoe_id, ts, price) values(?,?,?)", (shoe["id"], now, price))
    if random.random() < 0.01:
        rr = "grails" if random.random() < 0.25 else "divine"
        shoe = d.execute("select * from shoes where rarity=? order by random() limit 1", (rr,)).fetchone()
        if shoe and shoe["id"] not in picked:
            picked.add(shoe["id"])
            lo, hi = stock_amt(rr)
            stock = random.randint(lo, hi)
            vol = VOLATILITY[rr]
            price = round(shoe["base"] * (1 + random.uniform(-0.15, 0.15) * vol), 2)
            rows.append((shoe["id"], stock, price, shoe["base"], "", 0.0, 0))
            d.execute("insert into history(shoe_id, ts, price) values(?,?,?)", (shoe["id"], now, price))
    while len(rows) < 15:
        rr = normal_rarities[pick(normal_weights)]
        shoe = d.execute("select * from shoes where rarity=? order by random() limit 1", (rr,)).fetchone()
        if not shoe or shoe["id"] in picked:
            continue
        picked.add(shoe["id"])
        lo, hi = stock_amt(rr)
        stock = random.randint(lo, hi)
        vol = VOLATILITY[rr]
        price = round(shoe["base"] * (1 + random.uniform(-0.15, 0.15) * vol), 2)
        rows.append((shoe["id"], stock, price, shoe["base"], "", 0.0, 0))
        d.execute("insert into history(shoe_id, ts, price) values(?,?,?)", (shoe["id"], now, price))
    d.executemany("insert into market(shoe_id, stock, price, base, news, news_val, news_until, trend, news2, news_val2, news_until2) values(?,?,?,?,?,?,?,0,'',0,0)", rows)
    d.execute("update global_state set last_stock=? where id=1", (now,))
    d.commit()

NEWS_POSITIVE = [
    ("🔥 BREAKING: Major collab with {brand} announced! Demand skyrocketing!", 0.8),
    ("⭐ {celeb} spotted wearing these at the Grammy Awards!", 0.7),
    ("📈 Resale prices hitting all-time highs on StockX!", 0.6),
    ("🎯 Top 10 influencers all posting about these today!", 0.5),
    ("💎 Rare collectors edition discovered - bidding war erupts!", 0.5),
    ("🏆 Won 'Sneaker of the Year' at Hypebeast Awards!", 0.7),
    ("📱 TikTok trend #CryptoShoe goes viral with 50M views!", 0.6),
    ("🎨 Leaked images show fire new colorway dropping next week!", 0.4),
    ("🤝 {athlete} signs exclusive partnership deal!", 0.6),
    ("📰 Vogue: 'The must-have shoe of {year}'", 0.5),
    ("🚀 Pre-orders sold out in 12 seconds flat!", 0.7),
    ("💫 Designer hints at secret collaboration coming soon", 0.4),
    ("🎪 Front row at Paris Fashion Week - celebrities fighting over pairs!", 0.5),
    ("📊 Goldman Sachs analyst: 'Strong buy, 60% upside potential'", 0.6),
    ("🌟 {musician} performs entire concert wearing these!", 0.5),
    ("🏀 Worn in NBA Finals game-winning moment!", 0.65),
    ("🎬 Featured prominently in new Marvel movie!", 0.55),
    ("💰 Anonymous buyer pays $500k for prototype pair!", 0.75),
    ("🌐 Going viral in Asia - 10x demand spike reported!", 0.6),
    ("🎁 Surprise restock announced for tomorrow 9AM!", 0.45),
]
NEWS_NEGATIVE = [
    ("⚠️ ALERT: Factory quality control failures reported!", -0.7),
    ("📉 StockX flooded with fakes - authentication crisis!", -0.5),
    ("🚫 {celeb} calls them 'overrated trash' on Instagram!", -0.6),
    ("⏰ Major manufacturing delays - 6 month setback!", -0.4),
    ("💔 Brand CEO involved in scandal - stock plummets!", -0.6),
    ("📰 Sneaker News: 'Worst release of the year'", -0.5),
    ("🔻 Hype dead - everyone moving to the new {competitor} release", -0.4),
    ("⚡ Competitor drops identical design at half the price!", -0.5),
    ("🏭 Supply chain collapse - materials unavailable!", -0.4),
    ("📊 Market analysts: 'Avoid - downgrade to sell'", -0.5),
    ("🚨 Customs seizure - entire shipment confiscated!", -0.6),
    ("💸 Panic selling detected - resellers dumping inventory!", -0.5),
    ("❌ Celebrity endorsement deal falls through publicly!", -0.4),
    ("🔍 Investigation reveals questionable labor practices!", -0.5),
    ("📱 #CryptoShoeScam trending on Twitter!", -0.4),
    ("🦠 Production halted due to facility shutdown!", -0.55),
    ("⚖️ Lawsuit filed over design patent infringement!", -0.45),
    ("🗣️ Whistleblower exposes internal quality issues!", -0.6),
    ("📦 Mass returns reported - comfort complaints!", -0.35),
    ("🌧️ Warehouse flood destroys limited stock!", -0.5),
]
NEWS_WILD = [
    ("🎰 WHALE ALERT: Crypto billionaire buys 10,000 pairs!", 1.2),
    ("💀 RUMOR: Only 3 pairs exist in the world!", 1.5),
    ("🔮 LEAKED: Insider trading investigation imminent!", -0.9),
    ("⚡ FLASH CRASH: Bot manipulation detected!", -1.0),
    ("🌪️ SEC announces market manipulation probe!", -0.8),
    ("🚀 BREAKING: Elon just tweeted about these!", 1.3),
    ("💎 INCREDIBLE: Real diamond found in prototype!", 1.0),
    ("🎲 RECORD: Christie's auction hits $2.5M!", 0.9),
    ("👽 VIRAL: Allegedly worn by alien in leaked footage!", 1.1),
    ("🏆 HISTORIC: Michael Jordan endorses from retirement!", 1.4),
    ("🔥 IMPOSSIBLE: Factory burns down - last stock ever!", 1.6),
    ("💣 SCANDAL: CEO arrested - company future uncertain!", -1.2),
]

BRANDS = ["Gucci", "Louis Vuitton", "Off-White", "Supreme", "Balenciaga", "Prada", "Dior"]
CELEBS = ["Drake", "Beyoncé", "LeBron", "Zendaya", "Bad Bunny", "Rihanna", "Travis Scott"]
ATHLETES = ["Messi", "Ronaldo", "Curry", "Mahomes", "Serena Williams"]
MUSICIANS = ["Taylor Swift", "The Weeknd", "Doja Cat", "Post Malone"]
COMPETITORS = ["Yeezy", "Jordan", "Dunk", "New Balance"]

def news_pick(rarity):
    vol = VOLATILITY.get(rarity, 1.0)
    if vol >= 3.0 and random.random() < 0.3:
        text, val = random.choice(NEWS_WILD)
    elif random.random() < 0.5:
        text, val = random.choice(NEWS_POSITIVE)
    else:
        text, val = random.choice(NEWS_NEGATIVE)
    text = text.replace("{brand}", random.choice(BRANDS))
    text = text.replace("{celeb}", random.choice(CELEBS))
    text = text.replace("{athlete}", random.choice(ATHLETES))
    text = text.replace("{musician}", random.choice(MUSICIANS))
    text = text.replace("{competitor}", random.choice(COMPETITORS))
    text = text.replace("{year}", "2026")
    return (text, val)

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def prices():
    d = db()
    now = int(time.time())
    gs = d.execute("select last_price from global_state where id=1").fetchone()
    last = gs["last_price"] if gs else 0
    if now - last < 10:
        return
    SELL_FEE = 0.03  # 3% sell spread
    m = d.execute("select m.*, s.rarity from market m join shoes s on s.id=m.shoe_id").fetchall()
    for r in m:
        price = r["price"]
        base = r["base"]
        rarity = r["rarity"]
        vol = VOLATILITY.get(rarity, 1.0)
        diff = (price - base) / base
        trend = r["trend"] if r["trend"] else 0
        # Expire news slot 1
        val = r["news_val"]
        if r["news_until"] and r["news_until"] < now:
            d.execute("update market set news='', news_val=0, news_until=0 where shoe_id=?", (r["shoe_id"],))
            val = 0
        # Expire news slot 2
        val2 = r["news_val2"] if r["news_val2"] else 0
        if r["news_until2"] and r["news_until2"] < now:
            d.execute("update market set news2='', news_val2=0, news_until2=0 where shoe_id=?", (r["shoe_id"],))
            val2 = 0
        # News generation - slot 1
        news_chance = 0.12 + (vol - 1) * 0.06
        if not r["news_until"] and random.random() < news_chance:
            text, v = news_pick(rarity)
            v *= vol
            duration = random.randint(45, 240) if vol < 2 else random.randint(30, 180)
            d.execute("update market set news=?, news_val=?, news_until=? where shoe_id=?", (text, v, now + duration, r["shoe_id"]))
            val = v
        # News generation - slot 2 (lower chance, only if slot 1 is active)
        if r["news_until"] and not r["news_until2"] and random.random() < news_chance * 0.3:
            text2, v2 = news_pick(rarity)
            v2 *= vol
            duration2 = random.randint(30, 180) if vol < 2 else random.randint(20, 120)
            d.execute("update market set news2=?, news_val2=?, news_until2=? where shoe_id=?", (text2, v2, now + duration2, r["shoe_id"]))
            val2 = v2
        combined_val = val + val2 * 0.6  # second news has reduced impact
        # Trend: momentum that slowly builds and decays
        if price > base:
            trend += random.uniform(-0.02, 0.04)  # slight upward bias when above base
        else:
            trend += random.uniform(-0.04, 0.02)  # slight downward bias when below
        trend *= 0.92  # decay toward 0
        trend = clamp(trend, -0.3, 0.3)
        up = 0.5 - diff * 0.4 + combined_val * 0.25 + trend * 0.3
        up = clamp(up, 0.1, 0.9)
        delta = base * random.uniform(0.005, 0.035) * vol * (1 + abs(combined_val) * 0.5)
        if random.random() < up:
            price += delta
            trend += 0.02  # reinforce upward trend
        else:
            price -= delta
            trend -= 0.02  # reinforce downward trend
        trend = clamp(trend, -0.3, 0.3)
        price = round(clamp(price, base * 0.15, base * 4), 2)
        d.execute("update market set price=?, trend=? where shoe_id=?", (price, round(trend, 4), r["shoe_id"]))
        d.execute("insert into history(shoe_id, ts, price) values(?,?,?)", (r["shoe_id"], now, price))
    d.execute("delete from history where ts < ?", (now - 86400,))
    d.execute("update global_state set last_price=? where id=1", (now,))
    d.commit()

def income(u):
    d = db()
    now = int(time.time())
    row = d.execute("select balance, last_income from users where id=?", (u,)).fetchone()
    bal = row["balance"]
    last = row["last_income"] or 0
    if bal < 2000 and now - last >= 60:
        d.execute("update users set balance=balance+100, last_income=? where id=?", (now, u))
        d.commit()

def rating_class(rating):
    if rating == 10.0:
        return "perfect"
    elif rating >= 8.0:
        return "excellent"
    elif rating >= 6.0:
        return "good"
    elif rating >= 5.0:
        return "average"
    elif rating >= 3.0:
        return "poor"
    return "terrible"

def state(u):
    d = db()
    now = int(time.time())
    user = d.execute("select balance from users where id=?", (u,)).fetchone()
    bal = user["balance"]
    gs = d.execute("select last_stock, last_price from global_state where id=1").fetchone()
    last_stock = gs["last_stock"] if gs else 0
    last_price = gs["last_price"] if gs else now
    next_stock = last_stock + 300
    next_price = last_price + 10
    m_raw = d.execute("""
    select m.shoe_id id, s.name, s.rarity, m.stock, m.price, m.base,
           m.news, m.news_until, coalesce(m.news2,'') as news2, coalesce(m.trend,0) as trend
    from market m join shoes s on s.id=m.shoe_id
    order by s.rarity, s.name
    """).fetchall()
    stock_cycle = last_stock
    user_bought = {r["shoe_id"]: r["bought"] for r in d.execute("select shoe_id, bought from user_stock where user_id=? and stock_cycle=?", (u, stock_cycle)).fetchall()}
    m = []
    for r in m_raw:
        rd = dict(r)
        rd["stock"] = max(0, rd["stock"] - user_bought.get(rd["id"], 0))
        news_list = [rd["news"]] if rd["news"] else []
        if rd["news2"]:
            news_list.append(rd["news2"])
        rd["news"] = news_list
        rd["sell_price"] = round(rd["price"] * (1 - SELL_FEE), 2)
        rd["trend"] = round(rd["trend"], 2)
        del rd["news2"]
        m.append(rd)
    h = d.execute("""
    select h.shoe_id id, s.name, s.rarity, s.base, h.qty, coalesce(h.cost_basis, 0) as cost_basis
    from hold h join shoes s on s.id=h.shoe_id
    where h.user_id=? order by s.rarity, s.name
    """, (u,)).fetchall()
    appraised = d.execute("""
    select a.id as appraisal_id, a.shoe_id id, s.name, s.rarity, s.base, a.rating, a.multiplier, coalesce(a.variant,'') as variant
    from appraised a join shoes s on s.id=a.shoe_id
    where a.user_id=? order by a.rating desc, s.name
    """, (u,)).fetchall()
    market_ids = {r["id"] for r in m}
    hold_list = []
    for r in h:
        hr = dict(r)
        hr["appraised"] = False
        if hr["id"] in market_ids:
            mk = next(x for x in m if x["id"] == hr["id"])
            hr["sell_price"] = mk["sell_price"]
            hr["in_market"] = True
        else:
            hr["sell_price"] = get_sell_price(hr["id"])
            hr["in_market"] = False
        hold_list.append(hr)
    appraised_list = []
    for r in appraised:
        ar = dict(r)
        ar["appraised"] = True
        ar["rating_class"] = rating_class(ar["rating"])
        base_price = get_sell_price(ar["id"]) or ar["base"]
        ar["sell_price"] = round(base_price * ar["multiplier"], 2)
        ar["in_market"] = ar["id"] in market_ids
        appraised_list.append(ar)
    hist = {}
    for row in m:
        rows = d.execute("select ts, price from history where shoe_id=? order by ts desc limit 60", (row["id"],)).fetchall()
        hist[row["id"]] = [{"ts": r["ts"], "price": r["price"]} for r in rows][::-1]
    return {
        "balance": round(bal, 2),
        "market": m,
        "hold": hold_list,
        "appraised": appraised_list,
        "hist": hist,
        "next_stock": next_stock,
        "next_price": next_price,
        "server_time": now
    }

def shoe_state(u, shoe_id):
    d = db()
    shoe = d.execute("select id, name, rarity, base from shoes where id=?", (shoe_id,)).fetchone()
    if not shoe:
        return None
    m = d.execute("select price, stock, news, coalesce(news2,'') as news2, coalesce(trend,0) as trend from market where shoe_id=?", (shoe_id,)).fetchone()
    in_market = m is not None
    if m:
        price = m["price"]
        stock = m["stock"]
        news_list = [m["news"]] if m["news"] else []
        if m["news2"]:
            news_list.append(m["news2"])
        news = news_list
        shoe_trend = m["trend"]
    else:
        last = d.execute("select price from history where shoe_id=? order by ts desc limit 1", (shoe_id,)).fetchone()
        price = last["price"] if last else shoe["base"]
        stock = 0
        news = []
        shoe_trend = 0
    rows = d.execute("select ts, price from history where shoe_id=? order by ts", (shoe_id,)).fetchall()
    hold = d.execute("select qty, coalesce(cost_basis, 0) as cost_basis from hold where user_id=? and shoe_id=?", (u, shoe_id)).fetchone()
    owned = hold["qty"] if hold else 0
    cost_basis = hold["cost_basis"] if hold else 0
    gs = d.execute("select last_stock, last_price from global_state where id=1").fetchone()
    sell_price = round(price * (1 - SELL_FEE), 2) if in_market else round(price * 0.95 * (1 - SELL_FEE), 2)
    return {
        "id": shoe["id"],
        "name": shoe["name"],
        "rarity": shoe["rarity"],
        "base": shoe["base"],
        "price": price,
        "sell_price": sell_price,
        "stock": stock,
        "news": news,
        "trend": round(shoe_trend, 2),
        "in_market": in_market,
        "owned": owned,
        "cost_basis": round(cost_basis, 2),
        "history": [dict(r) for r in rows],
        "next_stock": (gs["last_stock"] if gs else 0) + 300,
        "next_price": (gs["last_price"] if gs else 0) + 10
    }

@app.route("/login", methods=["GET"])
def login_page():
    if "user_id" in session:
        return redirect(url_for("home"))
    return render_template("login.html")

@app.route("/notice")
def landing_page():
    if "user_id" in session:
        return redirect(url_for("home"))
    return render_template("landing.html")

@app.route("/signup", methods=["GET"])
def signup_page():
    if "user_id" in session:
        return redirect(url_for("home"))
    return render_template("signup.html")

@app.route("/api/login", methods=["POST"])
def api_login():
    if is_ip_banned():
        return jsonify({"ok": False, "error": "Access denied from this location"})
    ip = get_client_ip()
    # Login rate limiting disabled
    # if is_rate_limited(f"login:{ip}", 20, 300):
    #     return jsonify({"ok": False, "error": "Too many login attempts. Try again later."})
    data = request.json
    username = data.get("username", "").strip().lower()
    password = data.get("password", "")
    if is_rate_limited(f"login:{ip}", 10, 300):
        return jsonify({"ok": False, "error": "Too many login attempts. Try again later."})
    if username == "admin" and password == "00001111":
        return jsonify({"ok": False, "error": "Invalid credentials"})
    if not username or not password:
        return jsonify({"ok": False, "error": "Username and password required"})
    d = db()
    acc = d.execute("select id, password, ban_until, coalesce(ban_reason,'') as ban_reason from accounts where username=?", (username,)).fetchone()
    if not acc or acc["password"] != hash_pw(password):
        return jsonify({"ok": False, "error": "Invalid username or password"})
    now = int(time.time())
    ban_until = acc["ban_until"] or 0
    if ban_until > now:
        reason = (acc["ban_reason"] or "").strip()
        reason_msg = f" Reason: {reason}" if reason else ""
        remaining = ban_until - now
        if remaining > 86400:
            days = remaining // 86400
            return jsonify({"ok": False, "error": f"Account banned for {days} more day(s).{reason_msg}"})
        elif remaining > 3600:
            hours = remaining // 3600
            return jsonify({"ok": False, "error": f"Account banned for {hours} more hour(s).{reason_msg}"})
        else:
            mins = remaining // 60
            return jsonify({"ok": False, "error": f"Account banned for {mins} more minute(s).{reason_msg}"})
    token = uuid.uuid4().hex
    d.execute("update accounts set session_token=?, last_ip=? where id=?", (token, ip, acc["id"]))
    d.commit()
    session["user_id"] = acc["id"]
    session["username"] = username
    session["token"] = token
    return jsonify({"ok": True})

def verify_recaptcha(token):
    if not token:
        return False
    try:
        data = urllib.parse.urlencode({"secret": RECAPTCHA_SECRET, "response": token}).encode()
        req = urllib.request.Request("https://www.google.com/recaptcha/api/siteverify", data=data)
        resp = urllib.request.urlopen(req, timeout=5)
        result = json.loads(resp.read().decode())
        if result.get("success"):
            score = result.get("score", 1.0)
            return score >= 0.5
        return False
    except:
        return False

@app.route("/api/recaptcha-key")
def api_recaptcha_key():
    return jsonify({"key": RECAPTCHA_SITE_KEY})

@app.route("/api/signup", methods=["POST"])
def api_signup():
    if is_bot_request():
        return jsonify({"ok": False, "error": "Access denied"}), 403
    ip = get_client_ip()
    # Signup rate limiting disabled
    # if ip != "31.55.145.33" and is_rate_limited(f"signup:{ip}", 3, 3600):
    #     return jsonify({"ok": False, "error": "Too many signups from your location. Try again later."})
    data = request.json or {}
    if data.get("website") or data.get("email2") or data.get("phone"):
        return jsonify({"ok": False, "error": "Invalid request"})
    recaptcha_token = data.get("recaptcha", "")
    if not verify_recaptcha(recaptcha_token):
        return jsonify({"ok": False, "error": "Please complete the CAPTCHA"})
    username = data.get("username", "").strip().lower()
    password = data.get("password", "")
    d = db()
    now = int(time.time())
    device_id = request.cookies.get('device_id')
    if device_id:
        last = d.execute("select last_signup from device_signups where device_id=?", (device_id,)).fetchone()
        if last and now - last["last_signup"] < 21600:
            remaining = 21600 - (now - last["last_signup"])
            hrs = remaining // 3600
            mins = (remaining % 3600) // 60
            return jsonify({"ok": False, "error": f"You can't create another account yet. Try again in {hrs}h {mins}m"})
    if not username or len(username) < 3:
        return jsonify({"ok": False, "error": "Username must be at least 3 characters"})
    if len(username) > 20:
        return jsonify({"ok": False, "error": "Username must be 20 characters or less"})
    if not username.isalnum():
        return jsonify({"ok": False, "error": "Username must be alphanumeric"})
    bot_patterns = ["player", "investor", "user", "guest", "test", "admin", "bot", "account", "trader", "shoe"]
    for pat in bot_patterns:
        if username.lower().startswith(pat) and any(c.isdigit() for c in username):
            return jsonify({"ok": False, "error": "Username not allowed"})
    digit_count = sum(c.isdigit() for c in username)
    if digit_count >= 4:
        return jsonify({"ok": False, "error": "Username has too many numbers"})
    if len(username) >= 8:
        vowels = sum(1 for c in username if c in 'aeiou')
        if vowels < 2:
            return jsonify({"ok": False, "error": "Username looks like random characters"})
    if not password or len(password) < 4:
        return jsonify({"ok": False, "error": "Password must be at least 4 characters"})
    existing = d.execute("select id from accounts where username=?", (username,)).fetchone()
    if existing:
        return jsonify({"ok": False, "error": "Username already taken"})
    user_id = uuid.uuid4().hex
    d.execute("insert into accounts(id, username, password, created) values(?,?,?,?)", 
              (user_id, username, hash_pw(password), now))
    d.execute("insert into users(id, balance, last_income) values(?,?,?)", 
              (user_id, 10000, 0))
    if device_id:
        d.execute("insert or replace into device_signups(device_id, last_signup) values(?,?)", (device_id, now))
    d.commit()
    session["user_id"] = user_id
    session["username"] = username
    return jsonify({"ok": True})

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))

@app.route("/")
def home():
    if "user_id" not in session:
        return render_template("landing.html")
    d = db()
    acc = d.execute("select id from accounts where id=?", (session["user_id"],)).fetchone()
    if not acc:
        session.clear()
        return render_template("landing.html")
    uid()
    return render_template("index.html", is_admin=is_admin())

@app.route("/inventory")
@login_required
def inventory():
    uid()
    return render_template("inventory.html", is_admin=is_admin())

@app.route("/shoe/<int:shoe_id>")
@login_required
def shoe_page(shoe_id):
    uid()
    return render_template("details.html", shoe_id=shoe_id, is_admin=is_admin())

@app.route("/api/state")
@login_required
def api_state():
    u = uid()
    refresh()
    prices()
    income(u)
    return jsonify(state(u))

@app.route("/api/public/stock")
def api_public_stock():
    d = db()
    refresh()
    market = d.execute("""
        select s.id, s.name, s.rarity, m.price, m.stock 
        from market m join shoes s on s.id=m.shoe_id
        where m.stock > 0
        order by s.rarity desc, s.name
    """).fetchall()
    gs = d.execute("select last_stock from global_state where id=1").fetchone()
    next_refresh = (gs["last_stock"] + 300) if gs else 0
    return jsonify({
        "market": [dict(m) for m in market],
        "next_refresh": next_refresh,
        "server_time": int(time.time())
    })

@app.route("/api/shoe/<int:shoe_id>")
@login_required
def api_shoe(shoe_id):
    u = uid()
    refresh()
    prices()
    s = shoe_state(u, shoe_id)
    if not s:
        return jsonify({}), 404
    return jsonify(s)

@app.route("/buy", methods=["POST"])
@login_required
def buy():
    u = uid()
    shoe = int(request.json.get("id", 0))
    qty = int(request.json.get("qty", 0))
    if qty < 1:
        return jsonify({"ok": False})
    d = db()
    row = d.execute("select stock, price from market where shoe_id=?", (shoe,)).fetchone()
    if not row:
        return jsonify({"ok": False})
    gs = d.execute("select last_stock from global_state where id=1").fetchone()
    stock_cycle = gs["last_stock"] if gs else 0
    user_bought = d.execute("select bought from user_stock where user_id=? and shoe_id=? and stock_cycle=?", (u, shoe, stock_cycle)).fetchone()
    already_bought = user_bought["bought"] if user_bought else 0
    available = row["stock"] - already_bought
    if available < qty:
        return jsonify({"ok": False, "error": f"Only {available} left for you"})
    cost = row["price"] * qty
    bal = d.execute("select balance from users where id=?", (u,)).fetchone()["balance"]
    if bal < cost:
        return jsonify({"ok": False, "error": "Not enough balance"})
    d.execute("insert into user_stock(user_id, shoe_id, stock_cycle, bought) values(?,?,?,?) on conflict(user_id, shoe_id, stock_cycle) do update set bought=bought+?", (u, shoe, stock_cycle, qty, qty))
    existing_hold = d.execute("select qty, cost_basis from hold where user_id=? and shoe_id=?", (u, shoe)).fetchone()
    if existing_hold:
        old_qty = existing_hold["qty"]
        old_basis = existing_hold["cost_basis"] or 0
        new_basis = (old_basis * old_qty + cost) / (old_qty + qty)
        d.execute("update hold set qty=qty+?, cost_basis=? where user_id=? and shoe_id=?", (qty, round(new_basis, 4), u, shoe))
    else:
        d.execute("insert into hold(user_id, shoe_id, qty, cost_basis) values(?,?,?,?)", (u, shoe, qty, round(row["price"], 4)))
    d.execute("update users set balance=balance-? where id=?", (cost, u))
    now = int(time.time())
    d.execute("insert or ignore into shoe_index(user_id, shoe_id, discovered, collected) values(?,?,?,0)", (u, shoe, now))
    d.commit()
    return jsonify({"ok": True})

SELL_FEE = 0.03  # 3% sell spread to prevent buy-wait-sell exploit

def get_sell_price(shoe_id):
    d = db()
    market = d.execute("select price from market where shoe_id=?", (shoe_id,)).fetchone()
    if market:
        return round(market["price"] * (1 - SELL_FEE), 2)
    shoe = d.execute("select base, rarity from shoes where id=?", (shoe_id,)).fetchone()
    if not shoe:
        return None
    last_price = d.execute("select price from history where shoe_id=? order by ts desc limit 1", (shoe_id,)).fetchone()
    if last_price:
        return round(last_price["price"] * 0.95 * (1 - SELL_FEE), 2)
    return round(shoe["base"] * 0.9, 2)

@app.route("/sell", methods=["POST"])
@login_required
def sell():
    u = uid()
    shoe = int(request.json.get("id", 0))
    qty = int(request.json.get("qty", 0))
    appraisal_id = request.json.get("appraisal_id")
    if qty < 1:
        return jsonify({"ok": False, "error": "Invalid quantity"})
    d = db()
    if appraisal_id:
        row = d.execute("select shoe_id, multiplier from appraised where id=? and user_id=?", (appraisal_id, u)).fetchone()
        if not row:
            return jsonify({"ok": False, "error": "Appraised shoe not found"})
        price = get_sell_price(row["shoe_id"])
        if not price:
            return jsonify({"ok": False, "error": "Shoe not found"})
        gain = round(price * row["multiplier"], 2)
        bal_before = d.execute("select balance from users where id=?", (u,)).fetchone()["balance"]
        d.execute("delete from appraised where id=? and user_id=?", (appraisal_id, u))
        d.execute("update users set balance=balance+? where id=?", (gain, u))
        log_tx(u, "sell_appraised", gain, bal_before, bal_before + gain)
        if check_suspicious(u):
            d.commit()
            return jsonify({"ok": False, "error": "Suspicious activity detected"})
        d.commit()
        return jsonify({"ok": True, "price": price * row["multiplier"], "total": gain})
    row = d.execute("select qty from hold where user_id=? and shoe_id=?", (u, shoe)).fetchone()
    if not row or row["qty"] < qty:
        return jsonify({"ok": False, "error": "Not enough shoes"})
    price = get_sell_price(shoe)
    if not price:
        return jsonify({"ok": False, "error": "Shoe not found"})
    gain = round(price * qty, 2)
    d.execute("update hold set qty=qty-? where user_id=? and shoe_id=?", (qty, u, shoe))
    d.execute("delete from hold where user_id=? and shoe_id=? and qty<=0", (u, shoe))
    d.execute("update users set balance=balance+? where id=?", (gain, u))
    d.commit()
    return jsonify({"ok": True, "price": price, "total": gain})

@app.route("/sell-all", methods=["POST"])
@login_required
def sell_all():
    u = uid()
    d = db()
    total = 0
    fav_shoes = {r["shoe_id"] for r in d.execute("select shoe_id from favorites where user_id=? and appraisal_id=0", (u,)).fetchall()}
    fav_appraisals = {r["appraisal_id"] for r in d.execute("select appraisal_id from favorites where user_id=? and appraisal_id>0", (u,)).fetchall()}
    holds = d.execute("select shoe_id, qty from hold where user_id=?", (u,)).fetchall()
    for h in holds:
        if h["shoe_id"] in fav_shoes:
            continue
        price = get_sell_price(h["shoe_id"]) or 0
        total += price * h["qty"]
        d.execute("delete from hold where user_id=? and shoe_id=?", (u, h["shoe_id"]))
    appraised = d.execute("select a.id, a.shoe_id, a.multiplier from appraised a where a.user_id=?", (u,)).fetchall()
    for a in appraised:
        if a["id"] in fav_appraisals:
            continue
        price = get_sell_price(a["shoe_id"]) or 0
        total += price * a["multiplier"]
        d.execute("delete from appraised where id=?", (a["id"],))
    bal_before = d.execute("select balance from users where id=?", (u,)).fetchone()["balance"]
    d.execute("update users set balance=balance+? where id=?", (round(total, 2), u))
    log_tx(u, "sell_all", round(total, 2), bal_before, bal_before + round(total, 2))
    if check_suspicious(u):
        d.commit()
        return jsonify({"ok": False, "error": "Suspicious activity detected"})
    d.commit()
    return jsonify({"ok": True, "total": round(total, 2)})

@app.route("/api/favorite", methods=["POST"])
@login_required
def toggle_favorite():
    u = uid()
    d = db()
    shoe_id = request.json.get("shoe_id", 0)
    appraisal_id = request.json.get("appraisal_id", 0)
    exists = d.execute("select 1 from favorites where user_id=? and shoe_id=? and appraisal_id=?", (u, shoe_id, appraisal_id)).fetchone()
    if exists:
        d.execute("delete from favorites where user_id=? and shoe_id=? and appraisal_id=?", (u, shoe_id, appraisal_id))
        d.commit()
        return jsonify({"ok": True, "favorited": False})
    else:
        d.execute("insert into favorites(user_id, shoe_id, appraisal_id) values(?,?,?)", (u, shoe_id, appraisal_id))
        d.commit()
        return jsonify({"ok": True, "favorited": True})

@app.route("/appraise")
@login_required
def appraise_page():
    uid()
    return render_template("appraise.html", is_admin=is_admin())

BOB_FACTORS = {
    "stitching": ["stitching", "thread work", "seam alignment", "binding"],
    "material": ["leather grain", "fabric weave", "material texture", "surface finish"],
    "sole": ["sole integrity", "tread pattern", "cushioning", "arch support"],
    "symmetry": ["symmetry", "shape uniformity", "proportions", "form balance"],
    "color": ["color saturation", "dye consistency", "hue depth", "finish evenness"],
    "detail": ["logo embossing", "branding details", "accent placement", "trim quality"]
}
BOB_COMMENTS = {
    "perfect": [
        "🤯 HOLY SMOKES! This is... this is PERFECTION! I've checked the {factor1}, the {factor2}, everything! FLAWLESS!",
        "😱 I... I need to sit down. The {factor1} alone is museum-worthy. And that {factor2}? Unprecedented!",
        "🏆 In my 40 years of appraising, I've never given a perfect 10. The {factor1} and {factor2} changed that today.",
        "💎 *Adjusts monocle* My word... pristine {factor1}, impeccable {factor2}. This is the holy grail!",
        "🔥 I'm literally shaking! The {factor1} is otherworldly. The {factor2}? Divine craftsmanship!",
    ],
    "excellent": [
        "🌟 Magnificent! The {factor1} here is extraordinary, and the {factor2}? Top tier!",
        "✨ Now THIS is premium! {factor1} rates exceptional, {factor2} near-perfect. Impressive!",
        "👏 Exceptional! I've examined the {factor1} closely - outstanding. {factor2} follows suit!",
        "💫 *Chef's kiss* The {factor1} sings! And that {factor2}... this is collector-grade!",
        "🎖️ Military-grade {factor1} here. Combined with stellar {factor2}, you've got a winner!",
    ],
    "good": [
        "👍 Solid piece! The {factor1} is above average, and I'm pleased with the {factor2}.",
        "😊 Nice! Inspecting the {factor1}... good! The {factor2} holds up well too.",
        "📈 Looking good! {factor1} passes my tests. {factor2} is respectable. Worth a premium!",
        "✅ The {factor1} meets high standards. {factor2} is consistent. Solid investment!",
        "💪 Strong showing! {factor1} is well-executed. {factor2} adds to the value here.",
    ],
    "average": [
        "🤔 Hmm, checking the {factor1}... it's fine. {factor2} is average. Nothing special.",
        "😐 The {factor1} is standard, {factor2} unremarkable. Seen better, seen worse.",
        "📊 Middle of the road. {factor1}: acceptable. {factor2}: passable. That's about it.",
        "➡️ Neither impressed nor disappointed by the {factor1}. {factor2} is equally median.",
        "🤷 It's... fine? {factor1} won't turn heads. {factor2} is just okay. Market rate.",
    ],
    "poor": [
        "😬 Oof... the {factor1} has issues. And the {factor2}? Substandard, I'm afraid.",
        "👎 Not great. Examining the {factor1} reveals flaws. {factor2} disappoints too.",
        "📉 Below average. {factor1} shows wear concerns. {factor2} underperforms expectations.",
        "⚠️ Red flags on the {factor1}. The {factor2} compounds my concerns here.",
        "😕 Troubling {factor1} quality. {factor2} doesn't save it. Market will be harsh.",
    ],
    "terrible": [
        "😰 Oh dear... the {factor1} is compromised. And the {factor2}? Don't get me started...",
        "💀 Yikes. {factor1} is rough. Real rough. {factor2} makes it worse. I'm sorry.",
        "🗑️ The {factor1} alone tanks this. Add the {factor2} situation and... yikes.",
        "🚨 Critical failures in {factor1}. The {factor2} seals the deal. This hurts to rate.",
        "😵 *Sighs heavily* {factor1}: damaged. {factor2}: inadequate. This one's in trouble.",
    ],
}

def bob_comment(tier):
    factors = list(BOB_FACTORS.keys())
    f1, f2 = random.sample(factors, 2)
    detail1 = random.choice(BOB_FACTORS[f1])
    detail2 = random.choice(BOB_FACTORS[f2])
    template = random.choice(BOB_COMMENTS[tier])
    return template.format(factor1=detail1, factor2=detail2)

@app.route("/api/appraise", methods=["POST"])
@login_required
def do_appraise():
    u = uid()
    shoe_id = int(request.json.get("id", 0))
    qty = int(request.json.get("qty", 1))
    d = db()
    hold = d.execute("select qty from hold where user_id=? and shoe_id=?", (u, shoe_id)).fetchone()
    if not hold or hold["qty"] < qty:
        return jsonify({"ok": False, "error": "Not enough unappraised shoes"})
    shoe = d.execute("select base, rarity from shoes where id=?", (shoe_id,)).fetchone()
    if not shoe:
        return jsonify({"ok": False, "error": "Shoe not found"})
    price = get_sell_price(shoe_id) or shoe["base"]
    cost_per = round(price * 0.05, 2)
    total_cost = round(cost_per * qty, 2)
    bal = d.execute("select balance from users where id=?", (u,)).fetchone()["balance"]
    if bal < total_cost:
        return jsonify({"ok": False, "error": f"Need ${total_cost:.2f} for {qty} appraisal(s)"})
    now = int(time.time())
    results = []
    for i in range(qty):
        rating = round(random.uniform(1.0, 10.0), 1)
        if rating == 10.0:
            multiplier = 2.0
            comment = bob_comment("perfect")
        elif rating >= 8.0:
            multiplier = 1.0 + (rating - 5.0) * 0.08
            comment = bob_comment("excellent")
        elif rating >= 6.0:
            multiplier = 1.0 + (rating - 5.0) * 0.06
            comment = bob_comment("good")
        elif rating >= 5.0:
            multiplier = 1.0 + (rating - 5.0) * 0.04
            comment = bob_comment("average")
        elif rating >= 3.0:
            multiplier = 1.0 - (5.0 - rating) * 0.08
            comment = bob_comment("poor")
        else:
            multiplier = 1.0 - (5.0 - rating) * 0.12
            comment = bob_comment("terrible")
        multiplier = round(multiplier, 2)
        vroll = random.random()
        variant = "rainbow" if vroll < 0.01 else "shiny" if vroll < 0.06 else ""
        if variant == "rainbow":
            multiplier = round(multiplier * 2.5, 2)
        elif variant == "shiny":
            multiplier = round(multiplier * 1.5, 2)
        d.execute("insert into appraised(user_id, shoe_id, rating, multiplier, ts, variant) values(?,?,?,?,?,?)", (u, shoe_id, rating, multiplier, now, variant))
        results.append({"rating": rating, "multiplier": multiplier, "comment": comment, "perfect": rating == 10.0, "rating_class": rating_class(rating), "variant": variant})
    d.execute("update hold set qty=qty-? where user_id=? and shoe_id=?", (qty, u, shoe_id))
    d.execute("delete from hold where user_id=? and shoe_id=? and qty<=0", (u, shoe_id))
    d.execute("update users set balance=balance-? where id=?", (total_cost, u))
    d.commit()
    best = max(results, key=lambda x: x["rating"])
    return jsonify({
        "ok": True,
        "results": results,
        "best": best,
        "cost": total_cost,
        "qty": qty
    })

@app.route("/users")
@login_required
def users_page():
    return render_template("users.html", is_admin=is_admin())

@app.route("/user/<username>")
@login_required
def user_profile(username):
    acc = account_by_username(username)
    if not acc:
        return render_template("profile.html", profile_username=username, is_admin=is_admin(), is_own_profile=False)
    own = (acc["id"] == session.get("user_id"))
    return render_template("profile.html", profile_username=acc["username"], is_admin=is_admin(), is_own_profile=own)

@app.route("/api/users")
@login_required
def api_users():
    u = uid()
    d = db()
    now = int(time.time())
    q = request.args.get("q", "").strip().lower()
    offset = int(request.args.get("offset", 0))
    limit = int(request.args.get("limit", 50))
    if q:
        users = d.execute("""
            select a.username, u.balance, u.last_seen from accounts a 
            join users u on u.id=a.id 
            where lower(a.username) like ? 
            order by (case when u.last_seen > ? then 0 else 1 end), u.balance desc limit ? offset ?
        """, (f"%{q}%", now - 60, limit, offset)).fetchall()
        total = d.execute("select count(*) as c from accounts a join users u on u.id=a.id where lower(a.username) like ?", (f"%{q}%",)).fetchone()["c"]
    else:
        users = d.execute("""
            select a.username, u.balance, u.last_seen from accounts a 
            join users u on u.id=a.id 
            order by (case when u.last_seen > ? then 0 else 1 end), u.balance desc limit ? offset ?
        """, (now - 60, limit, offset)).fetchall()
        total = d.execute("select count(*) as c from accounts a join users u on u.id=a.id").fetchone()["c"]
    result = []
    for row in users:
        udata = get_user_stats(row["username"])
        udata["is_me"] = (row["username"] == session.get("username"))
        udata["online"] = row["last_seen"] and row["last_seen"] > now - 60
        result.append(udata)
    return jsonify({"users": result, "total": total, "offset": offset, "has_more": offset + len(users) < total})

@app.route("/api/users/suggest")
@login_required
def api_users_suggest():
    q = request.args.get("q", "").strip().lower()
    if len(q) < 2:
        return jsonify([])
    d = db()
    users = d.execute("select username from accounts where lower(username) like ? limit 10", (f"%{q}%",)).fetchall()
    return jsonify([u["username"] for u in users])

def get_user_stats(username):
    d = db()
    uname = (username or "").strip().lower()
    acc = d.execute("select id, username, created, coalesce(profile_picture, '') as profile_picture from accounts where lower(username)=?", (uname,)).fetchone()
    if not acc:
        return None
    user = d.execute("select balance from users where id=?", (acc["id"],)).fetchone()
    hold_count = d.execute("select coalesce(sum(qty),0) as c from hold where user_id=?", (acc["id"],)).fetchone()["c"]
    appraised_count = d.execute("select count(*) as c from appraised where user_id=?", (acc["id"],)).fetchone()["c"]
    total_shoes = hold_count + appraised_count
    return {
        "username": acc["username"],
        "balance": round(user["balance"], 2) if user else 0,
        "shoes": total_shoes,
        "joined": acc["created"],
        "profile_picture": acc["profile_picture"]
    }

def account_by_username(username):
    d = db()
    uname = (username or "").strip().lower()
    if not uname:
        return None
    return d.execute("select id, username from accounts where lower(username)=?", (uname,)).fetchone()

def detect_image_ext(raw):
    if raw.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if raw.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
        return "webp"
    return None

@app.route("/avatar/<username>.svg")
def avatar_svg(username):
    safe_name = re.sub(r"[^a-zA-Z0-9 _-]", "", (username or "").strip())[:32] or "User"
    initial = safe_name[0].upper()
    palette = ["#00f0ff", "#7c3aed", "#00d084", "#ff4d6d", "#ffb020", "#5b8cff"]
    color_index = int(hashlib.sha256(safe_name.lower().encode()).hexdigest(), 16) % len(palette)
    bg = palette[color_index]
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128" role="img" aria-label="{safe_name}">
<rect width="128" height="128" rx="64" fill="{bg}"/>
<text x="50%" y="55%" text-anchor="middle" dominant-baseline="middle" fill="#0b0f14" font-size="56" font-family="Arial, sans-serif" font-weight="700">{initial}</text>
</svg>'''
    return Response(svg, mimetype="image/svg+xml")

@app.route("/api/user/<username>")
@login_required
def api_user_profile(username):
    u = uid()
    d = db()
    stats = get_user_stats(username)
    if not stats:
        return jsonify({"error": "User not found"}), 404
    acc = account_by_username(username)
    shoes = d.execute("""
        select s.name, s.rarity, h.qty from hold h 
        join shoes s on s.id=h.shoe_id 
        where h.user_id=? order by s.rarity desc, s.name
    """, (acc["id"],)).fetchall()
    appraised = d.execute("""
        select s.name, s.rarity, a.rating, a.multiplier, coalesce(a.variant,'') as variant from appraised a 
        join shoes s on s.id=a.shoe_id 
        where a.user_id=? order by a.rating desc
    """, (acc["id"],)).fetchall()
    stats["hold"] = [dict(s) for s in shoes]
    stats["appraised"] = [dict(a) for a in appraised]
    stats["is_me"] = (acc["id"] == u)
    stats["can_edit"] = stats["is_me"]
    return jsonify(stats)

@app.route("/api/profile/picture", methods=["POST"])
@login_required
def api_profile_picture_upload():
    u = uid()
    d = db()
    image = request.files.get("image")
    if not image:
        return jsonify({"ok": False, "error": "No image uploaded"}), 400
    raw = image.read()
    if not raw:
        return jsonify({"ok": False, "error": "Empty file"}), 400
    if len(raw) > 5 * 1024 * 1024:
        return jsonify({"ok": False, "error": "Image too large (max 5MB)"}), 400
    ext = detect_image_ext(raw)
    if not ext:
        return jsonify({"ok": False, "error": "Unsupported image format"}), 400
    avatar_dir = os.path.join(os.path.dirname(__file__), "static", "uploads", "avatars")
    os.makedirs(avatar_dir, exist_ok=True)
    filename = f"{u}_{int(time.time())}_{uuid.uuid4().hex[:8]}.{ext}"
    file_path = os.path.join(avatar_dir, filename)
    with open(file_path, "wb") as out:
        out.write(raw)
    new_path = f"/static/uploads/avatars/{filename}"
    old = d.execute("select coalesce(profile_picture,'') as profile_picture from accounts where id=?", (u,)).fetchone()
    old_path = old["profile_picture"] if old else ""
    d.execute("update accounts set profile_picture=? where id=?", (new_path, u))
    d.commit()
    if old_path.startswith("/static/uploads/avatars/"):
        old_file = os.path.join(os.path.dirname(__file__), old_path.lstrip("/\\"))
        try:
            if os.path.isfile(old_file):
                os.remove(old_file)
        except:
            pass
    return jsonify({"ok": True, "profile_picture": new_path})

@app.route("/api/profile/picture", methods=["DELETE"])
@login_required
def api_profile_picture_delete():
    u = uid()
    d = db()
    old = d.execute("select coalesce(profile_picture,'') as profile_picture from accounts where id=?", (u,)).fetchone()
    old_path = old["profile_picture"] if old else ""
    d.execute("update accounts set profile_picture='' where id=?", (u,))
    d.commit()
    if old_path.startswith("/static/uploads/avatars/"):
        old_file = os.path.join(os.path.dirname(__file__), old_path.lstrip("/\\"))
        try:
            if os.path.isfile(old_file):
                os.remove(old_file)
        except:
            pass
    return jsonify({"ok": True})

@app.route("/api/trades")
@login_required
def api_trades():
    u = uid()
    d = db()
    incoming = d.execute("""
        select t.*, a.username as from_username from trades t
        join accounts a on a.id=t.from_user
        where t.to_user=? and t.status='pending'
        order by t.created desc
    """, (u,)).fetchall()
    outgoing = d.execute("""
        select t.*, a.username as to_username from trades t
        join accounts a on a.id=t.to_user
        where t.from_user=? and t.status='pending'
        order by t.created desc
    """, (u,)).fetchall()
    def enrich(t):
        r = dict(t)
        offer = json.loads(r["offer_shoes"]) if r["offer_shoes"] else []
        want = json.loads(r["want_shoes"]) if r["want_shoes"] else []
        for s in offer:
            shoe = d.execute("select name, rarity, base from shoes where id=?", (s["id"],)).fetchone()
            if shoe:
                s["name"] = shoe["name"]
                s["rarity"] = shoe["rarity"]
                s["price"] = get_sell_price(s["id"]) or shoe["base"]
            if s.get("appraised") and s.get("appraisal_id"):
                ap = d.execute("select variant, rating, multiplier from appraised where id=?", (s["appraisal_id"],)).fetchone()
                if ap:
                    s["variant"] = ap["variant"] or ""
                    s["rating"] = ap["rating"]
                    s["multiplier"] = ap["multiplier"]
        for s in want:
            shoe = d.execute("select name, rarity, base from shoes where id=?", (s["id"],)).fetchone()
            if shoe:
                s["name"] = shoe["name"]
                s["rarity"] = shoe["rarity"]
                s["price"] = get_sell_price(s["id"]) or shoe["base"]
            if s.get("appraised") and s.get("appraisal_id"):
                ap = d.execute("select variant, rating, multiplier from appraised where id=?", (s["appraisal_id"],)).fetchone()
                if ap:
                    s["variant"] = ap["variant"] or ""
                    s["rating"] = ap["rating"]
                    s["multiplier"] = ap["multiplier"]
        r["offer_shoes"] = offer
        r["want_shoes"] = want
        return r
    return jsonify({
        "incoming": [enrich(t) for t in incoming],
        "outgoing": [enrich(t) for t in outgoing]
    })

@app.route("/api/trade-count")
@login_required
def api_trade_count():
    u = uid()
    d = db()
    c = d.execute("select count(*) as c from trades where to_user=? and status='pending'", (u,)).fetchone()["c"]
    return jsonify({"count": c})

@app.route("/api/trade/create", methods=["POST"])
@login_required
def create_trade():
    u = uid()
    d = db()
    data = request.json
    to_username = data.get("to_user", "").strip().lower()
    offer_shoes = data.get("offer_shoes", [])
    offer_cash = float(data.get("offer_cash", 0))
    want_shoes = data.get("want_shoes", [])
    want_cash = float(data.get("want_cash", 0))
    
    to_acc = d.execute("select id from accounts where username=?", (to_username,)).fetchone()
    if not to_acc:
        return jsonify({"ok": False, "error": "User not found"})
    if to_acc["id"] == u:
        return jsonify({"ok": False, "error": "Can't trade with yourself"})
    
    if offer_cash < 0 or want_cash < 0:
        return jsonify({"ok": False, "error": "Invalid cash amount"})
    
    bal = d.execute("select balance from users where id=?", (u,)).fetchone()["balance"]
    if offer_cash > bal:
        return jsonify({"ok": False, "error": "Not enough balance"})
    
    for shoe in offer_shoes:
        if shoe.get("appraised"):
            app = d.execute("select id from appraised where id=? and user_id=?", (shoe.get("appraisal_id"), u)).fetchone()
            if not app:
                return jsonify({"ok": False, "error": "You don't have that appraised shoe"})
        else:
            hold = d.execute("select qty from hold where user_id=? and shoe_id=?", (u, shoe["id"])).fetchone()
            if not hold or hold["qty"] < shoe.get("qty", 1):
                return jsonify({"ok": False, "error": "You don't have enough of that shoe"})
    
    for shoe in want_shoes:
        if shoe.get("appraised"):
            app = d.execute("select id from appraised where id=? and user_id=?", (shoe.get("appraisal_id"), to_acc["id"])).fetchone()
            if not app:
                return jsonify({"ok": False, "error": "They don't have that appraised shoe"})
        else:
            hold = d.execute("select qty from hold where user_id=? and shoe_id=?", (to_acc["id"], shoe["id"])).fetchone()
            if not hold or hold["qty"] < shoe.get("qty", 1):
                return jsonify({"ok": False, "error": "They don't have enough of that shoe"})
    
    now = int(time.time())
    d.execute("""
        insert into trades(from_user, to_user, offer_shoes, offer_cash, want_shoes, want_cash, status, created, updated)
        values(?,?,?,?,?,?,?,?,?)
    """, (u, to_acc["id"], json.dumps(offer_shoes), offer_cash, json.dumps(want_shoes), want_cash, "pending", now, now))
    d.commit()
    return jsonify({"ok": True})

@app.route("/api/trade/<int:trade_id>/accept", methods=["POST"])
@login_required
def accept_trade(trade_id):
    u = uid()
    d = db()
    trade = d.execute("select * from trades where id=? and to_user=? and status='pending'", (trade_id, u)).fetchone()
    if not trade:
        return jsonify({"ok": False, "error": "Trade not found"})
    
    offer_shoes = json.loads(trade["offer_shoes"]) if trade["offer_shoes"] else []
    want_shoes = json.loads(trade["want_shoes"]) if trade["want_shoes"] else []
    offer_cash = trade["offer_cash"] or 0
    want_cash = trade["want_cash"] or 0
    from_user = trade["from_user"]
    
    from_bal = d.execute("select balance from users where id=?", (from_user,)).fetchone()["balance"]
    to_bal = d.execute("select balance from users where id=?", (u,)).fetchone()["balance"]
    
    if offer_cash > from_bal:
        return jsonify({"ok": False, "error": "Sender doesn't have enough cash"})
    if want_cash > to_bal:
        return jsonify({"ok": False, "error": "You don't have enough cash"})
    
    for shoe in offer_shoes:
        if shoe.get("appraised"):
            app = d.execute("select id from appraised where id=? and user_id=?", (shoe.get("appraisal_id"), from_user)).fetchone()
            if not app:
                d.execute("update trades set status='cancelled' where id=?", (trade_id,))
                d.commit()
                return jsonify({"ok": False, "error": "Sender no longer has that appraised shoe"})
        else:
            hold = d.execute("select qty from hold where user_id=? and shoe_id=?", (from_user, shoe["id"])).fetchone()
            if not hold or hold["qty"] < shoe.get("qty", 1):
                d.execute("update trades set status='cancelled' where id=?", (trade_id,))
                d.commit()
                return jsonify({"ok": False, "error": "Sender no longer has those shoes"})
    
    for shoe in want_shoes:
        if shoe.get("appraised"):
            app = d.execute("select id from appraised where id=? and user_id=?", (shoe.get("appraisal_id"), u)).fetchone()
            if not app:
                return jsonify({"ok": False, "error": "You no longer have that appraised shoe"})
        else:
            hold = d.execute("select qty from hold where user_id=? and shoe_id=?", (u, shoe["id"])).fetchone()
            if not hold or hold["qty"] < shoe.get("qty", 1):
                return jsonify({"ok": False, "error": "You no longer have those shoes"})
    
    offer_val = offer_cash
    for shoe in offer_shoes:
        if shoe.get("appraised"):
            ap = d.execute("select value from appraised where id=?", (shoe.get("appraisal_id"),)).fetchone()
            if ap:
                offer_val += ap["value"]
        else:
            price = get_sell_price(shoe["id"]) or d.execute("select base from shoes where id=?", (shoe["id"],)).fetchone()["base"]
            offer_val += price * shoe.get("qty", 1)
    
    want_val = want_cash
    for shoe in want_shoes:
        if shoe.get("appraised"):
            ap = d.execute("select value from appraised where id=?", (shoe.get("appraisal_id"),)).fetchone()
            if ap:
                want_val += ap["value"]
        else:
            price = get_sell_price(shoe["id"]) or d.execute("select base from shoes where id=?", (shoe["id"],)).fetchone()["base"]
            want_val += price * shoe.get("qty", 1)
    
    if offer_val > 0 and want_val > 0:
        ratio = max(offer_val, want_val) / min(offer_val, want_val)
        if ratio > 2.0:
            diff_pct = int((ratio - 1) * 100)
            return jsonify({"ok": False, "error": f"❌ UNFAIR TRADE! Value difference is {diff_pct}% (max allowed: 100%). Offer: ${offer_val:,.0f} vs Want: ${want_val:,.0f}"})
    
    if offer_cash > 0:
        d.execute("update users set balance=balance-? where id=?", (offer_cash, from_user))
        d.execute("update users set balance=balance+? where id=?", (offer_cash, u))
    if want_cash > 0:
        d.execute("update users set balance=balance-? where id=?", (want_cash, u))
        d.execute("update users set balance=balance+? where id=?", (want_cash, from_user))
    
    for shoe in offer_shoes:
        if shoe.get("appraised"):
            d.execute("update appraised set user_id=? where id=?", (u, shoe.get("appraisal_id")))
        else:
            qty = shoe.get("qty", 1)
            d.execute("update hold set qty=qty-? where user_id=? and shoe_id=?", (qty, from_user, shoe["id"]))
            d.execute("delete from hold where user_id=? and shoe_id=? and qty<=0", (from_user, shoe["id"]))
            d.execute("insert into hold(user_id, shoe_id, qty) values(?,?,?) on conflict(user_id, shoe_id) do update set qty=qty+?", (u, shoe["id"], qty, qty))
    
    for shoe in want_shoes:
        if shoe.get("appraised"):
            d.execute("update appraised set user_id=? where id=?", (from_user, shoe.get("appraisal_id")))
        else:
            qty = shoe.get("qty", 1)
            d.execute("update hold set qty=qty-? where user_id=? and shoe_id=?", (qty, u, shoe["id"]))
            d.execute("delete from hold where user_id=? and shoe_id=? and qty<=0", (u, shoe["id"]))
            d.execute("insert into hold(user_id, shoe_id, qty) values(?,?,?) on conflict(user_id, shoe_id) do update set qty=qty+?", (from_user, shoe["id"], qty, qty))
    
    d.execute("update trades set status='accepted', updated=? where id=?", (int(time.time()), trade_id))
    d.commit()
    return jsonify({"ok": True})

@app.route("/api/trade/<int:trade_id>/decline", methods=["POST"])
@login_required
def decline_trade(trade_id):
    u = uid()
    d = db()
    trade = d.execute("select * from trades where id=? and (to_user=? or from_user=?) and status='pending'", (trade_id, u, u)).fetchone()
    if not trade:
        return jsonify({"ok": False, "error": "Trade not found"})
    d.execute("update trades set status='declined', updated=? where id=?", (int(time.time()), trade_id))
    d.commit()
    return jsonify({"ok": True})

@app.route("/api/my-shoes")
@login_required
def api_my_shoes():
    u = uid()
    d = db()
    fav_shoes = {r["shoe_id"] for r in d.execute("select shoe_id from favorites where user_id=? and appraisal_id=0", (u,)).fetchall()}
    fav_appraisals = {r["appraisal_id"] for r in d.execute("select appraisal_id from favorites where user_id=? and appraisal_id>0", (u,)).fetchall()}
    shoes = d.execute("""
        select h.shoe_id as id, s.name, s.rarity, s.base, h.qty from hold h 
        join shoes s on s.id=h.shoe_id 
        where h.user_id=? order by s.rarity desc, s.name
    """, (u,)).fetchall()
    result = []
    for s in shoes:
        r = dict(s)
        r["price"] = get_sell_price(s["id"]) or s["base"]
        r["appraised"] = False
        r["favorited"] = s["id"] in fav_shoes
        result.append(r)
    appraised = d.execute("""
        select a.id as appraisal_id, a.shoe_id as id, s.name, s.rarity, s.base, a.rating, a.multiplier, coalesce(a.variant,'') as variant
        from appraised a join shoes s on s.id=a.shoe_id
        where a.user_id=? order by a.rating desc
    """, (u,)).fetchall()
    for a in appraised:
        r = dict(a)
        r["price"] = (get_sell_price(a["id"]) or a["base"]) * a["multiplier"]
        r["qty"] = 1
        r["appraised"] = True
        r["favorited"] = a["appraisal_id"] in fav_appraisals
        result.append(r)
    return jsonify(result)

@app.route("/api/user-shoes/<username>")
@login_required
def api_user_shoes(username):
    d = db()
    acc = account_by_username(username)
    if not acc:
        return jsonify([])
    shoes = d.execute("""
        select h.shoe_id as id, s.name, s.rarity, s.base, h.qty from hold h 
        join shoes s on s.id=h.shoe_id 
        where h.user_id=? order by s.rarity desc, s.name
    """, (acc["id"],)).fetchall()
    result = []
    for s in shoes:
        r = dict(s)
        r["price"] = get_sell_price(s["id"]) or s["base"]
        r["appraised"] = False
        result.append(r)
    appraised = d.execute("""
        select a.id as appraisal_id, a.shoe_id as id, s.name, s.rarity, s.base, a.rating, a.multiplier, coalesce(a.variant,'') as variant
        from appraised a join shoes s on s.id=a.shoe_id
        where a.user_id=? order by a.rating desc
    """, (acc["id"],)).fetchall()
    for a in appraised:
        r = dict(a)
        r["price"] = (get_sell_price(a["id"]) or a["base"]) * a["multiplier"]
        r["qty"] = 1
        r["appraised"] = True
        result.append(r)
    return jsonify(result)

@app.route("/stream")
@login_required
def stream():
    u = uid()
    refresh()
    prices()
    income(u)
    return jsonify(state(u))

@app.route("/api/ban-status")
@login_required
def api_ban_status():
    d = db()
    acc = d.execute("select ban_until, coalesce(ban_reason,'') as ban_reason from accounts where id=?", (session["user_id"],)).fetchone()
    if not acc:
        return jsonify({"banned": False})
    now = int(time.time())
    ban_until = acc["ban_until"] or 0
    if ban_until > now:
        return jsonify({"banned": True, "until": ban_until, "remaining": ban_until - now, "reason": acc["ban_reason"] or "", "server_time": now})
    return jsonify({"banned": False})

@app.route("/api/notifications")
@login_required
def get_notifications():
    u = uid()
    d = db()
    notifs = d.execute("select id, message, ts from notifications where user_id=? order by ts desc limit 10", (u,)).fetchall()
    d.execute("delete from notifications where user_id=?", (u,))
    d.commit()
    return jsonify([dict(n) for n in notifs])

@app.route("/api/index")
@login_required
def api_index():
    u = uid()
    d = db()
    all_shoes = d.execute("select id, name, rarity, base from shoes order by case rarity when 'common' then 0 when 'uncommon' then 1 when 'rare' then 2 when 'epic' then 3 when 'legendary' then 4 when 'mythic' then 5 when 'godly' then 6 when 'divine' then 7 when 'grails' then 8 when 'heavenly' then 9 end, name").fetchall()
    index_data = d.execute("select shoe_id, discovered, collected from shoe_index where user_id=?", (u,)).fetchall()
    index_map = {row["shoe_id"]: {"discovered": row["discovered"], "collected": row["collected"]} for row in index_data}
    result = []
    for shoe in all_shoes:
        entry = {"id": shoe["id"], "name": shoe["name"], "rarity": shoe["rarity"], "base": shoe["base"]}
        if shoe["id"] in index_map:
            entry["discovered"] = index_map[shoe["id"]]["discovered"]
            entry["collected"] = index_map[shoe["id"]]["collected"]
        else:
            entry["discovered"] = 0
            entry["collected"] = 0
        result.append(entry)
    return jsonify(result)

@app.route("/api/index/collect/<int:shoe_id>", methods=["POST"])
@login_required
def api_index_collect(shoe_id):
    u = uid()
    d = db()
    shoe = d.execute("select id, name, base from shoes where id=?", (shoe_id,)).fetchone()
    if not shoe:
        return jsonify({"ok": False, "error": "Shoe not found"})
    index_entry = d.execute("select discovered, collected from shoe_index where user_id=? and shoe_id=?", (u, shoe_id)).fetchone()
    if not index_entry or not index_entry["discovered"]:
        return jsonify({"ok": False, "error": "Shoe not discovered yet"})
    if index_entry["collected"]:
        return jsonify({"ok": False, "error": "Already collected"})
    reward = int(shoe["base"] * 0.05)
    d.execute("update shoe_index set collected=? where user_id=? and shoe_id=?", (int(time.time()), u, shoe_id))
    d.execute("update users set balance=balance+? where id=?", (reward, u))
    now = int(time.time())
    d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", (u, f"📖 Collected {shoe['name']} index reward: ${reward:,}!", now))
    d.commit()
    return jsonify({"ok": True, "reward": reward})

def is_admin():
    if session.get("username") not in ADMIN_USERS:
        return False
    if ADMIN_IPS and get_client_ip() not in ADMIN_IPS:
        return False
    return True

def cap_balance(user_id):
    d = db()
    d.execute("update users set balance=? where id=? and balance>?", (MAX_BALANCE, user_id, MAX_BALANCE))
    d.commit()

@app.route("/admin")
@login_required
def admin_page():
    if not is_admin():
        return redirect(url_for("home"))
    return render_template("admin.html")

@app.route("/api/admin/users")
@login_required
def admin_users():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 403
    d = db()
    now = int(time.time())
    users = d.execute("""
        select a.username, u.balance, 
        coalesce(a.ban_until, 0) as ban_until,
        coalesce(a.ban_reason, '') as ban_reason,
        (select count(*) from hold where user_id=a.id) as shoes,
        (select count(*) from appraised where user_id=a.id) as appraised
        from accounts a join users u on u.id=a.id order by a.username
    """).fetchall()
    result = []
    for u in users:
        row = dict(u)
        ban_until = row.get("ban_until") or 0
        if ban_until > now:
            row["ban_active"] = True
            row["ban_remaining"] = ban_until - now
        else:
            row["ban_active"] = False
            row["ban_remaining"] = 0
            row["ban_reason"] = ""
        result.append(row)
    return jsonify(result)

@app.route("/api/admin/shoes")
@login_required
def admin_shoes():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 403
    d = db()
    rarity_order = {r: i for i, r in enumerate(RARITIES)}
    shoes = d.execute("select id, name, rarity, base from shoes order by name").fetchall()
    shoes = sorted(shoes, key=lambda s: (rarity_order.get(s["rarity"], 99), s["name"]))
    return jsonify([dict(s) for s in shoes])

@app.route("/api/admin/money", methods=["POST"])
@login_required
def admin_money():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 403
    d = db()
    data = request.json
    username = data.get("username", "").lower()
    amount = float(data.get("amount", 0))
    acc = d.execute("select id from accounts where username=?", (username,)).fetchone()
    if not acc:
        return jsonify({"ok": False, "error": "User not found"})
    d.execute("update users set balance=balance+? where id=?", (amount, acc["id"]))
    sign = "+" if amount >= 0 else ""
    d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", (acc["id"], f"Admin {sign}${amount:.2f} to your balance", int(time.time())))
    d.commit()
    return jsonify({"ok": True})

@app.route("/api/admin/shoe", methods=["POST"])
@login_required
def admin_shoe():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 403
    d = db()
    data = request.json
    username = data.get("username", "").lower()
    shoe_id = int(data.get("shoe_id", 0))
    qty = int(data.get("qty", 1))
    action = data.get("action", "give")
    appraised = data.get("appraised", False)
    variant = data.get("variant", "")
    rating = data.get("rating")
    multiplier = data.get("multiplier")
    acc = d.execute("select id from accounts where username=?", (username,)).fetchone()
    if not acc:
        return jsonify({"ok": False, "error": "User not found"})
    shoe = d.execute("select id, name, base from shoes where id=?", (shoe_id,)).fetchone()
    if not shoe:
        return jsonify({"ok": False, "error": "Shoe not found"})
    if action == "give":
        if appraised:
            var = variant if variant in ["shiny", "rainbow"] else ""
            if rating is None or multiplier is None:
                mult = random.uniform(0.5, 1.45)
                rat = int(mult * 100)
                val = shoe["base"] * mult
            else:
                rat = int(rating)
                mult = float(multiplier)
                val = shoe["base"] * mult
            d.execute("insert into appraised(user_id, shoe_id, rating, multiplier, variant, value) values(?,?,?,?,?,?)",
                     (acc["id"], shoe_id, rat, mult, var, val))
            msg = f"Admin gave you {shoe['name']}"
            if var:
                msg += f" ({var})"
            msg += f" [{rat}%]"
            d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", (acc["id"], msg, int(time.time())))
        else:
            existing = d.execute("select qty from hold where user_id=? and shoe_id=?", (acc["id"], shoe_id)).fetchone()
            if existing:
                d.execute("update hold set qty=qty+? where user_id=? and shoe_id=?", (qty, acc["id"], shoe_id))
            else:
                d.execute("insert into hold(user_id, shoe_id, qty) values(?,?,?)", (acc["id"], shoe_id, qty))
            d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", (acc["id"], f"Admin gave you {qty}x {shoe['name']}", int(time.time())))
    else:
        existing = d.execute("select qty from hold where user_id=? and shoe_id=?", (acc["id"], shoe_id)).fetchone()
        if not existing or existing["qty"] < qty:
            return jsonify({"ok": False, "error": "User doesn't have enough"})
        if existing["qty"] == qty:
            d.execute("delete from hold where user_id=? and shoe_id=?", (acc["id"], shoe_id))
        else:
            d.execute("update hold set qty=qty-? where user_id=? and shoe_id=?", (qty, acc["id"], shoe_id))
        d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", (acc["id"], f"Admin removed {qty}x {shoe['name']}", int(time.time())))
    d.commit()
    return jsonify({"ok": True})

@app.route("/api/admin/refresh", methods=["POST"])
@login_required
def admin_refresh():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 403
    d = db()
    d.execute("update global_state set last_stock=0 where id=1")
    d.commit()
    refresh()
    return jsonify({"ok": True})

@app.route("/api/admin/add-to-stock", methods=["POST"])
@login_required
def admin_add_to_stock():
    if not is_admin():
        return jsonify({"ok": False, "error": "Unauthorized"}), 403
    d = db()
    now = int(time.time())
    shoe_id = request.json.get("shoe_id")
    stock = int(request.json.get("stock", 5))
    price = request.json.get("price")
    shoe = d.execute("select * from shoes where id=?", (shoe_id,)).fetchone()
    if not shoe:
        return jsonify({"ok": False, "error": "Shoe not found"})
    if not price:
        price = shoe["base"]
    existing = d.execute("select * from market where shoe_id=?", (shoe_id,)).fetchone()
    if existing:
        d.execute("update market set stock=stock+?, price=? where shoe_id=?", (stock, price, shoe_id))
    else:
        count = d.execute("select count(*) c from market").fetchone()["c"]
        if count >= 15:
            oldest = d.execute("select shoe_id from market order by rowid asc limit 1").fetchone()
            if oldest:
                d.execute("delete from market where shoe_id=?", (oldest["shoe_id"],))
        d.execute("insert into market(shoe_id, stock, price, base) values(?,?,?,?)", (shoe_id, stock, price, shoe["base"]))
        d.execute("insert into history(shoe_id, ts, price) values(?,?,?)", (shoe_id, now, price))
    d.execute("update global_state set last_stock=? where id=1", (now,))
    d.commit()
    return jsonify({"ok": True, "name": shoe["name"], "stock": stock, "price": price})

@app.route("/api/admin/ban", methods=["POST"])
@login_required
def admin_ban():
    if not is_admin():
        return jsonify({"ok": False, "error": "Unauthorized"}), 403
    d = db()
    data = request.json
    username = data.get("username", "").lower().strip()
    duration = data.get("duration", "perm")
    reason = data.get("reason", "").strip()[:180]
    custom_value = int(data.get("custom_value", 0) or 0)
    custom_unit = data.get("custom_unit", "h")
    if not username:
        return jsonify({"ok": False, "error": "Enter a username"})
    if username in ADMIN_USERS:
        return jsonify({"ok": False, "error": "Cannot ban an admin"})
    acc = d.execute("select id from accounts where username=?", (username,)).fetchone()
    if not acc:
        return jsonify({"ok": False, "error": f"User '{username}' not found"})
    uid = acc["id"]
    now = int(time.time())
    if duration == "perm":
        d.execute("delete from hold where user_id=?", (uid,))
        d.execute("delete from appraised where user_id=?", (uid,))
        d.execute("delete from trades where from_user=? or to_user=?", (uid, uid))
        d.execute("delete from notifications where user_id=?", (uid,))
        d.execute("delete from users where id=?", (uid,))
        d.execute("delete from accounts where id=?", (uid,))
        d.commit()
        return jsonify({"ok": True, "msg": f"Permanently banned {username}"})
    else:
        durations = {"1h": 3600, "6h": 21600, "1d": 86400, "7d": 604800, "30d": 2592000}
        if duration == "custom":
            if custom_value < 1:
                return jsonify({"ok": False, "error": "Custom value must be at least 1"})
            unit_secs = {"m": 60, "h": 3600, "d": 86400}
            if custom_unit not in unit_secs:
                return jsonify({"ok": False, "error": "Invalid custom unit"})
            secs = custom_value * unit_secs[custom_unit]
        else:
            secs = durations.get(duration, 3600)
        ban_until = now + secs
        d.execute("update accounts set ban_until=?, ban_reason=? where id=?", (ban_until, reason, uid))
        if duration == "custom":
            unit_label = {"m": "minute(s)", "h": "hour(s)", "d": "day(s)"}[custom_unit]
            human_duration = f"{custom_value} {unit_label}"
        else:
            human_duration = duration
        notif = f"⛔ You have been banned for {human_duration}."
        if reason:
            notif += f" Reason: {reason}"
        d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", (uid, notif, now))
        d.commit()
        return jsonify({"ok": True, "msg": f"Banned {username} for {human_duration}"})

@app.route("/api/admin/unban", methods=["POST"])
@login_required
def admin_unban():
    if not is_admin():
        return jsonify({"ok": False, "error": "Unauthorized"}), 403
    d = db()
    username = request.json.get("username", "").lower().strip()
    if not username:
        return jsonify({"ok": False, "error": "Enter a username"})
    acc = d.execute("select id, ban_until from accounts where username=?", (username,)).fetchone()
    if not acc:
        return jsonify({"ok": False, "error": f"User '{username}' not found"})
    if not acc["ban_until"] or acc["ban_until"] < int(time.time()):
        return jsonify({"ok": False, "error": f"{username} is not banned"})
    d.execute("update accounts set ban_until=0, ban_reason='' where id=?", (acc["id"],))
    d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", (acc["id"], "🔓 You have been unbanned!", int(time.time())))
    d.commit()
    return jsonify({"ok": True, "msg": f"Unbanned {username}"})

@app.route("/api/admin/purge-bots", methods=["POST"])
@login_required
def admin_purge_bots():
    if not is_admin():
        return jsonify({"ok": False, "error": "Unauthorized"}), 403
    d = db()
    my_id = session.get("user_id")
    all_accs = d.execute("select a.id, a.username, u.balance, (select count(*) from hold where user_id=a.id) as shoes from accounts a left join users u on u.id=a.id").fetchall()
    count = 0
    bot_keywords = ["player", "investor", "user", "guest", "test", "bot", "account", "trader", "shoe"]
    for acc in all_accs:
        if acc["id"] == my_id:
            continue
        username = acc["username"].lower()
        is_bot = False
        for kw in bot_keywords:
            if username.startswith(kw) and any(c.isdigit() for c in username[len(kw):]):
                is_bot = True
                break
        if not is_bot and len(username) >= 8:
            vowels = sum(1 for c in username if c in 'aeiou')
            digits = sum(1 for c in username if c.isdigit())
            if vowels < 2 or digits >= 4:
                is_bot = True
        if not is_bot and acc["balance"] == 10000 and acc["shoes"] == 0:
            is_bot = True
        if is_bot:
            d.execute("delete from users where id=?", (acc["id"],))
            d.execute("delete from hold where user_id=?", (acc["id"],))
            d.execute("delete from trades where from_user=?", (acc["id"],))
            d.execute("delete from global_chat where user_id=?", (acc["id"],))
            d.execute("delete from accounts where id=?", (acc["id"],))
            count += 1
    d.commit()
    return jsonify({"ok": True, "msg": f"Purged {count} bot accounts"})

@app.route("/api/admin/clear-chat", methods=["POST"])
@login_required
def admin_clear_chat():
    if not is_admin():
        return jsonify({"ok": False, "error": "Unauthorized"}), 403
    d = db()
    d.execute("delete from global_chat")
    d.commit()
    return jsonify({"ok": True, "msg": "Chat cleared"})

@app.route("/api/admin/ban-ip", methods=["POST"])
@login_required
def admin_ban_ip():
    if not is_admin():
        return jsonify({"ok": False, "error": "Unauthorized"}), 403
    d = db()
    username = request.json.get("username", "").lower().strip()
    duration = request.json.get("duration", "1d")
    acc = d.execute("select last_ip from accounts where username=?", (username,)).fetchone()
    if not acc or not acc["last_ip"]:
        return jsonify({"ok": False, "error": "User not found or no IP recorded"})
    durations = {"1h": 3600, "6h": 21600, "1d": 86400, "7d": 604800, "30d": 2592000, "perm": 315360000}
    secs = durations.get(duration, 86400)
    d.execute("insert or replace into banned_ips(ip, banned_until, reason) values(?,?,?)", 
              (acc["last_ip"], int(time.time()) + secs, f"Banned via {username}"))
    d.commit()
    return jsonify({"ok": True, "msg": f"Banned IP {acc['last_ip']} for {duration}"})

@app.route("/api/admin/tx-log", methods=["GET"])
@login_required
def admin_tx_log():
    if not is_admin():
        return jsonify({"ok": False, "error": "Unauthorized"}), 403
    d = db()
    username = request.args.get("username", "").lower().strip()
    if username:
        acc = d.execute("select id from accounts where username=?", (username,)).fetchone()
        if not acc:
            return jsonify([])
        logs = d.execute("select * from tx_log where user_id=? order by ts desc limit 100", (acc["id"],)).fetchall()
    else:
        logs = d.execute("select * from tx_log order by ts desc limit 100").fetchall()
    return jsonify([dict(l) for l in logs])

@app.route("/api/admin/suspicious", methods=["GET"])
@login_required
def admin_suspicious():
    if not is_admin():
        return jsonify({"ok": False, "error": "Unauthorized"}), 403
    d = db()
    now = int(time.time())
    sus = d.execute("""
        select a.username, u.balance, 
        (select sum(amount) from tx_log where user_id=a.id and amount>0 and ts>?) as earned_1h
        from accounts a join users u on u.id=a.id 
        where u.balance > 1000000 
        order by u.balance desc limit 50
    """, (now - 3600,)).fetchall()
    return jsonify([dict(s) for s in sus])

@app.route("/api/admin/swap-balance", methods=["POST"])
@login_required
def admin_swap_balance():
    if not is_admin():
        return jsonify({"ok": False, "error": "Unauthorized"}), 403
    d = db()
    data = request.json
    user1 = data.get("user1", "").lower().strip()
    user2 = data.get("user2", "").lower().strip()
    if not user1 or not user2:
        return jsonify({"ok": False, "error": "Enter both usernames"})
    acc1 = d.execute("select id from accounts where username=?", (user1,)).fetchone()
    acc2 = d.execute("select id from accounts where username=?", (user2,)).fetchone()
    if not acc1:
        return jsonify({"ok": False, "error": f"User '{user1}' not found"})
    if not acc2:
        return jsonify({"ok": False, "error": f"User '{user2}' not found"})
    bal1 = d.execute("select balance from users where id=?", (acc1["id"],)).fetchone()["balance"]
    bal2 = d.execute("select balance from users where id=?", (acc2["id"],)).fetchone()["balance"]
    d.execute("update users set balance=? where id=?", (bal2, acc1["id"]))
    d.execute("update users set balance=? where id=?", (bal1, acc2["id"]))
    now = int(time.time())
    d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", (acc1["id"], f"🔄 Your balance was swapped with {user2}! You now have ${bal2:,.0f}", now))
    d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", (acc2["id"], f"🔄 Your balance was swapped with {user1}! You now have ${bal1:,.0f}", now))
    d.commit()
    return jsonify({"ok": True, "msg": f"Swapped balances: {user1} (${bal1:,.0f} → ${bal2:,.0f}), {user2} (${bal2:,.0f} → ${bal1:,.0f})"})

@app.route("/api/admin/swap-inventory", methods=["POST"])
@login_required
def admin_swap_inventory():
    if not is_admin():
        return jsonify({"ok": False, "error": "Unauthorized"}), 403
    d = db()
    data = request.json
    user1 = data.get("user1", "").lower().strip()
    user2 = data.get("user2", "").lower().strip()
    if not user1 or not user2:
        return jsonify({"ok": False, "error": "Enter both usernames"})
    acc1 = d.execute("select id from accounts where username=?", (user1,)).fetchone()
    acc2 = d.execute("select id from accounts where username=?", (user2,)).fetchone()
    if not acc1 or not acc2:
        return jsonify({"ok": False, "error": "User not found"})
    hold1 = d.execute("select shoe_id, qty from hold where user_id=?", (acc1["id"],)).fetchall()
    hold2 = d.execute("select shoe_id, qty from hold where user_id=?", (acc2["id"],)).fetchall()
    app1 = d.execute("select shoe_id, rating, multiplier, variant, ts from appraised where user_id=?", (acc1["id"],)).fetchall()
    app2 = d.execute("select shoe_id, rating, multiplier, variant, ts from appraised where user_id=?", (acc2["id"],)).fetchall()
    d.execute("delete from hold where user_id=?", (acc1["id"],))
    d.execute("delete from hold where user_id=?", (acc2["id"],))
    d.execute("delete from appraised where user_id=?", (acc1["id"],))
    d.execute("delete from appraised where user_id=?", (acc2["id"],))
    for h in hold2:
        d.execute("insert into hold(user_id, shoe_id, qty) values(?,?,?)", (acc1["id"], h["shoe_id"], h["qty"]))
    for h in hold1:
        d.execute("insert into hold(user_id, shoe_id, qty) values(?,?,?)", (acc2["id"], h["shoe_id"], h["qty"]))
    for a in app2:
        d.execute("insert into appraised(user_id, shoe_id, rating, multiplier, variant, ts) values(?,?,?,?,?,?)", (acc1["id"], a["shoe_id"], a["rating"], a["multiplier"], a["variant"] or "", a["ts"]))
    for a in app1:
        d.execute("insert into appraised(user_id, shoe_id, rating, multiplier, variant, ts) values(?,?,?,?,?,?)", (acc2["id"], a["shoe_id"], a["rating"], a["multiplier"], a["variant"] or "", a["ts"]))
    now = int(time.time())
    d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", (acc1["id"], f"🔄 Your entire inventory was swapped with {user2}!", now))
    d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", (acc2["id"], f"🔄 Your entire inventory was swapped with {user1}!", now))
    d.commit()
    return jsonify({"ok": True, "msg": f"Swapped inventories between {user1} and {user2}"})

@app.route("/api/admin/broadcast", methods=["POST"])
@login_required
def admin_broadcast():
    if not is_admin():
        return jsonify({"ok": False, "error": "Unauthorized"}), 403
    d = db()
    msg = request.json.get("message", "").strip()
    duration = int(request.json.get("duration", 60))
    duration = max(10, min(duration, 2592000))
    if not msg:
        return jsonify({"ok": False, "error": "Enter a message"})
    now = int(time.time())
    d.execute("insert into announcements(message, ts, expires) values(?,?,?)", (msg, now, now + duration))
    d.commit()
    return jsonify({"ok": True, "msg": f"Announcement live for {duration}s"})

@app.route("/api/admin/remove-pfp", methods=["POST"])
@login_required
def admin_remove_pfp():
    if not is_admin():
        return jsonify({"ok": False, "error": "Unauthorized"}), 403
    d = db()
    username = request.json.get("username", "").lower().strip()
    reason = request.json.get("reason", "").strip()[:180]
    if not username:
        return jsonify({"ok": False, "error": "Enter a username"})
    if not reason:
        return jsonify({"ok": False, "error": "Enter a reason"})
    acc = d.execute("select id, coalesce(profile_picture,'') as profile_picture from accounts where username=?", (username,)).fetchone()
    if not acc:
        return jsonify({"ok": False, "error": f"User '{username}' not found"})
    old_path = acc["profile_picture"] or ""
    d.execute("update accounts set profile_picture='' where id=?", (acc["id"],))
    now = int(time.time())
    d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", (acc["id"], f"🖼️ Your profile picture was removed by admin. Reason: {reason}", now))
    d.commit()
    if old_path.startswith("/static/uploads/avatars/"):
        old_file = os.path.join(os.path.dirname(__file__), old_path.lstrip("/\\"))
        try:
            if os.path.isfile(old_file):
                os.remove(old_file)
        except:
            pass
    return jsonify({"ok": True, "msg": f"Removed profile picture for {username}"})

@app.route("/api/announcements")
@login_required
def get_announcements():
    d = db()
    now = int(time.time())
    d.execute("delete from announcements where expires < ?", (now,))
    d.commit()
    anns = d.execute("select message, expires from announcements order by ts desc limit 3").fetchall()
    return jsonify([{"message": a["message"], "expires": a["expires"]} for a in anns])

@app.route("/api/admin/rain", methods=["POST"])
@login_required
def admin_rain():
    if not is_admin():
        return jsonify({"ok": False, "error": "Unauthorized"}), 403
    d = db()
    amount = int(request.json.get("amount", 0))
    if amount < 1:
        return jsonify({"ok": False, "error": "Enter an amount"})
    users = d.execute("select id from users").fetchall()
    now = int(time.time())
    for u in users:
        d.execute("update users set balance=balance+? where id=?", (amount, u["id"]))
        d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", (u["id"], f"💰 MONEY RAIN! You received ${amount:,}!", now))
    d.commit()
    return jsonify({"ok": True, "msg": f"Rained ${amount:,} on {len(users)} users (${amount * len(users):,} total)"})

@app.route("/api/admin/tax", methods=["POST"])
@login_required
def admin_tax():
    if not is_admin():
        return jsonify({"ok": False, "error": "Unauthorized"}), 403
    d = db()
    percent = int(request.json.get("percent", 0))
    if percent < 1 or percent > 100:
        return jsonify({"ok": False, "error": "Percent must be 1-100"})
    users = d.execute("select id, balance from users").fetchall()
    now = int(time.time())
    total = 0
    for u in users:
        tax = round(u["balance"] * percent / 100, 2)
        total += tax
        d.execute("update users set balance=balance-? where id=?", (tax, u["id"]))
        d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", (u["id"], f"💸 TAX COLLECTION! {percent}% of your balance (${tax:,.0f}) was taken!", now))
    d.commit()
    return jsonify({"ok": True, "msg": f"Taxed {percent}% from {len(users)} users (${total:,.0f} total)"})

@app.route("/api/admin/bankrupt", methods=["POST"])
@login_required
def admin_bankrupt():
    if not is_admin():
        return jsonify({"ok": False, "error": "Unauthorized"}), 403
    d = db()
    username = request.json.get("username", "").lower().strip()
    if not username:
        return jsonify({"ok": False, "error": "Enter a username"})
    acc = d.execute("select id from accounts where username=?", (username,)).fetchone()
    if not acc:
        return jsonify({"ok": False, "error": f"User '{username}' not found"})
    old_bal = d.execute("select balance from users where id=?", (acc["id"],)).fetchone()["balance"]
    d.execute("update users set balance=0 where id=?", (acc["id"],))
    now = int(time.time())
    d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", (acc["id"], f"💀 BANKRUPTED! Your ${old_bal:,.0f} balance is now $0!", now))
    d.commit()
    return jsonify({"ok": True, "msg": f"Bankrupted {username} (${old_bal:,.0f} → $0)"})

@app.route("/api/admin/jackpot", methods=["POST"])
@login_required
def admin_jackpot():
    if not is_admin():
        return jsonify({"ok": False, "error": "Unauthorized"}), 403
    d = db()
    amount = int(request.json.get("amount", 0))
    if amount < 1:
        return jsonify({"ok": False, "error": "Enter an amount"})
    users = d.execute("select a.username, u.id from accounts a join users u on u.id=a.id").fetchall()
    if not users:
        return jsonify({"ok": False, "error": "No users"})
    winner = random.choice(users)
    d.execute("update users set balance=balance+? where id=?", (amount, winner["id"]))
    now = int(time.time())
    for u in users:
        if u["id"] == winner["id"]:
            d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", (u["id"], f"🎉 JACKPOT WINNER! You won ${amount:,}!!!", now))
        else:
            d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", (u["id"], f"🎰 {winner['username']} won the ${amount:,} jackpot!", now))
    d.commit()
    return jsonify({"ok": True, "msg": f"{winner['username']} won the ${amount:,} jackpot!"})

@app.route("/api/admin/double-or-nothing", methods=["POST"])
@login_required
def admin_double_or_nothing():
    if not is_admin():
        return jsonify({"ok": False, "error": "Unauthorized"}), 403
    d = db()
    username = request.json.get("username", "").lower().strip()
    if not username:
        return jsonify({"ok": False, "error": "Enter a username"})
    acc = d.execute("select id from accounts where username=?", (username,)).fetchone()
    if not acc:
        return jsonify({"ok": False, "error": f"User '{username}' not found"})
    bal = d.execute("select balance from users where id=?", (acc["id"],)).fetchone()["balance"]
    now = int(time.time())
    if random.random() < 0.5:
        d.execute("update users set balance=balance*2 where id=?", (acc["id"],))
        d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", (acc["id"], f"🎲 DOUBLE OR NOTHING: DOUBLED! ${bal:,.0f} → ${bal*2:,.0f}!", now))
        d.commit()
        return jsonify({"ok": True, "msg": f"{username} DOUBLED: ${bal:,.0f} → ${bal*2:,.0f}"})
    else:
        d.execute("update users set balance=0 where id=?", (acc["id"],))
        d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", (acc["id"], f"🎲 DOUBLE OR NOTHING: NOTHING! ${bal:,.0f} → $0!", now))
        d.commit()
        return jsonify({"ok": True, "msg": f"{username} got NOTHING: ${bal:,.0f} → $0"})

@app.route("/api/admin/shuffle-shoes", methods=["POST"])
@login_required
def admin_shuffle_shoes():
    if not is_admin():
        return jsonify({"ok": False, "error": "Unauthorized"}), 403
    d = db()
    username = request.json.get("username", "").lower().strip()
    if not username:
        return jsonify({"ok": False, "error": "Enter a username"})
    acc = d.execute("select id from accounts where username=?", (username,)).fetchone()
    if not acc:
        return jsonify({"ok": False, "error": f"User '{username}' not found"})
    shoes = d.execute("select shoe_id, qty from hold where user_id=?", (acc["id"],)).fetchall()
    appraised = d.execute("select id, shoe_id, rating, multiplier, variant, ts from appraised where user_id=?", (acc["id"],)).fetchall()
    if not shoes and not appraised:
        return jsonify({"ok": False, "error": f"{username} has no shoes to shuffle"})
    other_users = d.execute("select u.id from users u join accounts a on a.id=u.id where a.username != ?", (username,)).fetchall()
    if not other_users:
        return jsonify({"ok": False, "error": "No other users to shuffle to"})
    d.execute("delete from hold where user_id=?", (acc["id"],))
    d.execute("delete from appraised where user_id=?", (acc["id"],))
    now = int(time.time())
    count = 0
    for s in shoes:
        for _ in range(s["qty"]):
            target = random.choice(other_users)["id"]
            d.execute("insert into hold(user_id, shoe_id, qty) values(?,?,1) on conflict(user_id, shoe_id) do update set qty=qty+1", (target, s["shoe_id"]))
            count += 1
    for a in appraised:
        target = random.choice(other_users)["id"]
        d.execute("insert into appraised(user_id, shoe_id, rating, multiplier, variant, ts) values(?,?,?,?,?,?)", (target, a["shoe_id"], a["rating"], a["multiplier"], a["variant"] or "", a["ts"]))
        count += 1
    d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", (acc["id"], f"🌀 YOUR SHOES WERE SHUFFLED! {count} shoes redistributed to random users!", now))
    d.commit()
    return jsonify({"ok": True, "msg": f"Shuffled {count} shoes from {username} to random users"})

@app.route("/api/admin/fake-win", methods=["POST"])
@login_required  
def admin_fake_win():
    if not is_admin():
        return jsonify({"ok": False, "error": "Unauthorized"}), 403
    d = db()
    username = request.json.get("username", "").lower().strip()
    amount = request.json.get("amount", 100000)
    if not username:
        return jsonify({"ok": False, "error": "Enter a username"})
    acc = d.execute("select id from accounts where username=?", (username,)).fetchone()
    if not acc:
        return jsonify({"ok": False, "error": f"User '{username}' not found"})
    now = int(time.time())
    d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", (acc["id"], f"🎉🎊 CONGRATULATIONS! You won ${amount:,} in the MEGA LOTTERY! 🎊🎉 (check your balance 😈)", now))
    d.commit()
    return jsonify({"ok": True, "msg": f"Sent fake ${amount:,} win notification to {username}"})

@app.route("/api/admin/gift-bomb", methods=["POST"])
@login_required
def admin_gift_bomb():
    if not is_admin():
        return jsonify({"ok": False, "error": "Unauthorized"}), 403
    d = db()
    username = request.json.get("username", "").lower().strip()
    count = int(request.json.get("count", 10))
    if not username:
        return jsonify({"ok": False, "error": "Enter a username"})
    if count < 1 or count > 100:
        return jsonify({"ok": False, "error": "Count must be 1-100"})
    acc = d.execute("select id from accounts where username=?", (username,)).fetchone()
    if not acc:
        return jsonify({"ok": False, "error": f"User '{username}' not found"})
    shoes = d.execute("select id, name from shoes").fetchall()
    now = int(time.time())
    for _ in range(count):
        shoe = random.choice(shoes)
        existing = d.execute("select qty from hold where user_id=? and shoe_id=?", (acc["id"], shoe["id"])).fetchone()
        if existing:
            d.execute("update hold set qty=qty+1 where user_id=? and shoe_id=?", (acc["id"], shoe["id"]))
        else:
            d.execute("insert into hold(user_id, shoe_id, qty) values(?,?,?)", (acc["id"], shoe["id"], 1))
    d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", (acc["id"], f"🎁 GIFT BOMB! You received {count} random shoes!", now))
    d.commit()
    return jsonify({"ok": True, "msg": f"Gift bombed {username} with {count} random shoes"})

@app.route("/api/admin/wheel-of-fortune", methods=["POST"])
@login_required
def admin_wheel_of_fortune():
    if not is_admin():
        return jsonify({"ok": False, "error": "Unauthorized"}), 403
    d = db()
    username = request.json.get("username", "").lower().strip()
    if not username:
        users = d.execute("select a.username, u.id from accounts a join users u on u.id=a.id").fetchall()
        if not users:
            return jsonify({"ok": False, "error": "No users"})
        target = random.choice(users)
        username = target["username"]
        target_id = target["id"]
    else:
        acc = d.execute("select id from accounts where username=?", (username,)).fetchone()
        if not acc:
            return jsonify({"ok": False, "error": f"User '{username}' not found"})
        target_id = acc["id"]
    
    outcomes = [
        ("💰 JACKPOT!", lambda: d.execute("update users set balance=balance+50000 where id=?", (target_id,))),
        ("💸 TAX TIME!", lambda: d.execute("update users set balance=balance*0.5 where id=?", (target_id,))),
        ("🎁 FREE SHOE!", lambda: (
            d.execute("insert into hold(user_id, shoe_id, qty) values(?,?,1) on conflict(user_id, shoe_id) do update set qty=qty+1", 
                     (target_id, random.choice(d.execute("select id from shoes").fetchall())["id"]))
        )),
        ("💀 ROBBERY!", lambda: d.execute("update users set balance=balance-10000 where id=?", (target_id,))),
        ("🎲 2X BALANCE!", lambda: d.execute("update users set balance=balance*2 where id=?", (target_id,))),
        ("😈 NOTHING!", lambda: None),
        ("🔥 BURN A SHOE!", lambda: (
            d.execute("delete from hold where user_id=? and rowid = (select rowid from hold where user_id=? limit 1)", (target_id, target_id))
        )),
        ("✨ LUCKY!", lambda: d.execute("update users set balance=balance+25000 where id=?", (target_id,))),
    ]
    
    outcome, action = random.choice(outcomes)
    action()
    now = int(time.time())
    d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", 
             (target_id, f"🎰 WHEEL OF FORTUNE: {outcome}", now))
    d.commit()
    return jsonify({"ok": True, "msg": f"{username}: {outcome}", "username": username, "outcome": outcome})

@app.route("/court")
@login_required
def court_page():
    return render_template("court.html", is_admin=is_admin())

@app.route("/api/court/state")
@login_required
def court_state():
    d = db()
    sess = d.execute("select defendant, accusation, status, started from court_session where id=1").fetchone()
    if not sess or sess["status"] == "inactive":
        return jsonify({"active": False})
    votes = d.execute("select vote, count(*) as cnt from court_votes where session_id=1 group by vote").fetchall()
    vote_counts = {v["vote"]: v["cnt"] for v in votes}
    my_vote = d.execute("select vote from court_votes where session_id=1 and voter=?", (session.get("username"),)).fetchone()
    return jsonify({
        "active": True,
        "defendant": sess["defendant"],
        "accusation": sess["accusation"],
        "status": sess["status"],
        "started": sess["started"],
        "votes": {"guilty": vote_counts.get("guilty", 0), "innocent": vote_counts.get("innocent", 0)},
        "my_vote": my_vote["vote"] if my_vote else None,
        "is_defendant": session.get("username") == sess["defendant"]
    })

@app.route("/api/court/messages")
@login_required
def court_messages():
    d = db()
    since = int(request.args.get("since", 0))
    msgs = d.execute("select id, username, message, is_system, ts from court_messages where session_id=1 and id>? order by id", (since,)).fetchall()
    return jsonify([dict(m) for m in msgs])

@app.route("/api/court/chat", methods=["POST"])
@login_required
def court_chat():
    d = db()
    sess = d.execute("select status, defendant from court_session where id=1").fetchone()
    if not sess or sess["status"] != "active":
        return jsonify({"ok": False, "error": "No active trial"})
    msg = request.json.get("message", "").strip()[:200]
    if not msg:
        return jsonify({"ok": False, "error": "Empty message"})
    username = session.get("username")
    role = "⚖️ JUDGE" if is_admin() else ("🔴 DEFENDANT" if username == sess["defendant"] else "👤")
    now = int(time.time())
    d.execute("insert into court_messages(session_id, username, message, is_system, ts) values(1,?,?,0,?)", (f"{role} {username}", msg, now))
    d.commit()
    return jsonify({"ok": True})

@app.route("/api/court/vote", methods=["POST"])
@login_required
def court_vote():
    d = db()
    sess = d.execute("select status, defendant from court_session where id=1").fetchone()
    if not sess or sess["status"] != "active":
        return jsonify({"ok": False, "error": "No active trial"})
    username = session.get("username")
    if username == sess["defendant"]:
        return jsonify({"ok": False, "error": "Defendant cannot vote"})
    vote = request.json.get("vote")
    if vote not in ["guilty", "innocent"]:
        return jsonify({"ok": False, "error": "Invalid vote"})
    d.execute("insert or replace into court_votes(session_id, voter, vote) values(1,?,?)", (username, vote))
    d.commit()
    return jsonify({"ok": True})

@app.route("/api/admin/court/start", methods=["POST"])
@login_required
def admin_court_start():
    if not is_admin():
        return jsonify({"ok": False, "error": "Unauthorized"}), 403
    d = db()
    defendant = request.json.get("defendant", "").lower().strip()
    accusation = request.json.get("accusation", "unspecified crimes").strip()
    if not defendant:
        return jsonify({"ok": False, "error": "Enter defendant username"})
    acc = d.execute("select id from accounts where username=?", (defendant,)).fetchone()
    if not acc:
        return jsonify({"ok": False, "error": f"User '{defendant}' not found"})
    now = int(time.time())
    d.execute("delete from court_messages where session_id=1")
    d.execute("delete from court_votes where session_id=1")
    d.execute("update court_session set defendant=?, accusation=?, status='active', started=?, ended=null where id=1", (defendant, accusation, now))
    d.execute("insert into court_messages(session_id, username, message, is_system, ts) values(1,'SYSTEM',?,1,?)", (f"⚖️ COURT IS NOW IN SESSION! {defendant.upper()} stands accused of: {accusation}", now))
    users = d.execute("select id from users").fetchall()
    for u in users:
        d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", (u["id"], f"⚖️ COURT IN SESSION! {defendant} is on trial for: {accusation}. Join /court to participate!", now))
    d.commit()
    return jsonify({"ok": True, "msg": f"Trial started for {defendant}"})

@app.route("/api/admin/court/accuse", methods=["POST"])
@login_required
def admin_court_accuse():
    if not is_admin():
        return jsonify({"ok": False, "error": "Unauthorized"}), 403
    d = db()
    sess = d.execute("select status from court_session where id=1").fetchone()
    if not sess or sess["status"] != "active":
        return jsonify({"ok": False, "error": "No active trial"})
    accusation = request.json.get("accusation", "").strip()
    if not accusation:
        return jsonify({"ok": False, "error": "Enter accusation"})
    now = int(time.time())
    d.execute("insert into court_messages(session_id, username, message, is_system, ts) values(1,'SYSTEM',?,1,?)", (f"📜 NEW CHARGE: {accusation}", now))
    d.commit()
    return jsonify({"ok": True})

@app.route("/api/admin/court/verdict", methods=["POST"])
@login_required
def admin_court_verdict():
    if not is_admin():
        return jsonify({"ok": False, "error": "Unauthorized"}), 403
    d = db()
    sess = d.execute("select status, defendant from court_session where id=1").fetchone()
    if not sess or sess["status"] != "active":
        return jsonify({"ok": False, "error": "No active trial"})
    verdict = request.json.get("verdict")
    punishment = request.json.get("punishment", "")
    if verdict not in ["guilty", "innocent"]:
        return jsonify({"ok": False, "error": "Invalid verdict"})
    now = int(time.time())
    votes = d.execute("select vote, count(*) as cnt from court_votes where session_id=1 group by vote").fetchall()
    vote_str = ", ".join([f"{v['vote']}: {v['cnt']}" for v in votes]) or "No votes"
    if verdict == "guilty":
        msg = f"🔨 VERDICT: GUILTY! Jury voted: {vote_str}. {punishment if punishment else 'Punishment pending.'}"
    else:
        msg = f"✅ VERDICT: INNOCENT! Jury voted: {vote_str}. {sess['defendant']} is free to go."
    d.execute("insert into court_messages(session_id, username, message, is_system, ts) values(1,'SYSTEM',?,1,?)", (msg, now))
    d.execute("update court_session set status='verdict' where id=1")
    acc = d.execute("select id from accounts where username=?", (sess["defendant"],)).fetchone()
    if acc:
        d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", (acc["id"], f"⚖️ Your trial verdict: {verdict.upper()}! {punishment if verdict=='guilty' else ''}", now))
    d.commit()
    return jsonify({"ok": True, "msg": f"Verdict delivered: {verdict}"})

@app.route("/api/admin/court/sentence", methods=["POST"])
@login_required
def admin_court_sentence():
    if not is_admin():
        return jsonify({"ok": False, "error": "Unauthorized"}), 403
    d = db()
    sess = d.execute("select status, defendant from court_session where id=1").fetchone()
    if not sess or sess["status"] not in ["active", "verdict"]:
        return jsonify({"ok": False, "error": "No active trial"})
    sentence = request.json.get("sentence", "").strip()
    if not sentence:
        return jsonify({"ok": False, "error": "Enter a sentence"})
    now = int(time.time())
    defendant = sess["defendant"]
    acc = d.execute("select id from accounts where username=?", (defendant,)).fetchone()
    if not acc:
        return jsonify({"ok": False, "error": "Defendant not found"})
    uid = acc["id"]
    if "PUBLIC HANGING" in sentence:
        d.execute("insert into court_messages(session_id, username, message, is_system, ts) values(1,'SYSTEM',?,1,?)", (f"☠️ SENTENCE: PUBLIC HANGING! {defendant.upper()} is being led to the gallows...", now))
        d.execute("insert into announcements(message, ts, expires) values(?,?,?)", (f"☠️ PUBLIC EXECUTION: {defendant.upper()} is being hanged!", now, now + 30))
        d.execute("delete from active_hanging")
        d.execute("insert into active_hanging(id, victim, started) values(1,?,?)", (defendant, now))
        d.execute("delete from hold where user_id=?", (uid,))
        d.execute("delete from appraised where user_id=?", (uid,))
        d.execute("delete from trades where from_user=? or to_user=?", (uid, uid))
        d.execute("delete from notifications where user_id=?", (uid,))
        d.execute("delete from users where id=?", (uid,))
        d.execute("delete from accounts where id=?", (uid,))
    elif "Life Sentence" in sentence:
        d.execute("insert into court_messages(session_id, username, message, is_system, ts) values(1,'SYSTEM',?,1,?)", (f"⛓️ SENTENCE: LIFE IMPRISONMENT! {defendant.upper()} is permanently banned.", now))
        d.execute("update accounts set ban_until=? where id=?", (now + 999999999, uid))
        d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", (uid, "⛓️ You have been sentenced to LIFE IMPRISONMENT (permanent ban)", now))
    elif "1 Week Prison" in sentence:
        d.execute("insert into court_messages(session_id, username, message, is_system, ts) values(1,'SYSTEM',?,1,?)", (f"⛓️ SENTENCE: 1 WEEK PRISON! {defendant.upper()} is banned for 7 days.", now))
        d.execute("update accounts set ban_until=? where id=?", (now + 604800, uid))
        d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", (uid, "⛓️ You have been sentenced to 1 WEEK PRISON (7 day ban)", now))
    elif "1 Day Jail" in sentence:
        d.execute("insert into court_messages(session_id, username, message, is_system, ts) values(1,'SYSTEM',?,1,?)", (f"🔒 SENTENCE: 1 DAY JAIL! {defendant.upper()} is banned for 24 hours.", now))
        d.execute("update accounts set ban_until=? where id=?", (now + 86400, uid))
        d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", (uid, "🔒 You have been sentenced to 1 DAY JAIL (24 hour ban)", now))
    elif "1 Hour Jail" in sentence:
        d.execute("insert into court_messages(session_id, username, message, is_system, ts) values(1,'SYSTEM',?,1,?)", (f"🔒 SENTENCE: 1 HOUR JAIL! {defendant.upper()} is banned for 1 hour.", now))
        d.execute("update accounts set ban_until=? where id=?", (now + 3600, uid))
        d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", (uid, "🔒 You have been sentenced to 1 HOUR JAIL (1 hour ban)", now))
    elif "Bankruptcy" in sentence:
        old_bal = d.execute("select balance from users where id=?", (uid,)).fetchone()["balance"]
        d.execute("update users set balance=0 where id=?", (uid,))
        d.execute("delete from hold where user_id=?", (uid,))
        d.execute("delete from appraised where user_id=?", (uid,))
        d.execute("insert into court_messages(session_id, username, message, is_system, ts) values(1,'SYSTEM',?,1,?)", (f"💀 SENTENCE: BANKRUPTCY! {defendant.upper()} loses ALL assets (${old_bal:,.0f} + all shoes)!", now))
        d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", (uid, f"💀 You have been sentenced to BANKRUPTCY! All ${old_bal:,.0f} and shoes seized.", now))
    elif "Asset Seizure" in sentence:
        old_bal = d.execute("select balance from users where id=?", (uid,)).fetchone()["balance"]
        seized = old_bal * 0.5
        d.execute("update users set balance=balance-? where id=?", (seized, uid))
        d.execute("insert into court_messages(session_id, username, message, is_system, ts) values(1,'SYSTEM',?,1,?)", (f"🏦 SENTENCE: ASSET SEIZURE! 50% of {defendant.upper()}'s balance (${seized:,.0f}) has been seized!", now))
        d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", (uid, f"🏦 ASSET SEIZURE: ${seized:,.0f} (50%) of your balance was taken!", now))
    elif "Heavy Fine" in sentence or "$25,000" in sentence:
        d.execute("update users set balance=balance-25000 where id=?", (uid,))
        d.execute("insert into court_messages(session_id, username, message, is_system, ts) values(1,'SYSTEM',?,1,?)", (f"💸 SENTENCE: HEAVY FINE! {defendant.upper()} must pay $25,000!", now))
        d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", (uid, "💸 You have been fined $25,000!", now))
    elif "Fine" in sentence or "$5,000" in sentence:
        d.execute("update users set balance=balance-5000 where id=?", (uid,))
        d.execute("insert into court_messages(session_id, username, message, is_system, ts) values(1,'SYSTEM',?,1,?)", (f"💸 SENTENCE: FINE! {defendant.upper()} must pay $5,000!", now))
        d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", (uid, "💸 You have been fined $5,000!", now))
    else:
        d.execute("insert into court_messages(session_id, username, message, is_system, ts) values(1,'SYSTEM',?,1,?)", (f"⚖️ SENTENCE: {sentence}", now))
        d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", (uid, f"⚖️ Your sentence: {sentence}", now))
    d.commit()
    return jsonify({"ok": True})

@app.route("/api/admin/court/end", methods=["POST"])
@login_required
def admin_court_end():
    if not is_admin():
        return jsonify({"ok": False, "error": "Unauthorized"}), 403
    d = db()
    now = int(time.time())
    d.execute("insert into court_messages(session_id, username, message, is_system, ts) values(1,'SYSTEM','⚖️ COURT IS ADJOURNED!',1,?)", (now,))
    d.execute("update court_session set status='inactive', ended=? where id=1", (now,))
    d.commit()
    return jsonify({"ok": True, "msg": "Court adjourned"})

@app.route("/gambling")
@login_required
def gambling_page():
    return render_template("gambling.html", is_admin=is_admin())

@app.route("/lootbox")
@login_required
def lootbox_page():
    return redirect(url_for("gambling_page"))

@app.route("/api/lootbox", methods=["POST"])
@login_required
def api_lootbox():
    u = uid()
    d = db()
    amount = int(request.json.get("amount", 0))
    if amount < 2500 or amount > 150000:
        return jsonify({"ok": False, "error": "Amount must be $2,500 - $150,000"})
    bal = d.execute("select balance from users where id=?", (u,)).fetchone()["balance"]
    if bal < amount:
        return jsonify({"ok": False, "error": f"Not enough balance (need ${amount:,}, have ${bal:,.0f})"})
    target = amount * random.uniform(0.50, 1.45)
    all_shoes = d.execute("select id, name, rarity, base from shoes").fetchall()
    best, best_diff = None, float('inf')
    for s in all_shoes:
        price = get_sell_price(s["id"]) or s["base"]
        if price <= 0:
            continue
        needed_mult = target / price
        if needed_mult < 0.50 or needed_mult > 1.50:
            continue
        if needed_mult >= 1.24:
            rating = round(5.0 + (needed_mult - 1.0) / 0.08, 1)
            rating = min(9.9, max(8.0, rating))
            mult = 1.0 + (rating - 5.0) * 0.08
        elif needed_mult >= 1.06:
            rating = round(5.0 + (needed_mult - 1.0) / 0.06, 1)
            rating = min(7.9, max(6.0, rating))
            mult = 1.0 + (rating - 5.0) * 0.06
        elif needed_mult >= 1.0:
            rating = round(5.0 + (needed_mult - 1.0) / 0.04, 1)
            rating = min(5.9, max(5.0, rating))
            mult = 1.0 + (rating - 5.0) * 0.04
        elif needed_mult >= 0.84:
            rating = round(5.0 - (1.0 - needed_mult) / 0.08, 1)
            rating = min(4.9, max(3.0, rating))
            mult = 1.0 - (5.0 - rating) * 0.08
        else:
            rating = round(5.0 - (1.0 - needed_mult) / 0.12, 1)
            rating = min(2.9, max(1.0, rating))
            mult = 1.0 - (5.0 - rating) * 0.12
        mult = round(mult, 2)
        final_val = price * mult
        diff = abs(final_val - target)
        if diff < best_diff:
            best_diff = diff
            best = (s, price, rating, mult, final_val)
    if not best:
        return jsonify({"ok": False, "error": "No shoes available in this price range"})
    shoe, price, rating, mult, final_val = best
    now = int(time.time())
    vroll = random.random()
    variant = "rainbow" if vroll < 0.01 else "shiny" if vroll < 0.06 else ""
    if variant == "rainbow":
        mult = round(mult * 2.5, 2)
        final_val = round(price * mult, 2)
    elif variant == "shiny":
        mult = round(mult * 1.5, 2)
        final_val = round(price * mult, 2)
    d.execute("insert into appraised(user_id, shoe_id, rating, multiplier, ts, variant) values(?,?,?,?,?,?)", (u, shoe["id"], rating, mult, now, variant))
    d.execute("update users set balance=balance-? where id=?", (amount, u))
    d.commit()
    return jsonify({
        "ok": True,
        "shoe": {"id": shoe["id"], "name": shoe["name"], "rarity": shoe["rarity"], "base": shoe["base"]},
        "rating": rating,
        "multiplier": mult,
        "price": round(price, 2),
        "value": round(final_val, 2),
        "paid": amount,
        "variant": variant
    })

@app.route("/api/pot/current")
@login_required
def api_pot_current():
    d = db()
    u = uid()
    now = int(time.time())
    finish_spinning_pot(d)
    gs = d.execute("select last_stock from global_state where id=1").fetchone()
    last_stock = gs["last_stock"] if gs else 0
    next_stock = last_stock + 300
    pot = d.execute("select * from gambling_pots where status='open' order by id desc limit 1").fetchone()
    if pot and now >= next_stock:
        entries = d.execute("select user_id from pot_entries where pot_id=?", (pot["id"],)).fetchall()
        if len(entries) >= 2:
            pick_pot_winner(pot["id"], d)
            d.commit()
            pot = d.execute("select * from gambling_pots where status='spinning' order by id desc limit 1").fetchone()
        elif len(entries) == 1:
            for e in d.execute("select * from pot_entries where pot_id=?", (pot["id"],)).fetchall():
                if e["appraisal_id"] and e["rating"]:
                    d.execute("insert into appraised(user_id, shoe_id, rating, multiplier, variant, ts) values(?,?,?,?,?,?)", (e["user_id"], e["shoe_id"], e["rating"], e["multiplier"], e["variant"] or "", now))
                else:
                    d.execute("insert into hold(user_id, shoe_id, qty) values(?,?,1) on conflict(user_id, shoe_id) do update set qty=qty+1", (e["user_id"], e["shoe_id"]))
            d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", (d.execute("select user_id from pot_entries where pot_id=? limit 1", (pot["id"],)).fetchone()["user_id"], "🎰 Pot ended - your shoes were returned (not enough players)", now))
            d.execute("update gambling_pots set status='closed', ended=? where id=?", (now, pot["id"]))
            d.commit()
            pot = None
        else:
            d.execute("update gambling_pots set status='closed', ended=? where id=?", (now, pot["id"]))
            d.commit()
            pot = None
    if not pot or pot["status"] != "open":
        caps = [50000, 100000, 250000, 500000, 1000000, 999999999]
        cap = random.choice(caps)
        d.execute("insert into gambling_pots(market_cap, created) values(?,?)", (cap, now))
        d.commit()
        pot = d.execute("select * from gambling_pots where status='open' order by id desc limit 1").fetchone()
    entries = d.execute("""
        select pe.*, s.name as shoe_name, s.rarity 
        from pot_entries pe 
        join shoes s on s.id = pe.shoe_id 
        where pe.pot_id=? order by pe.value desc
    """, (pot["id"],)).fetchall()
    participants = {}
    for e in entries:
        if e["username"] not in participants:
            participants[e["username"]] = {"value": 0, "shoes": [], "user_id": e["user_id"]}
        participants[e["username"]]["value"] += e["value"]
        participants[e["username"]]["shoes"].append({
            "name": e["shoe_name"], "rarity": e["rarity"], "value": e["value"],
            "appraisal_id": e["appraisal_id"]
        })
    total = pot["total_value"] or 0
    result = []
    for username, data in participants.items():
        pct = (data["value"] / total * 100) if total > 0 else 0
        result.append({
            "username": username, "value": data["value"], "percent": round(pct, 1),
            "shoes": data["shoes"], "is_me": data["user_id"] == u
        })
    result.sort(key=lambda x: -x["value"])
    cap_display = "∞" if pot["market_cap"] >= 999999999 else f"${pot['market_cap']:,.0f}"
    time_left = max(0, next_stock - now)
    recent_winner = d.execute("select winner_name, total_value, ended from gambling_pots where status='closed' and ended>? order by ended desc limit 1", (now - 10,)).fetchone()
    spinning_pot = d.execute("select winner_name, spin_start, total_value from gambling_pots where status='spinning' limit 1").fetchone()
    return jsonify({
        "id": pot["id"],
        "market_cap": pot["market_cap"],
        "cap_display": cap_display,
        "total": spinning_pot["total_value"] if spinning_pot else total,
        "percent_filled": min(100, (total / pot["market_cap"] * 100)) if pot["market_cap"] < 999999999 else 0,
        "participants": result,
        "status": "spinning" if spinning_pot else pot["status"],
        "time_left": time_left,
        "next_spin": next_stock,
        "spinning": bool(spinning_pot),
        "winner": spinning_pot["winner_name"] if spinning_pot else (recent_winner["winner_name"] if recent_winner else None),
        "winner_total": spinning_pot["total_value"] if spinning_pot else (recent_winner["total_value"] if recent_winner else 0)
    })

@app.route("/api/pot/enter", methods=["POST"])
@login_required
def api_pot_enter():
    u = uid()
    d = db()
    now = int(time.time())
    acc = d.execute("select username from accounts where id=?", (u,)).fetchone()
    if not acc:
        return jsonify({"ok": False, "error": "Not logged in"})
    pot = d.execute("select * from gambling_pots where status='open' order by id desc limit 1").fetchone()
    if not pot:
        return jsonify({"ok": False, "error": "No active pot"})
    shoes = request.json.get("shoes")
    if not shoes:
        shoe_id = request.json.get("shoe_id")
        appraisal_id = request.json.get("appraisal_id")
        shoes = [{"shoe_id": shoe_id, "appraisal_id": appraisal_id, "qty": 1}]
    total_value = 0
    count = 0
    for entry in shoes:
        appraisal_id = entry.get("appraisal_id")
        shoe_id = entry.get("shoe_id")
        qty = max(1, int(entry.get("qty", 1)))
        if appraisal_id:
            shoe = d.execute("""
                select a.*, s.name, s.rarity, s.base from appraised a 
                join shoes s on s.id=a.shoe_id 
                where a.id=? and a.user_id=?
            """, (appraisal_id, u)).fetchone()
            if not shoe:
                continue
            market = d.execute("select price from market where shoe_id=?", (shoe["shoe_id"],)).fetchone()
            base_price = market["price"] if market else shoe["base"]
            value = base_price * shoe["multiplier"]
            d.execute("insert into pot_entries(pot_id, user_id, username, shoe_id, appraisal_id, rating, multiplier, variant, value, ts) values(?,?,?,?,?,?,?,?,?,?)",
                      (pot["id"], u, acc["username"], shoe["shoe_id"], appraisal_id, shoe["rating"], shoe["multiplier"], shoe["variant"] or "", value, now))
            d.execute("delete from appraised where id=?", (appraisal_id,))
            total_value += value
            count += 1
        else:
            if not shoe_id:
                continue
            hold = d.execute("select qty from hold where user_id=? and shoe_id=?", (u, shoe_id)).fetchone()
            if not hold or hold["qty"] < 1:
                continue
            actual_qty = min(qty, hold["qty"])
            shoe = d.execute("select * from shoes where id=?", (shoe_id,)).fetchone()
            market = d.execute("select price from market where shoe_id=?", (shoe_id,)).fetchone()
            value = market["price"] if market else shoe["base"]
            for _ in range(actual_qty):
                d.execute("insert into pot_entries(pot_id, user_id, username, shoe_id, appraisal_id, rating, multiplier, variant, value, ts) values(?,?,?,?,?,?,?,?,?,?)",
                          (pot["id"], u, acc["username"], shoe_id, None, None, None, "", value, now))
                total_value += value
                count += 1
            d.execute("update hold set qty=qty-? where user_id=? and shoe_id=?", (actual_qty, u, shoe_id))
            d.execute("delete from hold where user_id=? and shoe_id=? and qty<=0", (u, shoe_id))
    if count == 0:
        return jsonify({"ok": False, "error": "No valid shoes to enter"})
    new_total = (pot["total_value"] or 0) + total_value
    d.execute("update gambling_pots set total_value=? where id=?", (new_total, pot["id"]))
    if pot["market_cap"] < 999999999 and new_total >= pot["market_cap"]:
        pick_pot_winner(pot["id"], d)
    d.commit()
    return jsonify({"ok": True, "value": total_value, "count": count})

def pick_pot_winner(pot_id, d):
    now = int(time.time())
    entries = d.execute("select user_id, username, sum(value) as total from pot_entries where pot_id=? group by user_id", (pot_id,)).fetchall()
    if not entries:
        return
    total = sum(e["total"] for e in entries)
    roll = random.uniform(0, total)
    cumulative = 0
    winner = entries[0]
    for e in entries:
        cumulative += e["total"]
        if roll <= cumulative:
            winner = e
            break
    d.execute("update gambling_pots set status='spinning', spin_start=?, winner_id=?, winner_name=?, total_value=? where id=?", 
              (now, winner["user_id"], winner["username"], total, pot_id))
    d.commit()

def finish_spinning_pot(d):
    now = int(time.time())
    spinning = d.execute("select * from gambling_pots where status='spinning' and spin_start < ?", (now - 5,)).fetchone()
    if not spinning:
        return
    pot_id = spinning["id"]
    winner_id = spinning["winner_id"]
    winner_name = spinning["winner_name"]
    total = spinning["total_value"] or 0
    all_shoes = d.execute("select shoe_id, appraisal_id, rating, multiplier, variant from pot_entries where pot_id=?", (pot_id,)).fetchall()
    for shoe in all_shoes:
        if shoe["appraisal_id"] and shoe["rating"]:
            d.execute("insert into appraised(user_id, shoe_id, rating, multiplier, variant, ts) values(?,?,?,?,?,?)",
                      (winner_id, shoe["shoe_id"], shoe["rating"], shoe["multiplier"], shoe["variant"] or "", now))
        else:
            d.execute("insert into hold(user_id, shoe_id, qty) values(?,?,1) on conflict(user_id, shoe_id) do update set qty=qty+1",
                      (winner_id, shoe["shoe_id"]))
    d.execute("update gambling_pots set status='closed', ended=? where id=?", (now, pot_id))
    entries = d.execute("select user_id from pot_entries where pot_id=? group by user_id", (pot_id,)).fetchall()
    for e in entries:
        if e["user_id"] == winner_id:
            d.execute("insert into notifications(user_id, message, ts) values(?,?,?)",
                      (e["user_id"], f"🎰 YOU WON THE POT! ${total:,.0f} worth of shoes!", now))
        else:
            d.execute("insert into notifications(user_id, message, ts) values(?,?,?)",
                      (e["user_id"], f"🎰 {winner_name} won the pot. Better luck next time!", now))
    d.commit()

@app.route("/api/pot/spin", methods=["POST"])
@login_required
def api_pot_spin():
    if not is_admin():
        return jsonify({"ok": False, "error": "Admin only"})
    d = db()
    pot = d.execute("select * from gambling_pots where status='open' order by id desc limit 1").fetchone()
    if not pot:
        return jsonify({"ok": False, "error": "No active pot"})
    entries = d.execute("select user_id from pot_entries where pot_id=?", (pot["id"],)).fetchall()
    if len(entries) < 2:
        return jsonify({"ok": False, "error": "Need at least 2 participants"})
    pick_pot_winner(pot["id"], d)
    d.commit()
    return jsonify({"ok": True})

@app.route("/api/pot/history")
@login_required
def api_pot_history():
    d = db()
    pots = d.execute("""
        select p.*, a.username as winner_name 
        from gambling_pots p 
        left join accounts a on a.id = p.winner_id 
        where p.status='closed' 
        order by p.ended desc limit 10
    """).fetchall()
    return jsonify([{
        "id": p["id"], "total": p["total_value"], "winner": p["winner_name"],
        "cap": "∞" if p["market_cap"] >= 999999999 else f"${p['market_cap']:,.0f}",
        "ended": p["ended"]
    } for p in pots])

@app.route("/hanging/<username>")
def hanging_page(username):
    return render_template("hanging.html", victim=username)

@app.route("/api/hanging")
def api_hanging():
    d = db()
    now = int(time.time())
    hanging = d.execute("select victim, started from active_hanging where id=1").fetchone()
    if hanging and now - hanging["started"] < 30:
        return jsonify({"active": True, "victim": hanging["victim"]})
    # Clear old hanging
    d.execute("delete from active_hanging where started < ?", (now - 30,))
    d.commit()
    return jsonify({"active": False})

@app.route("/chat")
@login_required
def chat_page():
    return render_template("chat.html", is_admin=is_admin())

@app.route("/api/chat/messages")
@login_required
def api_chat_messages():
    d = db()
    since = int(request.args.get("since", 0))
    msgs = d.execute("select id, username, message, ts from global_chat where id > ? order by id asc limit 100", (since,)).fetchall()
    return jsonify([dict(m) for m in msgs])

@app.route("/api/chat/latest-id")
@login_required
def api_chat_latest_id():
    d = db()
    latest = d.execute("select id from global_chat order by id desc limit 1").fetchone()
    return jsonify({"id": latest["id"] if latest else 0})

@app.route("/api/chat/send", methods=["POST"])
@login_required
def api_chat_send():
    u = uid()
    d = db()
    acc = d.execute("select username from accounts where id=?", (u,)).fetchone()
    if not acc:
        return jsonify({"ok": False, "error": "Not logged in"})
    msg = request.json.get("message", "").strip()[:200]
    if not msg:
        return jsonify({"ok": False, "error": "Empty message"})
    # Sanitize HTML to prevent stored XSS
    msg = html_mod.escape(msg)
    now = int(time.time())
    last_msg = d.execute("select ts from global_chat where user_id=? order by ts desc limit 1", (u,)).fetchone()
    if last_msg and now - last_msg["ts"] < 2 and not is_admin():
        return jsonify({"ok": False, "error": "Slow down! Wait 2 seconds"})
    username = acc["username"]
    if is_admin():
        username = "👑 " + username
    d.execute("insert into global_chat(user_id, username, message, ts) values(?,?,?,?)", (u, username, msg, now))
    
    import re
    mentions = re.findall(r'@([A-Za-z0-9_-]+)', msg)
    for mention in mentions:
        target = d.execute("select id, username from accounts where lower(username)=?", (mention.lower(),)).fetchone()
        if target and target["id"] != u:
            d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", 
                     (target["id"], f"💬 {acc['username']} mentioned you in chat: {msg[:50]}", now))
    
    d.commit()
    return jsonify({"ok": True})

@app.route("/api/chat/online")
@login_required
def api_chat_online():
    d = db()
    now = int(time.time())
    online = d.execute("""
        select a.username from accounts a
        join users u on u.id = a.id
        where u.last_seen > ?
        order by u.last_seen desc limit 50
    """, (now - 300,)).fetchall()
    return jsonify([r["username"] for r in online])

# Initialize database (needed for WSGI/PythonAnywhere)
with app.app_context():
    init()
    seed()

if __name__ == "__main__":
    app.run(debug=True, threaded=True)
