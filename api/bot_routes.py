"""
Bot API Routes
==============
RESTful API endpoints for bot interactions.

Endpoints:
- GET  /api/bot - Get service info and session history
- POST /api/bot - Process user message and get AI response

All responses follow a standardized format with message, status, service, timestamp, and data fields.
"""

from flask import request
from datetime import datetime
import os

from . import api_bp
from utils.response_utils import (
    success_response,
    error_response,
    validation_error_response
)
from services.bot_service import bot_service


@api_bp.route('/bot', methods=['GET'])
def get_bot_info():
    """
    Get bot service information and session history.
    
    Query Parameters:
        session_id (optional): Session identifier to retrieve history for
    
    Returns:
        JSON response with:
        - service_info: Bot metadata (name, version, status, model)
        - session_history: List of past messages (if session_id provided)
        - greeting: Welcome message
    
    Example:
        GET /api/bot?session_id=user123
    """
    try:
        # Extract session_id from query parameters
        session_id = request.args.get('session_id')
        
        # Debug logging in development
        if os.environ.get('FLASK_ENV') == 'development':
            print(f"\n🔍 DEBUG - GET /api/bot")
            print(f"Session ID: {session_id}")
            print("=" * 50)
        
        # Get service information
        service_info = bot_service.get_service_info()
        
        # Get session history if session_id provided
        session_history = []
        if session_id:
            session_history = bot_service.get_session_history_from_firestore(session_id)
        
        # Prepare greeting message
        greeting = (
            f"Hello! I'm {service_info.get('service_name', 'your AI assistant')}. "
            "How can I help you today?"
        )
        
        return success_response(
            message=greeting,
            data={
                'service_info': service_info,
                'session_history': session_history,
            }
        )
        
    except Exception as e:
        print(f"Error in get_bot_info: {str(e)}")
        return error_response(
            message='An error occurred while getting bot information',
            error_code='GET_BOT_INFO_ERROR',
            http_status=500
        )


@api_bp.route('/bot', methods=['POST'])
def process_message():
    """
    Process user message and return AI-generated response.
    
    Query Parameters:
        session_id (optional): Session identifier for conversation continuity
    
    Headers:
        User-Role (optional): User role for context (e.g., 'user', 'admin')
    
    Request Body (JSON):
        {
            "input_msg": "string" - The user's message to process (required)
        }
    
    Returns:
        JSON response with:
        - response: AI-generated answer
        - message_type: Type of response ('ai_response', 'error')
        - confidence: Confidence score (0.0-1.0)
        - original_message: User's original message
        - session_id: Session identifier
        - user_role: User role
        - reasoning: ReAct sections (thought, action, observation, final_answer)
        - suggestions: Optional follow-up suggestions
    
    Example:
        POST /api/bot?session_id=user123
        Headers: User-Role: user
        Body: {"input_msg": "What is your knowledge base about?"}
    
    Error Responses:
        400: Missing or invalid request body/fields
        500: Internal processing error
    """
    try:
        # Get request data
        data = request.get_json()
        
        # Validate request body exists
        if not data:
            return validation_error_response(
                message='Request body is required',
                error_code='MISSING_BODY'
            )
        
        # Validate input_msg field
        if 'input_msg' not in data:
            return validation_error_response(
                message='input_msg field is required',
                error_code='MISSING_INPUT_MSG',
                data={'required_fields': ['input_msg']}
            )
        
        input_msg = data['input_msg']
        
        # Get optional parameters
        session_id = request.args.get('session_id')
        user_role = request.headers.get('User-Role')
        
        # Debug logging in development
        if os.environ.get('FLASK_ENV') == 'development':
            print(f"\n🔍 DEBUG - POST /api/bot")
            print(f"Input message: {input_msg[:100]}...")  # Truncate for display
            print(f"Session ID: {session_id}")
            print(f"User Role: {user_role}")
            print("=" * 50)
        
        # Validate input message type and content
        if not input_msg or not isinstance(input_msg, str):
            return validation_error_response(
                message='input_msg must be a non-empty string',
                error_code='INVALID_INPUT_MSG',
                data={'received_type': type(input_msg).__name__}
            )
        
        # Additional validation: check message length
        max_length = 5000  # Reasonable limit
        if len(input_msg) > max_length:
            return validation_error_response(
                message=f'input_msg exceeds maximum length of {max_length} characters',
                error_code='INPUT_TOO_LONG',
                data={'max_length': max_length, 'received_length': len(input_msg)}
            )
        
        # Process the message with bot service
        result = bot_service.process_message(input_msg, session_id, user_role)
        
        # Return successful response
        return success_response(
            message='Message processed successfully',
            data=result
        )
        
    except Exception as e:
        # Log the error
        print(f"❌ Error processing message: {str(e)}")
        
        return error_response(
            message='An error occurred while processing your message',
            error_code='PROCESSING_ERROR',
            http_status=500
        )


@api_bp.route('/bot/clear-session', methods=['POST'])
def clear_session():
    """
    Clear conversation history for a session.
    
    Query Parameters:
        session_id (required): Session identifier to clear
    
    Returns:
        JSON response confirming session was cleared
    
    Example:
        POST /api/bot/clear-session?session_id=user123
    """
    try:
        session_id = request.args.get('session_id')
        
        if not session_id:
            return validation_error_response(
                message='session_id query parameter is required',
                error_code='MISSING_SESSION_ID'
            )
        
        # Clear session from Redis
        bot_service.chat_session_repository.clear_session(session_id)
        
        return success_response(
            message='Session cleared successfully',
            data={'session_id': session_id}
        )
        
    except Exception as e:
        print(f"Error clearing session: {str(e)}")
        return error_response(
            message='An error occurred while clearing the session',
            error_code='CLEAR_SESSION_ERROR',
            http_status=500
        )


@api_bp.route('/bot/history', methods=['GET'])
def get_session_history():
    """
    Get full conversation history for a session.
    
    Query Parameters:
        session_id (required): Session identifier
        source (optional): 'redis' or 'firestore' (default: 'firestore')
    
    Returns:
        JSON response with conversation history
    
    Example:
        GET /api/bot/history?session_id=user123&source=firestore
    """
    try:
        session_id = request.args.get('session_id')
        source = request.args.get('source', 'firestore').lower()
        
        if not session_id:
            return validation_error_response(
                message='session_id query parameter is required',
                error_code='MISSING_SESSION_ID'
            )
        
        # Get history from specified source
        if source == 'redis':
            history = bot_service.get_session_history(session_id)
        else:
            history = bot_service.get_session_history_from_firestore(session_id)
        
        return success_response(
            message='Session history retrieved successfully',
            data={
                'session_id': session_id,
                'source': source,
                'message_count': len(history),
                'history': history
            }
        )
        
    except Exception as e:
        print(f"Error getting session history: {str(e)}")
        return error_response(
            message='An error occurred while retrieving session history',
            error_code='GET_HISTORY_ERROR',
            http_status=500
        )

