from app import app
from models import Inventory, User

with app.app_context():
    invs = Inventory.query.all()
    print(f"Total inventory records: {len(invs)}")
    for i in invs:
        bank = User.query.get(i.blood_bank_id)
        print(f"Bank: {bank.name if bank else 'Unknown'}, Group: {i.blood_group}, Units: {i.units}")

    banks = User.query.filter_by(role='blood_bank').all()
    print(f"Total blood banks: {len(banks)}")
    for b in banks:
        print(f"Bank: {b.name}, Email: {b.email}")
