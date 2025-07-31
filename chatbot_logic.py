"""
Chatbot Logic: Document Processing and Question Answering
Based on the Streamlit script provided, adapted for Flask
"""

import os
import time
import hashlib
from typing import List, Dict
import logging
from PyPDF2 import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec
from langchain.prompts import PromptTemplate
from langchain.chains import RetrievalQA
from langchain.chains.summarize import load_summarize_chain
from google.api_core.exceptions import ResourceExhausted
from config import Config

# Setup logging
logger = logging.getLogger(__name__)

class DocumentProcessor:
    """Handles document processing and storage"""
    
    def __init__(self):
        self.config = Config()
        self.pinecone_client = None
        self.embedding_model = None
        self._initialize_services()
    
    def _initialize_services(self):
        """Initialize Pinecone and embedding services"""
        try:
            # Initialize Pinecone
            if self.config.PINECONE_API_KEY:
                self.pinecone_client = Pinecone(api_key=self.config.PINECONE_API_KEY)
                logger.info("Pinecone client initialized")
            else:
                logger.warning("PINECONE_API_KEY not set")
            
            # Initialize embedding model
            if self.config.GOOGLE_API_KEY:
                self.embedding_model = GoogleGenerativeAIEmbeddings(
                    model=self.config.EMBEDDING_MODEL,
                    google_api_key=self.config.GOOGLE_API_KEY
                )
                logger.info("Embedding model initialized")
            else:
                logger.warning("GOOGLE_API_KEY not set")
                
        except Exception as e:
            logger.error(f"Error initializing services: {e}")
            raise
    
    def extract_text_from_pdf(self, pdf_file) -> tuple:
        """Extract text from PDF file and return text with page count"""
        logger.info(f"Extracting text from PDF: {pdf_file.filename}")
        
        try:
            pdf_file.seek(0)  # Reset file pointer
            reader = PdfReader(pdf_file)
            text = ""
            page_count = len(reader.pages)
            
            for page_num, page in enumerate(reader.pages):
                content = page.extract_text() or ""
                text += content
                logger.debug(f"Extracted text from page {page_num + 1}")
            
            logger.info(f"Total text length: {len(text)} characters from {page_count} pages")
            return text, page_count
            
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            raise
    
    def get_chunks(self, text: str) -> List[str]:
        """Split text into chunks for processing"""
        logger.info("Splitting text into chunks")
        
        try:
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.config.CHUNK_SIZE,
                chunk_overlap=self.config.CHUNK_OVERLAP
            )
            chunks = text_splitter.split_text(text)
            
            logger.info(f"Created {len(chunks)} chunks")
            return chunks
            
        except Exception as e:
            logger.error(f"Error chunking text: {e}")
            raise
    
    def store_in_pinecone(self, chunks: List[str], namespace: str, filename: str = None, page_count: int = 0):
        """Store text chunks in Pinecone vector database with filename and page metadata"""
        logger.info(f"Storing {len(chunks)} chunks in Pinecone namespace: {namespace} for file: {filename} ({page_count} pages)")
        
        try:
            if not self.pinecone_client or not self.embedding_model:
                raise ValueError("Pinecone client or embedding model not initialized")
            
            # Create index if it doesn't exist
            index_name = self.config.PINECONE_INDEX_NAME
            existing_indexes = [idx.name for idx in self.pinecone_client.list_indexes()]
            
            if index_name not in existing_indexes:
                logger.info(f"Creating Pinecone index: {index_name}")
                self.pinecone_client.create_index(
                    name=index_name,
                    dimension=768,  # Dimension for Google embeddings
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud="aws",
                        region="us-east-1"
                    )
                )
                # Wait for index to be ready
                time.sleep(10)
            
            # Get index and create vectorstore
            index = self.pinecone_client.Index(index_name)
            vectorstore = PineconeVectorStore(
                index=index,
                embedding=self.embedding_model,
                namespace=namespace
            )
            
            # Convert chunks to documents with metadata
            documents = []
            for i, chunk in enumerate(chunks):
                metadata = {
                    "text": chunk,
                    "chunk_index": i,
                    "total_pages": page_count
                }
                if filename:
                    # Clean filename - remove path and keep just the base name
                    clean_filename = filename.split('/')[-1].split('\\')[-1]
                    # Remove .pdf extension for display
                    if clean_filename.lower().endswith('.pdf'):
                        clean_filename = clean_filename[:-4]
                    metadata["file_name"] = clean_filename
                
                doc = Document(page_content=chunk, metadata=metadata)
                documents.append(doc)
            
            vectorstore.add_documents(documents)
            
            logger.info(f"Successfully stored {len(documents)} documents in Pinecone with metadata")
            
        except Exception as e:
            logger.error(f"Error storing in Pinecone: {e}")
            raise
    
    def delete_project_documents(self, namespace: str):
        """Delete all documents for a project from Pinecone"""
        logger.info(f"Deleting documents from namespace: {namespace}")
        
        try:
            if not self.pinecone_client:
                raise ValueError("Pinecone client not initialized")
            
            index = self.pinecone_client.Index(self.config.PINECONE_INDEX_NAME)
            index.delete(delete_all=True, namespace=namespace)
            
            logger.info(f"Successfully deleted documents from namespace: {namespace}")
            
        except Exception as e:
            logger.error(f"Error deleting documents: {e}")
            raise

