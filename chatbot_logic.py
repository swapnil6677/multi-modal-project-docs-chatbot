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
    
    def extract_text_from_pdf(self, pdf_file) -> str:
        """Extract text from PDF file"""
        logger.info(f"Extracting text from PDF: {pdf_file.filename}")
        
        try:
            pdf_file.seek(0)  # Reset file pointer
            reader = PdfReader(pdf_file)
            text = ""
            
            for page_num, page in enumerate(reader.pages):
                content = page.extract_text() or ""
                text += content
                logger.debug(f"Extracted text from page {page_num + 1}")
            
            logger.info(f"Total text length: {len(text)} characters")
            return text
            
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
    
    def store_in_pinecone(self, chunks: List[str], namespace: str):
        """Store text chunks in Pinecone vector database"""
        logger.info(f"Storing {len(chunks)} chunks in Pinecone namespace: {namespace}")
        
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
            
            # Convert chunks to documents and store
            documents = [Document(page_content=chunk) for chunk in chunks]
            vectorstore.add_documents(documents)
            
            logger.info(f"Successfully stored {len(documents)} documents in Pinecone")
            
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
    
    def answer_question(self, question: str, namespace: str) -> str:
        """Answer a question using RAG on project documents"""
        logger.info(f"Answering question: {question} for namespace: {namespace}")
        
        try:
            if not all([self.llm, self.embedding_model, self.pinecone_client]):
                raise ValueError("Required models not initialized")
            
            if not namespace:
                raise ValueError("No namespace provided")
            
            # Setup Pinecone vectorstore
            index = self.pinecone_client.Index(self.config.PINECONE_INDEX_NAME)
            vectorstore = PineconeVectorStore(
                index=index,
                embedding=self.embedding_model,
                namespace=namespace
            )
            retriever = vectorstore.as_retriever(search_kwargs={"k": 10})
            
            # Verify documents exist
            test_docs = retriever.invoke("test")
            logger.info(f"Retrieved {len(test_docs)} test documents from namespace: {namespace}")
            
            if not test_docs:
                return "No documents found in this project. Please upload some documents first."
            
            # Decompose question
            sub_questions = self._decompose_question(question)
            
            # Answer sub-questions
            all_answers = []
            qa_chain = self._get_qa_chain(retriever)
            
            for sub_q in sub_questions:
                logger.debug(f"Processing sub-question: {sub_q}")
                
                try:
                    result = qa_chain.invoke({"query": sub_q})
                    answer = result["result"]
                    all_answers.append(f"**{sub_q}**: {answer}")
                    logger.debug(f"Answer: {answer}")
                    
                except Exception as e:
                    logger.error(f"Error answering sub-question: {e}")
                    all_answers.append(f"**{sub_q}**: Unable to answer this question.")
            
            # Combine answers if multiple sub-questions
            if len(all_answers) > 1:
                summarizer = load_summarize_chain(self.llm, chain_type="stuff")
                documents = [Document(page_content=text) for text in all_answers]
                final_answer = summarizer.invoke({"input_documents": documents})["output_text"]
            else:
                final_answer = all_answers[0].split("**: ", 1)[1] if all_answers else "No answer generated."
            
            logger.info(f"Successfully answered question for namespace: {namespace}")
            return final_answer
            
        except Exception as e:
            logger.error(f"Error answering question: {e}")
            raise
