"""
Embedding utilities for text processing and vector operations
"""

import logging
import time
from typing import List
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from google.api_core.exceptions import ResourceExhausted
from config import Config

logger = logging.getLogger(__name__)

class EmbeddingProcessor:
    """Handles text chunking and embedding operations"""
    
    def __init__(self):
        self.config = Config()
        self.embedding_model = None
        self._initialize_embedding_model()
    
    def _initialize_embedding_model(self):
        """Initialize the embedding model"""
        try:
            if not self.config.GOOGLE_API_KEY:
                logger.error("GOOGLE_API_KEY not set in environment variables")
                raise ValueError("Google API key is required for embeddings")
            
            self.embedding_model = GoogleGenerativeAIEmbeddings(
                model=self.config.EMBEDDING_MODEL,
                google_api_key=self.config.GOOGLE_API_KEY
            )
            logger.info("Embedding model initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing embedding model: {e}")
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
    
    def create_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Create embeddings for a list of texts with retry logic"""
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Creating embeddings for {len(texts)} texts (attempt {attempt + 1})")
                embeddings = self.embedding_model.embed_documents(texts)
                logger.info(f"Successfully created {len(embeddings)} embeddings")
                return embeddings
                
            except ResourceExhausted as e:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    logger.warning(f"API quota exhausted. Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                else:
                    logger.error("Max retries exceeded for embedding creation")
                    raise e
            except Exception as e:
                logger.error(f"Error creating embeddings: {e}")
                raise
        
        return []
    
    def create_single_embedding(self, text: str) -> List[float]:
        """Create embedding for a single text"""
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"Creating embedding for text (attempt {attempt + 1})")
                embedding = self.embedding_model.embed_query(text)
                logger.debug("Successfully created single embedding")
                return embedding
                
            except ResourceExhausted as e:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    logger.warning(f"API quota exhausted. Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                else:
                    logger.error("Max retries exceeded for single embedding creation")
                    raise e
            except Exception as e:
                logger.error(f"Error creating single embedding: {e}")
                raise
        
        return []
