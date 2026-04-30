from app import app
from extensions import db
from models import User, Inventory, Donation
from werkzeug.security import generate_password_hash
from datetime import date, timedelta

def add_demo_data():
    with app.app_context():
        # 1. Create Admin
        if not User.query.filter_by(email='admin@bloodconnect.com').first():
            admin = User(
                name='Portal Admin',
                email='admin@bloodconnect.com',
                password=generate_password_hash('admin123'),
                role='admin',
                phone='9876543210'
            )
            db.session.add(admin)

        # 2. Create Blood Bank
        if not User.query.filter_by(email='vizag_bank@hospital.com').first():
            bank = User(
                name='Vizag Central Blood Bank',
                email='vizag_bank@hospital.com',
                password=generate_password_hash('bank123'),
                role='blood_bank',
                phone='0891-223344',
                lat=17.7231,
                lng=83.3012
            )
            db.session.add(bank)
            db.session.flush()

            # Add initial inventory
            groups = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
            for bg in groups:
                inv = Inventory(blood_bank_id=bank.id, blood_group=bg, units=10)
                db.session.add(inv)

        # 3. Create Demo Donors
        donors = [
            ('Ravi Kumar', 'ravi@gmail.com', 'O+', 17.6868, 83.2185, '2024-01-10'),
            ('Sita Devi', 'sita@gmail.com', 'B+', 17.7000, 83.2500, None),
            ('Arjun Singh', 'arjun@gmail.com', 'A-', 17.6500, 83.2000, '2023-11-15'),
            ('Priya Rao', 'priya@gmail.com', 'AB+', 17.7500, 83.3500, '2024-02-20'),
            ('Mohit Verma', 'mohit@gmail.com', 'O-', 17.6800, 83.2200, None),
        ]

        for name, email, bg, lat, lng, last_don in donors:
            if not User.query.filter_by(email=email).first():
                d = User(
                    name=name,
                    email=email,
                    password=generate_password_hash('donor123'),
                    role='donor',
                    phone='9988776655',
                    blood_group=bg,
                    lat=lat,
                    lng=lng,
                    last_donation_date=last_don,
                    wallet_balance=100.0 # Give them some initial wallet credit
                )
                db.session.add(d)

        # 4. Create a Seeker
        if not User.query.filter_by(email='seeker@gmail.com').first():
            seeker = User(
                name='Rajesh Seeker',
                email='seeker@gmail.com',
                password=generate_password_hash('seeker123'),
                role='seeker',
                phone='8877665544',
                lat=17.6880,
                lng=83.2190
            )
            db.session.add(seeker)

        db.session.commit()
        print("Demo data added successfully!")

if __name__ == '__main__':
    add_demo_data()
