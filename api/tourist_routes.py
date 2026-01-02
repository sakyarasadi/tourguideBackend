"""
Tourist API Routes with AI Agent Integration
============================================
RESTful API endpoints for tourist operations with AI-powered assistance.

Endpoints:
- GET    /api/tourist/requests - List tour requests with filters
- GET    /api/tourist/requests/<id> - Get single tour request
- POST   /api/tourist/requests - Create tour request (with AI assistance)
- PUT    /api/tourist/requests/<id> - Update tour request
- DELETE /api/tourist/requests/<id> - Cancel tour request
- GET    /api/tourist/bookings - List bookings
- GET    /api/tourist/applications - Get applications for a request
- POST   /api/tourist/applications/<id>/accept - Accept application
- POST   /api/tourist/ai-assist - AI agent for tourist queries
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
from services.tourist_service import tourist_service
from services.bot_service import bot_service


@api_bp.route('/tourist/requests', methods=['GET'])
def get_tour_requests():
    """
    Get tour requests with filters and pagination.
    
    Query Parameters:
        search: Search term
        tourType: Type of tour
        status: Request status
        touristId: Filter by tourist ID
        minBudget, maxBudget: Budget range
        minPeople, maxPeople: Number of people range
        startDateFrom, startDateTo: Date range
        sortBy: Field to sort by
        sortOrder: 'asc' or 'desc'
        page: Page number (default: 1)
        limit: Items per page (default: 10)
    
    Returns:
        JSON response with paginated tour requests
    """
    try:
        # Extract query parameters
        params = {
            'search': request.args.get('search'),
            'tourType': request.args.get('tourType'),
            'status': request.args.get('status'),
            'touristId': request.args.get('touristId'),
            'minBudget': request.args.get('minBudget', type=float),
            'maxBudget': request.args.get('maxBudget', type=float),
            'minPeople': request.args.get('minPeople', type=int),
            'maxPeople': request.args.get('maxPeople', type=int),
            'startDateFrom': request.args.get('startDateFrom'),
            'startDateTo': request.args.get('startDateTo'),
            'sortBy': request.args.get('sortBy', 'createdAt'),
            'sortOrder': request.args.get('sortOrder', 'desc'),
            'page': request.args.get('page', 1, type=int),
            'limit': request.args.get('limit', 10, type=int)
        }
        
        result = tourist_service.get_tour_requests(**params)
        return jsonify(result)
        
    except Exception as e:
        print(f"Error getting tour requests: {str(e)}")
        return error_response(
            message='An error occurred while fetching tour requests',
            error_code='GET_TOUR_REQUESTS_ERROR',
            http_status=500
        )


@api_bp.route('/tourist/requests/<request_id>', methods=['GET'])
def get_tour_request(request_id: str):
    """
    Get a single tour request by ID.
    
    Args:
        request_id: Tour request ID
    
    Returns:
        JSON response with tour request details
    """
    try:
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


@api_bp.route('/tourist/requests', methods=['POST'])
def create_tour_request():
    """
    Create a new tour request from natural language text with AI parsing.
    
    Request Body:
        {
            "text": "John Doe is planning a cultural tour to Paris, France, from June 1 to June 5, 2025, for two people with a total budget of $2000. The goal of the trip is to explore Paris's cultural heritage, including famous museums, historic landmarks, and authentic local cuisine. The tour should focus on cultural experiences and must include wheelchair-accessible locations. The tourist is comfortable communicating in English and French and has requested AI assistance to help plan and optimize the tour itinerary.",
            "touristId": "user123"  // Optional, can be extracted from text
        }
    
    Returns:
        JSON response with created tour request and AI suggestions
    """
    try:
        data = request.get_json()
        
        if not data:
            return validation_error_response(
                message='Request body is required',
                error_code='MISSING_BODY'
            )
        
        # Validate text field
        text = data.get('text') or data.get('description')
        if not text:
            return validation_error_response(
                message='text field is required',
                error_code='MISSING_TEXT'
            )
        
        # Use AI to parse the text and extract structured information
        try:
            parse_prompt = f"""Parse the following tour request text and extract structured information. 
            Return ONLY a valid JSON object with these exact fields (no markdown, no explanation, just JSON):
            {{
                "title": "extracted or generated tour title",
                "destination": "location/city",
                "startDate": "YYYY-MM-DD format",
                "endDate": "YYYY-MM-DD format",
                "budget": number,
                "numberOfPeople": number,
                "tourType": "cultural/adventure/beach/etc",
                "languages": ["list", "of", "languages"],
                "description": "full description",
                "requirements": "special requirements or empty string",
                "touristName": "name if mentioned",
                "touristEmail": "email if mentioned or empty string"
            }}
            
            Tour request text:
            {text}
            
            Extract all relevant information and return valid JSON only:"""
            
            session_id = f"parse_{data.get('touristId', 'anonymous')}"
            ai_parse_response = bot_service.process_message(parse_prompt, session_id=session_id)
            parsed_text = ai_parse_response.get('response', '')
            
            # Try to extract JSON from AI response
            import json
            import re
            
            # Find JSON in the response (handle markdown code blocks)
            json_match = re.search(r'\{[^{}]*\}', parsed_text, re.DOTALL)
            if json_match:
                parsed_json_str = json_match.group(0)
                parsed_data = json.loads(parsed_json_str)
            else:
                # Fallback: try to parse entire response
                try:
                    parsed_data = json.loads(parsed_text)
                except:
                    raise ValueError("Could not parse AI response as JSON")
            
            # Get touristId from request
            tourist_id = data.get('touristId') or data.get('userid') or data.get('userId')
            
            # Fetch user details from users collection if touristId is provided
            user_details = {}
            if tourist_id:
                try:
                    from utils.firebase_client import firebase_client_manager
                    user_doc = firebase_client_manager.db.collection('users').document(tourist_id).get()
                    if user_doc.exists:
                        user_data = user_doc.to_dict()
                        user_details = {
                            'touristName': f"{user_data.get('firstName', '')} {user_data.get('lastName', '')}".strip(),
                            'touristEmail': user_data.get('email', '')
                        }
                except Exception as e:
                    print(f"Error fetching user details: {e}")
                    # Continue without user details
            
            # Merge parsed data with provided data and user details
            structured_data = {
                **parsed_data,
                'touristId': tourist_id or parsed_data.get('touristName', 'anonymous').lower().replace(' ', '_'),
                'touristName': parsed_data.get('touristName') or user_details.get('touristName', ''),
                'touristEmail': parsed_data.get('touristEmail') or user_details.get('touristEmail', '')
            }
            
        except Exception as e:
            print(f"AI parsing error: {e}, using fallback parsing")
            # Fallback: basic extraction
            structured_data = tourist_service.parse_tour_request_text(text)
            tourist_id = data.get('touristId') or data.get('userid') or data.get('userId')
            
            # Fetch user details from users collection
            user_details = {}
            if tourist_id:
                try:
                    from utils.firebase_client import firebase_client_manager
                    user_doc = firebase_client_manager.db.collection('users').document(tourist_id).get()
                    if user_doc.exists:
                        user_data = user_doc.to_dict()
                        user_details = {
                            'touristName': f"{user_data.get('firstName', '')} {user_data.get('lastName', '')}".strip(),
                            'touristEmail': user_data.get('email', '')
                        }
                except Exception as e:
                    print(f"Error fetching user details: {e}")
            
            structured_data['touristId'] = tourist_id or 'anonymous'
            structured_data['touristName'] = structured_data.get('touristName') or user_details.get('touristName', '')
            structured_data['touristEmail'] = structured_data.get('touristEmail') or user_details.get('touristEmail', '')
        
        # Validate the structured data
        validation_result = tourist_service.validate_tour_request_data(structured_data)
        
        if not validation_result['is_valid']:
            # Generate questions for missing fields
            questions = tourist_service.generate_questions_for_missing_fields(
                validation_result['missing_fields'],
                validation_result['parsed_data'],
                text
            )
            
            return success_response(
                message='I need more information to create your tour request',
                data={
                    'missing_fields': validation_result['missing_fields'],
                    'questions': questions,
                    'collected_data': validation_result['parsed_data'],
                    'status': 'incomplete'
                },
                http_status=200
            )
        
        # All required fields are present, proceed with creation
        # Get AI suggestions based on the parsed information
        try:
            ai_query = f"""Based on this tour request: {text}
            
            Please provide suggestions for:
            1. Recommended activities/attractions
            2. Budget optimization tips
            3. Best practices for this type of tour
            4. What to pack/prepare
            
            Keep the response concise and actionable."""
            
            session_id = f"tourist_{validation_result['parsed_data'].get('touristId')}"
            ai_response = bot_service.process_message(ai_query, session_id=session_id)
            ai_suggestions = ai_response.get('response', '')
        except Exception as e:
            print(f"AI suggestions error: {e}")
            ai_suggestions = None
        
        # Create tour request with validated structured data
        tour_request = tourist_service.create_tour_request(validation_result['parsed_data'])
        
        response_data = {
            **tour_request,
            'aiSuggestions': ai_suggestions
        } if ai_suggestions else tour_request
        
        return success_response(
            message='Tour request created successfully',
            data=response_data,
            http_status=201
        )
        
    except Exception as e:
        print(f"Error creating tour request: {str(e)}")
        return error_response(
            message='An error occurred while creating tour request',
            error_code='CREATE_TOUR_REQUEST_ERROR',
            http_status=500
        )


@api_bp.route('/tourist/requests/<request_id>', methods=['PUT'])
def update_tour_request(request_id: str):
    """
    Update a tour request from natural language text.
    
    Args:
        request_id: Tour request ID
    
    Request Body:
        {
            "text": "Update the tour: change budget to $2500 and extend the trip by 2 days"
        }
        OR structured data (for backward compatibility)
    
    Returns:
        JSON response with updated tour request
    """
    try:
        data = request.get_json()
        
        if not data:
            return validation_error_response(
                message='Request body is required',
                error_code='MISSING_BODY'
            )
        
        # Check if text-based update
        if 'text' in data:
            # Use AI to parse update instructions
            try:
                # Get current request
                current_request = tourist_service.get_tour_request(request_id)
                if not current_request:
                    return error_response(
                        message='Tour request not found',
                        error_code='TOUR_REQUEST_NOT_FOUND',
                        http_status=404
                    )
                
                parse_prompt = f"""Current tour request:
                {json.dumps(current_request, indent=2)}
                
                Update instruction: {data['text']}
                
                Return ONLY a valid JSON object with updated fields (no markdown, just JSON):
                {{
                    "title": "...",
                    "destination": "...",
                    "startDate": "YYYY-MM-DD",
                    "endDate": "YYYY-MM-DD",
                    "budget": number,
                    "numberOfPeople": number,
                    ...
                }}
                
                Only include fields that need to be updated. Return valid JSON only:"""
                
                session_id = f"update_{request_id}"
                ai_response = bot_service.process_message(parse_prompt, session_id=session_id)
                parsed_text = ai_response.get('response', '')
                
                import json
                import re
                json_match = re.search(r'\{[^{}]*\}', parsed_text, re.DOTALL)
                if json_match:
                    update_data = json.loads(json_match.group(0))
                else:
                    # Fallback: basic text extraction
                    update_data = tourist_service.parse_update_text(data['text'])
            except Exception as e:
                print(f"AI parsing error: {e}, using fallback")
                update_data = tourist_service.parse_update_text(data['text'])
        else:
            # Structured data (backward compatibility)
            update_data = data
        
        updated_request = tourist_service.update_tour_request(request_id, update_data)
        
        if updated_request:
            return success_response(
                message='Tour request updated successfully',
                data=updated_request
            )
        else:
            return error_response(
                message='Tour request not found',
                error_code='TOUR_REQUEST_NOT_FOUND',
                http_status=404
            )
            
    except Exception as e:
        print(f"Error updating tour request: {str(e)}")
        return error_response(
            message='An error occurred while updating tour request',
            error_code='UPDATE_TOUR_REQUEST_ERROR',
            http_status=500
        )


@api_bp.route('/tourist/requests/<request_id>', methods=['DELETE'])
def cancel_tour_request(request_id: str):
    """
    Cancel a tour request.
    
    Args:
        request_id: Tour request ID
    
    Returns:
        JSON response confirming cancellation
    """
    try:
        success = tourist_service.cancel_tour_request(request_id)
        
        if success:
            return success_response(
                message='Tour request cancelled successfully',
                data={'requestId': request_id}
            )
        else:
            return error_response(
                message='Tour request not found',
                error_code='TOUR_REQUEST_NOT_FOUND',
                http_status=404
            )
            
    except Exception as e:
        print(f"Error cancelling tour request: {str(e)}")
        return error_response(
            message='An error occurred while cancelling tour request',
            error_code='CANCEL_TOUR_REQUEST_ERROR',
            http_status=500
        )


@api_bp.route('/tourist/bookings', methods=['GET'])
def get_bookings():
    """
    Get bookings with filters and pagination.
    
    Query Parameters: Same as tour requests
    
    Returns:
        JSON response with paginated bookings
    """
    try:
        params = {
            'search': request.args.get('search'),
            'status': request.args.get('status'),
            'guideId': request.args.get('guideId'),
            'touristId': request.args.get('touristId'),
            'minPrice': request.args.get('minPrice', type=float),
            'maxPrice': request.args.get('maxPrice', type=float),
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


@api_bp.route('/tourist/applications', methods=['GET'])
def get_applications():
    """
    Get applications for a tour request.
    
    Query Parameters:
        requestId: Tour request ID (required)
        status: Filter by status
        minPrice, maxPrice: Price range
        sortBy, sortOrder: Sorting
        page, limit: Pagination
    
    Returns:
        JSON response with paginated applications
    """
    try:
        request_id = request.args.get('requestId')
        
        if not request_id:
            return validation_error_response(
                message='requestId query parameter is required',
                error_code='MISSING_REQUEST_ID'
            )
        
        params = {
            'requestId': request_id,
            'status': request.args.get('status'),
            'minPrice': request.args.get('minPrice', type=float),
            'maxPrice': request.args.get('maxPrice', type=float),
            'sortBy': request.args.get('sortBy', 'createdAt'),
            'sortOrder': request.args.get('sortOrder', 'desc'),
            'page': request.args.get('page', 1, type=int),
            'limit': request.args.get('limit', 10, type=int)
        }
        
        result = tourist_service.get_applications(**params)
        return jsonify(result)
        
    except Exception as e:
        print(f"Error getting applications: {str(e)}")
        return error_response(
            message='An error occurred while fetching applications',
            error_code='GET_APPLICATIONS_ERROR',
            http_status=500
        )


@api_bp.route('/tourist/applications/<application_id>/accept', methods=['POST'])
def accept_application(application_id: str):
    """
    Accept an application and create a booking.
    
    Args:
        application_id: Application ID
    
    Request Body (text-based):
        {
            "text": "Accept the application for request ABC123 from guide Jane Smith"
        }
    
    OR structured (backward compatibility):
        {
            "requestId": "request123"
        }
    
    Returns:
        JSON response with booking details
    """
    try:
        data = request.get_json()
        
        if not data:
            return validation_error_response(
                message='Request body is required',
                error_code='MISSING_BODY'
            )
        
        # Check if text-based
        if 'text' in data:
            # Extract request ID from text using AI or regex
            try:
                parse_prompt = f"""Extract the request ID from this text: {data['text']}
                
                Return ONLY a JSON object with the requestId:
                {{"requestId": "extracted_id"}}
                
                Valid JSON only:"""
                
                session_id = f"accept_{application_id}"
                ai_response = bot_service.process_message(parse_prompt, session_id=session_id)
                parsed_text = ai_response.get('response', '')
                
                json_match = re.search(r'\{[^{}]*\}', parsed_text, re.DOTALL)
                if json_match:
                    parsed_data = json.loads(json_match.group(0))
                    request_id = parsed_data.get('requestId')
                else:
                    # Fallback: regex extraction
                    request_id_match = re.search(r'(?:request|id)[\s:]*([A-Z0-9]+)', data['text'], re.IGNORECASE)
                    request_id = request_id_match.group(1) if request_id_match else None
            except Exception as e:
                print(f"Error parsing text: {e}")
                # Fallback: regex
                request_id_match = re.search(r'(?:request|id)[\s:]*([A-Z0-9]+)', data['text'], re.IGNORECASE)
                request_id = request_id_match.group(1) if request_id_match else None
        else:
            request_id = data.get('requestId')
        
        if not request_id:
            return validation_error_response(
                message='Could not extract requestId from text or requestId is required in request body',
                error_code='MISSING_REQUEST_ID'
            )
        
        result = tourist_service.accept_application(application_id, request_id)
        
        if result:
            return success_response(
                message='Application accepted and booking created successfully',
                data=result
            )
        else:
            return error_response(
                message='Failed to accept application',
                error_code='ACCEPT_APPLICATION_ERROR',
                http_status=400
            )
            
    except Exception as e:
        print(f"Error accepting application: {str(e)}")
        return error_response(
            message='An error occurred while accepting application',
            error_code='ACCEPT_APPLICATION_ERROR',
            http_status=500
        )


@api_bp.route('/tourist/ai-assist', methods=['POST'])
def ai_assist():
    """
    AI agent endpoint for tourist assistance.
    
    Accepts natural language text for questions and assistance.
    
    Request Body:
        {
            "text": "What are the best places to visit in Paris for a cultural tour with a budget of $2000 for 2 people?",
            "sessionId": "user123"  // Optional for conversation continuity
        }
    
    Returns:
        JSON response with AI assistant's answer
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
        
        session_id = data.get('sessionId', 'tourist_ai_session')
        
        # Process with AI agent
        ai_response = bot_service.process_message(
            query_text,
            session_id=session_id,
            user_role='tourist'
        )
        
        return success_response(
            message='AI assistance provided successfully',
            data={
                'query': query_text,
                'response': ai_response.get('response', ''),
                'reasoning': ai_response.get('reasoning', {}),
                'sessionId': session_id
            }
        )
        
    except Exception as e:
        print(f"Error in AI assist: {str(e)}")
        return error_response(
            message='An error occurred while processing AI request',
            error_code='AI_ASSIST_ERROR',
            http_status=500
        )

