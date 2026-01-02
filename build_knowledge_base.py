"""
Knowledge Base Builder Script
==============================
This script builds a FAISS index and embeddings from a text file containing your knowledge base.

Usage:
    python build_knowledge_base.py [input_file]

Input file format:
    - Plain text file with documents/Q&A pairs
    - Separate documents with blank lines
    - Or one document per line

Example input file (knowledge.txt):
    What is this bot?
    This is an AI assistant that can help answer questions.

    How does it work?
    It uses RAG to find relevant information and provide accurate answers.

Output:
    - utils/rag/knowledge_base.index (FAISS index)
    - utils/rag/documents.pkl (document texts)
    - utils/rag/embeddings.pkl (cached embeddings)
"""

import sys
import os
import pickle
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


def build_knowledge_base(input_file='knowledge.txt', output_dir='utils/rag'):
    """
    Build FAISS index and embeddings from a text file.
    
    Args:
        input_file: Path to input text file
        output_dir: Directory to save output files
    """
    print(f"📚 Building knowledge base from: {input_file}")
    print("=" * 60)
    
    # Check if input file exists
    if not os.path.exists(input_file):
        print(f"❌ Error: Input file '{input_file}' not found!")
        print(f"\nCreate a file named '{input_file}' with your knowledge base content.")
        print("Example content:")
        print("-" * 60)
        print("What is this bot?")
        print("This is an AI assistant.")
        print()
        print("How does it work?")
        print("It uses RAG for accurate answers.")
        print("-" * 60)
        return False
    
    # Read documents
    print(f"📖 Reading documents from {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split by double newlines (paragraphs) or single newlines
    if '\n\n' in content:
        documents = [doc.strip() for doc in content.split('\n\n') if doc.strip()]
        print(f"   Split by paragraphs (double newlines)")
    else:
        documents = [line.strip() for line in content.split('\n') if line.strip()]
        print(f"   Split by lines")
    
    if not documents:
        print("❌ Error: No documents found in input file!")
        return False
    
    print(f"✅ Found {len(documents)} documents")
    
    # Show sample
    print(f"\n📄 Sample documents:")
    for i, doc in enumerate(documents[:3], 1):
        preview = doc[:100] + "..." if len(doc) > 100 else doc
        print(f"   {i}. {preview}")
    if len(documents) > 3:
        print(f"   ... and {len(documents) - 3} more")
    
    # Initialize embedding model
    print(f"\n🤖 Loading embedding model (all-mpnet-base-v2)...")
    print("   (This may take a moment on first run)")
    model = SentenceTransformer('all-mpnet-base-v2')
    print("✅ Model loaded")
    
    # Generate embeddings
    print(f"\n🔢 Generating embeddings for {len(documents)} documents...")
    embeddings = model.encode(documents, show_progress_bar=True, convert_to_numpy=True)
    embeddings = embeddings.astype('float32')
    print(f"✅ Generated embeddings with shape: {embeddings.shape}")
    
    # Create FAISS index
    print(f"\n🔍 Creating FAISS index...")
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)
    print(f"✅ Created FAISS index with {index.ntotal} vectors of dimension {dimension}")
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Save files
    print(f"\n💾 Saving knowledge base to {output_dir}/...")
    
    index_file = os.path.join(output_dir, 'knowledge_base.index')
    faiss.write_index(index, index_file)
    print(f"   ✅ Saved FAISS index: {index_file}")
    
    docs_file = os.path.join(output_dir, 'documents.pkl')
    with open(docs_file, 'wb') as f:
        pickle.dump(documents, f)
    print(f"   ✅ Saved documents: {docs_file}")
    
    embeddings_file = os.path.join(output_dir, 'embeddings.pkl')
    with open(embeddings_file, 'wb') as f:
        pickle.dump(embeddings, f)
    print(f"   ✅ Saved embeddings: {embeddings_file}")
    
    # Summary
    print("\n" + "=" * 60)
    print("✅ Knowledge base created successfully!")
    print(f"   📊 Statistics:")
    print(f"      - Documents: {len(documents)}")
    print(f"      - Embedding dimension: {dimension}")
    print(f"      - Index size: {index.ntotal} vectors")
    print(f"      - Output directory: {output_dir}/")
    print("\n🚀 You can now start the bot with: python app.py")
    print("=" * 60)
    
    return True


