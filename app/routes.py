"""
Application routes organized into blueprints
"""

import logging
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from werkzeug.utils import secure_filename
from app.models import db, User, Project, Document, ChatHistory
from app.auth import authenticate_user, register_user, logout_user, login_required
from app.utils.file_processor import FileProcessor
from app.utils.embedding import EmbeddingProcessor
from app.utils.pinecone_helper import PineconeHelper
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain.chains import RetrievalQA
from config import Config

logger = logging.getLogger(__name__)

# Initialize processors globally
file_processor = None
embedding_processor = None
pinecone_helper = None
qa_chain = None

def initialize_processors():
    """Initialize all processors and services"""
    global file_processor, embedding_processor, pinecone_helper, qa_chain
    
    try:
        # Initialize file processor (this should always work)
        file_processor = FileProcessor()
        logger.info("File processor initialized successfully")
        
        # Try to initialize embedding processor
        try:
            embedding_processor = EmbeddingProcessor()
            logger.info("Embedding processor initialized successfully")
        except Exception as e:
            logger.warning(f"Embedding processor initialization failed: {e}")
            logger.warning("Upload and question answering features will be disabled")
            embedding_processor = None
        
        # Try to initialize Pinecone helper
        try:
            if embedding_processor:
                pinecone_helper = PineconeHelper(embedding_processor.embedding_model)
                logger.info("Pinecone helper initialized successfully")
            else:
                pinecone_helper = None
                logger.warning("Pinecone helper not initialized due to missing embedding processor")
        except Exception as e:
            logger.warning(f"Pinecone helper initialization failed: {e}")
            logger.warning("Vector storage features will be disabled")
            pinecone_helper = None
        
        # Try to initialize QA chain
        try:
            if embedding_processor and pinecone_helper:
                config = Config()
                llm = ChatGoogleGenerativeAI(
                    model=config.LLM_MODEL,
                    google_api_key=config.GOOGLE_API_KEY,
                    temperature=config.TEMPERATURE
                )
                
                # QA prompt template
                qa_template = """
                You are a helpful AI assistant analyzing documents. Use the following context to answer the question.
                If you cannot find the answer in the context, say "I cannot find this information in the provided documents."
                
                Context: {context}
                
                Question: {question}
                
                Answer:
                """
                
                QA_PROMPT = PromptTemplate(
                    template=qa_template,
                    input_variables=["context", "question"]
                )
                
                # Create a retriever from the pinecone helper
                # Use a default namespace for general QA (this will be overridden per query)
                retriever = pinecone_helper.get_retriever(namespace="default")
                
                qa_chain = RetrievalQA.from_chain_type(
                    llm=llm,
                    chain_type="stuff",
                    retriever=retriever,
                    chain_type_kwargs={"prompt": QA_PROMPT},
                    return_source_documents=True
                )
                logger.info("QA chain initialized successfully")
            else:
                qa_chain = None
                logger.warning("QA chain not initialized due to missing dependencies")
        except Exception as e:
            logger.warning(f"QA chain initialization failed: {e}")
            logger.warning("Question answering features will be disabled")
            qa_chain = None
        
        logger.info("Processor initialization completed")
        
    except Exception as e:
        logger.error(f"Critical error in processor initialization: {e}")
        # Set all processors to None to prevent further errors
        file_processor = None
        embedding_processor = None
        pinecone_helper = None
        qa_chain = None
        logger.warning("All processors disabled due to initialization errors")

# Create blueprints
main_bp = Blueprint('main', __name__)
auth_bp = Blueprint('auth', __name__)
api_bp = Blueprint('api', __name__)

# Main routes
@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    projects = Project.query.filter_by(user_id=user_id).all()
    return render_template('dashboard.html', projects=projects)

@main_bp.route('/create_project', methods=['GET', 'POST'])
@login_required
def create_project():
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
            return redirect(url_for('main.dashboard'))
    
    return render_template('create_project.html')

@main_bp.route('/project/<int:project_id>')
@login_required
def project_detail(project_id):
    user_id = session['user_id']
    project = Project.query.filter_by(id=project_id, user_id=user_id).first()
    
    if not project:
        flash('Project not found', 'danger')
        return redirect(url_for('main.dashboard'))
    
    documents = Document.query.filter_by(project_id=project_id).all()
    chat_history = ChatHistory.query.filter_by(project_id=project_id).order_by(ChatHistory.created_at.asc()).all()
    
    return render_template('project_detail.html', project=project, documents=documents, chat_history=chat_history)

