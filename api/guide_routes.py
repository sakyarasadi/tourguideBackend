"""
Guide API Routes with AI Agent Integration
==========================================
RESTful API endpoints for guide operations with AI-powered assistance.

Endpoints:
- GET    /api/guide/requests - List available tour requests (open for application)
- GET    /api/guide/requests/<id> - Get single tour request details
- POST   /api/guide/applications - Apply to a tour request (with AI assistance)
- GET    /api/guide/applications - Get guide's applications
- PUT    /api/guide/applications/<id> - Update guide application
- DELETE /api/guide/applications/<id> - Withdraw application
- GET    /api/guide/bookings - List guide's bookings
- GET    /api/guide/bookings/<id> - Get single booking details
- POST   /api/guide/ai-assist - AI agent for guide queries
"""

from flask import request, jsonify
from datetime import datetime
from typing import Dict, Any, Optional
import os
import json
import re

from . import api_bp
from utils.response_utils import (
    success_response,
    error_response,
    validation_error_response
)
from services.bot_service import bot_service


@api_bp.route('/guide/requests', methods=['GET', 'POST'])
def get_available_tour_requests():
    """
    Get available tour requests that guides can apply to.
    
    Supports both structured query parameters and natural language text queries.
    
    Query Parameters (GET) or Body (POST):
        text: Natural language query (e.g., "Show me cultural tours in Kandy with budget above $1000")
        search: Search term
        tourType: Type of tour
        destination: Filter by destination
        minBudget, maxBudget: Budget range
        startDateFrom, startDateTo: Date range
        sortBy: Field to sort by
        sortOrder: 'asc' or 'desc'
        page: Page number (default: 1)
        limit: Items per page (default: 10)
    
    Returns:
        JSON response with paginated available tour requests
        OR questions if the query needs clarification
    """
    try:
        from services.tourist_service import tourist_service
        from services.guide_query_parser import parse_browse_query, validate_browse_query, generate_clarifying_questions
        
        # Get text query if provided (from query param or body)
        text_query = None
        if request.method == 'POST':
            data = request.get_json() or {}
            text_query = data.get('text') or data.get('query')
        else:
            text_query = request.args.get('text') or request.args.get('query')
        
        # If text query provided, parse it
        if text_query:
            # Use AI to parse the query first for better extraction
            try:
                parse_prompt = f"""Parse this guide's query for browsing tour requests and extract filters.
                Return ONLY a valid JSON object (no markdown, no explanation, just JSON):
                {{
                    "destination": "location/city or null",
                    "tourType": "cultural/adventure/beach/etc or null",
                    "minBudget": number or null,
                    "maxBudget": number or null,
                    "startDateFrom": "YYYY-MM-DD or null",
                    "startDateTo": "YYYY-MM-DD or null",
                    "languages": ["list", "of", "languages"] or [],
                    "numberOfPeople": number or null,
                    "requirements": "accessibility/special requirements or null",
                    "search": "search term or null"
                }}
                
                Guide's query: "{text_query}"
                
                Extract all relevant filters. Return valid JSON only:"""
                
                guide_id = request.args.get('guideId') or (request.get_json() or {}).get('guideId', 'anonymous')
                session_id = f"guide_browse_{guide_id}"
                ai_parse_response = bot_service.process_message(parse_prompt, session_id=session_id, user_role='guide')
                parsed_text = ai_parse_response.get('response', '')
                
                # Extract JSON from AI response
                json_match = re.search(r'\{[^{}]*\}', parsed_text, re.DOTALL)
                if json_match:
                    ai_filters = json.loads(json_match.group(0))
                else:
                    ai_filters = {}
            except Exception as e:
                print(f"AI parsing error: {e}, using fallback parser")
                ai_filters = {}
            
            # Merge AI results with regex parser (fallback)
            regex_filters = parse_browse_query(text_query)
            
            # Merge filters (AI takes priority, but regex fills gaps)
            merged_filters = {**regex_filters, **ai_filters}
            # Remove null values
            merged_filters = {k: v for k, v in merged_filters.items() if v is not None and v != ''}
            
            # Validate the query
            validation = validate_browse_query(merged_filters, text_query)
            
            if not validation['is_clear']:
                # Generate clarifying questions
                questions = generate_clarifying_questions(merged_filters, text_query)
                
                return success_response(
                    message='I need more details to find the best tour requests for you',
                    data={
                        'questions': questions,
                        'extracted_filters': merged_filters,
                        'confidence': validation['confidence'],
                        'status': 'needs_clarification'
                    },
                    http_status=200
                )
            
            # Query is clear, use extracted filters
            params = {
                'search': merged_filters.get('search') or request.args.get('search'),
                'tourType': merged_filters.get('tourType') or request.args.get('tourType'),
                'status': 'open',  # Only open requests
                'minBudget': merged_filters.get('minBudget') or request.args.get('minBudget', type=float),
                'maxBudget': merged_filters.get('maxBudget') or request.args.get('maxBudget', type=float),
                'startDateFrom': merged_filters.get('startDateFrom') or request.args.get('startDateFrom'),
                'startDateTo': merged_filters.get('startDateTo') or request.args.get('startDateTo'),
                'sortBy': request.args.get('sortBy', 'createdAt'),
                'sortOrder': request.args.get('sortOrder', 'desc'),
                'page': request.args.get('page', 1, type=int),
                'limit': request.args.get('limit', 10, type=int)
            }
        else:
            # No text query, use traditional query parameters
            params = {
                'search': request.args.get('search'),
                'tourType': request.args.get('tourType'),
                'status': 'open',  # Only open requests
                'minBudget': request.args.get('minBudget', type=float),
                'maxBudget': request.args.get('maxBudget', type=float),
                'startDateFrom': request.args.get('startDateFrom'),
                'startDateTo': request.args.get('startDateTo'),
                'sortBy': request.args.get('sortBy', 'createdAt'),
                'sortOrder': request.args.get('sortOrder', 'desc'),
                'page': request.args.get('page', 1, type=int),
                'limit': request.args.get('limit', 10, type=int)
            }
        
        # Get tour requests with filters
        result = tourist_service.get_tour_requests(**params)
        
        # Add metadata if it was a text query
        if text_query:
            result['query_text'] = text_query
            result['query_type'] = 'natural_language'
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error getting available tour requests: {str(e)}")
        return error_response(
            message='An error occurred while fetching available tour requests',
            error_code='GET_AVAILABLE_TOUR_REQUESTS_ERROR',
            http_status=500
        )


