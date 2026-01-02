"""
Smart Router with Knowledge Base First
=======================================
Intelligent routing endpoint that:
1. First checks knowledge base for answers
2. If knowledge base can't answer, uses AI to determine the correct endpoint
3. Routes to appropriate endpoint automatically
"""

from flask import request, jsonify
from typing import Dict, Any, Optional, List
from datetime import datetime
import json
import re

from . import api_bp
from utils.response_utils import (
    success_response,
    error_response,
    validation_error_response
)
from utils.knowledge_base_search import get_knowledge_base_search
from services.bot_service import bot_service


@api_bp.route('/smart-router', methods=['POST'])
def smart_router():
    """
    Smart router endpoint that checks knowledge base first, then routes to endpoints.
    
    Request Body:
        {
            "text": "User's query or request in natural language",
            "userid": "user_identifier_from_local_storage",
            "userRole": "tourist" or "guide" (optional, defaults to "tourist")
        }
    
    Flow:
    1. Check knowledge base - if similarity > 0.6, return knowledge base answer
    2. If not, use Gemini to understand the intent
    3. Determine which endpoint to call based on user role
    4. Call the appropriate endpoint
    5. Return response
    
    Returns:
        JSON response with answer from knowledge base OR result from routed endpoint
    """
    try:
        data = request.get_json()
        
        if not data:
            return validation_error_response(
                message='Request body is required',
                error_code='MISSING_BODY'
            )
        
        text = data.get('text') or data.get('query')
        if not text:
            return validation_error_response(
                message='text or query field is required',
                error_code='MISSING_TEXT'
            )
        
        # Extract userid and userRole
        userid = data.get('userid') or data.get('userId') or data.get('touristId') or data.get('guideId')
        user_role = data.get('userRole', 'tourist').lower()  # Default to tourist
        
        # Log user information
        print(f"\n🔐 User Info:")
        print(f"   User ID: {userid}")
        print(f"   User Role: {user_role}")
        print(f"   Query: {text[:100]}...")
        
        # Step 1: Check knowledge base first
        kb_search = get_knowledge_base_search()
        kb_result = kb_search.search_best_match(text, similarity_threshold=0.6)
        
        if kb_result and kb_result.get('similarity_score', 0) >= 0.6:
            # Knowledge base can answer
            return success_response(
                message='Answer found in knowledge base',
                data={
                    'source': 'knowledge_base',
                    'query': text,
                    'answer': kb_result['text'],
                    'similarity_score': kb_result['similarity_score'],
                    'filename': kb_result.get('filename')
                }
            )
        
        # Step 2: Knowledge base can't answer - use AI to determine endpoint
        # Customize router prompt based on user role
        if user_role == 'guide':
            router_prompt = f"""You are a smart router for a tour guide platform. Analyze the guide's request and determine which endpoint should be called.

User Role: GUIDE

Available endpoints for guides:
1. get_available_requests - List tour requests available for application (browse requests, show available tours, find opportunities)
2. apply_to_request - Apply to a tour request with proposal
3. get_my_applications - View guide's applications
4. get_my_bookings - View guide's confirmed bookings
5. update_application - Update/withdraw an application
6. get_application_details - Get single application with tour details
7. ai_assist_guide - General AI assistance for guides

User request: "{text}"

IMPORTANT: 
- "browse", "show available", "find requests", "give all requests" → get_available_requests
- "my applications", "show my applications" → get_my_applications
- "my bookings", "show my bookings", "show my [tour name] booking" → get_my_bookings
- "apply to" → apply_to_request

Return ONLY a valid JSON object (no markdown, no explanation, just JSON):
{{
    "endpoint": "endpoint_name",
    "confidence": 0.0-1.0,
    "parameters": {{
        "guideId": "{userid or "null"}",
        "requestId": "extracted or null",
        "applicationId": "extracted or null"
    }},
    "reasoning": "brief explanation of why this endpoint"
}}

Valid JSON only:"""
        else:
            router_prompt = f"""You are a smart router for a tourist booking system. Analyze the user request and determine which endpoint should be called.

User Role: TOURIST

CRITICAL RULES:
1. If the user mentions planning/creating/booking a tour with ANY details (destination, dates, budget, people), route to create_tour_request
2. DO NOT route tour creation requests to ai_assist - they MUST go to create_tour_request
3. The ai_assist endpoint is ONLY for general questions that don't involve tour operations

Available endpoints and their purposes:
1. create_tour_request - For creating/planning new tour requests. Use when user wants to:
   - Plan a tour, create a tour, book a tour, request a tour
   - Describe a trip they want to take (dates, destination, budget, people)
   - Any request mentioning "planning", "want to visit", "going to", "tour to [destination]"

2. get_tour_requests - For listing/searching existing tour requests. Use when user wants to:
   - See their requests, list tours, show my requests, find tours

3. get_tour_request - For getting details of a single tour request. Use when:
   - User asks about a specific request ID or wants details of one request

4. update_tour_request - For updating existing tour requests. Use when:
   - User wants to change, modify, update, edit an existing tour

5. cancel_tour_request - For cancelling tour requests. Use when:
   - User wants to cancel, delete, remove a tour request

6. get_bookings - For viewing bookings. Use when:
   - User asks about bookings, my bookings, booked tours, show my bookings
   - User asks about specific tour bookings like "show my japan tour booking"

7. get_applications - For viewing applications. Use when:
   - User wants to see applications, applicants, proposals for a request

8. accept_application - For accepting applications. Use when:
   - User wants to accept, approve, select a guide application

9. ai_assist - ONLY use for general questions that don't involve tour operations:
   - General travel advice
   - Questions about destinations (NOT for creating tours)
   - General help/information

User request: "{text}"

Analyze this carefully. If it's a tour creation/planning request, route to create_tour_request.
Extract any parameters you can identify (touristId, requestId, etc.) from the text.

Return ONLY a valid JSON object (no markdown, no explanation, just JSON):
{{
    "endpoint": "endpoint_name",
    "confidence": 0.0-1.0,
    "parameters": {{
        "touristId": "{userid or "null"}",
        "requestId": "extracted or null",
        "applicationId": "extracted or null"
    }},
    "reasoning": "brief explanation of why this endpoint"
}}

Valid JSON only:"""
        
        # Check if this is a continuation of an application process (before AI routing)
        if user_role == 'guide':
            apply_session_id = f"guide_apply_{userid}"
            apply_session_history = bot_service.get_session_history(apply_session_id)
            regular_session_id = f"{user_role}_{userid}"
            regular_session_history = bot_service.get_session_history(regular_session_id)
            
            # Check if there's a pending application that needs information
            pending_request_id = None
            # Check apply session first
            for msg in reversed(apply_session_history[-10:]):
                if msg.get('role') == 'assistant':
                    content = msg.get('content', '') or msg.get('message', '')
                    # Check if it's a needs_information response
                    if 'needs_information' in content or 'To complete your application' in content or 'proposed price' in content.lower():
                        # Try to extract requestId
                        try:
                            json_match = re.search(r'"requestId"\s*:\s*"([^"]+)"', content)
                            if json_match:
                                pending_request_id = json_match.group(1)
                                break
                        except:
                            pass
            
            # Also check regular session for requestId mentions
            if not pending_request_id:
                for msg in reversed(regular_session_history[-10:]):
                    if msg.get('role') == 'assistant':
                        content = msg.get('content', '') or msg.get('message', '')
                        # Look for requestId in any format
                        try:
                            # Try UUID pattern
                            uuid_match = re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', content, re.IGNORECASE)
                            if uuid_match and ('needs_information' in content or 'To complete your application' in content or 'proposed price' in content.lower()):
                                pending_request_id = uuid_match.group(0)
                                break
                        except:
                            pass
            
            # Check if user is providing price/cover letter information
            price_pattern = r'(?:proposed|price|budget|cost).*?(\d+(?:\.\d+)?)'
            has_price = bool(re.search(price_pattern, text, re.IGNORECASE))
            has_cover_letter_mention = bool(re.search(r'cover\s+letter|coverletter', text, re.IGNORECASE))
            
            # If user mentions price or cover letter, try to find requestId from context or route anyway
            if has_price or has_cover_letter_mention:
                # If we have a pending requestId, use it
                if pending_request_id:
                    print(f"   🔄 Detected application continuation with requestId: {pending_request_id}")
                    params = {'guideId': userid, 'requestId': pending_request_id}
                    merged_data = {**data, **params, 'userid': userid, 'userRole': user_role}
                    return _route_to_apply_to_request(params, text, merged_data)
                
                # Try to find tour name from recent conversation history
                tour_name_from_history = None
                for msg in reversed(regular_session_history[-5:]):
                    if msg.get('role') == 'user':
                        user_msg = msg.get('content', '') or msg.get('message', '')
                        # Look for "apply to [Tour Name]" or "want to apply [Tour Name]"
                        tour_match = re.search(r'(?:apply to|want to apply|apply for|apply)\s+([A-Za-z][a-zA-Z\s,]+?)(?:\.|,|$|\s+(?:tour|trip|request))', user_msg, re.IGNORECASE)
                        if tour_match:
                            tour_name_from_history = tour_match.group(1).strip()
                            break
                
                # If we found a tour name, route to apply with it
                if tour_name_from_history:
                    print(f"   🔄 Detected application continuation with tour name: {tour_name_from_history}")
                    params = {'guideId': userid}
                    merged_data = {**data, **params, 'userid': userid, 'userRole': user_role}
                    # Pass tour name in the text so apply endpoint can find it
                    combined_text = f"{tour_name_from_history}. {text}"
                    return _route_to_apply_to_request(params, combined_text, merged_data)
        
        session_id = data.get('sessionId') or f"{user_role}_{userid}" if userid else 'smart_router'
        ai_response = bot_service.process_message(router_prompt, session_id=session_id, user_role=user_role)
        routing_text = ai_response.get('response', '')
        
        # Extract JSON from AI response
        try:
            # Try to find JSON in the response
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', routing_text, re.DOTALL)
            if json_match:
                routing_data = json.loads(json_match.group(0))
            else:
                # Try parsing entire response
                routing_data = json.loads(routing_text)
        except Exception as e:
            print(f"Error parsing routing response: {e}")
            print(f"AI Response: {routing_text}")
            # Fallback: try to determine endpoint from keywords
            routing_data = _determine_endpoint_from_keywords(text)
        
        endpoint = routing_data.get('endpoint', 'create_tour_request')  # Default to create_tour_request if unclear
        confidence = routing_data.get('confidence', 0.5)
        
        # Safety check: if endpoint is ai_assist but text looks like tour creation, override
        if endpoint == 'ai_assist' and any(kw in text.lower() for kw in ['planning', 'tour to', 'visit', 'destination', 'budget', 'people', 'going to']):
            print(f"   ⚠️ Override: ai_assist → create_tour_request (detected tour creation keywords)")
            endpoint = 'create_tour_request'
            confidence = 0.7
        
        # Log routing decision
        print(f"\n🔀 Smart Router Decision:")
        print(f"   Query: {text[:100]}...")
        print(f"   Endpoint: {endpoint}")
        print(f"   Confidence: {confidence}")
        print(f"   Reasoning: {routing_data.get('reasoning', 'N/A')}")
        
        # Step 3: Route to appropriate endpoint
        # Merge routing parameters with original data and ensure userid is included
        params = routing_data.get('parameters', {})
        
        # Set appropriate ID based on user role
        if user_role == 'guide':
            if not params.get('guideId'):
                params['guideId'] = userid
        else:
            if not params.get('touristId'):
                params['touristId'] = userid
        
        # Merge all data
        merged_data = {**data, **params, 'userid': userid, 'userRole': user_role}
        
        print(f"   Routing to: {endpoint}")
        
        try:
            # Route based on user role and endpoint
            if user_role == 'guide':
                # Guide-specific routing
                if endpoint == 'get_available_requests':
                    return _route_to_get_available_requests(params, merged_data, text)
                elif endpoint == 'apply_to_request':
                    return _route_to_apply_to_request(params, text, merged_data)
                elif endpoint == 'get_my_applications':
                    return _route_to_get_my_applications(params, merged_data)
                elif endpoint == 'get_my_bookings':
                    return _route_to_get_guide_bookings(params, merged_data, text)
                elif endpoint == 'update_application':
                    return _route_to_update_application(params, text, merged_data)
                elif endpoint == 'get_application_details':
                    return _route_to_get_application_details(params, merged_data)
                elif endpoint == 'ai_assist_guide':
                    return _route_to_ai_assist_guide(text, merged_data)
                else:
                    print(f"   ⚠️ Unknown guide endpoint '{endpoint}', using AI assist")
                    return _route_to_ai_assist_guide(text, merged_data)
            else:
                # Tourist-specific routing
                if endpoint == 'create_tour_request':
                    return _route_to_create_tour_request(text, merged_data)
                elif endpoint == 'get_tour_requests':
                    return _route_to_get_tour_requests(params, merged_data)
                elif endpoint == 'get_tour_request':
                    return _route_to_get_tour_request(params, merged_data)
                elif endpoint == 'update_tour_request':
                    return _route_to_update_tour_request(params, text, merged_data)
                elif endpoint == 'cancel_tour_request':
                    return _route_to_cancel_tour_request(params, merged_data)
                elif endpoint == 'get_bookings':
                    return _route_to_get_bookings(params, merged_data, text)
                elif endpoint == 'get_applications':
                    return _route_to_get_applications(params, merged_data)
                elif endpoint == 'accept_application':
                    return _route_to_accept_application(params, text, merged_data)
                else:
                    # Only use AI assist for truly general questions
                    print(f"   ⚠️ Unknown endpoint '{endpoint}', using AI assist")
                    return _route_to_ai_assist(text, merged_data)
        except Exception as e:
            print(f"   ❌ Error routing to {endpoint}: {e}")
            # Fallback to AI assist if routing fails
            if user_role == 'guide':
                return _route_to_ai_assist_guide(text, merged_data)
            else:
                return _route_to_ai_assist(text, merged_data)
            
    except Exception as e:
        print(f"Error in smart router: {str(e)}")
        return error_response(
            message='An error occurred in smart routing',
            error_code='SMART_ROUTER_ERROR',
            http_status=500
        )


