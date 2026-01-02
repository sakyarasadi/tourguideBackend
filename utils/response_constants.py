"""
Response Constants
==================
Standardized constants for API responses including HTTP status codes,
response statuses, service names, and default messages.
"""

# ===== HTTP Status Codes =====
HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_SERVER_ERROR = 500

# ===== Response Status =====
STATUS_SUCCESS = 'success'
STATUS_ERROR = 'error'
STATUS_WARNING = 'warning'

# ===== Service Name =====
# This will be overridden by config in actual responses
SERVICE_BOT = 'ai-bot-service'

# ===== Default Messages =====
MSG_SUCCESS = 'Operation completed successfully'
MSG_SERVER_ERROR = 'Internal server error occurred'
MSG_INVALID_REQUEST = 'Invalid request data'
MSG_NOT_FOUND = 'Resource not found'

