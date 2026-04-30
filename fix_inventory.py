from app import app
from extensions import db
from models import User, Inventory

def fix_inventory():
    with app.app_context():
        # Find all blood banks
        banks = User.query.filter_by(role='blood_bank').all()
        print(f"Found {len(banks)} blood banks.")
        
        groups = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
        
        for bank in banks:
            print(f"Adding inventory to {bank.name}...")
            for bg in groups:
                # Check if already exists
                existing = Inventory.query.filter_by(blood_bank_id=bank.id, blood_group=bg).first()
                if existing:
                    existing.units = 50 # Increase to a healthy amount
                    print(f"  Updated {bg} to 50 units")
                else:
                    inv = Inventory(blood_bank_id=bank.id, blood_group=bg, units=50)
                    db.session.add(inv)
                    print(f"  Added {bg} with 50 units")
        
        db.session.commit()
        print("Inventory fix complete!")

if __name__ == '__main__':
    fix_inventory()
