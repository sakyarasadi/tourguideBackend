"""
Redis Client Manager
====================
Manages Redis connection lifecycle with Flask application context.
Implements singleton pattern for efficient connection management.

Features:
- Lazy initialization with Flask app context
- Connection testing with ping
- Graceful error handling
- Support for password authentication
"""

import redis


class RedisClient:
    """
    Singleton-like Redis client manager for Flask applications.
    Handles connection initialization and provides access to Redis client.
    """
    
    def __init__(self):
        """Initialize manager with None value (lazy initialization)"""
        self._redis_client = None

    def init_app(self, app):
        """
        Initialize Redis client with Flask app configuration.
        
        Args:
            app (Flask): Flask application instance
            
        Configuration keys used:
            - REDIS_HOST: Redis server hostname
            - REDIS_PORT: Redis server port (default: 6379)
            - REDIS_DB: Redis database number (default: 0)
            - REDIS_PASSWORD: Redis password (optional)
        """
        redis_host = app.config.get('REDIS_HOST')
        redis_port = app.config.get('REDIS_PORT', 6379)
        redis_db = app.config.get('REDIS_DB', 0)
        redis_password = app.config.get('REDIS_PASSWORD')
        
        # Skip initialization if host not configured
        if not redis_host:
            app.logger.warning("Redis configuration missing; skipping Redis initialization.")
            self._redis_client = None
            return
        
        try:
            # Create Redis client with connection parameters
            self._redis_client = redis.StrictRedis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                password=redis_password,
                decode_responses=True  # Automatically decode responses to strings
            )
            
            # Test connection with ping
            self._redis_client.ping()
            app.logger.info("Redis connected successfully")
            print("✅ Redis connected successfully")
            
        except redis.exceptions.ConnectionError as e:
            app.logger.error(f"Error connecting to Redis: {e}")
            print(f"❌ Error connecting to Redis: {e}")
            self._redis_client = None
            # Do NOT re-raise: allow the app to start in degraded mode

    @property
    def client(self):
        """
        Get the Redis client instance.
        
        Returns:
            redis.StrictRedis: Redis client instance
            
        Raises:
            RuntimeError: If Redis client is not initialized
        """
        if self._redis_client is None:
            raise RuntimeError("Redis client has not been initialized. Call init_app first.")
        return self._redis_client
    
    def is_connected(self) -> bool:
        """
        Check if Redis client is connected.
        
        Returns:
            bool: True if connected, False otherwise
        """
        return self._redis_client is not None


# Create a global instance for use across the application
redis_client_manager = RedisClient()