# Authentication routes
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        
        success, result = register_user(username, email, password)
        
        if success:
            logger.info(f"New user registered: {username}")
            
            if request.is_json:
                return jsonify({'message': 'User created successfully'}), 201
            else:
                flash('Registration successful! Please login.', 'success')
                return redirect(url_for('auth.login'))
        else:
            if request.is_json:
                return jsonify({'error': result}), 400
            else:
                flash(result, 'danger')
                return render_template('register.html')
    
    return render_template('register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        
        username = data.get('username')
        password = data.get('password')
        
        success, user = authenticate_user(username, password)
        
        if success:
            if request.is_json:
                return jsonify({'message': 'Login successful', 'redirect': '/dashboard'}), 200
            else:
                flash('Login successful!', 'success')
                return redirect(url_for('main.dashboard'))
        else:
            if request.is_json:
                return jsonify({'error': 'Invalid credentials'}), 401
            else:
                flash('Invalid username or password', 'danger')
                return render_template('login.html')
    
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('main.index'))

# API routes
@api_bp.route('/projects/<int:project_id>/upload', methods=['POST'])
@login_required
def upload_documents(project_id):
    try:
        user_id = session['user_id']
        project = Project.query.filter_by(id=project_id, user_id=user_id).first()
        
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        if 'files' not in request.files:
            return jsonify({'error': 'No files provided'}), 400
        
        files = request.files.getlist('files')
        
        if not files or all(f.filename == '' for f in files):
            return jsonify({'error': 'No files selected'}), 400
        
        # Check if processors are initialized
        if not file_processor:
            logger.error("File processor not initialized")
            return jsonify({'error': 'File processing service unavailable. Please check server configuration.'}), 503
            
        if not embedding_processor or not pinecone_helper:
            logger.error("AI processors not initialized")
            return jsonify({'error': 'AI services unavailable. Please check API keys and try again.'}), 503
        
        processed_files = []
        
        for file in files:
            if file and file.filename.lower().endswith(('.pdf', '.jpg', '.jpeg', '.png')):
                filename = secure_filename(file.filename)
                logger.info(f"Starting processing of {filename} for project {project_id}")
                
                try:
                    # Process document (PDF or Image)
                    text, page_count = file_processor.process_file(file)
                    chunks = embedding_processor.get_chunks(text)
                    
                    logger.info(f"Extracted text from {filename}: {len(text)} characters, {page_count} pages")
                    logger.info(f"Split {filename} into {len(chunks)} chunks")
                    
                    # Calculate file hash for deduplication
                    file_hash = file_processor.calculate_file_hash(text)
                    
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
                    
                    logger.info(f"Storing {filename} in Pinecone...")
                    
                    # Store in Pinecone
                    pinecone_helper.store_vectors(
                        chunks=chunks, 
                        namespace=project.namespace, 
                        filename=filename,
                        page_count=page_count
                    )
                    
                    logger.info(f"Successfully stored {filename} in Pinecone")
                    
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
                    
                    logger.info(f"Document {filename} processed successfully for project {project_id}")
                    
                except Exception as file_error:
                    logger.error(f"Error processing file {filename}: {file_error}")
                    processed_files.append({
                        'filename': filename,
                        'status': 'error',
                        'error': str(file_error)
                    })
            else:
                processed_files.append({
                    'filename': file.filename if file else 'Unknown',
                    'status': 'error',
                    'error': 'Invalid file type. Only PDF, JPG, JPEG, and PNG files are supported.'
                })
        
        db.session.commit()
        
        success_count = len([f for f in processed_files if f['status'] == 'success'])
        
        return jsonify({
            'message': f'Successfully processed {success_count} files',
            'files': processed_files
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in upload endpoint: {e}")
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@api_bp.route('/projects/<int:project_id>/ask', methods=['POST'])
@login_required
def ask_question(project_id):
    try:
        user_id = session['user_id']
        project = Project.query.filter_by(id=project_id, user_id=user_id).first()
        
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        data = request.get_json()
        question = data.get('question')
        
        if not question:
            return jsonify({'error': 'Question is required'}), 400
        
        # Check if processors are initialized
        if not pinecone_helper or not qa_chain:
            logger.error("AI processors not initialized")
            return jsonify({'error': 'AI services unavailable. Please check API keys and try again.'}), 503
        
        logger.info(f"Processing question for project {project_id}: {question}")
        
        # Use hybrid search for better retrieval
        search_results = pinecone_helper.hybrid_search(question, project.namespace, top_k=10)
        
        if not search_results:
            logger.warning(f"No relevant documents found for question: {question}")
            return jsonify({
                'answer': 'I could not find any relevant information in the uploaded documents to answer your question.',
                'sources': []
            }), 200
        
        # Create documents from search results
        from langchain_core.documents import Document as LangchainDocument
        retrieved_docs = []
        for result in search_results:
            metadata = result.get('metadata', {})
            text = metadata.get('text', '')
            
            doc = LangchainDocument(
                page_content=text,
                metadata=metadata
            )
            retrieved_docs.append(doc)
        
        logger.info(f"Retrieved {len(retrieved_docs)} documents for QA")
        
        # Use retrieved documents for QA
        if retrieved_docs:
            # Create context from retrieved documents with source numbering
            context_parts = []
            for i, doc in enumerate(retrieved_docs, 1):
                context_parts.append(f"[Source {i}]:\n{doc.page_content}")
            
            context = "\n\n".join(context_parts)
            
            # Create a more detailed prompt that encourages source references
            qa_prompt = f"""
            Based on the following numbered sources from the uploaded documents, please answer the question.
            When providing information, include source references like [Source 1], [Source 2], etc. to indicate where the information comes from.
            If the answer is not found in the sources, say "I cannot find this information in the provided documents."
            
            {context}
            
            Question: {question}
            
            Answer (include source references where appropriate):
            """
            
            try:
                # Get answer using the LLM directly with better context
                config = Config()
                llm = ChatGoogleGenerativeAI(
                    model=config.LLM_MODEL,
                    google_api_key=config.GOOGLE_API_KEY,
                    temperature=config.TEMPERATURE
                )
                
                response = llm.invoke(qa_prompt)
                answer = response.content
                
                logger.info(f"Generated answer for project {project_id}")
                
            except Exception as e:
                logger.error(f"Error generating answer: {e}")
                # Fallback to qa_chain
                vector_store = pinecone_helper.get_vector_store(project.namespace)
                retriever = vector_store.as_retriever(search_kwargs={"k": 5})
                qa_chain.retriever = retriever
                result = qa_chain({"query": question})
                answer = result.get('result', '')
                retrieved_docs = result.get('source_documents', retrieved_docs)
        else:
            answer = 'I could not find any relevant information in the uploaded documents to answer your question.'
        
        # Format sources
        sources = []
        for doc in retrieved_docs:
            source_info = {
                'content': doc.page_content[:200] + '...' if len(doc.page_content) > 200 else doc.page_content,
                'metadata': doc.metadata
            }
            sources.append(source_info)
        
        # Save chat history to database
        chat_history = ChatHistory(
            question=question,
            answer=answer,
            sources=sources,
            project_id=project.id
        )
        
        db.session.add(chat_history)
        db.session.commit()
        
        logger.info(f"Saved chat history for project {project_id}")
        
        return jsonify({
            'answer': answer,
            'sources': sources,
            'question': question,
            'chat_id': chat_history.id
        }), 200
        
    except Exception as e:
        logger.error(f"Error answering question: {e}")
        return jsonify({'error': f'Error processing question: {str(e)}'}), 500

@api_bp.route('/projects/<int:project_id>/delete', methods=['DELETE'])
@login_required
def delete_project(project_id):
    try:
        user_id = session['user_id']
        project = Project.query.filter_by(id=project_id, user_id=user_id).first()
        
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        # Check if processors are initialized
        if not pinecone_helper:
            logger.warning("Pinecone helper not initialized, skipping vector deletion")
        else:
            # Delete vectors from Pinecone
            pinecone_helper.delete_namespace_vectors(project.namespace)
        
        # Delete project (documents will be deleted due to cascade)
        db.session.delete(project)
        db.session.commit()
        
        return jsonify({'message': 'Project deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting project: {e}")
        return jsonify({'error': f'Error deleting project: {str(e)}'}), 500
