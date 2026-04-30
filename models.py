from datetime import datetime
from flask_login import UserMixin
from extensions import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), nullable=False)
    email       = db.Column(db.String(100), unique=True, nullable=False)
    password    = db.Column(db.String(200), nullable=False)
    role        = db.Column(db.String(20), nullable=False) # donor, seeker, blood_bank, admin
    phone       = db.Column(db.String(20))
    blood_group = db.Column(db.String(5))
    lat         = db.Column(db.Float)
    lng         = db.Column(db.Float)
    last_donation_date = db.Column(db.String(10)) # YYYY-MM-DD
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

class Donation(db.Model):
    __tablename__ = 'donations'
    id            = db.Column(db.Integer, primary_key=True)
    donor_id      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    donated_on    = db.Column(db.Date, nullable=False)
    place         = db.Column(db.String(200))
    units         = db.Column(db.Float, default=1.0)
    blood_group   = db.Column(db.String(5))
    certificate_issued = db.Column(db.Boolean, default=False)
    notes         = db.Column(db.Text)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    
    donor = db.relationship('User', backref=db.backref('donations_rel', lazy=True))

class BloodRequest(db.Model):
    __tablename__ = 'requests'
    id            = db.Column(db.Integer, primary_key=True)
    seeker_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    blood_group   = db.Column(db.String(5), nullable=False)
    units         = db.Column(db.Integer, nullable=False)
    urgency       = db.Column(db.String(20), nullable=False)
    hospital_name = db.Column(db.String(200), default='City Hospital')
    lat           = db.Column(db.Float)
    lng           = db.Column(db.Float)
    status        = db.Column(db.String(20), default='open')
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

class Match(db.Model):
    __tablename__ = 'matches'
    id          = db.Column(db.Integer, primary_key=True)
    request_id  = db.Column(db.Integer, db.ForeignKey('requests.id'), nullable=False)
    donor_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    distance_km = db.Column(db.Float)
    status      = db.Column(db.String(20), default='pending') # pending, accepted, declined
    token       = db.Column(db.String(36), unique=True)
    matched_at  = db.Column(db.DateTime, default=datetime.utcnow)
    responded_at = db.Column(db.DateTime)

    donor = db.relationship('User', backref=db.backref('matches_rel', lazy=True))
    blood_request = db.relationship('BloodRequest', backref=db.backref('matches_rel', lazy=True))

class Inventory(db.Model):
    __tablename__ = 'inventory'
    id            = db.Column(db.Integer, primary_key=True)
    blood_bank_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    blood_group   = db.Column(db.String(5), nullable=False)
    units         = db.Column(db.Integer, default=0)
    updated_at    = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Alert(db.Model):
    __tablename__ = 'alerts'
    id            = db.Column(db.Integer, primary_key=True)
    blood_group   = db.Column(db.String(5), nullable=False)
    triggered_at  = db.Column(db.DateTime, default=datetime.utcnow)
    message       = db.Column(db.Text)
    resolved      = db.Column(db.Boolean, default=False)
