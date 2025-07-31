"""
Flask Application Factory for Document Chatbot
Creates and configures the Flask application with all extensions and blueprints.
"""

import os
from flask import Flask, request, jsonify
from flask_bcrypt import Bcrypt
from app.models import db
from config import Config

# Initialize extensions
bcrypt = Bcrypt()

def create_app(config_class=Config):
    """Application factory pattern"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions with app
    db.init_app(app)
    bcrypt.init_app(app)
    
    # Register blueprints
    from app.routes import main_bp, auth_bp, api_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Error handlers for API routes
    @app.errorhandler(404)
    def handle_404(e):
        # Return JSON for API routes, HTML for others
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Endpoint not found'}), 404
        # For non-API routes, let Flask handle normally
        return e
    
    @app.errorhandler(500)
    def handle_500(e):
        # Return JSON for API routes, HTML for others
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Internal server error'}), 500
        # For non-API routes, let Flask handle normally
        return e
    
    # Create database tables
    with app.app_context():
        db.create_all()
        app.logger.info("Database tables created")
    
    app.logger.info("Flask application created successfully")
    
    return app