class QuestionAnswerer:
    """Handles question answering using RAG"""
    
    def __init__(self):
        self.config = Config()
        self.llm = None
        self.embedding_model = None
        self.pinecone_client = None
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize LLM and other models"""
        try:
            # Initialize LLM
            if self.config.GOOGLE_API_KEY:
                self.llm = ChatGoogleGenerativeAI(
                    model=self.config.LLM_MODEL,
                    temperature=0.1,
                    timeout=120,
                    max_retries=2,
                    google_api_key=self.config.GOOGLE_API_KEY
                )
                logger.info("LLM model initialized")
            else:
                logger.warning("GOOGLE_API_KEY not set")
            
            # Initialize embedding model
            if self.config.GOOGLE_API_KEY:
                self.embedding_model = GoogleGenerativeAIEmbeddings(
                    model=self.config.EMBEDDING_MODEL,
                    google_api_key=self.config.GOOGLE_API_KEY
                )
                logger.info("Embedding model for QA initialized")
            
            # Initialize Pinecone
            if self.config.PINECONE_API_KEY:
                self.pinecone_client = Pinecone(api_key=self.config.PINECONE_API_KEY)
                logger.info("Pinecone client for QA initialized")
                
        except Exception as e:
            logger.error(f"Error initializing QA models: {e}")
            raise
    
    def _safe_generate(self, prompt: str):
        """Generate response with retry logic"""
        for attempt in range(3):
            try:
                logger.debug(f"Sending prompt to LLM (attempt {attempt + 1}/3)")
                response = self.llm.invoke(prompt)
                logger.debug("Successfully got response from LLM")
                return response
                
            except ResourceExhausted as e:
                logger.warning(f"LLM quota hit (Attempt {attempt + 1}). Retrying in 60s...")
                if attempt < 2:
                    time.sleep(60)
                else:
                    raise Exception("LLM quota exceeded after 3 retries")
                    
            except Exception as e:
                logger.error(f"LLM API error (Attempt {attempt + 1}): {str(e)}")
                if attempt < 2:
                    time.sleep(30)
                else:
                    raise Exception(f"LLM API unavailable after 3 retries. Last error: {str(e)}")
    
    def _decompose_question(self, question: str) -> List[str]:
        """Break down complex questions into simpler sub-questions"""
        logger.info(f"Decomposing question: {question}")
        
        try:
            prompt = f"""
            Break this question into 2-3 simple sub-questions. Return only the questions, numbered:
            
            {question}
            
            1.
            2.
            3.
            """
            
            response = self._safe_generate(prompt)
            content = response.content.strip()
            
            # Parse sub-questions
            subqs = []
            for line in content.split("\n"):
                line = line.strip()
                if (line and 
                    any(line.startswith(f"{i}.") for i in range(1, 10)) and
                    "?" in line):
                    question_text = line.split(".", 1)[1].strip()
                    subqs.append(question_text)
            
            if subqs:
                logger.debug(f"Decomposed into sub-questions: {subqs}")
                return subqs
                
        except Exception as e:
            logger.error(f"Question decomposition failed: {str(e)}")
        
        # Fallback to original question
        logger.warning("Using original question as fallback")
        return [question]
    
    def _get_qa_chain(self, retriever):
        """Create QA chain with custom prompt"""
        logger.debug("Building RetrievalQA chain")
        
        template = """Use the following pieces of context to answer the question at the end. 
        If you don't know the answer, just say that you don't know, don't try to make up an answer. 
        Use three sentences maximum. Keep the answer as concise as possible.

        {context}

        Question: {question}
        Helpful Answer:"""
        
        qa_prompt = PromptTemplate(
            input_variables=["context", "question"],
            template=template,
        )
        
        qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=retriever,
            return_source_documents=True,
            chain_type_kwargs={"prompt": qa_prompt}
        )
        
        return qa_chain
    
    def answer_question(self, question: str, namespace: str) -> dict:
        """Answer a question using direct Pinecone retrieval with Microsoft Copilot-style source references"""
        logger.info(f"Answering question: {question} for namespace: {namespace}")
        
        try:
            if not all([self.llm, self.embedding_model, self.pinecone_client]):
                raise ValueError("Required models not initialized")
            
            if not namespace:
                raise ValueError("No namespace provided")
            
            # Use direct Pinecone index access (bypassing LangChain wrapper issues)
            index = self.pinecone_client.Index(self.config.PINECONE_INDEX_NAME)
            
            # Verify documents exist first
            test_vector = self.embedding_model.embed_query("test content")
            test_result = index.query(
                vector=test_vector,
                top_k=1,
                namespace=namespace,
                include_metadata=True
            )
            
            if not test_result.matches:
                return {
                    "answer": "No documents found in this project. Please upload some documents first.",
                    "sources": [],
                    "streaming": False
                }
            
            # Decompose question for complex queries
            sub_questions = self._decompose_question(question)
            logger.info(f"Processing {len(sub_questions)} sub-questions")
            
            all_sources = []
            used_texts = set()  # Track unique content to avoid duplicates
            
            # Process each sub-question using direct Pinecone search
            for i, sub_q in enumerate(sub_questions):
                logger.debug(f"Processing sub-question {i+1}: {sub_q}")
                
                # Convert sub-question to embedding
                question_vector = self.embedding_model.embed_query(sub_q)
                
                # Search for relevant documents using direct Pinecone query
                search_results = index.query(
                    vector=question_vector,
                    top_k=3,  # Fewer results per sub-question to avoid too much context
                    namespace=namespace,
                    include_metadata=True,
                    include_values=False
                )
                
                # Extract unique sources (avoid duplicates by content)
                for match in search_results.matches:
                    doc_text = match.metadata.get('text', '') if match.metadata else ''
                    if not doc_text:
                        continue
                        
                    # Check if this content is already included
                    if doc_text in used_texts:
                        continue
                        
                    used_texts.add(doc_text)
                    
                    # Get clean filename from metadata
                    file_name = match.metadata.get('file_name') if match.metadata else None
                    total_pages = match.metadata.get('total_pages', 1) if match.metadata else 1
                    
                    if not file_name:
                        file_name = f'Document {len(all_sources) + 1}'
                    
                    # Ensure we have a reasonable source limit
                    if len(all_sources) >= 5:  # Limit to 5 sources max
                        break
                        
                    all_sources.append({
                        "page_content": doc_text,
                        "metadata": {
                            "file_name": file_name,
                            "total_pages": total_pages,
                            "sub_question": sub_q if len(sub_questions) > 1 else None
                        },
                        "score": match.score
                    })
                
                # Break if we have enough sources
                if len(all_sources) >= 5:
                    break
            
            if not all_sources:
                return {
                    "answer": "No relevant document content found for your question.",
                    "sources": [],
                    "streaming": False
                }
            
            logger.info(f"Found {len(all_sources)} unique sources for the question")
            
            # Create context for the prompt with source references
            context_parts = []
            for i, source in enumerate(all_sources):
                context_parts.append(f"[Source {i+1}] {source['page_content']}")
            
            context_text = "\n\n".join(context_parts)
            
            # Create comprehensive prompt for complex question handling
            if len(sub_questions) > 1:
                sub_q_text = "\n".join([f"- {sq}" for sq in sub_questions])
                prompt = f"""Based on the following document excerpts with source references, please answer the complex question by addressing its components. Use the source references [Source X] in your answer to cite where information comes from.

