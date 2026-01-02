"""
Flask Application Factory
=========================
AI Chatbot Boilerplate - A proprietary asset of Exe.lk

Author: A B Geethan Imal
Organization: Exe.lk
Copyright (c) 2024 Exe.lk. All rights reserved.

This module creates and configures the Flask application using the application factory pattern.
This pattern allows for multiple instances of the app with different configurations.

The app initialization includes:
- Configuration loading
- Logging setup
- CORS configuration
- Database client initialization (MongoDB, Redis)
- Blueprint registration
- Health check endpoints
- Error handlers
"""

import os

# Suppress noisy gRPC/absl pre-initialization warnings before heavy imports
os.environ.setdefault('GRPC_VERBOSITY', 'ERROR')
os.environ.setdefault('GRPC_CPP_LOG_LEVEL', 'ERROR')
os.environ.setdefault('GLOG_minloglevel', '3')
os.environ.setdefault('ABSL_LOGGING_STDERR_THRESHOLD', '3')
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')

from dotenv import load_dotenv
load_dotenv()

from flask import Flask
from flask_cors import CORS
import logging
from datetime import datetime

from utils.response_utils import (
    success_response,
    error_response,
    not_found_response
)
from utils.firebase_client import firebase_client_manager
from utils.redis_client import redis_client_manager


def create_app(config_name=None):
    """
    Application factory function - creates and configures Flask app
    
    Args:
        config_name (str): Configuration name ('development', 'production', 'testing')
                          Defaults to FLASK_ENV environment variable or 'development'
    
    Returns:
        Flask: Configured Flask application instance
    """
    try:
        app = Flask(__name__)
        
        # ===== Load Configuration =====
        if config_name is None:
            config_name = os.environ.get('FLASK_ENV', 'development')
        
        app.config.from_object(f'config.{config_name.capitalize()}Config')
        
        # ===== Setup Logging =====
        setup_logging(app)
        
        # ===== Enable CORS =====
        cors_origins = app.config.get('CORS_ORIGINS', '*')
        if isinstance(cors_origins, str):
            cors_origins = [cors_origins]
        
        CORS(app, origins=cors_origins, supports_credentials=True)
        
        # ===== Initialize Database Clients =====
        # Firebase - for Firestore (persistent message storage), Storage, and Authentication
        firebase_client_manager.init_app(app)
        
        # Redis - for session management
        redis_client_manager.init_app(app)
        
        # ===== Register Blueprints =====
        from api import api_bp
        app.register_blueprint(api_bp, url_prefix='/api')
        
        # ===== Health Check Endpoints =====
        
        @app.route('/health')
        def health_check():
            """
            Basic health check endpoint
            Returns service status and database connection status
            """
            try:
                # Import bot service to get service info
                from services.bot_service import bot_service
                service_info = bot_service.get_service_info()
                
                # Check database connections
                firebase_connected = firebase_client_manager.is_connected()
                redis_connected = redis_client_manager._redis_client is not None
                
                # Determine overall status
                if firebase_connected and redis_connected:
                    overall_status = 'healthy'
                elif firebase_connected or redis_connected:
                    overall_status = 'degraded'
                else:
                    overall_status = 'unhealthy'
                
                return success_response(
                    message=f"Service is {overall_status}",
                    data={
                        'status': overall_status,
                        'timestamp': datetime.utcnow().isoformat(),
                        'service': app.config.get('BOT_NAME', 'AI Bot'),
                        'version': app.config.get('BOT_VERSION', '1.0.0'),
                        'service_info': service_info,
                        'database_connections': {
                            'firebase': firebase_connected,
                            'redis': redis_connected
                        }
                    }
                )
            except Exception as e:
                return error_response(
                    message="Service health check failed",
                    data={
                        'status': 'unhealthy',
                        'timestamp': datetime.utcnow().isoformat(),
                        'service': app.config.get('BOT_NAME', 'AI Bot'),
                        'error': str(e)
                    },
                    http_status=503
                )
        
        @app.route('/health/detailed')
        def detailed_health_check():
            """
            Detailed health check endpoint with comprehensive diagnostics
            """
            try:
                from services.bot_service import bot_service
                service_info = bot_service.get_service_info()
                
                # Comprehensive health checks
                firebase_connected = firebase_client_manager.is_connected()
                redis_connected = redis_client_manager._redis_client is not None
                
                health_checks = {
                    'service_info': service_info,
                    'database_connections': {
                        'firebase': {
                            'connected': firebase_connected,
                            'status': 'connected' if firebase_connected else 'disconnected'
                        },
                        'redis': {
                            'connected': redis_connected,
                            'status': 'connected' if redis_connected else 'disconnected'
                        }
                    },
                    'environment': {
                        'flask_env': os.environ.get('FLASK_ENV', 'unknown'),
                        'log_level': app.config.get('LOG_LEVEL', 'INFO')
                    }
                }
                
                # Determine overall status
                critical_checks = [firebase_connected, redis_connected]
                
                if all(critical_checks):
                    overall_status = 'healthy'
                elif any(critical_checks):
                    overall_status = 'degraded'
                else:
                    overall_status = 'unhealthy'
                
                return success_response(
                    message=f"Detailed health check completed - Service is {overall_status}",
                    data={
                        'status': overall_status,
                        'timestamp': datetime.utcnow().isoformat(),
                        'service': app.config.get('BOT_NAME', 'AI Bot'),
                        'health_checks': health_checks
                    }
                )
            except Exception as e:
                return error_response(
                    message="Detailed health check failed",
                    data={
                        'status': 'unhealthy',
                        'timestamp': datetime.utcnow().isoformat(),
                        'service': app.config.get('BOT_NAME', 'AI Bot'),
                        'error': str(e)
                    },
                    http_status=503
                )
        
        # ===== Register Error Handlers =====
        register_error_handlers(app)
        
        return app
        
    except Exception as e:
        print(f"Error creating app: {e}")
        raise


def setup_logging(app):
    """
    Setup application logging with configured level and format
    
    Args:
        app (Flask): Flask application instance
    """
    log_level = getattr(logging, app.config.get('LOG_LEVEL', 'INFO').upper())
    log_format = app.config.get('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.StreamHandler()
        ]
    )


def register_error_handlers(app):
    """
    Register global error handlers for common HTTP errors
    
    Args:
        app (Flask): Flask application instance
    """
    @app.errorhandler(404)
    def not_found(error):
        return not_found_response(
            message="Resource not found",
            error_code="NOT_FOUND"
        )
    
    @app.errorhandler(500)
    def internal_error(error):
        return error_response(
            message="Internal server error",
            error_code="INTERNAL_ERROR"
        )


# ===== WSGI Entrypoint =====
# Create app instance for production servers (Gunicorn, Waitress, etc.)
app = create_app()

if __name__ == '__main__':
    # Development server
    app.run(host='0.0.0.0', port=5000, debug=True)

