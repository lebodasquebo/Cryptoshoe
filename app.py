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
            return redirect(url_for("login_page"))
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

def init():
    d = db()
    d.executescript("""
    create table if not exists accounts(id text primary key, username text unique, password text, created integer);
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
    insert or ignore into global_state(id, last_stock, last_price) values(1, 0, 0);
    """)
    try:
        d.execute("alter table users add column last_income integer default 0")
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

RARITIES = ["common","uncommon","rare","epic","legendary","mythic","secret"]
WEIGHTS = [45,25,15,8,4,2,1]
BASE_PRICES = {
    "common": (500, 1500),
    "uncommon": (1200, 3500),
    "rare": (3000, 8000),
    "epic": (7000, 18000),
    "legendary": (15000, 40000),
    "mythic": (35000, 90000),
    "secret": (80000, 250000),
}
VOLATILITY = {
    "common": 1.4,
    "uncommon": 1.6,
    "rare": 1.8,
    "epic": 2.2,
    "legendary": 2.8,
    "mythic": 3.5,
    "secret": 4.5,
}

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
    while len(rows) < 130:
        name = f"{random.choice(a)} {random.choice(b)} {random.choice(c)}"
        if name in names:
            continue
        names.add(name)
        rr = RARITIES[pick(WEIGHTS)]
        lo, hi = BASE_PRICES[rr]
        rows.append((name, rr, round(random.uniform(lo, hi), 2)))
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
    while len(rows) < 15:
        rr = RARITIES[pick(WEIGHTS)]
        shoe = d.execute("select * from shoes where rarity=? order by random() limit 1", (rr,)).fetchone()
        if shoe["id"] in picked:
            continue
        picked.add(shoe["id"])
        lo, hi = stock_amt(rr)
        stock = random.randint(lo, hi)
        base = shoe["base"]
        vol = VOLATILITY[rr]
        price = round(base * (1 + random.uniform(-0.15, 0.15) * vol), 2)
        rows.append((shoe["id"], stock, price, base, "", 0.0, 0))
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
    acc = d.execute("select id, password from accounts where username=?", (username,)).fetchone()
    if not acc or acc["password"] != hash_pw(password):
        return jsonify({"ok": False, "error": "Invalid username or password"})
    session["user_id"] = acc["id"]
    session["username"] = username
    return jsonify({"ok": True})

@app.route("/api/signup", methods=["POST"])
def api_signup():
    data = request.json
    username = data.get("username", "").strip().lower()
    password = data.get("password", "")
    if not username or len(username) < 3:
        return jsonify({"ok": False, "error": "Username must be at least 3 characters"})
    if len(username) > 20:
        return jsonify({"ok": False, "error": "Username must be 20 characters or less"})
    if not username.isalnum():
        return jsonify({"ok": False, "error": "Username must be alphanumeric"})
    if not password or len(password) < 4:
        return jsonify({"ok": False, "error": "Password must be at least 4 characters"})
    d = db()
    existing = d.execute("select id from accounts where username=?", (username,)).fetchone()
    if existing:
        return jsonify({"ok": False, "error": "Username already taken"})
    user_id = uuid.uuid4().hex
    d.execute("insert into accounts(id, username, password, created) values(?,?,?,?)", 
              (user_id, username, hash_pw(password), int(time.time())))
    d.execute("insert into users(id, balance, last_income) values(?,?,?)", 
              (user_id, 10000, 0))
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
    return render_template("index.html")

@app.route("/inventory")
@login_required
def inventory():
    uid()
    return render_template("inventory.html")

@app.route("/shoe/<int:shoe_id>")
@login_required
def shoe_page(shoe_id):
    uid()
    return render_template("details.html", shoe_id=shoe_id)

@app.route("/api/state")
def api_state():
    u = uid()
    refresh()
    prices()
    income(u)
    return jsonify(state(u))

@app.route("/api/shoe/<int:shoe_id>")
def api_shoe(shoe_id):
    u = uid()
    refresh()
    prices()
    s = shoe_state(u, shoe_id)
    if not s:
        return jsonify({}), 404
    return jsonify(s)

@app.route("/buy", methods=["POST"])
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
    return render_template("appraise.html")