def _determine_endpoint_from_keywords(text: str) -> Dict[str, Any]:
    """Fallback: determine endpoint from keywords"""
    text_lower = text.lower()
    
    # Tour creation keywords (most common)
    create_keywords = [
        'planning', 'plan', 'create', 'book', 'new tour', 'request tour',
        'want to visit', 'going to', 'tour to', 'trip to', 'visit',
        'cultural tour', 'adventure tour', 'budget', 'people', 'destination'
    ]
    
    if any(kw in text_lower for kw in create_keywords):
        return {
            'endpoint': 'create_tour_request',
            'confidence': 0.8,
            'parameters': {},
            'reasoning': 'Keywords suggest tour creation'
        }
    elif any(kw in text_lower for kw in ['list', 'show', 'my requests', 'all requests', 'search']):
        return {
            'endpoint': 'get_tour_requests',
            'confidence': 0.7,
            'parameters': {},
            'reasoning': 'Keywords suggest listing requests'
        }
    elif any(kw in text_lower for kw in ['update', 'change', 'modify', 'edit']):
        return {
            'endpoint': 'update_tour_request',
            'confidence': 0.7,
            'parameters': {},
            'reasoning': 'Keywords suggest update operation'
        }
    elif any(kw in text_lower for kw in ['cancel', 'delete', 'remove']):
        return {
            'endpoint': 'cancel_tour_request',
            'confidence': 0.7,
            'parameters': {},
            'reasoning': 'Keywords suggest cancellation'
        }
    elif any(kw in text_lower for kw in ['bookings', 'my bookings']):
        return {
            'endpoint': 'get_bookings',
            'confidence': 0.7,
            'parameters': {},
            'reasoning': 'Keywords suggest booking query'
        }
    elif any(kw in text_lower for kw in ['applications', 'applicants', 'proposals']):
        return {
            'endpoint': 'get_applications',
            'confidence': 0.7,
            'parameters': {},
            'reasoning': 'Keywords suggest application query'
        }
    elif any(kw in text_lower for kw in ['accept', 'approve', 'select guide']):
        return {
            'endpoint': 'accept_application',
            'confidence': 0.7,
            'parameters': {},
            'reasoning': 'Keywords suggest accepting application'
        }
    else:
        # Default to create if it mentions tour/trip/destination
        if any(kw in text_lower for kw in ['tour', 'trip', 'destination', 'visit', 'travel']):
            return {
                'endpoint': 'create_tour_request',
                'confidence': 0.6,
                'parameters': {},
                'reasoning': 'Contains tour-related keywords, defaulting to create'
            }
        return {
            'endpoint': 'ai_assist',
            'confidence': 0.5,
            'parameters': {},
            'reasoning': 'No clear endpoint match, using AI assist'
        }


