"""
Configuration settings for the Flask application
"""

import os
from datetime import timedelta

class Config:
    """Base configuration class"""
    
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Database settings
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///instance/chatbot.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # JWT settings
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-string'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=1)
    
    # File upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    UPLOAD_FOLDER = 'uploads'
    
    # API Keys
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
    PINECONE_API_KEY = os.environ.get('PINECONE_API_KEY')
    
    # Pinecone settings
    PINECONE_INDEX_NAME = os.environ.get('PINECONE_INDEX_NAME') or 'pdf-notes'
    PINECONE_ENVIRONMENT = os.environ.get('PINECONE_ENVIRONMENT') or 'aped-4627-b74a'
    PINECONE_HOST = os.environ.get('PINECONE_HOST')
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL') or 'INFO'
    
    # RAG settings
    CHUNK_SIZE = int(os.environ.get('CHUNK_SIZE') or '1000')
    CHUNK_OVERLAP = int(os.environ.get('CHUNK_OVERLAP') or '200')
    EMBEDDING_MODEL = os.environ.get('EMBEDDING_MODEL') or 'models/embedding-001'
    LLM_MODEL = os.environ.get('LLM_MODEL') or 'gemini-2.5-flash'
    
    @staticmethod
    def init_app(app):
        """Initialize app with configuration"""
        # Create upload folder if it doesn't exist
        if not os.path.exists(Config.UPLOAD_FOLDER):
            os.makedirs(Config.UPLOAD_FOLDER)

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or 'sqlite:///chatbot_dev.db'

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'postgresql://user:pass@localhost/chatbot'

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