@api_bp.route('/guide/requests/<request_id>', methods=['GET'])
def get_tour_request_for_guide(request_id: str):
    """
    Get a single tour request details for guide review.
    
    Args:
        request_id: Tour request ID
    
    Returns:
        JSON response with tour request details
    """
    try:
        from services.tourist_service import tourist_service
        
        result = tourist_service.get_tour_request(request_id)
        if result:
            return success_response(
                message='Tour request retrieved successfully',
                data=result
            )
        else:
            return error_response(
                message='Tour request not found',
                error_code='TOUR_REQUEST_NOT_FOUND',
                http_status=404
            )
            
    except Exception as e:
        print(f"Error getting tour request: {str(e)}")
        return error_response(
            message='An error occurred while fetching tour request',
            error_code='GET_TOUR_REQUEST_ERROR',
            http_status=500
        )


@api_bp.route('/guide/applications', methods=['POST'])
def create_guide_application():
    """
    Apply to a tour request with AI-powered proposal generation.
    
    Request Body:
        {
            "text": "I am an experienced guide with 5 years in Paris cultural tours. I propose $1800 for this tour with premium museum access and expert historical commentary.",
            "requestId": "tour_request_id",
            "guideId": "guide_user_id"
        }
    
    OR structured data:
        {
            "requestId": "tour_request_id",
            "guideId": "guide_user_id",
            "proposedPrice": 1800,
            "coverLetter": "...",
            "experience": "..."
        }
    
    Returns:
        JSON response with created application
    """
    try:
        from services.guide_service import guide_service
        
        data = request.get_json()
        
        if not data:
            return validation_error_response(
                message='Request body is required',
                error_code='MISSING_BODY'
            )
        
        # Check if text-based or structured
        if 'text' in data:
            # AI-powered parsing
            text = data['text']
            
            parse_prompt = f"""Parse this guide application and extract structured information.
            Return ONLY a valid JSON object with these exact fields (no markdown, no explanation, just JSON):
            {{
                "proposedPrice": number,
                "coverLetter": "professional cover letter text",
                "experience": "relevant experience description",
                "specializations": ["list", "of", "specializations"],
                "languages": ["list", "of", "languages"]
            }}
            
            Application text:
            {text}
            
            Extract all relevant information and return valid JSON only:"""
            
            guide_id = data.get('guideId') or data.get('userid')
            session_id = f"guide_apply_{guide_id}"
            
            ai_parse_response = bot_service.process_message(parse_prompt, session_id=session_id, user_role='guide')
            parsed_text = ai_parse_response.get('response', '')
            
            # Extract JSON from AI response
            json_match = re.search(r'\{[^{}]*\}', parsed_text, re.DOTALL)
            if json_match:
                parsed_data = json.loads(json_match.group(0))
            else:
                # Fallback
                parsed_data = {
                    'proposedPrice': 0,
                    'coverLetter': text,
                    'experience': '',
                    'specializations': [],
                    'languages': []
                }
            
            # Merge with provided data
            application_data = {
                **parsed_data,
                'requestId': data.get('requestId'),
                'guideId': guide_id
            }
        else:
            # Structured data (backward compatibility)
            application_data = data
        
        # Validate required fields
        if not application_data.get('requestId'):
            return validation_error_response(
                message='requestId is required',
                error_code='MISSING_REQUEST_ID'
            )
        
        if not application_data.get('guideId'):
            return validation_error_response(
                message='guideId is required',
                error_code='MISSING_GUIDE_ID'
            )
        
        # Create application
        result = guide_service.apply_to_request(application_data)
        
        # Get AI suggestions for the application
        try:
            ai_query = f"""Based on this guide application for a tour request, provide suggestions for:
            1. How to improve the proposal
            2. Competitive pricing strategy
            3. Key selling points to highlight
            4. Follow-up actions
            
            Keep the response concise and actionable."""
            
            session_id = f"guide_{application_data.get('guideId')}"
            ai_response = bot_service.process_message(ai_query, session_id=session_id, user_role='guide')
            ai_suggestions = ai_response.get('response', '')
        except:
            ai_suggestions = None
        
        response_data = {
            **result,
            'aiSuggestions': ai_suggestions
        } if ai_suggestions else result
        
        return success_response(
            message='Application submitted successfully',
            data=response_data,
            http_status=201
        )
        
    except Exception as e:
        print(f"Error creating application: {str(e)}")
        return error_response(
            message='An error occurred while creating application',
            error_code='CREATE_APPLICATION_ERROR',
            http_status=500
        )


