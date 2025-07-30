"""
Flask Application with User Management and Project-based Document Chatbot
Features:
- User authentication and management
- Project-based document organization
- RAG-based question answering
- Document upload and processing
- Pinecone vector storage
"""

import os
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from datetime import datetime, timedelta
import logging
from logging.handlers import RotatingFileHandler
import hashlib
import json
from werkzeug.utils import secure_filename
import uuid

# Import our custom modules
from models import db, User, Project, Document, ChatHistory
from chatbot_logic import DocumentProcessor, QuestionAnswerer
from config import Config

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize extensions
    db.init_app(app)
    bcrypt = Bcrypt(app)
    
    # Setup logging
    setup_logging(app)
    
    # Create tables
    with app.app_context():
        db.create_all()
        create_dummy_users(bcrypt)
    
    # Initialize document processor
    doc_processor = DocumentProcessor()
    qa_system = QuestionAnswerer()
    
    # Routes
    @app.route('/')
    def index():
        return render_template('index.html')
    
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'POST':
            data = request.get_json() if request.is_json else request.form
            
            username = data.get('username')
            email = data.get('email')
            password = data.get('password')
            
            if User.query.filter_by(username=username).first():
                return jsonify({'error': 'Username already exists'}), 400
            
            if User.query.filter_by(email=email).first():
                return jsonify({'error': 'Email already exists'}), 400
            
            hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
            user = User(username=username, email=email, password_hash=hashed_password)
            
            db.session.add(user)
            db.session.commit()
            
            app.logger.info(f"New user registered: {username}")
            
            if request.is_json:
                return jsonify({'message': 'User created successfully'}), 201
            else:
                flash('Registration successful! Please login.', 'success')
                return redirect(url_for('login'))
        
        return render_template('register.html')
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            data = request.get_json() if request.is_json else request.form
            
            username = data.get('username')
            password = data.get('password')
            
            user = User.query.filter_by(username=username).first()
            
            if user and bcrypt.check_password_hash(user.password_hash, password):
                # Set session data
                session['user_id'] = user.id
                session['username'] = user.username
                
                user.last_login = datetime.utcnow()
                db.session.commit()
                
                app.logger.info(f"User logged in: {username}")
                
                if request.is_json:
                    return jsonify({
                        'user_id': user.id,
                        'username': user.username
                    }), 200
                else:
                    flash('Login successful!', 'success')
                    return redirect(url_for('dashboard'))
            else:
                if request.is_json:
                    return jsonify({'error': 'Invalid credentials'}), 401
                else:
                    flash('Invalid credentials', 'error')
        
        return render_template('login.html')
    
    @app.route('/logout')
    def logout():
        session.clear()
        flash('Logged out successfully!', 'info')
        return redirect(url_for('index'))
    
    @app.route('/dashboard')
    def dashboard():
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        user = User.query.get(session['user_id'])
        projects = Project.query.filter_by(user_id=user.id).all()
        
        return render_template('dashboard.html', user=user, projects=projects)
    
    @app.route('/api/projects', methods=['GET', 'POST'])
    def handle_projects():
        # For session-based auth instead of JWT
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
            
        user_id = session['user_id']
        
        if request.method == 'POST':
            data = request.get_json() if request.is_json else request.form
            
            project = Project(
                name=data.get('name'),
                description=data.get('description', ''),
                user_id=user_id,
                namespace=f"proj_{uuid.uuid4().hex[:8]}_{int(datetime.utcnow().timestamp())}"
            )
            
            db.session.add(project)
            db.session.commit()
            
            app.logger.info(f"New project created: {project.name} by user {user_id}")
            
            if request.is_json:
                return jsonify({
                    'id': project.id,
                    'name': project.name,
                    'description': project.description,
                    'namespace': project.namespace,
                    'created_at': project.created_at.isoformat()
                }), 201
            else:
                flash(f'Project "{project.name}" created successfully!', 'success')
                return redirect(url_for('dashboard'))
        
        # GET request
        projects = Project.query.filter_by(user_id=user_id).all()
        return jsonify([{
            'id': p.id,
            'name': p.name,
            'description': p.description,
            'namespace': p.namespace,
            'created_at': p.created_at.isoformat(),
            'document_count': len(p.documents)
        } for p in projects])
    
    @app.route('/api/projects/<int:project_id>', methods=['GET', 'DELETE'])
    def handle_project(project_id):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
            
        user_id = session['user_id']
        project = Project.query.filter_by(id=project_id, user_id=user_id).first()
        
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        if request.method == 'DELETE':
            # Delete from Pinecone
            try:
                doc_processor.delete_project_documents(project.namespace)
                app.logger.info(f"Deleted Pinecone data for project {project_id}")
            except Exception as e:
                app.logger.error(f"Error deleting Pinecone data: {e}")
            
            # Delete from database
            db.session.delete(project)
            db.session.commit()
            
            app.logger.info(f"Project {project_id} deleted by user {user_id}")
            return jsonify({'message': 'Project deleted successfully'})
        
        # GET request
        return jsonify({
            'id': project.id,
            'name': project.name,
            'description': project.description,
            'namespace': project.namespace,
            'created_at': project.created_at.isoformat(),
            'documents': [{
                'id': d.id,
                'filename': d.filename,
                'uploaded_at': d.uploaded_at.isoformat()
            } for d in project.documents],
            'chat_history': [{
                'id': c.id,
                'question': c.question,
                'answer': c.answer,
                'created_at': c.created_at.isoformat()
            } for c in project.chat_history]
        })
    
    @app.route('/api/projects/<int:project_id>/upload', methods=['POST'])
    def upload_documents(project_id):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
            
        user_id = session['user_id']
        project = Project.query.filter_by(id=project_id, user_id=user_id).first()
        
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        if 'files' not in request.files:
            return jsonify({'error': 'No files uploaded'}), 400
        
        files = request.files.getlist('files')
        processed_files = []
        
        try:
            for file in files:
                if file.filename == '':
                    continue
                
                if file and file.filename.lower().endswith('.pdf'):
                    filename = secure_filename(file.filename)
                    
                    # Process document
                    text = doc_processor.extract_text_from_pdf(file)
                    chunks = doc_processor.get_chunks(text)
                    
                    # Store in Pinecone
                    doc_processor.store_in_pinecone(chunks, project.namespace)
                    
                    # Save to database
                    document = Document(
                        filename=filename,
                        project_id=project.id,
                        chunk_count=len(chunks)
                    )
                    db.session.add(document)
                    
                    processed_files.append({
                        'filename': filename,
                        'chunks': len(chunks)
                    })
                    
                    app.logger.info(f"Document {filename} processed for project {project_id}")
            
            db.session.commit()
            
            return jsonify({
                'message': f'Successfully processed {len(processed_files)} files',
                'files': processed_files
            }), 200
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error processing documents: {e}")
            return jsonify({'error': f'Error processing documents: {str(e)}'}), 500
    
    @app.route('/api/projects/<int:project_id>/ask', methods=['POST'])
    def ask_question(project_id):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
            
        user_id = session['user_id']
        project = Project.query.filter_by(id=project_id, user_id=user_id).first()
        
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        data = request.get_json()
        question = data.get('question')
        
        if not question:
            return jsonify({'error': 'Question is required'}), 400
        
        try:
            # Get answer using RAG
            answer = qa_system.answer_question(question, project.namespace)
            
            # Save chat history
            chat = ChatHistory(
                question=question,
                answer=answer,
                project_id=project.id
            )
            db.session.add(chat)
            db.session.commit()
            
            app.logger.info(f"Question answered for project {project_id}")
            
            return jsonify({
                'question': question,
                'answer': answer,
                'timestamp': chat.created_at.isoformat()
            })
            
        except Exception as e:
            app.logger.error(f"Error answering question: {e}")
            return jsonify({'error': f'Error processing question: {str(e)}'}), 500
    
    @app.route('/project/<int:project_id>')
    def project_detail(project_id):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        project = Project.query.filter_by(id=project_id, user_id=session['user_id']).first()
        if not project:
            flash('Project not found', 'error')
            return redirect(url_for('dashboard'))
        
        return render_template('project_detail.html', project=project)
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Not found'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"Internal error: {error}")
        return jsonify({'error': 'Internal server error'}), 500
    
    return app

def setup_logging(app):
    """Setup application logging"""
    if not app.debug:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        file_handler = RotatingFileHandler(
            'logs/chatbot_app.log',
            maxBytes=10240000,
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info('Chatbot application startup')

def create_dummy_users(bcrypt):
    """Create 4-5 dummy users for testing"""
    dummy_users = [
        {'username': 'admin', 'email': 'admin@example.com', 'password': 'admin123'},
        {'username': 'john_doe', 'email': 'john@example.com', 'password': 'password123'},
        {'username': 'jane_smith', 'email': 'jane@example.com', 'password': 'password123'},
        {'username': 'bob_wilson', 'email': 'bob@example.com', 'password': 'password123'},
        {'username': 'alice_brown', 'email': 'alice@example.com', 'password': 'password123'}
    ]
    
    for user_data in dummy_users:
        if not User.query.filter_by(username=user_data['username']).first():
            user = User(
                username=user_data['username'],
                email=user_data['email'],
                password_hash=bcrypt.generate_password_hash(user_data['password']).decode('utf-8')
            )
            db.session.add(user)
    
    db.session.commit()

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