CONTEXT DOCUMENTS WITH SOURCE REFERENCES:
{context_text}

MAIN QUESTION: {question}

SUB-COMPONENTS TO ADDRESS:
{sub_q_text}

INSTRUCTIONS:
- Use the source references [Source 1], [Source 2], etc. to cite information in your answer
- Address each component of the question comprehensively
- Synthesize information from multiple sources when relevant
- If any component cannot be answered from the context, clearly state what information is missing
- Provide specific details and examples when available
- Structure your response to address the full complexity of the question

COMPREHENSIVE ANSWER WITH SOURCE REFERENCES:"""
            else:
                prompt = f"""Based on the following document excerpts with source references, please answer the question accurately and comprehensively. Use the source references [Source X] in your answer to cite where information comes from.

CONTEXT DOCUMENTS WITH SOURCE REFERENCES:
{context_text}

QUESTION: {question}

INSTRUCTIONS:
- Use the source references [Source 1], [Source 2], etc. to cite information in your answer
- If the answer is not fully available in the context, state what information is missing
- Provide specific details and examples when available
- Keep the response focused and relevant to the question
- If multiple documents contain relevant information, synthesize them coherently

ANSWER WITH SOURCE REFERENCES:"""

            # Get answer from LLM using direct generation
            response = self._safe_generate(prompt)
            answer = response.content.strip()
            
            logger.info(f"Successfully answered question for namespace: {namespace}")
            
            return {
                "answer": answer,
                "sources": all_sources,
                "streaming": False
            }
            
        except Exception as e:
            logger.error(f"Error answering question: {e}")
            return {
                "answer": f"Error processing question: {str(e)}",
                "sources": [],
                "streaming": False
            }
