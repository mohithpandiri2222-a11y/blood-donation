from app import app
from extensions import db
from models import User, BloodRequest
from datetime import datetime

def add_demo_request():
    with app.app_context():
        seeker = User.query.filter_by(email='seeker@gmail.com').first()
        if seeker:
            # Add an open request
            req = BloodRequest(
                seeker_id=seeker.id,
                blood_group='O+',
                units=2,
                urgency='high',
                hospital_name='Apollo Vizag',
                lat=17.6880,
                lng=83.2190,
                status='open'
            )
            db.session.add(req)
            db.session.commit()
            print(f"Demo request created for {seeker.name}")

if __name__ == '__main__':
    add_demo_request()
