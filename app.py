import os, sqlite3, time, random, json, uuid, hashlib
from flask import Flask, g, render_template, session, request, jsonify, Response, redirect, url_for
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "cryptoshoe-secret-key-change-me")
db_path = os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "data.db"))
booted = False

def hash_pw(pw):
    return hashlib.sha256((pw + app.secret_key).encode()).hexdigest()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("signup_page"))
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
    create table if not exists accounts(id text primary key, username text unique, password text, created integer);
    create table if not exists device_signups(device_id text primary key, last_signup integer);
    create table if not exists shoes(id integer primary key, name text unique, rarity text, base real);
    create table if not exists users(id text primary key, balance real);
    create table if not exists global_state(id integer primary key, last_stock integer, last_price integer);
    create table if not exists market(shoe_id integer primary key, stock integer, price real, base real, news text, news_val real, news_until integer);
    create table if not exists hold(user_id text, shoe_id integer, qty integer, primary key(user_id, shoe_id));
    create table if not exists history(shoe_id integer, ts integer, price real);
    create table if not exists appraised(id integer primary key autoincrement, user_id text, shoe_id integer, rating real, multiplier real, ts integer);
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
    create table if not exists notifications(id integer primary key autoincrement, user_id text, message text, ts integer);
    create table if not exists announcements(id integer primary key autoincrement, message text, ts integer, expires integer);
    create table if not exists court_session(id integer primary key, defendant text, accusation text, status text, started integer, ended integer);
    create table if not exists court_messages(id integer primary key autoincrement, session_id integer, username text, message text, is_system integer, ts integer);
    create table if not exists court_votes(session_id integer, voter text, vote text, primary key(session_id, voter));
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
        d.execute("alter table users add column last_seen integer default 0")
    except:
        pass
    d.commit()

def pick(w):
    r = random.random() * sum(w)
    s = 0
    for i, v in enumerate(w):
        s += v
        if r <= s:
            return i
    return len(w) - 1

RARITIES = ["common","uncommon","rare","epic","legendary","mythic","secret","dexies","lebos"]
WEIGHTS = [40,22,14,10,6,4,2,1.5,0.5]
BASE_PRICES = {
    "common": (500, 1500),
    "uncommon": (1200, 3500),
    "rare": (3000, 8000),
    "epic": (7000, 18000),
    "legendary": (15000, 40000),
    "mythic": (35000, 90000),
    "secret": (80000, 250000),
    "dexies": (200000, 500000),
    "lebos": (500000, 2000000),
}
VOLATILITY = {
    "common": 1.2,
    "uncommon": 1.4,
    "rare": 1.6,
    "epic": 1.9,
    "legendary": 2.3,
    "mythic": 2.8,
    "secret": 3.4,
    "dexies": 3.8,
    "lebos": 4.25,
}
ADMIN_USERS = ["lebodapotato"]

