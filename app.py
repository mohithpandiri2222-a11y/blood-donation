import os
import math
import json
import time
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, abort, Response, stream_with_context
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db, mail
from models import User, Donation, BloodRequest, Match, Inventory, Alert
from routes.health_card import health_card_bp
from routes.lang import lang_bp, get_t
from notifications import notifications_bp, send_match_emails
from scheduler import init_scheduler
from compatibility import can_donate, get_compatible_donors

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'bloodbank_secret_key_2024')

# Config
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blood_bank.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAIL_SERVER']        = 'smtp.gmail.com'
app.config['MAIL_PORT']          = 587
app.config['MAIL_USE_TLS']       = True
app.config['MAIL_USERNAME']      = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD']      = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER']= os.environ.get('MAIL_USERNAME')

db.init_app(app)
mail.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Register blueprints
app.register_blueprint(health_card_bp)
app.register_blueprint(lang_bp)
app.register_blueprint(notifications_bp)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.context_processor
def inject_globals():
    return dict(t=get_t(), lang=session.get('lang', 'en'), blood_groups=BLOOD_GROUPS)

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
# Public Routes
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    inventory = db.session.query(Inventory.blood_group, db.func.sum(Inventory.units).label('total'))\
                          .group_by(Inventory.blood_group).all()
    return render_template('index.html', inventory=inventory)

@app.route('/inventory')
def public_inventory():
    inventory = db.session.query(
        Inventory.id, Inventory.blood_group, Inventory.units, 
        User.name.label('bank_name'), Inventory.updated_at.label('last_updated')
    ).join(User, User.id == Inventory.blood_bank_id)\
     .order_by(Inventory.blood_group).all()
    return render_template('inventory.html', inventory=inventory)

@app.route('/api/inventory')
def api_inventory():
    items = db.session.query(
        Inventory.blood_group, Inventory.units, 
        User.name.label('bank_name'), Inventory.updated_at
    ).join(User, User.id == Inventory.blood_bank_id).all()
    
    data = []
    for i in items:
        data.append({
            'blood_group': i.blood_group,
            'units': i.units,
            'bank_name': i.bank_name,
            'last_updated': i.updated_at.strftime('%d %b %Y, %I:%M %p')
        })
    return jsonify(data)

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
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form['email'].strip().lower()
        password = request.form['password']
        user     = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash(f'Welcome back, {user.name}!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid credentials.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
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
        donations = Donation.query.filter_by(donor_id=current_user.id).order_by(Donation.donated_on.desc()).all()
        data['donations'] = donations[:5]
        data['donation_count'] = len(donations)
        
        # Calculate eligibility
        if current_user.last_donation_date:
            last_date = datetime.strptime(current_user.last_donation_date, '%Y-%m-%d').date()
            next_eligible = last_date + timedelta(days=90)
            data['days_left'] = (next_eligible - date.today()).days
        else:
            data['days_left'] = 0

        # Matches logic
        matches = db.session.query(Match, BloodRequest, User.name)\
            .join(BloodRequest, Match.request_id == BloodRequest.id)\
            .join(User, BloodRequest.seeker_id == User.id)\
            .filter(Match.donor_id == current_user.id)\
            .order_by(Match.matched_at.desc()).limit(5).all()
        data['matches'] = matches
        data['requests'] = BloodRequest.query.filter_by(seeker_id=current_user.id).order_by(BloodRequest.created_at.desc()).all()

    elif role == 'blood_bank':
        data['inventory'] = Inventory.query.filter_by(blood_bank_id=current_user.id).order_by(Inventory.blood_group).all()

    return render_template('dashboard.html', role=role, data=data)

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
        hosp = request.form.get('hospital_name', 'City Hospital')
        lat = float(request.form.get('lat', 17.6868))
        lng = float(request.form.get('lng', 83.2185))

        req = BloodRequest(seeker_id=current_user.id, blood_group=bg, units=units, urgency=urgency, hospital_name=hosp, lat=lat, lng=lng)
        db.session.add(req)
        db.session.flush()

        matches = _find_matches(bg, lat, lng)
        # Send emails asynchronously or in background is better, but here we call it
        send_match_emails(req, matches)
        
        db.session.commit()
        flash(f'Blood request submitted! {len(matches)} donors notified via email.', 'success')
        return redirect(url_for('seeker_matches', req_id=req.id))

    return render_template('seeker_request.html')

@app.route('/seeker/matches/<int:req_id>')
@login_required
def seeker_matches(req_id):
    req = BloodRequest.query.get_or_404(req_id)
    if req.seeker_id != current_user.id: abort(403)
    matches = Match.query.filter_by(request_id=req_id).order_by(Match.distance_km).all()
    return render_template('seeker_matches.html', req=req, matches=matches)

def _find_matches(blood_group, lat, lng, radius_km=10):
    compatible = get_compatible_donors(blood_group)
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
            results.append({
                'id': d.id, 'name': d.name, 'email': d.email, 
                'phone': d.phone, 'distance': dist, 'blood_group': d.blood_group
            })
    results.sort(key=lambda x: x['distance'])
    return results

# ---------------------------------------------------------------------------
# Real-time SSE updates
# ---------------------------------------------------------------------------
@app.route('/stream/<int:request_id>')
def stream(request_id):
    def event_stream():
        last_count = -1
        for _ in range(200): # ~10 minutes
            with app.app_context():
                matches   = Match.query.filter_by(request_id=request_id).all()
                accepted  = [m for m in matches if m.status == 'accepted']
                pending   = [m for m in matches if m.status == 'pending']
                count     = len(accepted)

                if count != last_count:
                    last_count = count
                    donors = [{
                        'name':        m.donor.name,
                        'blood_group': m.donor.blood_group,
                        'phone':       m.donor.phone or ''
                    } for m in accepted]

                    data = json.dumps({
                        'accepted': len(accepted),
                        'pending':  len(pending),
                        'total':    len(matches),
                        'donors':   donors
                    })
                    yield f"data: {data}\n\n"
            time.sleep(3)

    return Response(
        stream_with_context(event_stream()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
    )

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
    return render_template('bloodbank_inventory.html', inventory=full)

# ---------------------------------------------------------------------------
# Donor profile and logs
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
    return render_template('donor_profile.html')

@app.route('/donor/log_donation', methods=['POST'])
@login_required
def log_donation():
    if current_user.role != 'donor': abort(403)
    units = float(request.form.get('units', 1.0))
    place = request.form.get('place', 'Local Hospital')
    today = date.today()
    donation = Donation(donor_id=current_user.id, donated_on=today, place=place, units=units, blood_group=current_user.blood_group)
    db.session.add(donation)
    current_user.last_donation_date = today.strftime('%Y-%m-%d')
    db.session.commit()
    flash('Donation logged successfully!', 'success')
    return redirect(url_for('dashboard'))

# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------
def init_db():
    db.create_all()

with app.app_context():
    init_db()
    init_scheduler(app)

if __name__ == '__main__':
    app.run(debug=True)
