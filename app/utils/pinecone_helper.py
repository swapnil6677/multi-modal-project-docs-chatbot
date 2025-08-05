"""
Pinecone vector database helper utilities
"""

import logging
import time
from typing import List, Dict, Any
from pinecone import Pinecone, ServerlessSpec
from langchain_pinecone import PineconeVectorStore
from langchain_core.documents import Document
from config import Config

logger = logging.getLogger(__name__)

class PineconeHelper:
    """Handles Pinecone vector database operations"""
    
    def __init__(self, embedding_model=None):
        self.config = Config()
        self.pinecone_client = None
        self.embedding_model = embedding_model
        self._initialize_pinecone()
    
    def _initialize_pinecone(self):
        """Initialize Pinecone client"""
        try:
            if not self.config.PINECONE_API_KEY:
                logger.error("PINECONE_API_KEY not set in environment variables")
                raise ValueError("Pinecone API key is required")
            
            self.pinecone_client = Pinecone(api_key=self.config.PINECONE_API_KEY)
            logger.info("Pinecone client initialized successfully")
            self._ensure_index_exists()
            
        except Exception as e:
            logger.error(f"Error initializing Pinecone: {e}")
            raise
    
    def _ensure_index_exists(self):
        """Ensure the Pinecone index exists, create if it doesn't"""
        try:
            existing_indexes = self.pinecone_client.list_indexes()
            index_names = [index.name for index in existing_indexes]
            
            if self.config.PINECONE_INDEX_NAME not in index_names:
                logger.info(f"Creating Pinecone index: {self.config.PINECONE_INDEX_NAME}")
                self.pinecone_client.create_index(
                    name=self.config.PINECONE_INDEX_NAME,
                    dimension=self.config.EMBEDDING_DIMENSION,
                    metric='cosine',
                    spec=ServerlessSpec(
                        cloud=self.config.PINECONE_CLOUD,
                        region=self.config.PINECONE_REGION
                    )
                )
                
                # Wait for index to be ready
                while not self.pinecone_client.describe_index(self.config.PINECONE_INDEX_NAME).status['ready']:
                    logger.info("Waiting for index to be ready...")
                    time.sleep(1)
                
                logger.info("Index created and ready")
            else:
                logger.info(f"Index {self.config.PINECONE_INDEX_NAME} already exists")
                
        except Exception as e:
            logger.error(f"Error ensuring index exists: {e}")
            raise
    
    def store_vectors(self, chunks: List[str], namespace: str, filename: str, page_count: int, page_mapping: List[Dict[str, Any]], chunk_pages: List[int]) -> None:
        """Store text chunks as vectors in Pinecone"""
        try:
            if not self.embedding_model:
                logger.error("Embedding model not initialized")
                raise ValueError("Embedding model is required")
            
            if not chunks:
                logger.warning(f"No chunks to store for file: {filename}")
                return
            
            if len(chunks) != len(chunk_pages):
                logger.error(f"Mismatch between chunks and chunk_pages lengths")
                raise ValueError("Each chunk must have a corresponding page number")

            logger.info(f"Creating embeddings for {len(chunks)} chunks")
            embeddings = self.embedding_model.embed_documents(chunks)
            
            # Get index
            index = self.pinecone_client.Index(self.config.PINECONE_INDEX_NAME)
            
            # Create metadata for each chunk
            vectors_to_upsert = []
            for i, (chunk, embedding, page_num) in enumerate(zip(chunks, embeddings, chunk_pages)):
                metadata = {
                    'text': chunk,
                    'filename': filename,
                    'page_count': page_count,
                    'page': page_num  # Store the actual page number for this chunk
                }
                vectors_to_upsert.append({
                    'id': f"{filename}_{i}",
                    'values': embedding,
                    'metadata': metadata
                })
            
            # Batch upsert vectors
            logger.info(f"Upserting {len(vectors_to_upsert)} vectors to namespace: {namespace}")
            index.upsert(vectors=vectors_to_upsert, namespace=namespace)
            logger.info("Vector storage complete")
            
        except Exception as e:
            logger.error(f"Error storing vectors: {e}")
            raise
    
    def get_vector_store(self, namespace: str):
        """Get existing vector store for a namespace"""
        try:
            if not self.embedding_model:
                raise ValueError("Embedding model not initialized")
            
            vector_store = PineconeVectorStore(
                index_name=self.config.PINECONE_INDEX_NAME,
                embedding=self.embedding_model,
                namespace=namespace
            )
            
            logger.info(f"Retrieved vector store for namespace: {namespace}")
            return vector_store
            
        except Exception as e:
            logger.error(f"Error getting vector store: {e}")
            raise
    
    def get_retriever(self, namespace: str = "default", search_kwargs: dict = None):
        """Get retriever for semantic search"""
        try:
            vector_store = self.get_vector_store(namespace)
            
            # Default search parameters
            default_search_kwargs = {"k": 5}
            if search_kwargs:
                default_search_kwargs.update(search_kwargs)
            
            retriever = vector_store.as_retriever(search_kwargs=default_search_kwargs)
            logger.info(f"Created retriever for namespace: {namespace}")
            return retriever
            
        except Exception as e:
            logger.error(f"Error creating retriever: {e}")
            raise
    
    def delete_namespace_vectors(self, namespace: str):
        """Delete all vectors in a specific namespace"""
        try:
            index = self.pinecone_client.Index(self.config.PINECONE_INDEX_NAME)
            index.delete(delete_all=True, namespace=namespace)
            logger.info(f"Deleted all vectors in namespace: {namespace}")
            
        except Exception as e:
            logger.error(f"Error deleting namespace vectors: {e}")
            raise
    
    def get_namespace_stats(self, namespace: str) -> Dict[str, Any]:
        """Get statistics for a namespace"""
        try:
            index = self.pinecone_client.Index(self.config.PINECONE_INDEX_NAME)
            stats = index.describe_index_stats()
            
            namespace_stats = stats.get('namespaces', {}).get(namespace, {})
            
            logger.info(f"Retrieved stats for namespace: {namespace}")
            return namespace_stats
            
        except Exception as e:
            logger.error(f"Error getting namespace stats: {e}")
            return {}
    
    def search_vectors(self, query_vector: List[float], namespace: str, top_k: int = 5) -> List[Dict]:
        """Search for similar vectors in a namespace"""
        try:
            index = self.pinecone_client.Index(self.config.PINECONE_INDEX_NAME)
            
            results = index.query(
                vector=query_vector,
                top_k=top_k,
                namespace=namespace,
                include_metadata=True
            )
            
            logger.info(f"Found {len(results['matches'])} matches in namespace: {namespace}")
            return results['matches']
            
        except Exception as e:
            logger.error(f"Error searching vectors: {e}")
            return []
    
    def manual_search(self, query_text: str, namespace: str, top_k: int = 5) -> List[Dict]:
        """Manual keyword-based search as fallback when embedding search fails"""
        try:
            # Get all vectors in the namespace first
            index = self.pinecone_client.Index(self.config.PINECONE_INDEX_NAME)
            
            # Query with a dummy vector to get all results
            dummy_vector = [0.0] * self.config.EMBEDDING_DIMENSION
            
            # Get more results to filter manually
            results = index.query(
                vector=dummy_vector,
                top_k=100,  # Get more results for manual filtering
                namespace=namespace,
                include_metadata=True
            )
            
            # Extract query keywords
            query_keywords = query_text.lower().split()
            
            # Score chunks based on keyword matches
            scored_chunks = []
            for match in results.get('matches', []):
                metadata = match.get('metadata', {})
                text = metadata.get('text', '').lower()
                
                # Calculate keyword match score
                score = 0
                for keyword in query_keywords:
                    if len(keyword) > 2:  # Only consider keywords longer than 2 chars
                        score += text.count(keyword)
                
                if score > 0:  # Only include chunks with keyword matches
                    scored_chunks.append({
                        'match': match,
                        'score': score
                    })
            
            # Sort by score and return top_k
            scored_chunks.sort(key=lambda x: x['score'], reverse=True)
            
            manual_results = [item['match'] for item in scored_chunks[:top_k]]
            
            logger.info(f"Manual search found {len(manual_results)} relevant chunks for query: {query_text}")
            return manual_results
            
        except Exception as e:
            logger.error(f"Error in manual search: {e}")
            return []
    
    def hybrid_search(self, query_text: str, namespace: str, top_k: int = 5) -> List[Dict]:
        """Combine embedding search with manual keyword search"""
        try:
            all_results = []
            
            # Try embedding search first
            if self.embedding_model:
                try:
                    query_embedding = self.embedding_model.embed_query(query_text)
                    embedding_results = self.search_vectors(query_embedding, namespace, top_k)
                    
                    # Check if embedding search returned good results
                    if embedding_results and any(match.get('score', 0) > 0.7 for match in embedding_results):
                        logger.info("Embedding search returned high-confidence results")
                        return embedding_results
                    else:
                        all_results.extend(embedding_results)
                        logger.info("Embedding search returned low-confidence results, trying manual search")
                except Exception as e:
                    logger.warning(f"Embedding search failed: {e}")
            
            # Try manual keyword search as fallback
            manual_results = self.manual_search(query_text, namespace, top_k)
            all_results.extend(manual_results)
            
            # Remove duplicates and return top results
            seen_ids = set()
            unique_results = []
            for result in all_results:
                result_id = result.get('id')
                if result_id and result_id not in seen_ids:
                    seen_ids.add(result_id)
                    unique_results.append(result)
            
            return unique_results[:top_k]
            
        except Exception as e:
            logger.error(f"Error in hybrid search: {e}")
            return []
