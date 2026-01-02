"""
Message Log Repository
======================
Manages persistent message storage in Firebase Firestore.

This repository handles:
- Logging messages to Firestore for permanent storage
- Managing session/ticket metadata
- Retrieving message history
- Generating unique ticket IDs

Collections:
- messages: Individual message logs
- sessions: Session/ticket metadata
- counters: Auto-incrementing ticket ID sequences
"""

from utils.firebase_client import firebase_client_manager
from datetime import datetime
from typing import List, Optional, Dict, Any
from google.cloud import firestore
from google.cloud.firestore_v1 import SERVER_TIMESTAMP


class MessageLogRepository:
    """
    Repository for managing message logs and sessions in Firestore.
    Provides persistence layer for chat history and analytics.
    """
    
    def __init__(self):
        """Initialize repository with Firestore database connection"""
        self.db = firebase_client_manager.db
        self._collection = None
        self._session_collection = None
        self._counter_collection = None

    @property
    def collection(self):
        """
        Lazily load the messages collection.
        This ensures we're within a request context when accessing Flask config.
        
        Returns:
            CollectionReference: Firestore messages collection
        """
        if self._collection is None:
            from flask import current_app
            collection_name = current_app.config['FIRESTORE_COLLECTION_MESSAGES']
            self._collection = self.db.collection(collection_name)
        return self._collection

    @property
    def session_collection(self):
        """
        Lazily load the sessions collection.
        
        Returns:
            CollectionReference: Firestore sessions collection
        """
        if self._session_collection is None:
            from flask import current_app
            collection_name = current_app.config['FIRESTORE_COLLECTION_SESSIONS']
            self._session_collection = self.db.collection(collection_name)
        return self._session_collection

    @property
    def counter_collection(self):
        """
        Lazily load the counters collection.
        
        Returns:
            CollectionReference: Firestore counters collection
        """
        if self._counter_collection is None:
            from flask import current_app
            collection_name = current_app.config['FIRESTORE_COLLECTION_COUNTERS']
            self._counter_collection = self.db.collection(collection_name)
        return self._counter_collection

    def _generate_ticket_id(self) -> str:
        """
        Generate a unique ticket ID using Firestore counters collection.
        Format: TKT{YY}{MM}{SEQ} (e.g., TKT250103 for January 2025, sequence 3)
        
        Returns:
            str: Unique ticket ID
        """
        now = datetime.utcnow()
        year = now.year % 100  # Last two digits: 2025 -> 25
        month = now.month

        # Counter key pattern: ticketId:YY-MM
        counter_id = f"ticketId:{year:02d}-{month:02d}"

        # Atomically increment counter using Firestore transaction
        @firestore.transactional
        def increment_counter(transaction, counter_ref):
            snapshot = counter_ref.get(transaction=transaction)
            
            if snapshot.exists:
                current_value = snapshot.get('sequence_value')
                new_value = current_value + 1
            else:
                new_value = 1
            
            transaction.set(counter_ref, {
                'sequence_value': new_value,
                'updated_at': SERVER_TIMESTAMP
            }, merge=True)
            
            return new_value

        counter_ref = self.counter_collection.document(counter_id)
        transaction = self.db.transaction()
        seq_num = increment_counter(transaction, counter_ref)

        # Format: TKT-25-01-03 -> TKT250103
        ticket_id = f"TKT{year:02d}{month:02d}{seq_num:02d}"
        return ticket_id

    def log_message(self, session_id: str, message: str, role: str) -> Optional[str]:
        """
        Log a single message to Firestore for permanent storage.
        
        Args:
            session_id (str): Session/client identifier
            message (str): Message content
            role (str): Message role ('user', 'bot', 'system', etc.)
            
        Returns:
            str: Inserted document ID, or None if failed
        """
        try:
            message_doc = {
                'session_id': session_id,
                'role': role,
                'message': message,
                'timestamp': SERVER_TIMESTAMP
            }

            # Add document to Firestore
            doc_ref = self.collection.add(message_doc)
            
            # doc_ref is a tuple (timestamp, DocumentReference)
            if isinstance(doc_ref, tuple):
                return doc_ref[1].id
            else:
                return doc_ref.id
            
        except Exception as e:
            print(f"Error logging message: {e}")
            return None

    def get_all_messages_for_session(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all logged messages for a specific session from Firestore.
        
        Args:
            session_id (str): Session/client identifier
            
        Returns:
            List[Dict]: List of messages sorted by timestamp (ascending)
        """
        try:
            # Query Firestore for messages with matching session_id
            query = (
                self.collection
                .where('session_id', '==', session_id)
                .order_by('timestamp')
            )
            
            docs = query.stream()
            
            results = []
            for doc in docs:
                data = doc.to_dict()
                ts = data.get('timestamp')
                
                results.append({
                    '_id': doc.id,
                    'session_id': data.get('session_id'),
                    'role': data.get('role'),
                    'message': data.get('message'),
                    'timestamp': ts.isoformat() + 'Z' if ts and hasattr(ts, 'isoformat') else None
                })
            
            return results
            
        except Exception as e:
            print(f"Error retrieving messages: {e}")
            return []

    def get_recent_messages(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get the most recent messages for a session.
        
        Args:
            session_id (str): Session/client identifier
            limit (int): Maximum number of messages to retrieve
            
        Returns:
            List[Dict]: List of recent messages (chronological order)
        """
        try:
            # Query Firestore for recent messages
            query = (
                self.collection
                .where('session_id', '==', session_id)
                .order_by('timestamp', direction='DESCENDING')
                .limit(limit)
            )
            
            docs = list(query.stream())
            
            # Reverse to get chronological order
            docs.reverse()
            
            messages = []
            for doc in docs:
                data = doc.to_dict()
                ts = data.get('timestamp')
                
                messages.append({
                    '_id': doc.id,
                    'session_id': data.get('session_id'),
                    'role': data.get('role'),
                    'message': data.get('message'),
                    'timestamp': ts.isoformat() + 'Z' if ts and hasattr(ts, 'isoformat') else None
                })
            
            return messages
            
        except Exception as e:
            print(f"Error retrieving recent messages: {e}")
            return []

    def create_session(self, session_id: str, metadata: Dict[str, Any] = None) -> Optional[str]:
        """
        Create a new session entry in Firestore.
        
        Args:
            session_id (str): Unique session identifier
            metadata (dict): Optional session metadata
            
        Returns:
            str: Inserted document ID, or None if failed
        """
        try:
            session_doc = {
                'session_id': session_id,
                'created_at': SERVER_TIMESTAMP,
                'updated_at': SERVER_TIMESTAMP,
                'status': 'active',
                **(metadata or {})
            }

            # Use session_id as document ID for easy lookup
            doc_ref = self.session_collection.document(session_id)
            doc_ref.set(session_doc)
            
            return doc_ref.id
            
        except Exception as e:
            print(f"Error creating session: {e}")
            return None

    def update_session(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update session metadata.
        
        Args:
            session_id (str): Unique session identifier
            updates (dict): Fields to update
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            updates['updated_at'] = SERVER_TIMESTAMP
            
            doc_ref = self.session_collection.document(session_id)
            doc_ref.update(updates)
            
            return True
            
        except Exception as e:
            print(f"Error updating session: {e}")
            return False

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session metadata.
        
        Args:
            session_id (str): Unique session identifier
            
        Returns:
            dict: Session data, or None if not found
        """
        try:
            doc_ref = self.session_collection.document(session_id)
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                data['_id'] = doc.id
                return data
            else:
                return None
                
        except Exception as e:
            print(f"Error getting session: {e}")
            return None

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and all its messages.
        
        Args:
            session_id (str): Unique session identifier
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Delete session document
            session_ref = self.session_collection.document(session_id)
            session_ref.delete()
            
            # Delete all messages for this session
            query = self.collection.where('session_id', '==', session_id)
            docs = query.stream()
            
            for doc in docs:
                doc.reference.delete()
            
            print(f"Session {session_id} deleted successfully")
            return True
            
        except Exception as e:
            print(f"Error deleting session: {e}")
            return False
