"""
Configuration Module
====================
AI Chatbot Boilerplate - A proprietary asset of Exe.lk

Author: A B Geethan Imal
Organization: Exe.lk
Copyright (c) 2024 Exe.lk. All rights reserved.

This module defines configuration classes for different environments (development, production).
Customize the values here to match your bot's requirements.

Environment Variables Required:
- SECRET_KEY: Flask secret key for session management
- GEMINI_FLASH_API_KEY: Google Gemini API key for the LLM
- FIREBASE_CREDENTIALS_PATH: Path to Firebase service account JSON file
- FIREBASE_PROJECT_ID: Firebase project ID
- FIREBASE_STORAGE_BUCKET: Firebase storage bucket name
- REDIS_HOST: Redis server host
- REDIS_PORT: Redis server port (default: 6379)
- REDIS_PASSWORD: Redis password (if required)
- REDIS_DB: Redis database number (default: 0)
"""

import os
from datetime import timedelta


class Config:
    """Base configuration class with common settings"""
    
    # ===== Bot Information =====
    # Customize these values for your specific bot
    BOT_NAME = os.environ.get('BOT_NAME', 'AI Assistant Bot')
    BOT_VERSION = os.environ.get('BOT_VERSION', '1.0.1')
    BOT_DESCRIPTION = os.environ.get('BOT_DESCRIPTION', 'AI-powered chatbot service')
    
    # ===== Security =====
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # ===== CORS Configuration =====
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*')
    
    # ===== Logging =====
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # ===== Redis Configuration =====
    # Redis is used for session management and conversation history
    REDIS_HOST = os.environ.get('REDIS_HOST')
    REDIS_PORT = int(os.environ.get('REDIS_PORT') or 6379)
    REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD')
    REDIS_DB = int(os.environ.get('REDIS_DB') or 0)
    
    # Session settings
    SESSION_TTL_SECONDS = int(os.environ.get('SESSION_TTL_SECONDS', str(60 * 60 * 24)))  # 24 hours default
    REDIS_SESSION_PREFIX = os.environ.get('REDIS_SESSION_PREFIX', 'bot_chat_session:')
    
    # ===== Firebase Configuration =====
    # Firebase is used for Firestore (database), Storage, and Authentication
    FIREBASE_CREDENTIALS_PATH = os.environ.get('FIREBASE_CREDENTIALS_PATH')
    FIREBASE_CREDENTIALS_JSON = os.environ.get('FIREBASE_CREDENTIALS_JSON')  # Alternative: JSON string from env var
    FIREBASE_PROJECT_ID = os.environ.get('FIREBASE_PROJECT_ID')
    FIREBASE_STORAGE_BUCKET = os.environ.get('FIREBASE_STORAGE_BUCKET')
    
    # Firestore collection names
    FIRESTORE_COLLECTION_MESSAGES = os.environ.get('FIRESTORE_COLLECTION_MESSAGES', 'messages')
    FIRESTORE_COLLECTION_SESSIONS = os.environ.get('FIRESTORE_COLLECTION_SESSIONS', 'sessions')
    FIRESTORE_COLLECTION_COUNTERS = os.environ.get('FIRESTORE_COLLECTION_COUNTERS', 'counters')
    
    # ===== API Settings =====
    API_TITLE = BOT_NAME
    API_VERSION = BOT_VERSION
    API_DESCRIPTION = BOT_DESCRIPTION
    
    # ===== LLM Configuration =====
    # Gemini API configuration
    GEMINI_API_KEY = os.environ.get('GEMINI_FLASH_API_KEY')
    LLM_MODEL = os.environ.get('LLM_MODEL', 'gemini-2.5-flash')
    LLM_TEMPERATURE = float(os.environ.get('LLM_TEMPERATURE', '0'))
    
    # ===== Conversation Management =====
    # Maximum number of past messages to include in LLM context
    MAX_CONVERSATION_HISTORY_MESSAGES = int(os.environ.get('MAX_CONVERSATION_HISTORY_MESSAGES', '10'))
    
    # ===== RAG (Retrieval-Augmented Generation) Settings =====
    # Path to sentence transformer model (for embeddings)
    SENTENCE_TRANSFORMER_MODEL_PATH = os.environ.get('SENTENCE_TRANSFORMER_MODEL_PATH', '/app/models/all-mpnet-base-v2')
    SENTENCE_TRANSFORMERS_HOME = os.environ.get('SENTENCE_TRANSFORMERS_HOME', '/app/models')
    
    # Number of documents to retrieve from knowledge base
    RAG_TOP_K = int(os.environ.get('RAG_TOP_K', '4'))


class DevelopmentConfig(Config):
    """Development environment configuration"""
    DEBUG = True
    TESTING = False
    LOG_LEVEL = 'DEBUG'


class ProductionConfig(Config):
    """Production environment configuration"""
    DEBUG = False
    TESTING = False
    LOG_LEVEL = 'INFO'


class TestingConfig(Config):
    """Testing environment configuration"""
    DEBUG = True
    TESTING = True
    LOG_LEVEL = 'DEBUG'


# Configuration dictionary for easy access
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