@api_bp.route('/guide/applications', methods=['GET'])
def get_guide_applications():
    """
    Get guide's applications with filters and pagination.
    
    Query Parameters:
        guideId: Guide ID (required)
        status: Filter by status (pending/accepted/rejected/withdrawn)
        requestId: Filter by specific request
        page: Page number (default: 1)
        limit: Items per page (default: 10)
    
    Returns:
        JSON response with paginated applications
    """
    try:
        from services.guide_service import guide_service
        
        guide_id = request.args.get('guideId')
        
        if not guide_id:
            return validation_error_response(
                message='guideId query parameter is required',
                error_code='MISSING_GUIDE_ID'
            )
        
        params = {
            'guideId': guide_id,
            'status': request.args.get('status'),
            'requestId': request.args.get('requestId'),
            'page': request.args.get('page', 1, type=int),
            'limit': request.args.get('limit', 10, type=int)
        }
        
        result = guide_service.get_my_applications(**params)
        return jsonify(result)
        
    except Exception as e:
        print(f"Error getting applications: {str(e)}")
        return error_response(
            message='An error occurred while fetching applications',
            error_code='GET_APPLICATIONS_ERROR',
            http_status=500
        )


@api_bp.route('/guide/applications/<application_id>', methods=['GET'])
def get_guide_application_details(application_id: str):
    """
    Get single application details with merged tour request data.
    
    Args:
        application_id: Application ID
    
    Query Parameters:
        requestId: Tour request ID (required for nested lookup)
        guideId: Guide ID (for verification)
    
    Returns:
        JSON response with application details including tour request info
    """
    try:
        from services.guide_service import guide_service
        from services.tourist_service import tourist_service
        
        request_id = request.args.get('requestId')
        
        if not request_id:
            return validation_error_response(
                message='requestId query parameter is required',
                error_code='MISSING_REQUEST_ID'
            )
        
        # Get application
        application = guide_service.get_application(application_id, request_id)
        
        if not application:
            return error_response(
                message='Application not found',
                error_code='APPLICATION_NOT_FOUND',
                http_status=404
            )
        
        # Get tour request details to merge
        tour_request = tourist_service.get_tour_request(request_id)
        
        if tour_request:
            # Merge tour request data with application
            application['tourTitle'] = application.get('tourTitle') or tour_request.get('title')
            application['destination'] = application.get('destination') or tour_request.get('destination')
            application['touristName'] = application.get('touristName') or tour_request.get('touristName')
            application['touristId'] = tour_request.get('touristId')
            application['startDate'] = application.get('startDate') or tour_request.get('startDate')
            application['endDate'] = application.get('endDate') or tour_request.get('endDate')
            application['touristBudget'] = application.get('touristBudget') or tour_request.get('budget')
            application['tourType'] = application.get('tourType') or tour_request.get('tourType')
            application['numberOfPeople'] = tour_request.get('numberOfPeople')
            application['description'] = tour_request.get('description')
            application['requirements'] = tour_request.get('requirements')
            application['languages'] = tour_request.get('languages', [])
        
        return success_response(
            message='Application details retrieved successfully',
            data=application
        )
        
    except Exception as e:
        print(f"Error getting application details: {str(e)}")
        return error_response(
            message='An error occurred while fetching application details',
            error_code='GET_APPLICATION_DETAILS_ERROR',
            http_status=500
        )


