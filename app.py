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
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session, send_file
from flask_bcrypt import Bcrypt
from datetime import datetime, timedelta
import hashlib
from werkzeug.utils import secure_filename
from chatbot_logic import DocumentProcessor, QuestionAnswerer
from models import db, User, Project, Document, ChatHistory
from config import Config

# Initialize Flask app
app = Flask(__name__)

# Configuration
app.config.from_object(Config)

# Initialize extensions
db.init_app(app)
bcrypt = Bcrypt(app)

def create_app():
    # Create database tables
    with app.app_context():
        db.create_all()
        app.logger.info("Database tables created")
    
    # Initialize processors
    doc_processor = DocumentProcessor()
    qa_processor = QuestionAnswerer()
    
    app.logger.info("Chatbot application startup")
    
    return app, doc_processor, qa_processor

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
            session['user_id'] = user.id
            session['username'] = user.username
            
            if request.is_json:
                return jsonify({'message': 'Login successful', 'redirect': '/dashboard'}), 200
            else:
                flash('Login successful!', 'success')
                return redirect(url_for('dashboard'))
        else:
            if request.is_json:
                return jsonify({'error': 'Invalid credentials'}), 401
            else:
                flash('Invalid username or password', 'danger')
                return render_template('login.html')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    projects = Project.query.filter_by(user_id=user_id).all()
    
    return render_template('dashboard.html', projects=projects)

@app.route('/create_project', methods=['GET', 'POST'])
def create_project():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        
        name = data.get('name')
        description = data.get('description', '')
        
        if not name:
            return jsonify({'error': 'Project name is required'}), 400
        
        # Create unique namespace
        namespace = f"user_{session['user_id']}_project_{name.lower().replace(' ', '_')}"
        
        project = Project(
            name=name,
            description=description,
            namespace=namespace,
            user_id=session['user_id']
        )
        
        db.session.add(project)
        db.session.commit()
        
        if request.is_json:
            return jsonify({'message': 'Project created successfully', 'project_id': project.id}), 201
        else:
            flash('Project created successfully!', 'success')
            return redirect(url_for('dashboard'))
    
    return render_template('create_project.html')

@app.route('/project/<int:project_id>')
def project_detail(project_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    project = Project.query.filter_by(id=project_id, user_id=user_id).first()
    
    if not project:
        flash('Project not found', 'danger')
        return redirect(url_for('dashboard'))
    
    documents = Document.query.filter_by(project_id=project_id).all()
    chat_history = ChatHistory.query.filter_by(project_id=project_id).order_by(ChatHistory.created_at.asc()).all()
    
    return render_template('project_detail.html', project=project, documents=documents, chat_history=chat_history)

@app.route('/api/projects/<int:project_id>/upload', methods=['POST'])
def upload_documents(project_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    user_id = session['user_id']
    project = Project.query.filter_by(id=project_id, user_id=user_id).first()
    
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    
    if 'files' not in request.files:
        return jsonify({'error': 'No files provided'}), 400
    
    files = request.files.getlist('files')
    
    if not files or all(f.filename == '' for f in files):
        return jsonify({'error': 'No files selected'}), 400
    
    try:
        processed_files = []
        
        for file in files:
            if file and file.filename.lower().endswith('.pdf'):
                filename = secure_filename(file.filename)
                app.logger.info(f"Starting processing of {filename} for project {project_id}")
                
                # Process document
                text, page_count = doc_processor.extract_text_from_pdf(file)
                chunks = doc_processor.get_chunks(text)
                
                app.logger.info(f"Extracted text from {filename}: {len(text)} characters, {page_count} pages")
                app.logger.info(f"Split {filename} into {len(chunks)} chunks")
                
                # Calculate file hash for deduplication
                file_hash = hashlib.md5(text.encode()).hexdigest()
                
                # Check if document already exists
                existing_doc = Document.query.filter_by(
                    project_id=project.id,
                    file_hash=file_hash
                ).first()
                
                if existing_doc:
                    processed_files.append({
                        'filename': filename,
                        'status': 'already_exists',
                        'chunks': len(chunks),
                        'pages': page_count
                    })
                    continue
                
                app.logger.info(f"Storing {filename} in Pinecone...")
                
                doc_processor.store_in_pinecone(
                    chunks=chunks, 
                    namespace=project.namespace, 
                    filename=filename,
                    page_count=page_count
                )
                
                app.logger.info(f"Successfully stored {filename} in Pinecone")
                
                # Save document record
                document = Document(
                    filename=filename,
                    original_filename=filename,
                    file_size=len(text),
                    file_hash=file_hash,
                    chunk_count=len(chunks),
                    page_count=page_count,
                    project_id=project.id
                )
                
                db.session.add(document)
                
                processed_files.append({
                    'filename': filename,
                    'status': 'success',
                    'chunks': len(chunks),
                    'pages': page_count
                })
                
                app.logger.info(f"Document {filename} processed successfully for project {project_id}")
        
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
        result = qa_processor.answer_question(question, project.namespace)
        
        # Handle both old string format and new dict format for backward compatibility
        if isinstance(result, dict):
            answer = result.get('answer', '')
            sources = result.get('sources', [])
        else:
            # Legacy format - just a string
            answer = result
            sources = []
        
        # Save chat history to database
        chat_history = ChatHistory(
            question=question,
            answer=answer,
            sources=sources,  # Store sources as JSON
            project_id=project.id
        )
        
        db.session.add(chat_history)
        db.session.commit()
        
        app.logger.info(f"Saved chat history for project {project_id}")
        
        return jsonify({
            'answer': answer,
            'sources': sources,
            'question': question,
            'chat_id': chat_history.id
        }), 200
        
    except Exception as e:
        app.logger.error(f"Error answering question: {e}")
        return jsonify({'error': f'Error processing question: {str(e)}'}), 500

@app.route('/api/projects/<int:project_id>/delete', methods=['DELETE'])
def delete_project(project_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    user_id = session['user_id']
    project = Project.query.filter_by(id=project_id, user_id=user_id).first()
    
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    
    try:
        # Delete vectors from Pinecone
        doc_processor.delete_namespace_vectors(project.namespace)
        
        # Delete project (documents will be deleted due to cascade)
        db.session.delete(project)
        db.session.commit()
        
        return jsonify({'message': 'Project deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error deleting project: {e}")
        return jsonify({'error': f'Error deleting project: {str(e)}'}), 500

if __name__ == '__main__':
    app, doc_processor, qa_processor = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
