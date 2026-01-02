"""
Chat Session Repository
========================
Manages conversation history and session data in Redis.

This repository handles:
- Storing and retrieving conversation history
- Managing session summaries for long conversations
- Setting TTL (time-to-live) on sessions
- Session cleanup

Redis Key Structure:
- {REDIS_SESSION_PREFIX}{session_id} -> conversation history (JSON array)
- {REDIS_SESSION_PREFIX}{session_id}:summary -> conversation summary (string)
"""

import json
from datetime import datetime
from flask import current_app
from typing import List, Dict, Any
from utils.redis_client import redis_client_manager


class ChatSessionRepository:
    """
    Repository for managing chat sessions in Redis.
    Provides CRUD operations for conversation history and summaries.
    """
    
    def __init__(self):
        """Initialize repository with Redis client"""
        self._redis = redis_client_manager.client
    
    def _get_redis_key(self, session_id: str) -> str:
        """
        Construct a standardized Redis key for a chat session.
        
        Args:
            session_id (str): Unique session identifier
            
        Returns:
            str: Formatted Redis key
        """
        try:
            prefix = current_app.config['REDIS_SESSION_PREFIX']
            return f"{prefix}{session_id}"
        except Exception as e:
            print(f"Error getting Redis key: {e}")
            return f"chat_session:{session_id}"

    def _get_summary_key(self, session_id: str) -> str:
        """
        Construct a standardized Redis key for a chat session summary.
        
        Args:
            session_id (str): Unique session identifier
            
        Returns:
            str: Formatted Redis key for summary
        """
        try:
            prefix = current_app.config['REDIS_SESSION_PREFIX']
            return f"{prefix}{session_id}:summary"
        except Exception as e:
            print(f"Error getting summary key: {e}")
            return f"chat_session:{session_id}:summary"

    def get_conversation_history(self, session_id: str) -> List[Dict[str, str]]:
        """
        Retrieve the conversation history for a given session.
        
        Args:
            session_id (str): Unique session identifier
            
        Returns:
            List[Dict[str, str]]: List of messages with role, message, and timestamp
                                 Returns empty list if session not found
        """
        try:
            key = self._get_redis_key(session_id)
            history_json = self._redis.get(key)
            if history_json:
                return json.loads(history_json)
            return []
        except Exception as e:
            print(f"Error getting conversation history: {e}")
            return []

    def add_message(self, session_id: str, role: str, message: str):
        """
        Add a new message to the conversation history.
        
        Args:
            session_id (str): Unique session identifier
            role (str): Message role ('user' or 'assistant')
            message (str): Message content
        """
        try:
            key = self._get_redis_key(session_id)
            history = self.get_conversation_history(session_id)
            
            # Add timestamp to the message
            message_with_timestamp = {
                'role': role,
                'message': message,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }
            
            history.append(message_with_timestamp)
            
            # Save the updated history back to Redis
            self._redis.set(key, json.dumps(history))
            
            # Set an expiration to prevent indefinite growth
            ttl_seconds = current_app.config['SESSION_TTL_SECONDS']
            self._redis.expire(key, ttl_seconds)

        except Exception as e:
            print(f"Error adding message: {e}")

    def set_conversation_history(self, session_id: str, messages: List[Dict[str, str]]):
        """
        Replace the stored conversation history with a new list.
        Useful for pruning old messages or resetting conversation.
        
        Args:
            session_id (str): Unique session identifier
            messages (List[Dict[str, str]]): New conversation history
        """
        try:
            key = self._get_redis_key(session_id)
            self._redis.set(key, json.dumps(messages))
            
            ttl_seconds = current_app.config['SESSION_TTL_SECONDS']
            self._redis.expire(key, ttl_seconds)
        except Exception as e:
            print(f"Error setting conversation history: {e}")

    def get_summary(self, session_id: str) -> str:
        """
        Retrieve the stored conversation summary for a session.
        
        Args:
            session_id (str): Unique session identifier
            
        Returns:
            str: Summary text, or None if not found
        """
        try:
            key = self._get_summary_key(session_id)
            return self._redis.get(key)
        except Exception as e:
            print(f"Error getting summary: {e}")
            return None

    def set_summary(self, session_id: str, summary: str):
        """
        Store or update the conversation summary for a session.
        
        Args:
            session_id (str): Unique session identifier
            summary (str): Summary text
        """
        try:
            key = self._get_summary_key(session_id)
            self._redis.set(key, summary)
            
            ttl_seconds = current_app.config['SESSION_TTL_SECONDS']
            self._redis.expire(key, ttl_seconds)
        except Exception as e:
            print(f"Error setting summary: {e}")

    def clear_session(self, session_id: str):
        """
        Remove a conversation history and summary from Redis.
        
        Args:
            session_id (str): Unique session identifier
        """
        try:
            # Clear conversation history
            key = self._get_redis_key(session_id)
            self._redis.delete(key)
            
            # Clear summary if present
            summary_key = self._get_summary_key(session_id)
            self._redis.delete(summary_key)
            
            print(f"Session {session_id} cleared successfully")
        except Exception as e:
            print(f"Error clearing session: {e}")

