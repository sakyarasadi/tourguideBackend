"""
Firebase Client Manager
========================
Manages Firebase Admin SDK connection lifecycle with Flask application context.
Implements singleton pattern for efficient connection pooling.

Features:
- Lazy initialization with Flask app context
- Firebase Firestore for database operations
- Firebase Storage for file storage
- Firebase Authentication for user management
- Graceful degradation if Firebase is unavailable
"""

import firebase_admin
from firebase_admin import credentials, firestore, storage, auth
import os
import json
import tempfile


class FirebaseClientManager:
    """
    Singleton-like Firebase client manager for Flask applications.
    Handles connection initialization, lifecycle, and access to Firebase services.
    """
    
    def __init__(self):
        """Initialize manager with None values (lazy initialization)"""
        self._app = None
        self._db = None
        self._storage_bucket = None
        self._initialized = False

    def init_app(self, app):
        """
        Initialize Firebase Admin SDK with Flask app configuration.
        
        Args:
            app (Flask): Flask application instance
            
        Configuration keys used:
            - FIREBASE_CREDENTIALS_PATH: Path to Firebase service account JSON file
            - FIREBASE_CREDENTIALS_JSON: Firebase credentials as JSON string (alternative to file path)
            - FIREBASE_PROJECT_ID: Firebase project ID
            - FIREBASE_STORAGE_BUCKET: Firebase storage bucket name
        """
        credentials_path = app.config.get('FIREBASE_CREDENTIALS_PATH')
        credentials_json = os.environ.get('FIREBASE_CREDENTIALS_JSON') or app.config.get('FIREBASE_CREDENTIALS_JSON')
        project_id = app.config.get('FIREBASE_PROJECT_ID')
        storage_bucket = app.config.get('FIREBASE_STORAGE_BUCKET')

        # If no credentials configured, skip initialization gracefully
        if not credentials_path and not credentials_json and not project_id:
            app.logger.warning("Firebase configuration missing; skipping Firebase initialization.")
            self._app = None
            self._db = None
            self._storage_bucket = None
            self._initialized = False
            return

        try:
            # Initialize Firebase Admin SDK
            cred = None
            
            # Priority 1: Use credentials from JSON string (environment variable)
            if credentials_json:
                try:
                    # Parse JSON string
                    if isinstance(credentials_json, str):
                        cred_dict = json.loads(credentials_json)
                    else:
                        cred_dict = credentials_json
                    # Create credentials from dictionary
                    cred = credentials.Certificate(cred_dict)
                    app.logger.info("Using Firebase credentials from environment variable")
                except (json.JSONDecodeError, ValueError, TypeError) as e:
                    app.logger.error(f"Failed to parse FIREBASE_CREDENTIALS_JSON: {e}")
                    cred = None
            
            # Priority 2: Use credentials from file path
            if not cred and credentials_path and os.path.exists(credentials_path):
                # Use service account credentials file
                cred = credentials.Certificate(credentials_path)
                app.logger.info(f"Using Firebase credentials from file: {credentials_path}")
            
            # Initialize Firebase with credentials or application default
            if cred:
                if storage_bucket:
                    self._app = firebase_admin.initialize_app(cred, {
                        'storageBucket': storage_bucket
                    })
                else:
                    self._app = firebase_admin.initialize_app(cred)
            elif project_id:
                # Use application default credentials (for Cloud Run, App Engine, etc.)
                options = {'projectId': project_id}
                if storage_bucket:
                    options['storageBucket'] = storage_bucket
                self._app = firebase_admin.initialize_app(options=options)
                app.logger.info("Using Firebase application default credentials")
            else:
                app.logger.error("Firebase credentials not found")
                return
            
            # Initialize Firestore client
            self._db = firestore.client()
            
            # Initialize Storage bucket if configured
            if storage_bucket:
                self._storage_bucket = storage.bucket()
            
            self._initialized = True
            
            app.logger.info("Firebase connected successfully")
            print("✅ Firebase connected successfully")
            print(f"   - Firestore: enabled")
            print(f"   - Storage: {'enabled' if storage_bucket else 'disabled'}")
            print(f"   - Authentication: enabled")
            
        except ValueError as e:
            # Firebase already initialized (can happen in testing or reload scenarios)
            if "The default Firebase app already exists" in str(e):
                self._app = firebase_admin.get_app()
                self._db = firestore.client()
                if storage_bucket:
                    self._storage_bucket = storage.bucket()
                self._initialized = True
                app.logger.info("Using existing Firebase app")
                print("✅ Using existing Firebase app")
            else:
                app.logger.error("Error connecting to Firebase: %s", e)
                print(f"❌ Error connecting to Firebase: {e}")
                self._app = None
                self._db = None
                self._storage_bucket = None
                self._initialized = False
        except Exception as e:
            app.logger.error("Error connecting to Firebase: %s", e)
            print(f"❌ Error connecting to Firebase: {e}")
            self._app = None
            self._db = None
            self._storage_bucket = None
            self._initialized = False
            # Do NOT re-raise: allow the app to start in degraded mode

        # Expose via Flask extensions for discoverability
        if not hasattr(app, 'extensions'):
            app.extensions = {}
        app.extensions['firebase'] = self

    def close(self):
        """
        Close the Firebase connection and reset internal state.
        Call this when shutting down the application.
        """
        if self._app is not None:
            try:
                firebase_admin.delete_app(self._app)
                print("Firebase connection closed")
            except Exception as e:
                print(f"Error closing Firebase connection: {e}")
            finally:
                self._app = None
                self._db = None
                self._storage_bucket = None
                self._initialized = False

    @property
    def db(self):
        """
        Get the Firestore database instance.
        
        Returns:
            Firestore client: Firestore database instance
            
        Raises:
            RuntimeError: If Firebase is not initialized
        """
        if self._db is None:
            raise RuntimeError("Firebase not initialized. Call init_app first.")
        return self._db

    @property
    def storage(self):
        """
        Get the Firebase Storage bucket instance.
        
        Returns:
            Bucket: Firebase Storage bucket
            
        Raises:
            RuntimeError: If Firebase Storage is not initialized
        """
        if self._storage_bucket is None:
            raise RuntimeError("Firebase Storage not initialized or not configured.")
        return self._storage_bucket

    @property
    def auth(self):
        """
        Get the Firebase Authentication service.
        
        Returns:
            Auth: Firebase Authentication service
            
        Raises:
            RuntimeError: If Firebase is not initialized
        """
        if not self._initialized:
            raise RuntimeError("Firebase not initialized. Call init_app first.")
        return auth

    def is_connected(self) -> bool:
        """
        Check if Firebase client is connected.
        
        Returns:
            bool: True if connected, False otherwise
        """
        return self._initialized and self._db is not None

    def verify_id_token(self, id_token: str):
        """
        Verify a Firebase ID token.
        
        Args:
            id_token (str): Firebase ID token to verify
            
        Returns:
            dict: Decoded token containing user information
            
        Raises:
            firebase_admin.auth.InvalidIdTokenError: If token is invalid
        """
        if not self._initialized:
            raise RuntimeError("Firebase not initialized. Call init_app first.")
        return auth.verify_id_token(id_token)

    def create_user(self, email: str, password: str, **kwargs):
        """
        Create a new Firebase user.
        
        Args:
            email (str): User's email address
            password (str): User's password
            **kwargs: Additional user properties (display_name, photo_url, etc.)
            
        Returns:
            UserRecord: Created user record
        """
        if not self._initialized:
            raise RuntimeError("Firebase not initialized. Call init_app first.")
        return auth.create_user(
            email=email,
            password=password,
            **kwargs
        )

    def get_user(self, uid: str):
        """
        Get a Firebase user by UID.
        
        Args:
            uid (str): User's unique identifier
            
        Returns:
            UserRecord: User record
        """
        if not self._initialized:
            raise RuntimeError("Firebase not initialized. Call init_app first.")
        return auth.get_user(uid)

    def delete_user(self, uid: str):
        """
        Delete a Firebase user.
        
        Args:
            uid (str): User's unique identifier
        """
        if not self._initialized:
            raise RuntimeError("Firebase not initialized. Call init_app first.")
        auth.delete_user(uid)


# Create a global instance for use across the application
firebase_client_manager = FirebaseClientManager()