@api_bp.route('/guide/applications/<application_id>', methods=['PUT'])
def update_guide_application(application_id: str):
    """
    Update a guide application (only proposedPrice and coverLetter).
    
    Args:
        application_id: Application ID
    
    Query Parameters:
        requestId: Tour request ID (required)
    
    Request Body:
        {
            "proposedPrice": 1500,
            "coverLetter": "Updated proposal text",
            "guideId": "guide_user_id"
        }
        OR
        {
            "text": "Update proposal: I can reduce the price to $1500"
        }
    
    Returns:
        JSON response with updated application
    """
    try:
        from services.guide_service import guide_service
        
        data = request.get_json()
        request_id = request.args.get('requestId')
        
        if not data:
            return validation_error_response(
                message='Request body is required',
                error_code='MISSING_BODY'
            )
        
        if not request_id:
            return validation_error_response(
                message='requestId query parameter is required',
                error_code='MISSING_REQUEST_ID'
            )
        
        guide_id = data.get('guideId')
        if not guide_id:
            return validation_error_response(
                message='guideId is required in request body',
                error_code='MISSING_GUIDE_ID'
            )
        
        # Get existing application to verify ownership and status
        existing_app = guide_service.get_application(application_id, request_id)
        
        if not existing_app:
            return error_response(
                message='Application not found',
                error_code='APPLICATION_NOT_FOUND',
                http_status=404
            )
        
        # Verify guide owns this application
        if existing_app.get('guideId') != guide_id:
            return error_response(
                message='You can only edit your own applications',
                error_code='FORBIDDEN',
                http_status=403
            )
        
        # Only allow editing if status is pending
        if existing_app.get('status') != 'pending':
            return error_response(
                message='Can only edit pending applications',
                error_code='INVALID_STATUS',
                http_status=400
            )
        
        # Check if text-based update
        if 'text' in data:
            # Use AI to parse update
            parse_prompt = f"""Parse this application update:
            {{
                "proposedPrice": number or null,
                "coverLetter": "string" or null
            }}
            
            Update text: {data['text']}
            
            Only include fields to update. Return ONLY valid JSON:"""
            
            session_id = f"guide_update_{application_id}"
            ai_response = bot_service.process_message(parse_prompt, session_id=session_id, user_role='guide')
            parsed_text = ai_response.get('response', '')
            
            json_match = re.search(r'\{[^{}]*\}', parsed_text, re.DOTALL)
            if json_match:
                update_data = json.loads(json_match.group(0))
            else:
                update_data = {'coverLetter': data['text']}
        else:
            # Structured data - only allow proposedPrice and coverLetter
            update_data = {}
            if 'proposedPrice' in data:
                price = float(data['proposedPrice'])
                if price < 0:
                    return validation_error_response(
                        message='Invalid proposed price',
                        error_code='INVALID_PRICE'
                    )
                update_data['proposedPrice'] = price
            
            if 'coverLetter' in data:
                if not isinstance(data['coverLetter'], str):
                    return validation_error_response(
                        message='Cover letter must be a string',
                        error_code='INVALID_COVER_LETTER'
                    )
                update_data['coverLetter'] = data['coverLetter'].strip()
        
        # Update application
        result = guide_service.update_application(application_id, update_data, request_id)
        
        if result:
            return success_response(
                message='Application updated successfully',
                data=result
            )
        else:
            return error_response(
                message='Failed to update application',
                error_code='UPDATE_FAILED',
                http_status=400
            )
            
    except Exception as e:
        print(f"Error updating application: {str(e)}")
        return error_response(
            message='An error occurred while updating application',
            error_code='UPDATE_APPLICATION_ERROR',
            http_status=500
        )


@api_bp.route('/guide/applications/<application_id>', methods=['DELETE'])
def withdraw_guide_application(application_id: str):
    """
    Withdraw a guide application.
    
    Args:
        application_id: Application ID
    
    Returns:
        JSON response confirming withdrawal
    """
    try:
        from services.guide_service import guide_service
        
        success = guide_service.withdraw_application(application_id)
        
        if success:
            return success_response(
                message='Application withdrawn successfully',
                data={'applicationId': application_id}
            )
        else:
            return error_response(
                message='Application not found',
                error_code='APPLICATION_NOT_FOUND',
                http_status=404
            )
            
    except Exception as e:
        print(f"Error withdrawing application: {str(e)}")
        return error_response(
            message='An error occurred while withdrawing application',
            error_code='WITHDRAW_APPLICATION_ERROR',
            http_status=500
        )


