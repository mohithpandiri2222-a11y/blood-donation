import os
import math
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from models import db, User, Donation, BloodRequest, Match, Inventory
from routes.health_card import health_card_bp

app = Flask(__name__)
app.secret_key = 'bloodbank_secret_key_2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blood_bank.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

app.register_blueprint(health_card_bp)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

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

def compatible_donors_for(recipient_group):
    return [donor for donor, recipients in COMPATIBILITY.items() if recipient_group in recipients]

BLOOD_GROUPS = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']

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
# Routes – Public
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    inventory = db.session.query(Inventory.blood_group, db.func.sum(Inventory.units).label('total'))\
                          .group_by(Inventory.blood_group).all()
    return render_template('index.html', inventory=inventory, blood_groups=BLOOD_GROUPS)

@app.route('/inventory')
def public_inventory():
    inventory = db.session.query(Inventory.blood_group, Inventory.units, User.name.label('bank_name'))\
                          .join(User, User.id == Inventory.blood_bank_id)\
                          .order_by(Inventory.blood_group).all()
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
        lat         = request.form.get('lat')
        lng         = request.form.get('lng')
        last_don    = request.form.get('last_donation_date')

        if not name or not email or not password or not role:
            flash('All required fields must be filled.', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('register'))

        user = User(
            name=name, email=email, 
            password=generate_password_hash(password),
            role=role, phone=phone, blood_group=blood_group,
            lat=float(lat) if lat else None,
            lng=float(lng) if lng else None,
            last_donation_date=last_don
        )
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', blood_groups=BLOOD_GROUPS)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form['email'].strip().lower()
        password = request.form['password']
        user     = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            session['role'] = user.role # legacy support for some templates
            flash(f'Welcome back, {user.name}!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid credentials.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('index'))

# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@app.route('/dashboard')
@login_required
def dashboard():
    role = current_user.role
    data = {}

    if role == 'donor':
        data['donations'] = Donation.query.filter_by(donor_id=current_user.id).order_by(Donation.donated_on.desc()).limit(5).all()
        data['matches'] = db.session.query(Match, BloodRequest, User.name.label('seeker_name'))\
                                   .join(BloodRequest, BloodRequest.id == Match.request_id)\
                                   .join(User, User.id == BloodRequest.seeker_id)\
                                   .filter(Match.donor_id == current_user.id)\
                                   .order_by(Match.matched_at.desc()).limit(5).all()
        # Adapt data['matches'] format to expected template (if needed)
        # The template might expect list of dicts or objects with certain attributes.
        
    elif role == 'seeker':
        data['requests'] = BloodRequest.query.filter_by(seeker_id=current_user.id).order_by(BloodRequest.created_at.desc()).all()

    elif role == 'blood_bank':
        data['inventory'] = Inventory.query.filter_by(blood_bank_id=current_user.id).order_by(Inventory.blood_group).all()

    return render_template('dashboard.html', role=role, data=data, blood_groups=BLOOD_GROUPS)

# ---------------------------------------------------------------------------
# Donor routes
# ---------------------------------------------------------------------------
@app.route('/donor/profile', methods=['GET', 'POST'])
@login_required
def donor_profile():
    if current_user.role != 'donor': abort(403)
    if request.method == 'POST':
        current_user.phone = request.form.get('phone', '')
        current_user.blood_group = request.form.get('blood_group', '')
        lat = request.form.get('lat')
        lng = request.form.get('lng')
        current_user.lat = float(lat) if lat else None
        current_user.lng = float(lng) if lng else None
        current_user.last_donation_date = request.form.get('last_donation_date')
        db.session.commit()
        flash('Profile updated.', 'success')
        return redirect(url_for('donor_profile'))
    return render_template('donor_profile.html', user=current_user, blood_groups=BLOOD_GROUPS)

@app.route('/donor/log_donation', methods=['POST'])
@login_required
def log_donation():
    if current_user.role != 'donor': abort(403)
    units = float(request.form.get('units', 1.0))
    place = request.form.get('place', 'Local Hospital')
    notes = request.form.get('notes', '')
    today = date.today()
    
    donation = Donation(
        donor_id=current_user.id,
        donated_on=today,
        place=place,
        units=units,
        blood_group=current_user.blood_group,
        notes=notes
    )
    db.session.add(donation)
    current_user.last_donation_date = today.strftime('%Y-%m-%d')
    db.session.commit()
    flash('Donation logged successfully!', 'success')
    return redirect(url_for('dashboard'))

# ---------------------------------------------------------------------------
# Seeker routes
# ---------------------------------------------------------------------------
@app.route('/seeker/request', methods=['GET', 'POST'])
@login_required
def seeker_request():
    if current_user.role != 'seeker': abort(403)
    if request.method == 'POST':
        bg = request.form['blood_group']
        units = int(request.form['units'])
        urgency = request.form['urgency']
        lat = float(request.form.get('lat', 17.6868))
        lng = float(request.form.get('lng', 83.2185))

        req = BloodRequest(seeker_id=current_user.id, blood_group=bg, units=units, urgency=urgency)
        db.session.add(req)
        db.session.flush()

        matches = _find_matches(bg, lat, lng)
        for d in matches:
            m = Match(request_id=req.id, donor_id=d['id'], distance_km=round(d['distance'], 2))
            db.session.add(m)
        
        db.session.commit()
        flash(f'Blood request submitted! {len(matches)} donors found nearby.', 'success')
        return redirect(url_for('seeker_matches', req_id=req.id))

    return render_template('seeker_request.html', blood_groups=BLOOD_GROUPS)

@app.route('/seeker/matches/<int:req_id>')
@login_required
def seeker_matches(req_id):
    req = BloodRequest.query.get_or_404(req_id)
    if req.seeker_id != current_user.id: abort(403)
    matches = db.session.query(Match, User)\
                        .join(User, User.id == Match.donor_id)\
                        .filter(Match.request_id == req_id)\
                        .order_by(Match.distance_km).all()
    # Format matches for template (which expects list of dicts/objects with name, phone, etc.)
    formatted = []
    for m, u in matches:
        d = {
            'name': u.name, 'phone': u.phone, 'blood_group': u.blood_group,
            'lat': u.lat, 'lng': u.lng, 'distance_km': m.distance_km
        }
        formatted.append(d)
    return render_template('seeker_matches.html', req=req, matches=formatted)

def _find_matches(blood_group, lat, lng, radius_km=10):
    compatible = compatible_donors_for(blood_group)
    cutoff = (date.today() - timedelta(days=90)).strftime('%Y-%m-%d')
    
    donors = User.query.filter(
        User.role == 'donor',
        User.blood_group.in_(compatible),
        User.lat.isnot(None),
        User.lng.isnot(None)
    ).filter(
        db.or_(User.last_donation_date.is_(None), User.last_donation_date <= cutoff)
    ).all()
    
    results = []
    for d in donors:
        dist = haversine(lat, lng, d.lat, d.lng)
        if dist <= radius_km:
            results.append({'id': d.id, 'name': d.name, 'distance': dist})
    results.sort(key=lambda x: x['distance'])
    return results

# ---------------------------------------------------------------------------
# Blood Bank routes
# ---------------------------------------------------------------------------
@app.route('/bloodbank/inventory', methods=['GET', 'POST'])
@login_required
def bloodbank_inventory():
    if current_user.role != 'blood_bank': abort(403)
    if request.method == 'POST':
        bg = request.form['blood_group']
        units = int(request.form['units'])
        item = Inventory.query.filter_by(blood_bank_id=current_user.id, blood_group=bg).first()
        if item:
            item.units = units
        else:
            item = Inventory(blood_bank_id=current_user.id, blood_group=bg, units=units)
            db.session.add(item)
        db.session.commit()
        flash(f'Inventory updated for {bg}.', 'success')
        return redirect(url_for('bloodbank_inventory'))

    inventory = Inventory.query.filter_by(blood_bank_id=current_user.id).all()
    existing = {i.blood_group: i.units for i in inventory}
    full = [{'blood_group': bg, 'units': existing.get(bg, 0)} for bg in BLOOD_GROUPS]
    return render_template('bloodbank_inventory.html', inventory=full, blood_groups=BLOOD_GROUPS)

@app.route('/bloodbank/requests')
@login_required
def bloodbank_requests():
    if current_user.role != 'blood_bank': abort(403)
    reqs = db.session.query(BloodRequest, User.name.label('seeker_name'), User.phone.label('seeker_phone'))\
                     .join(User, User.id == BloodRequest.seeker_id)\
                     .order_by(BloodRequest.created_at.desc()).all()
    return render_template('bloodbank_requests.html', requests=reqs)

# ---------------------------------------------------------------------------
# DB Init & Seed
# ---------------------------------------------------------------------------
def init_db():
    db.create_all()
    if not User.query.first():
        _seed()

def _seed():
    pw = generate_password_hash("password123")
    donors_data = [
        ("Arjun Reddy",   "arjun@example.com",   "9000000001", "O+",  17.6868, 83.2185, "2024-10-01"),
        ("Priya Sharma",  "priya@example.com",   "9000000002", "A+",  17.7231, 83.3013, "2024-08-15"),
        ("Kiran Kumar",   "kiran@example.com",   "9000000003", "B-",  17.7010, 83.2978, "2024-07-20"),
        ("Sneha Patel",   "sneha@example.com",   "9000000004", "AB+", 17.6590, 83.1980, "2024-09-05"),
        ("Ravi Teja",     "ravi@example.com",    "9000000005", "O-",  17.7350, 83.3200, "2024-06-30"),
    ]
    for n, e, p, bg, lat, lng, ld in donors_data:
        u = User(name=n, email=e, password=pw, role='donor', phone=p, blood_group=bg, lat=lat, lng=lng, last_donation_date=ld)
        db.session.add(u)
    
    bb = User(name="Vizag Blood Bank", email="vizagbb@example.com", password=generate_password_hash("bloodbank123"), role='blood_bank', phone="8910000001")
    db.session.add(bb)
    db.session.flush()
    
    for bg in BLOOD_GROUPS:
        inv = Inventory(blood_bank_id=bb.id, blood_group=bg, units=20)
        db.session.add(inv)
        
    sk = User(name="Demo Seeker", email="seeker@example.com", password=generate_password_hash("seeker123"), role='seeker', phone="9111111111", blood_group="AB+")
    db.session.add(sk)
    db.session.commit()

with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(debug=True)
