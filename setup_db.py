from app import app, db, _seed

with app.app_context():
    print("Dropping all tables...")
    db.drop_all()
    print("Creating all tables...")
    db.create_all()
    print("Seeding data...")
    _seed()
    print("Database setup complete.")
