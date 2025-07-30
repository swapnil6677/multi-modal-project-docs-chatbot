"""
Database Models for the Chatbot Application
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    """User model for authentication and management"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    projects = db.relationship('Project', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<User {self.username}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'is_active': self.is_active
        }

class Project(db.Model):
    """Project model for organizing documents"""
    __tablename__ = 'projects'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    namespace = db.Column(db.String(100), unique=True, nullable=False)  # Pinecone namespace
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Foreign keys
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Relationships
    documents = db.relationship('Document', backref='project', lazy=True, cascade='all, delete-orphan')
    chat_history = db.relationship('ChatHistory', backref='project', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Project {self.name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'namespace': self.namespace,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_active': self.is_active,
            'user_id': self.user_id,
            'document_count': len(self.documents),
            'chat_count': len(self.chat_history)
        }

class Document(db.Model):
    """Document model for tracking uploaded files"""
    __tablename__ = 'documents'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255))
    file_size = db.Column(db.Integer)  # in bytes
    file_hash = db.Column(db.String(64))  # SHA256 hash for duplicate detection
    chunk_count = db.Column(db.Integer, default=0)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Foreign keys
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    
    def __repr__(self):
        return f'<Document {self.filename}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'original_filename': self.original_filename,
            'file_size': self.file_size,
            'file_hash': self.file_hash,
            'chunk_count': self.chunk_count,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None,
            'project_id': self.project_id
        }

class ChatHistory(db.Model):
    """Chat history model for storing questions and answers"""
    __tablename__ = 'chat_history'
    
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    response_time = db.Column(db.Float)  # Response time in seconds
    
    # Foreign keys
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    
    def __repr__(self):
        return f'<ChatHistory {self.id}: {self.question[:50]}...>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'question': self.question,
            'answer': self.answer,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'response_time': self.response_time,
            'project_id': self.project_id
        }