def _route_to_create_tour_request(text: str, original_data: Dict[str, Any]) -> Any:
    """Route to create tour request endpoint"""
    from services.tourist_service import tourist_service
    from services.bot_service import bot_service
    import json
    import re
    
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
        
        session_id = f"parse_{original_data.get('touristId', 'anonymous')}"
        ai_parse_response = bot_service.process_message(parse_prompt, session_id=session_id)
        parsed_text = ai_parse_response.get('response', '')
        
        # Extract JSON from AI response
        json_match = re.search(r'\{[^{}]*\}', parsed_text, re.DOTALL)
        if json_match:
            parsed_data = json.loads(json_match.group(0))
        else:
            parsed_data = tourist_service.parse_tour_request_text(text)
        
        # Get touristId from original_data
        tourist_id = original_data.get('touristId') or original_data.get('userid') or original_data.get('userId')
        
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
                print(f"Error fetching user details in smart router: {e}")
        
        # Merge with provided data and user details
        structured_data = {
            **parsed_data,
            'touristId': tourist_id or parsed_data.get('touristName', 'anonymous').lower().replace(' ', '_'),
            'touristName': parsed_data.get('touristName') or user_details.get('touristName', ''),
            'touristEmail': parsed_data.get('touristEmail') or user_details.get('touristEmail', '')
        }
        
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
        # Get AI suggestions
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
        except:
            ai_suggestions = None
        
        # Create tour request with validated structured data
        tour_request = tourist_service.create_tour_request(validation_result['parsed_data'])
        
        response_data = {
            **tour_request,
            'aiSuggestions': ai_suggestions
        } if ai_suggestions else tour_request
        
        return success_response(
            message='Tour request created successfully via smart router',
            data=response_data,
            http_status=201
        )
    except Exception as e:
        return error_response(
            message=f'Error creating tour request: {str(e)}',
            error_code='CREATE_TOUR_REQUEST_ERROR',
            http_status=500
        )


def _route_to_get_tour_requests(params: Dict[str, Any], original_data: Dict[str, Any]) -> Any:
    """Route to get tour requests endpoint"""
    from services.tourist_service import tourist_service
    
    try:
        result = tourist_service.get_tour_requests(
            search=params.get('search'),
            tourType=params.get('tourType'),
            status=params.get('status'),
            touristId=params.get('touristId') or original_data.get('touristId'),
            minBudget=params.get('minBudget'),
            maxBudget=params.get('maxBudget'),
            page=params.get('page', 1),
            limit=params.get('limit', 10)
        )
        return jsonify(result)
    except Exception as e:
        return error_response(
            message=f'Error getting tour requests: {str(e)}',
            error_code='GET_TOUR_REQUESTS_ERROR',
            http_status=500
        )


def _route_to_get_tour_request(params: Dict[str, Any], original_data: Dict[str, Any]) -> Any:
    """Route to get single tour request endpoint"""
    from services.tourist_service import tourist_service
    
    request_id = params.get('requestId') or params.get('id') or _extract_id_from_text(original_data.get('text', ''))
    if not request_id:
        return error_response(
            message='Could not extract request ID',
            error_code='MISSING_REQUEST_ID',
            http_status=400
        )
    
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


def _route_to_update_tour_request(params: Dict[str, Any], text: str, original_data: Dict[str, Any]) -> Any:
    """Route to update tour request endpoint"""
    from services.tourist_service import tourist_service
    from services.bot_service import bot_service
    import json
    import re
    
    request_id = params.get('requestId') or params.get('id')
    if not request_id:
        return error_response(
            message='Could not extract request ID for update',
            error_code='MISSING_REQUEST_ID',
            http_status=400
        )
    
    # Get current request
    current_request = tourist_service.get_tour_request(request_id)
    if not current_request:
        return error_response(
            message='Tour request not found',
            error_code='TOUR_REQUEST_NOT_FOUND',
            http_status=404
        )
    
    # Parse update instructions
    try:
        parse_prompt = f"""Current tour request:
        {json.dumps(current_request, indent=2)}
        
        Update instruction: {text}
        
        Return ONLY a valid JSON object with updated fields (no markdown, just JSON):
        {{
            "title": "...",
            "destination": "...",
            "budget": number,
            ...
        }}
        
        Only include fields that need to be updated. Return valid JSON only:"""
        
        session_id = f"update_{request_id}"
        ai_response = bot_service.process_message(parse_prompt, session_id=session_id)
        parsed_text = ai_response.get('response', '')
        
        json_match = re.search(r'\{[^{}]*\}', parsed_text, re.DOTALL)
        if json_match:
            update_data = json.loads(json_match.group(0))
        else:
            update_data = tourist_service.parse_update_text(text)
        
        updated_request = tourist_service.update_tour_request(request_id, update_data)
        
        if updated_request:
            return success_response(
                message='Tour request updated successfully via smart router',
                data=updated_request
            )
        else:
            return error_response(
                message='Failed to update tour request',
                error_code='UPDATE_TOUR_REQUEST_ERROR',
                http_status=400
            )
    except Exception as e:
        return error_response(
            message=f'Error updating tour request: {str(e)}',
            error_code='UPDATE_TOUR_REQUEST_ERROR',
            http_status=500
        )


