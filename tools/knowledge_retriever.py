"""
Knowledge Retriever Tool
=========================
RAG (Retrieval-Augmented Generation) tool for retrieving information from a knowledge base.

This tool uses:
- FAISS for efficient similarity search
- Sentence Transformers for encoding queries
- Pre-built knowledge base index

The tool is decorated with @tool to make it available to the LangChain agent.
The docstring is critical - it tells the LLM when and how to use this tool.
"""

from langchain_core.tools import tool
from utils.rag_loader import load_rag_components
import numpy as np

# Load RAG components on module import
# These are loaded once and reused across requests
embedding_model, faiss_index, knowledge_base_docs, K = load_rag_components()


@tool
def knowledge_retriever(query: str) -> str:
    """
    Retrieve information from the knowledge base using semantic search.
    
    USE THIS TOOL FOR:
    - Questions about the platform, features, or services
    - Questions about how things work or what is available
    - General "what is", "how to", "can I", "where do I" questions
    - Any factual question where you need specific information
    
    DO NOT USE THIS TOOL FOR:
    - Personal greetings or casual conversation
    - Questions that require external API calls or real-time data
    - Questions about things not related to the knowledge base
    
    IMPORTANT: Always use this tool when users ask factual questions.
    Do not rely on your training data - the knowledge base has up-to-date information.
    
    Args:
        query: The user's question or search query
        
    Returns:
        Relevant information from the knowledge base, or an error message if retrieval fails
    """
    try:
        # Check if RAG components are loaded
        if not embedding_model or not faiss_index or not knowledge_base_docs:
            return "Knowledge base is not available. Please ensure RAG components are properly initialized."
        
        # Encode the query into an embedding vector
        query_embedding = embedding_model.encode(query)
        query_embedding = np.array([query_embedding]).astype('float32')
        
        # Search FAISS index for top K similar documents
        distances, indices = faiss_index.search(query_embedding, K)
        
        # Retrieve the actual document texts
        relevant_documents = [
            knowledge_base_docs[i] for i in indices[0] if i != -1
        ]
        
        if relevant_documents:
            # Format the context with clear boundaries for LLM parsing
            rag_context = (
                "--- START KNOWLEDGE BASE CONTEXT ---\n" +
                "\n\n".join(relevant_documents) +
                "\n--- END KNOWLEDGE BASE CONTEXT ---"
            )
        else:
            rag_context = "No relevant information found in the knowledge base for this query."
        
        print(f"\n📚 Knowledge Retriever Tool Output:\n{rag_context}\n")
        return rag_context
        
    except Exception as e:
        error_msg = f"Error retrieving from knowledge base: {str(e)}"
        print(f"❌ {error_msg}")
        return error_msg

