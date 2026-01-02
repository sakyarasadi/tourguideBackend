"""
Response Utilities
==================
Provides standardized API response functions for consistent response formatting
across all endpoints.

All responses include:
- message: Human-readable message
- status: success/error/warning
- service: Service identifier
- timestamp: ISO 8601 timestamp
- data: Optional response payload
- error_code: Optional error code for errors
"""

from flask import jsonify
from datetime import datetime
from .response_constants import *


def create_response(message, status=STATUS_SUCCESS, data=None, error_code=None, http_status=HTTP_OK):
    """
    Create a standardized API response
    
    Args:
        message (str): Response message
        status (str): Response status (success, error, warning)
        data (dict): Response data payload
        error_code (str): Error code for error responses
        http_status (int): HTTP status code
    
    Returns:
        tuple: (json_response, http_status_code)
    """
    response = {
        'message': message,
        'status': status,
        'service': SERVICE_BOT,
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }
    
    if data is not None:
        response['data'] = data
    
    if error_code and status == STATUS_ERROR:
        response['error_code'] = error_code
    
    return jsonify(response), http_status


def success_response(message=MSG_SUCCESS, data=None, http_status=HTTP_OK):
    """
    Create a success response
    
    Args:
        message (str): Success message
        data (dict): Optional response data
        http_status (int): HTTP status code (default: 200)
    
    Returns:
        tuple: (json_response, http_status_code)
    """
    return create_response(message, STATUS_SUCCESS, data, http_status=http_status)


def error_response(message=MSG_SERVER_ERROR, error_code=None, data=None, http_status=HTTP_INTERNAL_SERVER_ERROR):
    """
    Create an error response
    
    Args:
        message (str): Error message
        error_code (str): Optional error code
        data (dict): Optional error details
        http_status (int): HTTP status code (default: 500)
    
    Returns:
        tuple: (json_response, http_status_code)
    """
    return create_response(message, STATUS_ERROR, data, error_code, http_status)


def validation_error_response(message=MSG_INVALID_REQUEST, error_code='VALIDATION_ERROR', data=None):
    """
    Create a validation error response
    
    Args:
        message (str): Validation error message
        error_code (str): Error code (default: VALIDATION_ERROR)
        data (dict): Optional validation details
    
    Returns:
        tuple: (json_response, http_status_code)
    """
    return create_response(message, STATUS_ERROR, data, error_code, HTTP_BAD_REQUEST)


def not_found_response(message=MSG_NOT_FOUND, error_code='NOT_FOUND'):
    """
    Create a not found response
    
    Args:
        message (str): Not found message
        error_code (str): Error code (default: NOT_FOUND)
    
    Returns:
        tuple: (json_response, http_status_code)
    """
    return create_response(message, STATUS_ERROR, error_code=error_code, http_status=HTTP_NOT_FOUND)