def _route_to_cancel_tour_request(params: Dict[str, Any], original_data: Dict[str, Any]) -> Any:
    """Route to cancel tour request endpoint"""
    from services.tourist_service import tourist_service
    
    request_id = params.get('requestId') or params.get('id') or _extract_id_from_text(original_data.get('text', ''))
    if not request_id:
        return error_response(
            message='Could not extract request ID for cancellation',
            error_code='MISSING_REQUEST_ID',
            http_status=400
        )
    
    success = tourist_service.cancel_tour_request(request_id)
    if success:
        return success_response(
            message='Tour request cancelled successfully via smart router',
            data={'requestId': request_id}
        )
    else:
        return error_response(
            message='Tour request not found',
            error_code='TOUR_REQUEST_NOT_FOUND',
            http_status=404
        )


def _get_user_role(userid: str) -> Optional[str]:
    """Get user role from users collection"""
    try:
        from utils.firebase_client import firebase_client_manager
        user_doc = firebase_client_manager.db.collection('users').document(userid).get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
            return user_data.get('userType')  # userType can be 'tourist', 'guide', or 'admin'
        return None
    except Exception as e:
        print(f"Error getting user role: {e}")
        return None


def _format_bookings_for_display(bookings: List[Dict[str, Any]]) -> str:
    """Format bookings list for display in chat"""
    if not bookings or len(bookings) == 0:
        return "No bookings found."
    
    formatted = f"📋 Found {len(bookings)} booking{'s' if len(bookings) > 1 else ''}:\n\n"
    
    for booking in bookings:
        formatted += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        formatted += f"📍 {booking.get('title', 'Untitled Tour')}\n"
        formatted += f"   Destination: {booking.get('destination', 'N/A')}\n"
        formatted += f"   Type: {booking.get('tourType', 'N/A')}\n\n"
        
        if booking.get('startDate') and booking.get('endDate'):
            formatted += f"📅 Dates: {booking.get('startDate')} to {booking.get('endDate')}\n"
        
        if booking.get('agreedPrice'):
            formatted += f"💰 Agreed Price: ${booking.get('agreedPrice'):,.0f}\n"
        elif booking.get('budget'):
            formatted += f"💰 Budget: ${booking.get('budget'):,.0f}\n"
        
        formatted += f"👥 People: {booking.get('numberOfPeople', 'N/A')}\n"
        formatted += f"📊 Status: {booking.get('status', 'N/A')}\n"
        
        if booking.get('touristName'):
            formatted += f"👤 Tourist: {booking.get('touristName')}\n"
        if booking.get('guideName'):
            formatted += f"👤 Guide: {booking.get('guideName')}\n"
        
        formatted += f"🆔 Booking ID: {booking.get('id', 'N/A')}\n"
        formatted += f"🆔 Request ID: {booking.get('requestId', 'N/A')}\n"
        
        formatted += "\n"
    
    formatted += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    
    return formatted