@api_bp.route('/guide/bookings', methods=['GET'])
def get_guide_bookings():
    """
    Get guide's bookings with filters and pagination.
    
    Query Parameters:
        guideId: Guide ID (required)
        status: Filter by status
        startDateFrom, startDateTo: Date range
        sortBy, sortOrder: Sorting
        page, limit: Pagination
    
    Returns:
        JSON response with paginated bookings
    """
    try:
        from services.tourist_service import tourist_service
        
        guide_id = request.args.get('guideId')
        
        if not guide_id:
            return validation_error_response(
                message='guideId query parameter is required',
                error_code='MISSING_GUIDE_ID'
            )
        
        params = {
            'guideId': guide_id,
            'status': request.args.get('status'),
            'startDateFrom': request.args.get('startDateFrom'),
            'startDateTo': request.args.get('startDateTo'),
            'sortBy': request.args.get('sortBy', 'createdAt'),
            'sortOrder': request.args.get('sortOrder', 'desc'),
            'page': request.args.get('page', 1, type=int),
            'limit': request.args.get('limit', 10, type=int)
        }
        
        result = tourist_service.get_bookings(**params)
        return jsonify(result)
        
    except Exception as e:
        print(f"Error getting bookings: {str(e)}")
        return error_response(
            message='An error occurred while fetching bookings',
            error_code='GET_BOOKINGS_ERROR',
            http_status=500
        )


@api_bp.route('/guide/bookings/<booking_id>', methods=['GET'])
def get_guide_booking(booking_id: str):
    """
    Get a single booking details.
    
    Args:
        booking_id: Booking ID
    
    Returns:
        JSON response with booking details
    """
    try:
        from services.guide_service import guide_service
        
        result = guide_service.get_booking(booking_id)
        
        if result:
            return success_response(
                message='Booking retrieved successfully',
                data=result
            )
        else:
            return error_response(
                message='Booking not found',
                error_code='BOOKING_NOT_FOUND',
                http_status=404
            )
            
    except Exception as e:
        print(f"Error getting booking: {str(e)}")
        return error_response(
            message='An error occurred while fetching booking',
            error_code='GET_BOOKING_ERROR',
            http_status=500
        )


@api_bp.route('/guide/ai-assist', methods=['POST'])
def guide_ai_assist():
    """
    AI agent endpoint for guide assistance.
    
    Accepts natural language text for questions and assistance.
    
    Request Body:
        {
            "text": "How should I price my tour proposal for a 5-day cultural tour in Paris with a budget of $2000?",
            "userid": "guide123",
            "sessionId": "guide123"  // Optional for conversation continuity
        }
    
    Returns:
        JSON response with AI assistant's answer tailored for guides
    """
    try:
        data = request.get_json()
        
        if not data:
            return validation_error_response(
                message='Request body is required',
                error_code='MISSING_BODY'
            )
        
        # Accept both 'text' and 'query' for backward compatibility
        query_text = data.get('text') or data.get('query')
        
        if not query_text:
            return validation_error_response(
                message='text or query field is required',
                error_code='MISSING_QUERY'
            )
        
        userid = data.get('userid') or data.get('guideId')
        session_id = data.get('sessionId') or f"guide_{userid}" if userid else 'guide_ai_session'
        
        # Add guide-specific context to the query
        enhanced_query = f"""As a tour guide assistant, help with this query:

{query_text}

Provide guidance specifically for tour guides, including:
- Professional proposal writing tips
- Competitive pricing strategies
- Customer service best practices
- Tour planning and execution advice
- How to stand out from other guides
"""
        
        # Process with AI agent
        ai_response = bot_service.process_message(
            enhanced_query,
            session_id=session_id,
            user_role='guide'
        )
        
        return success_response(
            message='AI assistance provided successfully for guide',
            data={
                'query': query_text,
                'response': ai_response.get('response', ''),
                'reasoning': ai_response.get('reasoning', {}),
                'sessionId': session_id,
                'userRole': 'guide'
            }
        )
        
    except Exception as e:
        print(f"Error in guide AI assist: {str(e)}")
        return error_response(
            message='An error occurred while processing AI request',
            error_code='GUIDE_AI_ASSIST_ERROR',
            http_status=500
        )

