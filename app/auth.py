"""
Authentication utilities and helper functions
"""

from flask import session, flash, redirect, url_for, jsonify, request
from flask_bcrypt import check_password_hash, generate_password_hash
from app.models import db, User
from datetime import datetime
from functools import wraps

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json:
                return jsonify({'error': 'Authentication required'}), 401
            else:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def authenticate_user(username, password):
    """Authenticate a user with username and password"""
    user = User.query.filter_by(username=username).first()
    
    if user and check_password_hash(user.password_hash, password):
        # Update last login
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # Set session
        session['user_id'] = user.id
        session['username'] = user.username
        
        return True, user
    
    return False, None

def register_user(username, email, password):
    """Register a new user"""
    # Check if username exists
    if User.query.filter_by(username=username).first():
        return False, 'Username already exists'
    
    # Check if email exists
    if User.query.filter_by(email=email).first():
        return False, 'Email already exists'
    
    # Create new user
    hashed_password = generate_password_hash(password).decode('utf-8')
    user = User(username=username, email=email, password_hash=hashed_password)
    
    try:
        db.session.add(user)
        db.session.commit()
        return True, user
    except Exception as e:
        db.session.rollback()
        return False, f'Error creating user: {str(e)}'

def logout_user():
    """Log out the current user"""
    session.clear()

def get_current_user():
    """Get the current logged-in user"""
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None

def is_authenticated():
    """Check if user is authenticated"""
    return 'user_id' in session
