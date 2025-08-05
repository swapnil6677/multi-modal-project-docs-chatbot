"""
Database initialization script.
Run this script to create a new database with all tables.
"""
from app import create_app
from app.models import db

def init_database():
    app = create_app()
    with app.app_context():
        # Create all tables
        db.create_all()
        print("Database initialized successfully!")

if __name__ == '__main__':
    init_database()
