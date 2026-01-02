"""
RAG (Retrieval-Augmented Generation) Component Loader
======================================================
Loads pre-built RAG components including:
- FAISS vector index for similarity search
- Sentence transformer embedding model
- Knowledge base documents

This module expects the following files to exist in the utils/rag/ directory:
- knowledge_base.index: FAISS index file
- documents.pkl: Pickled list of document texts
- embeddings.pkl: (optional) Cached embeddings

Usage:
    from utils.rag_loader import load_rag_components
    
    embedding_model, faiss_index, knowledge_base_docs, K = load_rag_components()
    
    if embedding_model and faiss_index:
        # Use RAG components
        query_embedding = embedding_model.encode(query)
        distances, indices = faiss_index.search(query_embedding, K)
"""

import os
import pickle
import faiss
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

# Define file paths for RAG components
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAG_DIR = os.path.join(BASE_DIR, "rag")
FAISS_INDEX_FILE = os.path.join(RAG_DIR, "knowledge_base.index")
DOCUMENTS_PKL_FILE = os.path.join(RAG_DIR, "documents.pkl")
EMBEDDINGS_PKL_FILE = os.path.join(RAG_DIR, "embeddings.pkl")

load_dotenv()


def load_rag_components():
    """
    Loads the pre-trained embedding model, FAISS index, and knowledge base documents.
    
    Returns:
        tuple: (embedding_model, faiss_index, knowledge_base_docs, K)
               - embedding_model: SentenceTransformer model for encoding queries
               - faiss_index: FAISS index for similarity search
               - knowledge_base_docs: List of document texts
               - K: Number of documents to retrieve (from config)
               
               If loading fails, returns (None, None, [], None)
    
    Environment Variables:
        SENTENCE_TRANSFORMER_MODEL_PATH: Path to pre-downloaded model (optional)
        SENTENCE_TRANSFORMERS_HOME: Cache directory for models (optional)
        RAG_TOP_K: Number of documents to retrieve (default: 4)
    """
    embedding_model = None
    faiss_index = None
    knowledge_base_docs = []
    K = None

    print("📚 Attempting to load knowledge base components...")
    
    try:
        # ===== 1. Load Sentence Transformer Embedding Model =====
        preferred_model_path = os.environ.get('SENTENCE_TRANSFORMER_MODEL_PATH', '/app/models/all-mpnet-base-v2')
        cache_dir = os.environ.get('SENTENCE_TRANSFORMERS_HOME', '/app/models')
        
        print(f"  Preferred model path: '{preferred_model_path}'")
        print(f"  Cache directory: '{cache_dir}'")

        # Try loading from preferred path first
        if preferred_model_path and os.path.exists(preferred_model_path):
            embedding_model = SentenceTransformer(preferred_model_path)
            print(f"  ✅ Embedding model loaded from '{preferred_model_path}'")
        else:
            # Fallback to model name; will download to cache if needed
            embedding_model = SentenceTransformer('all-mpnet-base-v2', cache_folder=cache_dir)
            print(f"  ✅ Embedding model 'all-mpnet-base-v2' loaded (cache: '{cache_dir}')")

        # ===== 2. Load FAISS Index =====
        if not os.path.exists(FAISS_INDEX_FILE):
            raise FileNotFoundError(f"FAISS index not found at: {FAISS_INDEX_FILE}")
        
        faiss_index = faiss.read_index(FAISS_INDEX_FILE)
        print(f"  ✅ FAISS index loaded from '{FAISS_INDEX_FILE}'")

        # ===== 3. Load Knowledge Base Documents =====
        if not os.path.exists(DOCUMENTS_PKL_FILE):
            raise FileNotFoundError(f"Documents file not found at: {DOCUMENTS_PKL_FILE}")
        
        with open(DOCUMENTS_PKL_FILE, "rb") as f:
            knowledge_base_docs = pickle.load(f)
        print(f"  ✅ Knowledge base documents loaded from '{DOCUMENTS_PKL_FILE}' ({len(knowledge_base_docs)} documents)")

        # ===== 4. Set retrieval parameter K =====
        K = int(os.environ.get('RAG_TOP_K', '4'))
        print(f"  ✅ RAG retrieval top K set to: {K}")

        print("✅ Knowledge base components loaded successfully!")
        return embedding_model, faiss_index, knowledge_base_docs, K

    except FileNotFoundError as e:
        print(
            f"❌ ERROR: Knowledge base files not found.\n"
            f"   {e}\n"
            f"   Please ensure '{FAISS_INDEX_FILE}' and '{DOCUMENTS_PKL_FILE}' exist.\n"
            f"   You may need to run knowledge base generation scripts first."
        )
        return None, None, [], None
        
    except Exception as e:
        print(f"❌ Unexpected error loading knowledge base components: {e}")
        return None, None, [], None