def test_knowledge_base(output_dir='utils/rag'):
    """
    Test that the knowledge base can be loaded.
    
    Args:
        output_dir: Directory containing knowledge base files
    """
    print("\n🧪 Testing knowledge base...")
    
    try:
        # Load files
        index_file = os.path.join(output_dir, 'knowledge_base.index')
        docs_file = os.path.join(output_dir, 'documents.pkl')
        
        index = faiss.read_index(index_file)
        with open(docs_file, 'rb') as f:
            documents = pickle.load(f)
        
        print(f"✅ Successfully loaded:")
        print(f"   - FAISS index: {index.ntotal} vectors")
        print(f"   - Documents: {len(documents)} items")
        
        # Test search
        model = SentenceTransformer('all-mpnet-base-v2')
        test_query = "What is this?"
        query_embedding = model.encode([test_query]).astype('float32')
        
        distances, indices = index.search(query_embedding, min(3, len(documents)))
        
        print(f"\n🔍 Test search for: '{test_query}'")
        print(f"   Top results:")
        for i, (dist, idx) in enumerate(zip(distances[0], indices[0]), 1):
            if idx < len(documents):
                preview = documents[idx][:80] + "..." if len(documents[idx]) > 80 else documents[idx]
                print(f"   {i}. (distance: {dist:.2f}) {preview}")
        
        print("\n✅ Knowledge base is working correctly!")
        return True
        
    except Exception as e:
        print(f"❌ Error testing knowledge base: {e}")
        return False


# ===== Semantic Search Functions =====

def load_knowledge_base(
    embeddings_file: str = 'utils/rag/embeddings.pkl',
    documents_file: str = 'utils/rag/documents.pkl',
    model_name: str = 'all-mpnet-base-v2'
):
    """
    Load the knowledge base embeddings, documents, and model.
    
    Args:
        embeddings_file: Path to embeddings pickle file
        documents_file: Path to documents pickle file
        model_name: Name of the sentence transformer model
        
    Returns:
        Tuple of (embeddings, documents, model)
        
    Raises:
        FileNotFoundError: If required files don't exist
    """
    if not os.path.exists(embeddings_file):
        raise FileNotFoundError(f"Embeddings file not found: {embeddings_file}. Please run build_knowledge_base.py first.")
    
    if not os.path.exists(documents_file):
        raise FileNotFoundError(f"Documents file not found: {documents_file}. Please run build_knowledge_base.py first.")
    
    # Load embeddings
    with open(embeddings_file, 'rb') as f:
        embeddings = np.array(pickle.load(f))
    
    # Load documents
    with open(documents_file, 'rb') as f:
        documents = pickle.load(f)
    
    # Load model
    model = SentenceTransformer(model_name)
    
    return embeddings, documents, model


def semantic_search_best_match(query: str, embeddings=None, documents=None, model=None):
    """
    Get the single best matching document using cosine similarity.
    
    Args:
        query: Search query string
        embeddings: Pre-computed embeddings array (optional, will load if None)
        documents: List of document texts (optional, will load if None)
        model: SentenceTransformer model (optional, will load if None)
        
    Returns:
        Dictionary with keys:
        - text: Document text/content
        - similarity_score: Cosine similarity score (0.0 to 1.0)
        - index: Original document index
        - filename: Filename if available
    """
    # Load if not provided
    if embeddings is None or documents is None or model is None:
        embeddings, documents, model = load_knowledge_base()
    
    # Encode query
    query_embedding = model.encode(query, convert_to_numpy=True)
    
    # Normalize embeddings for cosine similarity
    embeddings_norm = embeddings / (np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-10)
    query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-10)
    
    # Compute cosine similarity
    similarities = np.dot(embeddings_norm, query_norm)
    
    # Get best match
    top_idx = int(np.argmax(similarities))
    similarity_score = float(similarities[top_idx])
    
    # Get document
    doc = documents[top_idx]
    
    result = {
        'similarity_score': round(similarity_score, 4),
        'index': int(top_idx)
    }
    
    # Handle both string and dict document formats
    if isinstance(doc, dict):
        result['text'] = doc.get('content', str(doc))
        result['filename'] = doc.get('filename')
    else:
        result['text'] = str(doc)
        result['filename'] = None
    
    return result


if __name__ == "__main__":
    # Get input file from command line or use default
    input_file = sys.argv[1] if len(sys.argv) > 1 else 'knowledge.txt'
    
    # Build knowledge base
    success = build_knowledge_base(input_file)
    
    # Test if successful
    if success:
        test_knowledge_base()
    else:
        print("\n❌ Failed to build knowledge base")
        sys.exit(1)