def _extract_tour_name_from_query(text: str) -> Optional[str]:
    """Extract tour name/destination from query text like 'show my japan tour booking'"""
    try:
        text_lower = text.lower()
        
        # If query is just "show my bookings" or similar without a specific tour name, return None
        if re.match(r'^(show\s+)?(my\s+)?(all\s+)?bookings?$', text_lower.strip()):
            return None
        
        # Pattern: "show [tour name] booking" - extract tour name
        # Match patterns like: "show Japan Tour booking", "show my Japan Tour booking details"
        patterns = [
            r'show\s+(?:my\s+)?([A-Z][a-zA-Z\s,]+?)\s+booking',  # "show Japan Tour booking"
            r'my\s+([A-Z][a-zA-Z\s,]+?)\s+booking',  # "my Japan Tour booking"
            r'([A-Z][a-zA-Z\s,]+?)\s+booking\s+details?',  # "Japan Tour booking details"
            r'booking\s+(?:for|to|in|of)\s+([A-Z][a-zA-Z\s,]+?)(?:\.|,|$|\s+details?)',  # "booking for Japan Tour"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                tour_name = match.group(1).strip()
                # Remove common words at the end
                tour_name = re.sub(r'\s+(tour|trip|booking|request|details?)\s*$', '', tour_name, flags=re.IGNORECASE)
                # Remove "show" if it was captured
                tour_name = re.sub(r'^show\s+', '', tour_name, flags=re.IGNORECASE)
                if tour_name and len(tour_name) > 2:
                    return tour_name.strip()
        
        # If no specific pattern matched, try to extract capitalized words (likely tour names)
        # This handles cases like "show Japan Tour booking" where "Japan Tour" is capitalized
        capitalized_match = re.search(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', text)
        if capitalized_match:
            potential_name = capitalized_match.group(1).strip()
            # Don't return if it's just common words
            if not re.match(r'^(Show|My|The|A|An)\s+', potential_name, re.IGNORECASE):
                return potential_name
        
        return None
    except Exception as e:
        print(f"Error extracting tour name: {e}")
        return None


def _route_to_get_bookings(params: Dict[str, Any], original_data: Dict[str, Any], text: str = '') -> Any:
    """Route to get bookings endpoint - checks user role and filters accordingly"""
    from services.tourist_service import tourist_service
    
    try:
        userid = original_data.get('userid') or params.get('touristId') or params.get('guideId')
        if not userid:
            return error_response(
                message='User ID is required to get bookings',
                error_code='MISSING_USER_ID',
                http_status=400
            )
        
        # Get user role from users collection
        user_role = _get_user_role(userid)
        if not user_role:
            # Fallback to userRole from request
            user_role = original_data.get('userRole', 'tourist')
        
        print(f"🔍 User role determined: {user_role} for userid: {userid}")
        
        # Extract tour name from query if provided
        tour_name = _extract_tour_name_from_query(text) if text else None
        
        # Set filters based on user role - explicitly filter by touristId or guideId
        guide_id_filter = None
        tourist_id_filter = None
        
        if user_role == 'tourist':
            tourist_id_filter = userid
            print(f"🔍 Filtering bookings by touristId: {tourist_id_filter}")
        elif user_role == 'guide':
            guide_id_filter = userid
            print(f"🔍 Filtering bookings by guideId: {guide_id_filter}")
        else:
            # If role is unknown, try tourist first
            tourist_id_filter = userid
            print(f"⚠️ Unknown role '{user_role}', defaulting to touristId filter: {tourist_id_filter}")
        
        # Add search filter if tour name is extracted
        search_term = tour_name if tour_name else params.get('search')
        
        result = tourist_service.get_bookings(
            search=search_term,
            status=params.get('status'),
            guideId=guide_id_filter,
            touristId=tourist_id_filter,
            page=params.get('page', 1),
            limit=params.get('limit', 50)
        )
        
        print(f"📊 Bookings result: success={result.get('success')}, data_count={len(result.get('data', []))}")
        print(f"📊 Result keys: {result.keys() if isinstance(result, dict) else 'not a dict'}")
        
        # Format response for better display
        bookings = []
        if result.get('success') and result.get('data'):
            # Make a copy of the list to avoid reference issues
            data = result['data']
            print(f"📊 Data type: {type(data)}, is list: {isinstance(data, list)}")
            if isinstance(data, list):
                bookings = data.copy()  # Make a copy to avoid reference issues
            else:
                bookings = list(data) if data else []
            print(f"📊 Extracted {len(bookings)} bookings from result")
            if bookings:
                print(f"📊 First booking sample: {bookings[0].get('id', 'no id')} - {bookings[0].get('title', 'no title')}")
            
            print(f"📊 Tour name filter: {tour_name} (type: {type(tour_name)}, truthy: {bool(tour_name)})")
            if tour_name:
                # Additional client-side filtering by tour name/destination
                filtered_bookings = []
                tour_name_lower = tour_name.lower().strip()
                # Clean up tour name - remove "show", "my", etc.
                tour_name_lower = re.sub(r'^(show|my|the|a|an)\s+', '', tour_name_lower)
                tour_name_parts = tour_name_lower.split()
                
                print(f"📊 Filtering with tour name: '{tour_name_lower}' (parts: {tour_name_parts})")
                for booking in bookings:
                    title = booking.get('title', '').lower()
                    destination = booking.get('destination', '').lower()
                    
                    # Check if any significant part of tour name is in title or destination
                    # Or if the full tour name (without common words) matches
                    matches = False
                    if tour_name_lower in title or tour_name_lower in destination:
                        matches = True
                    else:
                        # Check if key words match (e.g., "japan" in "Japan Tour")
                        for part in tour_name_parts:
                            if len(part) > 2 and (part in title or part in destination):
                                matches = True
                                break
                    
                    if matches:
                        filtered_bookings.append(booking)
                        print(f"📊 Matched booking: {booking.get('title')} (title: '{title}', dest: '{destination}')")
                
                bookings = filtered_bookings
                print(f"📊 After tour name filtering: {len(bookings)} bookings")
        
        # Format bookings for display
        print(f"📊 Final bookings count before formatting: {len(bookings)}")
        print(f"📊 Bookings is empty: {not bookings}, bookings is None: {bookings is None}")
        if bookings:
            print(f"📊 Formatting {len(bookings)} bookings for display")
            formatted_message = _format_bookings_for_display(bookings)
            print(f"📊 Formatted message length: {len(formatted_message)}")
            return success_response(
                message=formatted_message,
                data=bookings,
                http_status=200
            )
        else:
            print("⚠️ No bookings found after processing")
            return success_response(
                message="No bookings found.",
                data=[],
                http_status=200
            )
    except Exception as e:
        return error_response(
            message=f'Error getting bookings: {str(e)}',
            error_code='GET_BOOKINGS_ERROR',
            http_status=500
        )


def _route_to_get_applications(params: Dict[str, Any], original_data: Dict[str, Any]) -> Any:
    """Route to get applications endpoint"""
    from services.tourist_service import tourist_service
    
    request_id = params.get('requestId') or params.get('id')
    if not request_id:
        return error_response(
            message='requestId is required',
            error_code='MISSING_REQUEST_ID',
            http_status=400
        )
    
    try:
        result = tourist_service.get_applications(
            requestId=request_id,
            status=params.get('status'),
            page=params.get('page', 1),
            limit=params.get('limit', 10)
        )
        return jsonify(result)
    except Exception as e:
        return error_response(
            message=f'Error getting applications: {str(e)}',
            error_code='GET_APPLICATIONS_ERROR',
            http_status=500
        )


def _route_to_accept_application(params: Dict[str, Any], text: str, original_data: Dict[str, Any]) -> Any:
    """Route to accept application endpoint"""
    from services.tourist_service import tourist_service
    import re
    
    application_id = params.get('applicationId') or params.get('id')
    if not application_id:
        # Try to extract from text
        app_id_match = re.search(r'(?:application|app)[\s:]*([A-Z0-9\-]+)', text, re.IGNORECASE)
        application_id = app_id_match.group(1) if app_id_match else None
    
    request_id = params.get('requestId') or _extract_id_from_text(text)
    
    if not application_id or not request_id:
        return error_response(
            message='Could not extract application ID or request ID',
            error_code='MISSING_ID',
            http_status=400
        )
    
    try:
        result = tourist_service.accept_application(application_id, request_id)
        if result:
            return success_response(
                message='Application accepted and booking created successfully via smart router',
                data=result
            )
        else:
            return error_response(
                message='Failed to accept application',
                error_code='ACCEPT_APPLICATION_ERROR',
                http_status=400
            )
    except Exception as e:
        return error_response(
            message=f'Error accepting application: {str(e)}',
            error_code='ACCEPT_APPLICATION_ERROR',
            http_status=500
        )


def _route_to_ai_assist(text: str, original_data: Dict[str, Any]) -> Any:
    """Route to AI assist endpoint"""
    from services.bot_service import bot_service
    
    session_id = original_data.get('sessionId', 'tourist_ai_session')
    
    try:
        ai_response = bot_service.process_message(
            text,
            session_id=session_id,
            user_role='tourist'
        )
        
        return success_response(
            message='AI assistance provided successfully via smart router',
            data={
                'query': text,
                'response': ai_response.get('response', ''),
                'reasoning': ai_response.get('reasoning', {}),
                'sessionId': session_id
            }
        )
    except Exception as e:
        return error_response(
            message=f'Error in AI assist: {str(e)}',
            error_code='AI_ASSIST_ERROR',
            http_status=500
        )


def _extract_id_from_text(text: str) -> Optional[str]:
    """Extract ID from text using regex"""
    # Try various ID patterns
    patterns = [
        r'(?:request|id|ID)[\s:]*([A-Z0-9\-]+)',
        r'([A-Z0-9]{8,})',  # UUID-like
        r'#(\d+)',  # Numeric ID with #
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None


# ===== Guide-Specific Routing Functions =====

def _route_to_get_available_requests(params: Dict[str, Any], original_data: Dict[str, Any], text: str = '') -> Any:
    """Route to get available tour requests for guides with natural language support"""
    from services.tourist_service import tourist_service
    from services.guide_query_parser import parse_browse_query, validate_browse_query, generate_clarifying_questions
    
    try:
        # If text query is provided, parse it
        if text:
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
                
                Guide's query: "{text}"
                
                Extract all relevant filters. Return valid JSON only:"""
                
                guide_id = params.get('guideId') or original_data.get('userid', 'anonymous')
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
                print(f"AI parsing error in router: {e}, using fallback parser")
                ai_filters = {}
            
            # Merge AI results with regex parser (fallback)
            regex_filters = parse_browse_query(text)
            
            # Merge filters (AI takes priority, but regex fills gaps)
            merged_filters = {**regex_filters, **ai_filters}
            # Remove null values
            merged_filters = {k: v for k, v in merged_filters.items() if v is not None and v != ''}
            
            # Validate the query
            validation = validate_browse_query(merged_filters, text)
            
            if not validation['is_clear']:
                # Generate clarifying questions
                questions = generate_clarifying_questions(merged_filters, text)
                
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
            
            # Query is clear, use extracted filters merged with params
            search_params = {
                'status': 'open',
                'destination': merged_filters.get('destination') or params.get('destination'),
                'search': merged_filters.get('search') or params.get('search'),
                'tourType': merged_filters.get('tourType') or params.get('tourType'),
                'minBudget': merged_filters.get('minBudget') or params.get('minBudget'),
                'maxBudget': merged_filters.get('maxBudget') or params.get('maxBudget'),
                'startDateFrom': merged_filters.get('startDateFrom') or params.get('startDateFrom'),
                'startDateTo': merged_filters.get('startDateTo') or params.get('startDateTo'),
                'requirements': merged_filters.get('requirements') or params.get('requirements'),
                'page': params.get('page', 1),
                'limit': params.get('limit', 10)
            }
        else:
            # No text query, use traditional parameters
            search_params = {
                'status': 'open',
                'search': params.get('search'),
                'tourType': params.get('tourType'),
                'minBudget': params.get('minBudget'),
                'maxBudget': params.get('maxBudget'),
                'requirements': params.get('requirements'),
                'page': params.get('page', 1),
                'limit': params.get('limit', 10)
            }
        
        # Get open tour requests that guides can apply to
        result = tourist_service.get_tour_requests(**search_params)
        
        if text:
            result['query_text'] = text
            result['query_type'] = 'natural_language'
        
        return jsonify(result)
    except Exception as e:
        return error_response(
            message=f'Error getting available requests: {str(e)}',
            error_code='GET_AVAILABLE_REQUESTS_ERROR',
            http_status=500
        )


def _route_to_apply_to_request(params: Dict[str, Any], text: str, original_data: Dict[str, Any]) -> Any:
    """Route to apply to a tour request with tour identification"""
    from services.guide_service import guide_service
    from services.tourist_service import tourist_service
    from services.bot_service import bot_service
    import json
    import re
    
    try:
        guide_id = params.get('guideId') or original_data.get('userid')
        session_id = f"guide_apply_{guide_id}"
        
        # Check if there's a pending application in session
        session_history = bot_service.get_session_history(session_id)
        pending_application = None
        
        # Look for saved application intent in recent messages
        for msg in reversed(session_history[-5:]):  # Check last 5 messages
            if msg.get('role') == 'assistant' and 'pending_application' in msg.get('content', ''):
                try:
                    pending_application = json.loads(msg['content'].split('pending_application:')[1].strip())
                    break
                except:
                    pass
        
        # Extract tour name/title from text
        # Pattern to match: "apply to Japan Tour", "want to apply Japan Tour", etc.
        tour_name_match = re.search(r'(?:apply to|want to apply|apply for|interested in|apply)\s+([A-Za-z][a-zA-Z\s,]+?)(?:\.|,|$|\s+(?:tour|trip|request|with))', text, re.IGNORECASE)
        if not tour_name_match:
            # Try simpler pattern: just look for capitalized words after "apply"
            tour_name_match = re.search(r'apply\s+([A-Z][a-zA-Z\s]+?)(?:\.|,|$)', text)
        tour_name = tour_name_match.group(1).strip() if tour_name_match else None
        
        # If we have a pending application and user provided details, use the saved requestId
        if pending_application and pending_application.get('requestId'):
            request_id = pending_application['requestId']
        else:
            # Try to extract requestId from text or params
            potential_id = params.get('requestId') or _extract_id_from_text(text)
            
            # Check if it's a valid UUID (actual ID) or a tour name
            # UUID format: 8-4-4-4-12 hex characters
            uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
            
            if potential_id and uuid_pattern.match(potential_id):
                # It's a valid UUID, use it as requestId
                request_id = potential_id
                tour_name = None  # Clear tour_name since we have a valid ID
            else:
                # It's not a UUID, treat it as a tour name
                request_id = None
                if potential_id and not tour_name:
                    # Use the potential_id as tour name if we didn't extract one from text
                    tour_name = potential_id.strip()
            
            # If we have a tour name but no requestId, search for it
            if not request_id and tour_name:
                search_results = tourist_service.get_tour_requests(
                    search=tour_name,
                    status='open',
                    limit=10
                )
                
                if search_results.get('success') and search_results.get('data'):
                    matching_tours = search_results['data']
                    # Find exact or close match
                    tour_name_lower = tour_name.lower()
                    exact_match = None
                    for tour in matching_tours:
                        if tour_name_lower in tour.get('title', '').lower() or tour_name_lower in tour.get('destination', '').lower():
                            exact_match = tour
                            break
                    
                    if exact_match:
                        request_id = exact_match.get('id')
                    elif len(matching_tours) == 1:
                        request_id = matching_tours[0].get('id')
                    else:
                        # Multiple matches or no exact match - save to session and ask for clarification
                        pending_data = {
                            'tourName': tour_name,
                            'matchingTours': matching_tours[:5],  # Limit to 5
                            'guideId': guide_id,
                            'timestamp': str(datetime.now())
                        }
                        
                        # Save to session
                        save_msg = f"pending_application: {json.dumps(pending_data)}"
                        bot_service.process_message(save_msg, session_id=session_id, user_role='guide')
                        
                        # Generate clarifying question
                        if len(matching_tours) > 1:
                            tour_list = '\n'.join([f"{i+1}. {t.get('title')} - {t.get('destination')} (ID: {t.get('id')})" 
                                                  for i, t in enumerate(matching_tours[:5])])
                            question = f"I found {len(matching_tours)} tours matching '{tour_name}'. Which one would you like to apply to?\n\n{tour_list}\n\nPlease specify the tour number or ID."
                        else:
                            question = f"I couldn't find an exact match for '{tour_name}'. Could you provide more details like the destination, dates, or the tour request ID?"
                        
                        return success_response(
                            message=question,
                            data={
                                'status': 'needs_clarification',
                                'matchingTours': matching_tours[:5],
                                'tourName': tour_name
                            },
                            http_status=200
                        )
        
        if not request_id:
            return error_response(
                message='Could not identify the tour request. Please provide the tour title, destination, or request ID.',
                error_code='MISSING_REQUEST_ID',
                http_status=400
            )
        
        # Get tour request details
        tour_request = tourist_service.get_tour_request(request_id)
        if not tour_request:
            return error_response(
                message='Tour request not found',
                error_code='TOUR_REQUEST_NOT_FOUND',
                http_status=404
            )
        
        # Check if application already exists for this guide and request
        existing_application = None
        try:
            from utils.firebase_client import firebase_client_manager
            # Check directly in the nested collection
            app_ref = firebase_client_manager.db.collection('tourRequests').document(request_id).collection('applications').document(guide_id)
            app_doc = app_ref.get()
            if app_doc.exists:
                existing_application = app_doc.to_dict()
                existing_application['id'] = app_doc.id
        except Exception as e:
            print(f"Error checking existing application: {e}")
            pass  # If check fails, proceed as new application
        
        # First, try to extract price directly from text using regex (more reliable)
        price_match = re.search(r'(?:proposed|price|budget|cost).*?(\d+(?:\.\d+)?)', text, re.IGNORECASE)
        extracted_price = None
        if price_match:
            try:
                extracted_price = float(price_match.group(1))
            except:
                pass
        
        # Use AI to parse application details from text
        parse_prompt = f"""Parse this guide application and extract:
        {{
            "proposedPrice": number or null,
            "coverLetter": "string or null"
        }}
        
        Application text: {text}
        Tour request: {tour_request.get('title')} in {tour_request.get('destination')}, Budget: ${tour_request.get('budget')}
        
        IMPORTANT: If user mentions a price/budget number, extract it as proposedPrice.
        If user says "cover letter no need" or similar, set coverLetter to null.
        
        Return ONLY valid JSON. If information is missing, use null:"""
        
        ai_response = bot_service.process_message(parse_prompt, session_id=session_id, user_role='guide')
        parsed_text = ai_response.get('response', '')
        
        json_match = re.search(r'\{[^{}]*\}', parsed_text, re.DOTALL)
        if json_match:
            parsed_data = json.loads(json_match.group(0))
        else:
            parsed_data = {
                'proposedPrice': None,
                'coverLetter': None
            }
        
        # Extract proposedPrice and coverLetter
        # Use regex-extracted price if available, otherwise use AI-parsed price
        proposed_price = extracted_price if extracted_price is not None else parsed_data.get('proposedPrice')
        cover_letter = parsed_data.get('coverLetter')
        
        # Handle "cover letter no need" - create a default cover letter if user says they don't need one
        cover_letter_not_needed = False
        if cover_letter and ('no need' in cover_letter.lower() or 'not needed' in cover_letter.lower() or 'dont need' in cover_letter.lower()):
            cover_letter_not_needed = True
            cover_letter = None
        # Also check in the original text
        if 'cover letter no need' in text.lower() or 'coverletter no need' in text.lower() or 'no cover letter' in text.lower() or "cover letter no need" in text.lower():
            cover_letter_not_needed = True
            cover_letter = None
        
        # If application exists, use existing data and only update proposedPrice and coverLetter
        if existing_application:
            tour_budget = tour_request.get('budget', 0)
            # Check if proposed price is same as budget
            if proposed_price is not None and proposed_price == tour_budget:
                return success_response(
                    message=f"The tourist's budget is ${tour_budget}. Please provide a different proposed price for your application.",
                    data={
                        'status': 'needs_information',
                        'missingFields': ['proposedPrice'],
                        'requestId': request_id,
                        'tourTitle': tour_request.get('title'),
                        'tourBudget': tour_budget
                    },
                    http_status=200
                )
            
            application_data = existing_application.copy()
            # Only update proposedPrice and coverLetter if provided
            if proposed_price is not None and proposed_price != tour_budget:
                application_data['proposedPrice'] = float(proposed_price)
            if cover_letter:
                application_data['coverLetter'] = cover_letter
        else:
            # New application - check for required fields
            missing_fields = []
            tour_budget = tour_request.get('budget', 0)
            
            if proposed_price is None or proposed_price == 0:
                missing_fields.append('proposedPrice')
            elif proposed_price == tour_budget:
                # Proposed price cannot be the same as tourist's budget
                missing_fields.append('proposedPrice')
            
            # If user said "cover letter no need", create a default one
            if cover_letter_not_needed and (not cover_letter or cover_letter.strip() == ''):
                cover_letter = f"I am interested in guiding the {tour_request.get('title', 'tour')} and would like to apply for this opportunity."
            elif not cover_letter or cover_letter.strip() == '':
                missing_fields.append('coverLetter')
            
            if missing_fields:
                questions = []
                if 'proposedPrice' in missing_fields:
                    if proposed_price == tour_budget:
                        questions.append(f"The tourist's budget is ${tour_budget}. Please provide your proposed price (it should be different from the budget).")
                    else:
                        questions.append(f"What is your proposed price for this tour? (Tourist's budget: ${tour_budget})")
                if 'coverLetter' in missing_fields:
                    questions.append("Please provide a cover letter explaining why you're the best guide for this tour.")
                
                question_text = "To complete your application, I need the following information:\n\n"
                for i, q in enumerate(questions, 1):
                    question_text += f"{i}. {q}\n"
                question_text += "\nYou can provide all information at once."
                
                return success_response(
                    message=question_text,
                    data={
                        'status': 'needs_information',
                        'missingFields': missing_fields,
                        'requestId': request_id,
                        'tourTitle': tour_request.get('title'),
                        'tourBudget': tour_budget
                    },
                    http_status=200
                )
            
            # Get guide details from users collection
            guide_email = ''
            guide_name = ''
            try:
                from utils.firebase_client import firebase_client_manager
                user_doc = firebase_client_manager.db.collection('users').document(guide_id).get()
                if user_doc.exists:
                    user_data = user_doc.to_dict()
                    guide_email = user_data.get('email', '')
                    first_name = user_data.get('firstName', '')
                    last_name = user_data.get('lastName', '')
                    guide_name = f"{first_name} {last_name}".strip() or user_data.get('email', '').split('@')[0]
            except Exception as e:
                print(f"Error fetching guide user details: {e}")
                guide_name = guide_id  # Fallback
            
            # Prepare new application with tour request details
            application_data = {
                'requestId': request_id,
                'guideId': guide_id,
                'guideEmail': guide_email,
                'guideName': guide_name,
                'proposedPrice': float(proposed_price),
                'coverLetter': cover_letter.strip(),
                'tourTitle': tour_request.get('title'),
                'destination': tour_request.get('destination'),
                'startDate': tour_request.get('startDate'),
                'endDate': tour_request.get('endDate'),
                'tourType': tour_request.get('tourType'),
                'touristId': tour_request.get('touristId'),
                'touristName': tour_request.get('touristName'),
                'touristBudget': tour_request.get('budget'),
                'status': 'pending'
            }
        
        # Create or update application
        if existing_application:
            # Update existing application - only update proposedPrice and coverLetter
            # Preserve all other fields from existing application
            update_data = {}
            if 'proposedPrice' in application_data:
                update_data['proposedPrice'] = application_data['proposedPrice']
            if 'coverLetter' in application_data:
                update_data['coverLetter'] = application_data['coverLetter']
            update_data['updatedAt'] = datetime.utcnow()
            
            # Use guide_id as document ID (matches frontend pattern)
            app_id = existing_application.get('id') or guide_id
            result = guide_service.update_application(
                app_id,
                update_data,
                request_id
            )
            # Merge with existing data for response (preserve createdAt and other fields)
            if result:
                # Preserve createdAt from existing application
                if 'createdAt' in existing_application:
                    result['createdAt'] = existing_application['createdAt']
                result = {**existing_application, **result}
            else:
                result = existing_application
        else:
            # Create new application - use guideId as document ID
            application_data['id'] = guide_id
            result = guide_service.apply_to_request(application_data)
        
        # Convert Firestore timestamps and other non-serializable objects to JSON-safe format
        def clean_for_json(obj):
            """Recursively clean object for JSON serialization"""
            if obj is None:
                return None
            elif isinstance(obj, dict):
                return {k: clean_for_json(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [clean_for_json(item) for item in obj]
            elif hasattr(obj, 'isoformat'):  # datetime objects
                return obj.isoformat() + 'Z'
            elif hasattr(obj, 'timestamp'):  # Firestore Timestamp
                try:
                    dt = obj.to_datetime()
                    return dt.isoformat() + 'Z'
                except:
                    return datetime.utcnow().isoformat() + 'Z'
            elif type(obj).__name__ == 'Sentinel':  # SERVER_TIMESTAMP
                # Replace SERVER_TIMESTAMP with current time
                return datetime.utcnow().isoformat() + 'Z'
            elif isinstance(obj, (str, int, float, bool)):
                return obj
            else:
                # Check if it's a Sentinel object by checking the module
                if hasattr(obj, '__class__') and 'google.cloud.firestore' in str(obj.__class__.__module__):
                    # It's a Firestore object, try to convert
                    if hasattr(obj, 'to_datetime'):
                        try:
                            return obj.to_datetime().isoformat() + 'Z'
                        except:
                            return datetime.utcnow().isoformat() + 'Z'
                    else:
                        return datetime.utcnow().isoformat() + 'Z'
                # Try to convert to string as fallback
                try:
                    return str(obj)
                except:
                    return None
        
        cleaned_result = clean_for_json(result)
        
        # Clear the session after successful application
        try:
            # Clear session from Redis
            bot_service.chat_session_repository.clear_session(session_id)
        except:
            pass  # Ignore if session deletion fails
        
        return success_response(
            message=f'Application submitted successfully to "{tour_request.get("title")}"!',
            data=cleaned_result,
            http_status=201
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return error_response(
            message=f'Error applying to request: {str(e)}',
            error_code='APPLY_TO_REQUEST_ERROR',
            http_status=500
        )


def _route_to_get_my_applications(params: Dict[str, Any], original_data: Dict[str, Any]) -> Any:
    """Route to get guide's applications"""
    from services.guide_service import guide_service
    
    try:
        guide_id = params.get('guideId') or original_data.get('userid')
        
        result = guide_service.get_my_applications(
            guideId=guide_id,
            status=params.get('status'),
            page=params.get('page', 1),
            limit=params.get('limit', 10)
        )
        return jsonify(result)
    except Exception as e:
        return error_response(
            message=f'Error getting applications: {str(e)}',
            error_code='GET_MY_APPLICATIONS_ERROR',
            http_status=500
        )


def _route_to_get_guide_bookings(params: Dict[str, Any], original_data: Dict[str, Any], text: str = '') -> Any:
    """Route to get guide's bookings - checks user role and filters by guideId"""
    from services.tourist_service import tourist_service
    
    try:
        userid = params.get('guideId') or original_data.get('userid')
        if not userid:
            return error_response(
                message='Guide ID is required to get bookings',
                error_code='MISSING_GUIDE_ID',
                http_status=400
            )
        
        # Verify user role is guide
        user_role = _get_user_role(userid)
        print(f"🔍 Guide bookings - User role: {user_role} for userid: {userid}")
        
        if user_role and user_role != 'guide':
            return error_response(
                message='User is not a guide',
                error_code='INVALID_USER_ROLE',
                http_status=403
            )
        
        # Extract tour name from query if provided
        tour_name = _extract_tour_name_from_query(text) if text else None
        
        # Explicitly filter by guideId
        print(f"🔍 Filtering bookings by guideId: {userid}")
        
        result = tourist_service.get_bookings(
            search=tour_name if tour_name else params.get('search'),
            guideId=userid,  # Explicitly filter by guideId
            touristId=None,  # Don't filter by touristId for guides
            status=params.get('status'),
            page=params.get('page', 1),
            limit=params.get('limit', 50)
        )
        
        print(f"📊 Bookings result: success={result.get('success')}, data_count={len(result.get('data', []))}")
        print(f"📊 Result keys: {result.keys() if isinstance(result, dict) else 'not a dict'}")
        
        # Format response for better display
        bookings = []
        if result.get('success') and result.get('data'):
            bookings = result['data']
            print(f"📊 Extracted {len(bookings)} bookings from result")
            if tour_name:
                # Additional client-side filtering by tour name/destination
                filtered_bookings = []
                tour_name_lower = tour_name.lower()
                for booking in bookings:
                    title = booking.get('title', '').lower()
                    destination = booking.get('destination', '').lower()
                    if tour_name_lower in title or tour_name_lower in destination:
                        filtered_bookings.append(booking)
                bookings = filtered_bookings
        
        # Format bookings for display
        print(f"📊 Final bookings count before formatting: {len(bookings)}")
        if bookings:
            print(f"📊 Formatting {len(bookings)} bookings for display")
            formatted_message = _format_bookings_for_display(bookings)
            print(f"📊 Formatted message length: {len(formatted_message)}")
            return success_response(
                message=formatted_message,
                data=bookings,
                http_status=200
            )
        else:
            print("⚠️ No bookings found after processing")
            return success_response(
                message="No bookings found.",
                data=[],
                http_status=200
            )
    except Exception as e:
        import traceback
        print(f"❌ Error in _route_to_get_guide_bookings: {str(e)}")
        traceback.print_exc()
        return error_response(
            message=f'Error getting guide bookings: {str(e)}',
            error_code='GET_GUIDE_BOOKINGS_ERROR',
            http_status=500
        )


def _route_to_update_application(params: Dict[str, Any], text: str, original_data: Dict[str, Any]) -> Any:
    """Route to update guide application"""
    from services.guide_service import guide_service
    from services.bot_service import bot_service
    import json
    import re
    
    try:
        application_id = params.get('applicationId') or _extract_id_from_text(text)
        
        if not application_id:
            return error_response(
                message='Could not extract application ID',
                error_code='MISSING_APPLICATION_ID',
                http_status=400
            )
        
        # Parse update from text
        parse_prompt = f"""Parse this application update:
        {{
            "proposedPrice": number or null,
            "coverLetter": "string" or null,
            "status": "pending/withdrawn" or null
        }}
        
        Update text: {text}
        
        Only include fields to update. Return ONLY valid JSON:"""
        
        session_id = f"guide_update_{application_id}"
        ai_response = bot_service.process_message(parse_prompt, session_id=session_id, user_role='guide')
        parsed_text = ai_response.get('response', '')
        
        json_match = re.search(r'\{[^{}]*\}', parsed_text, re.DOTALL)
        if json_match:
            update_data = json.loads(json_match.group(0))
        else:
            update_data = {'coverLetter': text}
        
        result = guide_service.update_application(application_id, update_data)
        
        if result:
            return success_response(
                message='Application updated successfully',
                data=result
            )
        else:
            return error_response(
                message='Application not found',
                error_code='APPLICATION_NOT_FOUND',
                http_status=404
            )
    except Exception as e:
        return error_response(
            message=f'Error updating application: {str(e)}',
            error_code='UPDATE_APPLICATION_ERROR',
            http_status=500
        )


def _route_to_get_application_details(params: Dict[str, Any], original_data: Dict[str, Any]) -> Any:
    """Route to get single application details"""
    from services.guide_service import guide_service
    from services.tourist_service import tourist_service
    
    try:
        application_id = params.get('applicationId') or _extract_id_from_text(original_data.get('text', ''))
        request_id = params.get('requestId')
        
        if not application_id:
            return error_response(
                message='Could not extract application ID',
                error_code='MISSING_APPLICATION_ID',
                http_status=400
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
        if not request_id:
            request_id = application.get('requestId')
        
        if request_id:
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
        return error_response(
            message=f'Error getting application details: {str(e)}',
            error_code='GET_APPLICATION_DETAILS_ERROR',
            http_status=500
        )


def _route_to_ai_assist_guide(text: str, original_data: Dict[str, Any]) -> Any:
    """Route to AI assist for guides"""
    from services.bot_service import bot_service
    
    guide_id = original_data.get('userid') or original_data.get('guideId')
    session_id = original_data.get('sessionId') or f"guide_{guide_id}"
    
    try:
        # Add guide-specific context to the prompt
        enhanced_prompt = f"""As a tour guide assistant, help with this query:
        
        User Query: {text}
        
        Provide guidance specifically for tour guides, including:
        - How to write compelling proposals
        - Pricing strategies
        - Customer service tips
        - Best practices for tour guiding
        """
        
        ai_response = bot_service.process_message(
            enhanced_prompt,
            session_id=session_id,
            user_role='guide'
        )
        
        return success_response(
            message='AI assistance provided successfully for guide',
            data={
                'query': text,
                'response': ai_response.get('response', ''),
                'reasoning': ai_response.get('reasoning', {}),
                'sessionId': session_id,
                'userRole': 'guide'
            }
        )
    except Exception as e:
        return error_response(
            message=f'Error in guide AI assist: {str(e)}',
            error_code='AI_ASSIST_GUIDE_ERROR',
            http_status=500
        )

