import os
import math
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
from flask import (Flask, render_template, request, redirect,
                   url_for, flash, session, g, jsonify)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'bloodbank_secret_key_2024'

DATABASE = 'blood_bank.db'

# ---------------------------------------------------------------------------
# Blood compatibility matrix
# ---------------------------------------------------------------------------
COMPATIBILITY = {
    'O-':  ['O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+'],
    'O+':  ['O+', 'A+', 'B+', 'AB+'],
    'A-':  ['A-', 'A+', 'AB-', 'AB+'],
    'A+':  ['A+', 'AB+'],
    'B-':  ['B-', 'B+', 'AB-', 'AB+'],
    'B+':  ['B+', 'AB+'],
    'AB-': ['AB-', 'AB+'],
    'AB+': ['AB+'],
}

# Reverse: who can donate to this blood_group?
def compatible_donors_for(recipient_group):
    """Return list of blood groups that can donate to recipient_group."""
    return [donor for donor, recipients in COMPATIBILITY.items()
            if recipient_group in recipients]

BLOOD_GROUPS = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def execute_db(query, args=()):
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    return cur.lastrowid

# ---------------------------------------------------------------------------
# Haversine distance (km)
# ---------------------------------------------------------------------------
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# ---------------------------------------------------------------------------
# Auth decorators
# ---------------------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if session.get('role') not in roles:
                flash('Access denied.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated
    return decorator

# ---------------------------------------------------------------------------
# Database initialisation & seed
# ---------------------------------------------------------------------------
def init_db():
    with app.app_context():
        db = get_db()
        db.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL,          -- donor / seeker / blood_bank
                phone TEXT,
                blood_group TEXT,
                lat REAL,
                lng REAL,
                last_donation_date TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS donations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                donor_id INTEGER NOT NULL,
                units INTEGER NOT NULL,
                donation_date TEXT NOT NULL,
                notes TEXT,
                FOREIGN KEY(donor_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seeker_id INTEGER NOT NULL,
                blood_group TEXT NOT NULL,
                units INTEGER NOT NULL,
                urgency TEXT NOT NULL,       -- low / medium / high / critical
                status TEXT DEFAULT 'open',  -- open / fulfilled / closed
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY(seeker_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL,
                donor_id INTEGER NOT NULL,
                distance_km REAL,
                status TEXT DEFAULT 'pending', -- pending / accepted / declined
                matched_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY(request_id) REFERENCES requests(id),
                FOREIGN KEY(donor_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                blood_bank_id INTEGER NOT NULL,
                blood_group TEXT NOT NULL,
                units INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY(blood_bank_id) REFERENCES users(id)
            );
        ''')
        db.commit()
        _seed(db)

def _seed(db):
    # Seed only if empty
    existing = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing > 0:
        return

    donors = [
        ("Arjun Reddy",   "arjun@example.com",   "9000000001", "O+",  17.6868, 83.2185, "2024-10-01"),
        ("Priya Sharma",  "priya@example.com",   "9000000002", "A+",  17.7231, 83.3013, "2024-08-15"),
        ("Kiran Kumar",   "kiran@example.com",   "9000000003", "B-",  17.7010, 83.2978, "2024-07-20"),
        ("Sneha Patel",   "sneha@example.com",   "9000000004", "AB+", 17.6590, 83.1980, "2024-09-05"),
        ("Ravi Teja",     "ravi@example.com",    "9000000005", "O-",  17.7350, 83.3200, "2024-06-30"),
        ("Divya Nair",    "divya@example.com",   "9000000006", "A-",  17.6750, 83.2100, "2024-11-01"),
        ("Suresh Babu",   "suresh@example.com",  "9000000007", "B+",  17.7100, 83.3100, "2024-05-18"),
        ("Meena Das",     "meena@example.com",   "9000000008", "AB-", 17.6900, 83.2400, "2024-10-20"),
        ("Vijay Anand",   "vijay@example.com",   "9000000009", "O+",  17.7200, 83.2700, "2024-04-10"),
        ("Lakshmi Rao",   "lakshmi@example.com", "9000000010", "A+",  17.6800, 83.3000, "2024-09-25"),
    ]

    pw = generate_password_hash("password123")
    for name, email, phone, bg, lat, lng, ld in donors:
        db.execute(
            "INSERT INTO users (name,email,password,role,phone,blood_group,lat,lng,last_donation_date) VALUES (?,?,?,?,?,?,?,?,?)",
            (name, email, pw, 'donor', phone, bg, lat, lng, ld)
        )

    # Blood bank user
    bb_pw = generate_password_hash("bloodbank123")
    db.execute(
        "INSERT INTO users (name,email,password,role,phone) VALUES (?,?,?,?,?)",
        ("Vizag Blood Bank", "vizagbb@example.com", bb_pw, 'blood_bank', "8910000001")
    )
    bb_id = db.execute("SELECT id FROM users WHERE email='vizagbb@example.com'").fetchone()[0]

    inv = [("A+", 15), ("A-", 8), ("B+", 20), ("B-", 5), ("AB+", 10), ("AB-", 3), ("O+", 25), ("O-", 12)]
    for bg, units in inv:
        db.execute(
            "INSERT INTO inventory (blood_bank_id, blood_group, units) VALUES (?,?,?)",
            (bb_id, bg, units)
        )

    # Seeker demo user
    sk_pw = generate_password_hash("seeker123")
    db.execute(
        "INSERT INTO users (name,email,password,role,phone,blood_group) VALUES (?,?,?,?,?,?)",
        ("Demo Seeker", "seeker@example.com", sk_pw, 'seeker', "9111111111", "AB+")
    )

    db.commit()

# ---------------------------------------------------------------------------
# Routes – Public
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    inventory = query_db(
        '''SELECT i.blood_group, SUM(i.units) as total
           FROM inventory i GROUP BY i.blood_group ORDER BY i.blood_group'''
    )
    return render_template('index.html', inventory=inventory, blood_groups=BLOOD_GROUPS)

@app.route('/inventory')
def public_inventory():
    inventory = query_db(
        '''SELECT i.blood_group, SUM(i.units) as total, u.name as bank_name
           FROM inventory i
           JOIN users u ON u.id = i.blood_bank_id
           GROUP BY i.blood_group, u.name
           ORDER BY i.blood_group'''
    )
    return render_template('inventory.html', inventory=inventory)

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name        = request.form['name'].strip()
        email       = request.form['email'].strip().lower()
        password    = request.form['password']
        role        = request.form['role']
        phone       = request.form.get('phone', '').strip()
        blood_group = request.form.get('blood_group', '')
        lat         = request.form.get('lat') or None
        lng         = request.form.get('lng') or None
        last_don    = request.form.get('last_donation_date') or None

        if not name or not email or not password or not role:
            flash('All required fields must be filled.', 'danger')
            return redirect(url_for('register'))

        existing = query_db("SELECT id FROM users WHERE email=?", [email], one=True)
        if existing:
            flash('Email already registered.', 'danger')
            return redirect(url_for('register'))

        pw_hash = generate_password_hash(password)
        execute_db(
            "INSERT INTO users (name,email,password,role,phone,blood_group,lat,lng,last_donation_date) VALUES (?,?,?,?,?,?,?,?,?)",
            (name, email, pw_hash, role, phone, blood_group, lat, lng, last_don)
        )
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', blood_groups=BLOOD_GROUPS)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form['email'].strip().lower()
        password = request.form['password']
        user     = query_db("SELECT * FROM users WHERE email=?", [email], one=True)
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['role']    = user['role']
            session['name']    = user['name']
            flash(f'Welcome back, {user["name"]}!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid credentials.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('index'))

# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@app.route('/dashboard')
@login_required
def dashboard():
    uid  = session['user_id']
    role = session['role']
    data = {}

    if role == 'donor':
        data['donations'] = query_db(
            "SELECT * FROM donations WHERE donor_id=? ORDER BY donation_date DESC LIMIT 5", [uid])
        data['matches'] = query_db(
            '''SELECT m.*, r.blood_group, r.urgency, r.units, u.name as seeker_name
               FROM matches m
               JOIN requests r ON r.id = m.request_id
               JOIN users u ON u.id = r.seeker_id
               WHERE m.donor_id=? ORDER BY m.matched_at DESC LIMIT 5''', [uid])
        data['user'] = query_db("SELECT * FROM users WHERE id=?", [uid], one=True)

    elif role == 'seeker':
        data['requests'] = query_db(
            "SELECT * FROM requests WHERE seeker_id=? ORDER BY created_at DESC", [uid])

    elif role == 'blood_bank':
        data['inventory'] = query_db(
            "SELECT * FROM inventory WHERE blood_bank_id=? ORDER BY blood_group", [uid])

    return render_template('dashboard.html', role=role, data=data, blood_groups=BLOOD_GROUPS)

# ---------------------------------------------------------------------------
# Donor routes
# ---------------------------------------------------------------------------
@app.route('/donor/profile', methods=['GET', 'POST'])
@login_required
@role_required('donor')
def donor_profile():
    uid = session['user_id']
    if request.method == 'POST':
        phone       = request.form.get('phone', '')
        blood_group = request.form.get('blood_group', '')
        lat         = request.form.get('lat') or None
        lng         = request.form.get('lng') or None
        last_don    = request.form.get('last_donation_date') or None
        execute_db(
            "UPDATE users SET phone=?, blood_group=?, lat=?, lng=?, last_donation_date=? WHERE id=?",
            (phone, blood_group, lat, lng, last_don, uid)
        )
        flash('Profile updated.', 'success')
        return redirect(url_for('donor_profile'))
    user = query_db("SELECT * FROM users WHERE id=?", [uid], one=True)
    return render_template('donor_profile.html', user=user, blood_groups=BLOOD_GROUPS)

@app.route('/donor/log_donation', methods=['POST'])
@login_required
@role_required('donor')
def log_donation():
    uid   = session['user_id']
    units = request.form.get('units', 1)
    notes = request.form.get('notes', '')
    today = datetime.today().strftime('%Y-%m-%d')
    execute_db(
        "INSERT INTO donations (donor_id, units, donation_date, notes) VALUES (?,?,?,?)",
        (uid, units, today, notes)
    )
    execute_db(
        "UPDATE users SET last_donation_date=? WHERE id=?", (today, uid)
    )
    flash('Donation logged successfully!', 'success')
    return redirect(url_for('dashboard'))

# ---------------------------------------------------------------------------
# Seeker routes
# ---------------------------------------------------------------------------
@app.route('/seeker/request', methods=['GET', 'POST'])
@login_required
@role_required('seeker')
def seeker_request():
    if request.method == 'POST':
        blood_group = request.form['blood_group']
        units       = int(request.form['units'])
        urgency     = request.form['urgency']
        lat         = float(request.form.get('lat', 17.6868))
        lng         = float(request.form.get('lng', 83.2185))

        req_id = execute_db(
            "INSERT INTO requests (seeker_id, blood_group, units, urgency) VALUES (?,?,?,?)",
            (session['user_id'], blood_group, units, urgency)
        )

        # Run matching engine
        matches = _find_matches(blood_group, lat, lng)
        count   = 0
        for donor in matches:
            execute_db(
                "INSERT INTO matches (request_id, donor_id, distance_km) VALUES (?,?,?)",
                (req_id, donor['id'], round(donor['distance'], 2))
            )
            count += 1

        if count:
            flash(f'✅ Blood request submitted! {count} compatible donor(s) found within 10 km.', 'success')
        else:
            flash('⚠️ Request submitted, but no compatible donors found nearby. We\'ll notify you when one is available.', 'warning')
        return redirect(url_for('seeker_matches', req_id=req_id))

    return render_template('seeker_request.html', blood_groups=BLOOD_GROUPS)

@app.route('/seeker/matches/<int:req_id>')
@login_required
@role_required('seeker')
def seeker_matches(req_id):
    req = query_db("SELECT * FROM requests WHERE id=? AND seeker_id=?",
                   [req_id, session['user_id']], one=True)
    if not req:
        flash('Request not found.', 'danger')
        return redirect(url_for('dashboard'))

    matches = query_db(
        '''SELECT m.*, u.name, u.phone, u.blood_group, u.lat, u.lng
           FROM matches m
           JOIN users u ON u.id = m.donor_id
           WHERE m.request_id=?
           ORDER BY m.distance_km''', [req_id]
    )
    return render_template('seeker_matches.html', req=req, matches=matches)

def _find_matches(blood_group, lat, lng, radius_km=10):
    compatible = compatible_donors_for(blood_group)
    if not compatible:
        return []
    placeholders = ','.join(['?' for _ in compatible])
    cutoff = (datetime.today() - timedelta(days=90)).strftime('%Y-%m-%d')
    donors = query_db(
        f'''SELECT id, name, phone, blood_group, lat, lng, last_donation_date
            FROM users
            WHERE role='donor'
              AND blood_group IN ({placeholders})
              AND lat IS NOT NULL AND lng IS NOT NULL
              AND (last_donation_date IS NULL OR last_donation_date <= ?)''',
        compatible + [cutoff]
    )
    results = []
    for d in donors:
        dist = haversine(lat, lng, d['lat'], d['lng'])
        if dist <= radius_km:
            results.append({**dict(d), 'distance': dist})
    results.sort(key=lambda x: x['distance'])
    return results

@app.route('/api/find_matches')
@login_required
@role_required('seeker')
def api_find_matches():
    blood_group = request.args.get('blood_group', '')
    lat  = float(request.args.get('lat', 17.6868))
    lng  = float(request.args.get('lng', 83.2185))
    matches = _find_matches(blood_group, lat, lng)
    return jsonify(matches)

# ---------------------------------------------------------------------------
# Blood Bank routes
# ---------------------------------------------------------------------------
@app.route('/bloodbank/inventory', methods=['GET', 'POST'])
@login_required
@role_required('blood_bank')
def bloodbank_inventory():
    uid = session['user_id']
    if request.method == 'POST':
        blood_group = request.form['blood_group']
        units       = int(request.form['units'])
        existing    = query_db(
            "SELECT id FROM inventory WHERE blood_bank_id=? AND blood_group=?", [uid, blood_group], one=True)
        if existing:
            execute_db(
                "UPDATE inventory SET units=?, updated_at=datetime('now') WHERE blood_bank_id=? AND blood_group=?",
                (units, uid, blood_group)
            )
        else:
            execute_db(
                "INSERT INTO inventory (blood_bank_id, blood_group, units) VALUES (?,?,?)",
                (uid, blood_group, units)
            )
        flash(f'Inventory updated: {blood_group} → {units} units.', 'success')
        return redirect(url_for('bloodbank_inventory'))

    inventory = query_db(
        "SELECT * FROM inventory WHERE blood_bank_id=? ORDER BY blood_group", [uid])
    # Fill missing groups with 0
    existing_groups = {row['blood_group']: row['units'] for row in inventory}
    full_inventory  = [{'blood_group': bg, 'units': existing_groups.get(bg, 0)} for bg in BLOOD_GROUPS]
    return render_template('bloodbank_inventory.html', inventory=full_inventory, blood_groups=BLOOD_GROUPS)

@app.route('/bloodbank/requests')
@login_required
@role_required('blood_bank')
def bloodbank_requests():
    all_requests = query_db(
        '''SELECT r.*, u.name as seeker_name, u.phone as seeker_phone
           FROM requests r
           JOIN users u ON u.id = r.seeker_id
           ORDER BY r.created_at DESC'''
    )
    return render_template('bloodbank_requests.html', requests=all_requests)

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    init_db()
    app.run(debug=True)