DEXIES_SHOES = [
    "Dexies Phantom Protocol", "Dexies Neural Apex", "Dexies Quantum Flux",
    "Dexies Void Walker", "Dexies Neon Genesis", "Dexies Cyber Nexus",
    "Dexies Hologram Prime", "Dexies Infinity Core", "Dexies Plasma Edge",
    "Dexies Dark Matter", "Dexies Stellar Drift", "Dexies Zero Gravity"
]
LEBOS_SHOES = [
    "Lebos Divine Ascension", "Lebos Eternal Crown", "Lebos Celestial One",
    "Lebos Golden Throne", "Lebos Supreme Omega", "Lebos Apex Deity",
    "Lebos Immortal Reign", "Lebos Cosmic Emperor", "Lebos Ultimate Genesis"
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
    normal_rarities = ["common","uncommon","rare","epic","legendary","mythic","secret"]
    normal_weights = [40,22,14,10,6,4,2]
    while len(rows) < 120:
        name = f"{random.choice(a)} {random.choice(b)} {random.choice(c)}"
        if name in names:
            continue
        names.add(name)
        rr = normal_rarities[pick(normal_weights)]
        lo, hi = BASE_PRICES[rr]
        rows.append((name, rr, round(random.uniform(lo, hi), 2)))
    for name in DEXIES_SHOES:
        lo, hi = BASE_PRICES["dexies"]
        rows.append((name, "dexies", round(random.uniform(lo, hi), 2)))
    for name in LEBOS_SHOES:
        lo, hi = BASE_PRICES["lebos"]
        rows.append((name, "lebos", round(random.uniform(lo, hi), 2)))
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
        "secret": (1, 3),
        "dexies": (1, 2),
        "lebos": (1, 1),
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
    normal_rarities = ["common","uncommon","rare","epic","legendary","mythic","secret"]
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
    if random.random() < 0.01:
        rr = "lebos" if random.random() < 0.25 else "dexies"
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
    d.executemany("insert into market(shoe_id, stock, price, base, news, news_val, news_until) values(?,?,?,?,?,?,?)", rows)
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
    m = d.execute("select m.*, s.rarity from market m join shoes s on s.id=m.shoe_id").fetchall()
    for r in m:
        price = r["price"]
        base = r["base"]
        rarity = r["rarity"]
        vol = VOLATILITY.get(rarity, 1.0)
        diff = (price - base) / base
        val = r["news_val"]
        if r["news_until"] and r["news_until"] < now:
            d.execute("update market set news='', news_val=0, news_until=0 where shoe_id=?", (r["shoe_id"],))
            val = 0
        news_chance = 0.12 + (vol - 1) * 0.06
        if not r["news_until"] and random.random() < news_chance:
            text, v = news_pick(rarity)
            v *= vol
            duration = random.randint(45, 240) if vol < 2 else random.randint(30, 180)
            d.execute("update market set news=?, news_val=?, news_until=? where shoe_id=?", (text, v, now + duration, r["shoe_id"]))
            val = v
        up = 0.5 - diff * 0.4 + val * 0.25
        up = clamp(up, 0.1, 0.9)
        delta = base * random.uniform(0.005, 0.035) * vol * (1 + abs(val) * 0.5)
        if random.random() < up:
            price += delta
        else:
            price -= delta
        price = round(clamp(price, base * 0.15, base * 4), 2)
        d.execute("update market set price=? where shoe_id=?", (price, r["shoe_id"]))
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
    m = d.execute("""
    select m.shoe_id id, s.name, s.rarity, m.stock, m.price, m.base, m.news, m.news_until
    from market m join shoes s on s.id=m.shoe_id
    order by s.rarity, s.name
    """).fetchall()
    h = d.execute("""
    select h.shoe_id id, s.name, s.rarity, s.base, h.qty
    from hold h join shoes s on s.id=h.shoe_id
    where h.user_id=? order by s.rarity, s.name
    """, (u,)).fetchall()
    appraised = d.execute("""
    select a.id as appraisal_id, a.shoe_id id, s.name, s.rarity, s.base, a.rating, a.multiplier
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
            hr["sell_price"] = mk["price"]
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
        "market": [dict(r) for r in m],
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
    m = d.execute("select price, stock, news from market where shoe_id=?", (shoe_id,)).fetchone()
    in_market = m is not None
    if m:
        price = m["price"]
        stock = m["stock"]
        news = m["news"]
    else:
        last = d.execute("select price from history where shoe_id=? order by ts desc limit 1", (shoe_id,)).fetchone()
        price = last["price"] if last else shoe["base"]
        stock = 0
        news = ""
    rows = d.execute("select ts, price from history where shoe_id=? order by ts", (shoe_id,)).fetchall()
    hold = d.execute("select qty from hold where user_id=? and shoe_id=?", (u, shoe_id)).fetchone()
    owned = hold["qty"] if hold else 0
    gs = d.execute("select last_stock, last_price from global_state where id=1").fetchone()
    return {
        "id": shoe["id"],
        "name": shoe["name"],
        "rarity": shoe["rarity"],
        "base": shoe["base"],
        "price": price,
        "stock": stock,
        "news": news,
        "in_market": in_market,
        "owned": owned,
        "history": [dict(r) for r in rows],
        "next_stock": (gs["last_stock"] if gs else 0) + 300,
        "next_price": (gs["last_price"] if gs else 0) + 10
    }

@app.route("/login", methods=["GET"])
def login_page():
    if "user_id" in session:
        return redirect(url_for("home"))
    return render_template("login.html")

@app.route("/signup", methods=["GET"])
def signup_page():
    if "user_id" in session:
        return redirect(url_for("home"))
    return render_template("signup.html")

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.json
    username = data.get("username", "").strip().lower()
    password = data.get("password", "")
    if not username or not password:
        return jsonify({"ok": False, "error": "Username and password required"})
    d = db()
    acc = d.execute("select id, password, ban_until from accounts where username=?", (username,)).fetchone()
    if not acc or acc["password"] != hash_pw(password):
        return jsonify({"ok": False, "error": "Invalid username or password"})
    now = int(time.time())
    ban_until = acc["ban_until"] or 0
    if ban_until > now:
        remaining = ban_until - now
        if remaining > 86400:
            days = remaining // 86400
            return jsonify({"ok": False, "error": f"Account banned for {days} more day(s)"})
        elif remaining > 3600:
            hours = remaining // 3600
            return jsonify({"ok": False, "error": f"Account banned for {hours} more hour(s)"})
        else:
            mins = remaining // 60
            return jsonify({"ok": False, "error": f"Account banned for {mins} more minute(s)"})
    session["user_id"] = acc["id"]
    session["username"] = username
    return jsonify({"ok": True})

@app.route("/api/signup", methods=["POST"])
def api_signup():
    data = request.json
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
@login_required
def home():
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
    if not row or row["stock"] < qty:
        return jsonify({"ok": False})
    cost = row["price"] * qty
    bal = d.execute("select balance from users where id=?", (u,)).fetchone()["balance"]
    if bal < cost:
        return jsonify({"ok": False})
    d.execute("update market set stock=stock-? where shoe_id=?", (qty, shoe))
    d.execute("insert into hold(user_id, shoe_id, qty) values(?,?,?) on conflict(user_id, shoe_id) do update set qty=qty+excluded.qty", (u, shoe, qty))
    d.execute("update users set balance=balance-? where id=?", (cost, u))
    d.commit()
    return jsonify({"ok": True})

def get_sell_price(shoe_id):
    d = db()
    market = d.execute("select price from market where shoe_id=?", (shoe_id,)).fetchone()
    if market:
        return market["price"]
    shoe = d.execute("select base, rarity from shoes where id=?", (shoe_id,)).fetchone()
    if not shoe:
        return None
    last_price = d.execute("select price from history where shoe_id=? order by ts desc limit 1", (shoe_id,)).fetchone()
    if last_price:
        return last_price["price"] * 0.95
    return shoe["base"] * 0.9

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
        d.execute("delete from appraised where id=? and user_id=?", (appraisal_id, u))
        d.execute("update users set balance=balance+? where id=?", (gain, u))
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
    holds = d.execute("select shoe_id, qty from hold where user_id=?", (u,)).fetchall()
    for h in holds:
        price = get_sell_price(h["shoe_id"]) or 0
        total += price * h["qty"]
    appraised = d.execute("select a.id, a.shoe_id, a.multiplier from appraised a where a.user_id=?", (u,)).fetchall()
    for a in appraised:
        price = get_sell_price(a["shoe_id"]) or 0
        total += price * a["multiplier"]
    d.execute("delete from hold where user_id=?", (u,))
    d.execute("delete from appraised where user_id=?", (u,))
    d.execute("update users set balance=balance+? where id=?", (round(total, 2), u))
    d.commit()
    return jsonify({"ok": True, "total": round(total, 2)})

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
        d.execute("insert into appraised(user_id, shoe_id, rating, multiplier, ts) values(?,?,?,?,?)", (u, shoe_id, rating, multiplier, now))
        results.append({"rating": rating, "multiplier": multiplier, "comment": comment, "perfect": rating == 10.0, "rating_class": rating_class(rating)})
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
    return render_template("profile.html", profile_username=username, is_admin=is_admin())

@app.route("/api/users")
@login_required
def api_users():
    u = uid()
    d = db()
    now = int(time.time())
    q = request.args.get("q", "").strip().lower()
    if q:
        users = d.execute("""
            select a.username, u.balance, u.last_seen from accounts a 
            join users u on u.id=a.id 
            where lower(a.username) like ? 
            order by (case when u.last_seen > ? then 0 else 1 end), u.balance desc limit 50
        """, (f"%{q}%", now - 60)).fetchall()
    else:
        users = d.execute("""
            select a.username, u.balance, u.last_seen from accounts a 
            join users u on u.id=a.id 
            order by (case when u.last_seen > ? then 0 else 1 end), u.balance desc limit 50
        """, (now - 60,)).fetchall()
    result = []
    for row in users:
        udata = get_user_stats(row["username"])
        udata["is_me"] = (row["username"] == session.get("username"))
        udata["online"] = row["last_seen"] and row["last_seen"] > now - 60
        result.append(udata)
    return jsonify(result)

def get_user_stats(username):
    d = db()
    acc = d.execute("select id, username, created from accounts where username=?", (username,)).fetchone()
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
        "joined": acc["created"]
    }

@app.route("/api/user/<username>")
@login_required
def api_user_profile(username):
    u = uid()
    d = db()
    stats = get_user_stats(username)
    if not stats:
        return jsonify({"error": "User not found"}), 404
    acc = d.execute("select id from accounts where username=?", (username,)).fetchone()
    shoes = d.execute("""
        select s.name, s.rarity, h.qty from hold h 
        join shoes s on s.id=h.shoe_id 
        where h.user_id=? order by s.rarity desc, s.name
    """, (acc["id"],)).fetchall()
    appraised = d.execute("""
        select s.name, s.rarity, a.rating from appraised a 
        join shoes s on s.id=a.shoe_id 
        where a.user_id=? order by a.rating desc
    """, (acc["id"],)).fetchall()
    stats["hold"] = [dict(s) for s in shoes]
    stats["appraised"] = [dict(a) for a in appraised]
    stats["is_me"] = (username == session.get("username"))
    return jsonify(stats)

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
        for s in want:
            shoe = d.execute("select name, rarity, base from shoes where id=?", (s["id"],)).fetchone()
            if shoe:
                s["name"] = shoe["name"]
                s["rarity"] = shoe["rarity"]
                s["price"] = get_sell_price(s["id"]) or shoe["base"]
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
        result.append(r)
    appraised = d.execute("""
        select a.id as appraisal_id, a.shoe_id as id, s.name, s.rarity, s.base, a.rating, a.multiplier
        from appraised a join shoes s on s.id=a.shoe_id
        where a.user_id=? order by a.rating desc
    """, (u,)).fetchall()
    for a in appraised:
        r = dict(a)
        r["price"] = (get_sell_price(a["id"]) or a["base"]) * a["multiplier"]
        r["qty"] = 1
        r["appraised"] = True
        result.append(r)
    return jsonify(result)

@app.route("/api/user-shoes/<username>")
@login_required
def api_user_shoes(username):
    d = db()
    acc = d.execute("select id from accounts where username=?", (username,)).fetchone()
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
        select a.id as appraisal_id, a.shoe_id as id, s.name, s.rarity, s.base, a.rating, a.multiplier
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

@app.route("/api/notifications")
@login_required
def get_notifications():
    u = uid()
    d = db()
    notifs = d.execute("select id, message, ts from notifications where user_id=? order by ts desc limit 10", (u,)).fetchall()
    d.execute("delete from notifications where user_id=?", (u,))
    d.commit()
    return jsonify([dict(n) for n in notifs])

def is_admin():
    return session.get("username") in ADMIN_USERS

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
    users = d.execute("""
        select a.username, u.balance, 
        (select count(*) from hold where user_id=a.id) as shoes,
        (select count(*) from appraised where user_id=a.id) as appraised
        from accounts a join users u on u.id=a.id order by a.username
    """).fetchall()
    return jsonify([dict(u) for u in users])

@app.route("/api/admin/shoes")
@login_required
def admin_shoes():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 403
    d = db()
    shoes = d.execute("select id, name, rarity, base from shoes order by rarity, name").fetchall()
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
    acc = d.execute("select id from accounts where username=?", (username,)).fetchone()
    if not acc:
        return jsonify({"ok": False, "error": "User not found"})
    shoe = d.execute("select id, name from shoes where id=?", (shoe_id,)).fetchone()
    if not shoe:
        return jsonify({"ok": False, "error": "Shoe not found"})
    if action == "give":
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

@app.route("/api/admin/ban", methods=["POST"])
@login_required
def admin_ban():
    if not is_admin():
        return jsonify({"ok": False, "error": "Unauthorized"}), 403
    d = db()
    data = request.json
    username = data.get("username", "").lower().strip()
    duration = data.get("duration", "perm")
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
        secs = durations.get(duration, 3600)
        ban_until = now + secs
        d.execute("update accounts set ban_until=? where id=?", (ban_until, uid))
        d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", (uid, f"You have been banned for {duration}", now))
        d.commit()
        return jsonify({"ok": True, "msg": f"Banned {username} for {duration}"})

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
    d.execute("update accounts set ban_until=0 where id=?", (acc["id"],))
    d.execute("insert into notifications(user_id, message, ts) values(?,?,?)", (acc["id"], "🔓 You have been unbanned!", int(time.time())))
    d.commit()
    return jsonify({"ok": True, "msg": f"Unbanned {username}"})

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
    app1 = d.execute("select shoe_id, rating, multiplier, ts from appraised where user_id=?", (acc1["id"],)).fetchall()
    app2 = d.execute("select shoe_id, rating, multiplier, ts from appraised where user_id=?", (acc2["id"],)).fetchall()
    d.execute("delete from hold where user_id=?", (acc1["id"],))
    d.execute("delete from hold where user_id=?", (acc2["id"],))
    d.execute("delete from appraised where user_id=?", (acc1["id"],))
    d.execute("delete from appraised where user_id=?", (acc2["id"],))
    for h in hold2:
        d.execute("insert into hold(user_id, shoe_id, qty) values(?,?,?)", (acc1["id"], h["shoe_id"], h["qty"]))
    for h in hold1:
        d.execute("insert into hold(user_id, shoe_id, qty) values(?,?,?)", (acc2["id"], h["shoe_id"], h["qty"]))
    for a in app2:
        d.execute("insert into appraised(user_id, shoe_id, rating, multiplier, ts) values(?,?,?,?,?)", (acc1["id"], a["shoe_id"], a["rating"], a["multiplier"], a["ts"]))
    for a in app1:
        d.execute("insert into appraised(user_id, shoe_id, rating, multiplier, ts) values(?,?,?,?,?)", (acc2["id"], a["shoe_id"], a["rating"], a["multiplier"], a["ts"]))
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
    if not msg:
        return jsonify({"ok": False, "error": "Enter a message"})
    now = int(time.time())
    d.execute("insert into announcements(message, ts, expires) values(?,?,?)", (msg, now, now + duration))
    d.commit()
    return jsonify({"ok": True, "msg": f"Announcement live for {duration}s"})

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
    appraised = d.execute("select id, shoe_id, rating, multiplier, ts from appraised where user_id=?", (acc["id"],)).fetchall()
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
            existing = d.execute("select qty from hold where user_id=? and shoe_id=?", (target, s["shoe_id"])).fetchone()
            if existing:
                d.execute("update hold set qty=qty+1 where user_id=? and shoe_id=?", (target, s["shoe_id"]))
            else:
                d.execute("insert into hold(user_id, shoe_id, qty) values(?,?,?)", (target, s["shoe_id"], 1))
            count += 1
    for a in appraised:
        target = random.choice(other_users)["id"]
        d.execute("insert into appraised(user_id, shoe_id, rating, multiplier, ts) values(?,?,?,?,?)", (target, a["shoe_id"], a["rating"], a["multiplier"], a["ts"]))
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
        d.execute("insert into court_messages(session_id, username, message, is_system, ts) values(1,'SYSTEM',?,1,?)", (f"☠️ SENTENCE: PUBLIC HANGING! {defendant.upper()} has been EXECUTED! Their account is permanently deleted.", now))
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

@app.route("/lootbox")
@login_required
def lootbox_page():
    return render_template("lootbox.html", is_admin=is_admin())

@app.route("/api/lootbox", methods=["POST"])
@login_required
def api_lootbox():
    u = uid()
    d = db()
    amount = int(request.json.get("amount", 0))
    if amount < 1000 or amount > 100000:
        return jsonify({"ok": False, "error": "Amount must be $1,000 - $100,000"})
    bal = d.execute("select balance from users where id=?", (u,)).fetchone()["balance"]
    if bal < amount:
        return jsonify({"ok": False, "error": f"Not enough balance (need ${amount:,}, have ${bal:,.0f})"})
    target = amount * random.uniform(0.6, 1.4)
    all_shoes = d.execute("select s.id, s.name, s.rarity, s.base, m.price from shoes s left join market m on m.shoe_id=s.id").fetchall()
    best, best_diff = None, float('inf')
    for s in all_shoes:
        price = s["price"] if s["price"] else s["base"]
        needed_mult = target / price
        if needed_mult < 0.52 or needed_mult > 2.0:
            continue
        if needed_mult >= 2.0:
            rating = 10.0
            mult = 2.0
        elif needed_mult >= 1.24:
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
    d.execute("insert into appraised(user_id, shoe_id, rating, multiplier, ts) values(?,?,?,?,?)", (u, shoe["id"], rating, mult, now))
    d.execute("update users set balance=balance-? where id=?", (amount, u))
    d.commit()
    return jsonify({
        "ok": True,
        "shoe": {"id": shoe["id"], "name": shoe["name"], "rarity": shoe["rarity"], "base": shoe["base"]},
        "rating": rating,
        "multiplier": mult,
        "price": round(price, 2),
        "value": round(final_val, 2),
        "paid": amount
    })

if __name__ == "__main__":
    with app.app_context():
        init()
        seed()
    app.run(debug=True, threaded=True)