BOB_COMMENTS = {
    "perfect": [
        "🤯 HOLY SMOKES! This is... this is PERFECTION! I've never seen anything like it!",
        "😱 I... I need to sit down. This is the greatest shoe I've ever witnessed!",
        "🏆 In my 40 years of appraising, I've never given a perfect 10. Until now.",
    ],
    "excellent": [
        "🌟 Magnificent! The craftsmanship here is extraordinary!",
        "✨ Now THIS is what I call a premium specimen!",
        "👏 Exceptional quality! You've got a real gem here!",
    ],
    "good": [
        "👍 Solid piece! Above average quality for sure.",
        "😊 Nice! This one's got some good features.",
        "📈 Looking good! Definitely worth more than base.",
    ],
    "average": [
        "🤔 Hmm, it's... fine. Nothing special, nothing terrible.",
        "😐 Average quality. Seen better, seen worse.",
        "📊 Right in the middle. Standard specimen.",
    ],
    "poor": [
        "😬 Oof... I've seen better days on these.",
        "👎 Not great, I'm afraid. Some issues here.",
        "📉 Below average. The market won't love this one.",
    ],
    "terrible": [
        "😰 Oh dear... I hate to be the bearer of bad news...",
        "💀 Yikes. This one's rough. Real rough.",
        "🗑️ I... wow. This is pretty bad. Sorry, friend.",
    ],
}

@app.route("/api/appraise", methods=["POST"])
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
            comment = random.choice(BOB_COMMENTS["perfect"])
        elif rating >= 8.0:
            multiplier = 1.0 + (rating - 5.0) * 0.08
            comment = random.choice(BOB_COMMENTS["excellent"])
        elif rating >= 6.0:
            multiplier = 1.0 + (rating - 5.0) * 0.06
            comment = random.choice(BOB_COMMENTS["good"])
        elif rating >= 5.0:
            multiplier = 1.0 + (rating - 5.0) * 0.04
            comment = random.choice(BOB_COMMENTS["average"])
        elif rating >= 3.0:
            multiplier = 1.0 - (5.0 - rating) * 0.08
            comment = random.choice(BOB_COMMENTS["poor"])
        else:
            multiplier = 1.0 - (5.0 - rating) * 0.12
            comment = random.choice(BOB_COMMENTS["terrible"])
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
    return render_template("users.html")

@app.route("/user/<username>")
@login_required
def user_profile(username):
    return render_template("profile.html", profile_username=username)

@app.route("/api/users")
@login_required
def api_users():
    u = uid()
    d = db()
    q = request.args.get("q", "").strip().lower()
    if q:
        users = d.execute("""
            select a.username, u.balance from accounts a 
            join users u on u.id=a.id 
            where lower(a.username) like ? 
            order by u.balance desc limit 50
        """, (f"%{q}%",)).fetchall()
    else:
        users = d.execute("""
            select a.username, u.balance from accounts a 
            join users u on u.id=a.id 
            order by u.balance desc limit 50
        """).fetchall()
    result = []
    for row in users:
        udata = get_user_stats(row["username"])
        udata["is_me"] = (row["username"] == session.get("username"))
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
        hold = d.execute("select qty from hold where user_id=? and shoe_id=?", (u, shoe["id"])).fetchone()
        if not hold or hold["qty"] < shoe.get("qty", 1):
            return jsonify({"ok": False, "error": f"You don't have enough of that shoe"})
    
    for shoe in want_shoes:
        hold = d.execute("select qty from hold where user_id=? and shoe_id=?", (to_acc["id"], shoe["id"])).fetchone()
        if not hold or hold["qty"] < shoe.get("qty", 1):
            return jsonify({"ok": False, "error": f"They don't have enough of that shoe"})
    
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
        hold = d.execute("select qty from hold where user_id=? and shoe_id=?", (from_user, shoe["id"])).fetchone()
        if not hold or hold["qty"] < shoe.get("qty", 1):
            d.execute("update trades set status='cancelled' where id=?", (trade_id,))
            d.commit()
            return jsonify({"ok": False, "error": "Sender no longer has those shoes"})
    
    for shoe in want_shoes:
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
        qty = shoe.get("qty", 1)
        d.execute("update hold set qty=qty-? where user_id=? and shoe_id=?", (qty, from_user, shoe["id"]))
        d.execute("delete from hold where user_id=? and shoe_id=? and qty<=0", (from_user, shoe["id"]))
        d.execute("insert into hold(user_id, shoe_id, qty) values(?,?,?) on conflict(user_id, shoe_id) do update set qty=qty+?", (u, shoe["id"], qty, qty))
    
    for shoe in want_shoes:
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
def stream():
    u = uid()
    def gen():
        while True:
            refresh()
            prices()
            income(u)
            data = state(u)
            yield f"data: {json.dumps(data)}\n\n"
            time.sleep(2)
    resp = Response(gen(), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    return resp

if __name__ == "__main__":
    with app.app_context():
        init()
        seed()
    app.run(debug=True, threaded=True)
