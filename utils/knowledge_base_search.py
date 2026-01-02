"""
Knowledge Base Semantic Search
===============================
Semantic search functions for querying the knowledge base.
Uses FAISS index and sentence transformers for similarity search.
"""

import os
import pickle
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any, Optional, Tuple


class KnowledgeBaseSearch:
    """
    Semantic search class for knowledge base queries.
    Loads embeddings and documents for fast similarity search.
    """
    
    def __init__(
        self,
        embeddings_file: str = 'utils/rag/embeddings.pkl',
        documents_file: str = 'utils/rag/documents.pkl',
        index_file: str = 'utils/rag/knowledge_base.index',
        model_name: str = 'all-mpnet-base-v2'
    ):
        """
        Initialize knowledge base search.
        
        Args:
            embeddings_file: Path to embeddings pickle file
            documents_file: Path to documents pickle file
            index_file: Path to FAISS index file
            model_name: Sentence transformer model name
        """
        self.embeddings_file = embeddings_file
        self.documents_file = documents_file
        self.index_file = index_file
        self.model_name = model_name
        
        self._embeddings = None
        self._documents = None
        self._index = None
        self._model = None
        self._loaded = False
    
    def load(self) -> bool:
        """
        Load knowledge base files.
        
        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            # Check if files exist
            if not os.path.exists(self.embeddings_file):
                print(f"⚠️ Embeddings file not found: {self.embeddings_file}")
                return False
            
            if not os.path.exists(self.documents_file):
                print(f"⚠️ Documents file not found: {self.documents_file}")
                return False
            
            # Load embeddings
            with open(self.embeddings_file, 'rb') as f:
                self._embeddings = np.array(pickle.load(f))
            
            # Load documents
            with open(self.documents_file, 'rb') as f:
                self._documents = pickle.load(f)
            
            # Load FAISS index if available
            if os.path.exists(self.index_file):
                try:
                    self._index = faiss.read_index(self.index_file)
                except Exception as e:
                    print(f"⚠️ Could not load FAISS index: {e}, using embeddings directly")
            
            # Load model
            self._model = SentenceTransformer(self.model_name)
            
            self._loaded = True
            print(f"✅ Knowledge base loaded: {len(self._documents)} documents")
            return True
            
        except Exception as e:
            print(f"❌ Error loading knowledge base: {e}")
            return False
    
    def search(
        self,
        query: str,
        top_k: int = 1,
        similarity_threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search on the knowledge base.
        
        Args:
            query: Search query string
            top_k: Number of results to return
            similarity_threshold: Minimum similarity score (0.0 to 1.0)
        
        Returns:
            List of dictionaries with search results:
            - text: Document text/content
            - similarity_score: Cosine similarity score
            - index: Document index
            - filename: Filename if available (for dict format)
        """
        if not self._loaded:
            if not self.load():
                return []
        
        try:
            # Encode query
            query_embedding = self._model.encode(query, convert_to_numpy=True)
            query_embedding = query_embedding.astype('float32')
            
            # Use FAISS index if available, otherwise compute similarity directly
            if self._index is not None:
                # Search using FAISS
                distances, indices = self._index.search(
                    query_embedding.reshape(1, -1),
                    min(top_k, len(self._documents))
                )
                
                results = []
                for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
                    if idx < len(self._documents):
                        # Convert L2 distance to similarity (inverse relationship)
                        # Smaller distance = higher similarity
                        similarity = 1.0 / (1.0 + float(dist))
                        
                        if similarity >= similarity_threshold:
                            doc = self._documents[idx]
                            result = {
                                'similarity_score': round(similarity, 4),
                                'index': int(idx)
                            }
                            
                            # Handle both string and dict document formats
                            if isinstance(doc, dict):
                                result['text'] = doc.get('content', str(doc))
                                result['filename'] = doc.get('filename')
                            else:
                                result['text'] = str(doc)
                                result['filename'] = None
                            
                            results.append(result)
                
                return results[:top_k]
            else:
                # Fallback: compute cosine similarity directly
                return self._cosine_similarity_search(query_embedding, top_k, similarity_threshold)
                
        except Exception as e:
            print(f"❌ Error in semantic search: {e}")
            return []
    
    def _cosine_similarity_search(
        self,
        query_embedding: np.ndarray,
        top_k: int,
        similarity_threshold: float
    ) -> List[Dict[str, Any]]:
        """
        Perform cosine similarity search using embeddings directly.
        
        Args:
            query_embedding: Query embedding vector
            top_k: Number of results
            similarity_threshold: Minimum similarity score
        
        Returns:
            List of search results
        """
        # Normalize embeddings for cosine similarity
        embeddings_norm = self._embeddings / (
            np.linalg.norm(self._embeddings, axis=1, keepdims=True) + 1e-10
        )
        query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-10)
        
        # Compute cosine similarity
        similarities = np.dot(embeddings_norm, query_norm)
        
        # Get top K results
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            similarity = float(similarities[idx])
            if similarity >= similarity_threshold:
                doc = self._documents[idx]
                result = {
                    'text': doc.get('content', str(doc)) if isinstance(doc, dict) else str(doc),
                    'similarity_score': round(similarity, 4),
                    'index': int(idx),
                    'filename': doc.get('filename') if isinstance(doc, dict) else None
                }
                results.append(result)
        
        return results
    
    def search_best_match(
        self,
        query: str,
        similarity_threshold: float = 0.5
    ) -> Optional[Dict[str, Any]]:
        """
        Get the single best matching document.
        
        Args:
            query: Search query string
            similarity_threshold: Minimum similarity score
        
        Returns:
            Dictionary with best match or None
        """
        results = self.search(query, top_k=1, similarity_threshold=similarity_threshold)
        return results[0] if results else None
    
    def can_answer(self, query: str, threshold: float = 0.6) -> bool:
        """
        Check if knowledge base can answer the query.
        
        Args:
            query: Query string
            threshold: Minimum similarity threshold to consider as answerable
        
        Returns:
            True if knowledge base has relevant information
        """
        result = self.search_best_match(query, similarity_threshold=threshold)
        return result is not None


# Global instance (lazy loaded)
_kb_search_instance = None


def get_knowledge_base_search() -> KnowledgeBaseSearch:
    """
    Get or create the global knowledge base search instance.
    
    Returns:
        KnowledgeBaseSearch instance
    """
    global _kb_search_instance
    if _kb_search_instance is None:
        _kb_search_instance = KnowledgeBaseSearch()
    return _kb_search_instance


def semantic_search(
    query: str,
    top_k: int = 1,
    similarity_threshold: float = 0.5
) -> List[Dict[str, Any]]:
    """
    Convenience function for semantic search.
    
    Args:
        query: Search query
        top_k: Number of results
        similarity_threshold: Minimum similarity
    
    Returns:
        List of search results
    """
    kb_search = get_knowledge_base_search()
    return kb_search.search(query, top_k, similarity_threshold)


def semantic_search_best_match(
    query: str,
    similarity_threshold: float = 0.5
) -> Optional[Dict[str, Any]]:
    """
    Get best match from knowledge base.
    
    Args:
        query: Search query
        similarity_threshold: Minimum similarity
    
    Returns:
        Best match dictionary or None
    """
    kb_search = get_knowledge_base_search()
    return kb_search.search_best_match(query, similarity_threshold)

