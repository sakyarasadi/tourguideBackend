"""
Tourist Service
===============
Service layer for tourist operations including tour requests, bookings, and applications.
Handles business logic and coordinates with repositories and Firebase.
"""

import uuid
import json
import re
from datetime import datetime
from typing import Dict, Any, Optional, List
from flask import current_app
from repository.tourist_repository import TouristRepository


class TouristService:
    """
    Service class for tourist operations.
    Provides high-level methods for managing tour requests, bookings, and applications.
    """
    
    def __init__(self):
        """Initialize the tourist service with repository"""
        self.repository = TouristRepository()
    
    def get_tour_requests(
        self,
        search: Optional[str] = None,
        destination: Optional[str] = None,
        tourType: Optional[str] = None,
        status: Optional[str] = None,
        touristId: Optional[str] = None,
        minBudget: Optional[float] = None,
        maxBudget: Optional[float] = None,
        minPeople: Optional[int] = None,
        maxPeople: Optional[int] = None,
        startDateFrom: Optional[str] = None,
        startDateTo: Optional[str] = None,
        requirements: Optional[str] = None,
        sortBy: str = 'createdAt',
        sortOrder: str = 'desc',
        page: int = 1,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Get tour requests with filters and pagination.
        
        Returns:
            Dictionary with paginated results
        """
        try:
            # Build filters
            filters = {}
            if search:
                filters['search'] = search
            if destination:
                filters['destination'] = destination
            if tourType:
                filters['tourType'] = tourType
            if status:
                filters['status'] = status
            if touristId:
                filters['touristId'] = touristId
            if minBudget is not None:
                filters['minBudget'] = minBudget
            if maxBudget is not None:
                filters['maxBudget'] = maxBudget
            if minPeople is not None:
                filters['minPeople'] = minPeople
            if maxPeople is not None:
                filters['maxPeople'] = maxPeople
            if startDateFrom:
                filters['startDateFrom'] = startDateFrom
            if startDateTo:
                filters['startDateTo'] = startDateTo
            if requirements:
                filters['requirements'] = requirements
            
            # Get requests from repository
            requests, total = self.repository.get_tour_requests(
                filters=filters,
                sort_by=sortBy,
                sort_order=sortOrder,
                page=page,
                limit=limit
            )
            
            # Calculate pagination
            total_pages = (total + limit - 1) // limit
            
            return {
                'success': True,
                'code': 200,
                'data': requests,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total,
                    'totalPages': total_pages,
                    'hasNextPage': page < total_pages,
                    'hasPreviousPage': page > 1
                }
            }
            
        except Exception as e:
            print(f"Error in get_tour_requests: {e}")
            raise
    
    def get_tour_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get a single tour request by ID"""
        try:
            return self.repository.get_tour_request(request_id)
        except Exception as e:
            print(f"Error in get_tour_request: {e}")
            raise
    
    def validate_tour_request_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate tour request data and identify missing required fields.
        
        Args:
            data: Tour request data dictionary
            
        Returns:
            Dictionary with:
                'is_valid': bool - Whether all required fields are present
                'missing_fields': List[str] - List of missing required field names
                'parsed_data': Dict - Cleaned and parsed data
        """
        required_fields = {
            'destination': 'destination',
            'startDate': 'startDate',
            'endDate': 'endDate',
            'budget': 'budget',
            'numberOfPeople': 'numberOfPeople',
            'tourType': 'tourType',
            'description': 'description',
            'touristId': 'touristId'
        }
        
        missing_fields = []
        parsed_data = {}
        
        # Check each required field
        for field_key, field_name in required_fields.items():
            value = data.get(field_key) or data.get(field_name)
            
            # Handle None, empty string, or 'N/A' values
            if value is None:
                missing_fields.append(field_name)
            elif isinstance(value, str):
                value_stripped = value.strip()
                if value_stripped == '' or value_stripped.lower() == 'n/a':
                    missing_fields.append(field_name)
                else:
                    parsed_data[field_key] = value_stripped
            else:
                # Non-string values (numbers, lists, etc.) are valid
                parsed_data[field_key] = value
        
        # Handle special cases and type conversion
        # Budget: must be a valid number > 0
        if 'budget' in parsed_data:
            try:
                budget_value = float(parsed_data['budget'])
                if budget_value <= 0:
                    missing_fields.append('budget')
                    parsed_data.pop('budget', None)
                else:
                    parsed_data['budget'] = budget_value  # Store as float
            except (ValueError, TypeError):
                missing_fields.append('budget')
                parsed_data.pop('budget', None)
        
        # Number of people: must be a valid integer > 0
        if 'numberOfPeople' in parsed_data:
            try:
                people_value = int(parsed_data['numberOfPeople'])
                if people_value <= 0:
                    missing_fields.append('numberOfPeople')
                    parsed_data.pop('numberOfPeople', None)
                else:
                    parsed_data['numberOfPeople'] = people_value  # Store as int
            except (ValueError, TypeError):
                missing_fields.append('numberOfPeople')
                parsed_data.pop('numberOfPeople', None)
        
        # Dates: must be valid date format
        for date_field in ['startDate', 'endDate']:
            if date_field in parsed_data:
                date_value = str(parsed_data[date_field])
                # Check if it's a valid date format (YYYY-MM-DD or recognizable date string)
                if len(date_value) < 8 or date_value.lower() in ['none', 'n/a', '']:
                    missing_fields.append(date_field)
                    parsed_data.pop(date_field, None)
        
        # Title is optional, generate if missing
        if not data.get('title'):
            if 'destination' in parsed_data:
                parsed_data['title'] = f"{parsed_data['destination']} Tour"
            else:
                parsed_data['title'] = 'Tour Request'
        
        # Copy optional fields
        parsed_data['languages'] = data.get('languages', [])
        parsed_data['requirements'] = data.get('requirements', '')
        parsed_data['touristName'] = data.get('touristName', '')
        parsed_data['touristEmail'] = data.get('touristEmail', '')
        
        is_valid = len(missing_fields) == 0
        
        return {
            'is_valid': is_valid,
            'missing_fields': missing_fields,
            'parsed_data': parsed_data
        }
    
    def generate_questions_for_missing_fields(self, missing_fields: List[str], partial_data: Dict[str, Any], original_text: str = '') -> str:
        """
        Generate natural language questions to ask the user for missing fields.
        
        Args:
            missing_fields: List of missing required field names
            partial_data: Already collected data
            original_text: Original user message for context
            
        Returns:
            Natural language string with questions
        """
        field_questions = {
            'destination': 'Where would you like to visit? Please provide the destination city or region.',
            'startDate': 'When would you like to start your tour? Please provide the start date (e.g., "June 10, 2025" or "2025-06-10").',
            'endDate': 'When would you like your tour to end? Please provide the end date (e.g., "June 14, 2025" or "2025-06-14").',
            'budget': 'What is your total budget for this tour? Please provide the amount (e.g., "$1,600" or "1600 USD").',
            'numberOfPeople': 'How many people will be traveling? Please provide the number of travelers.',
            'tourType': 'What type of tour are you interested in? (e.g., cultural, adventure, beach, historical, nature, etc.)',
            'description': 'Could you provide more details about what you\'d like to see and do during your tour?',
            'touristId': 'Please provide your user ID or tourist identifier.'
        }
        
        questions = []
        for field in missing_fields:
            if field in field_questions:
                questions.append(field_questions[field])
        
        if len(questions) == 1:
            return f"To complete your tour request, I need one more piece of information: {questions[0]}"
        elif len(questions) > 1:
            question_text = "To complete your tour request, I need a few more details:\n\n"
            for i, q in enumerate(questions, 1):
                question_text += f"{i}. {q}\n"
            question_text += "\nPlease provide these details so I can create your tour request."
            return question_text
        else:
            return "I need more information to create your tour request. Could you please provide the missing details?"
    
    def create_tour_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new tour request"""
        try:
            # Generate ID if not provided
            request_id = data.get('id') or str(uuid.uuid4())
            
            # Prepare document
            tour_request = {
                'id': request_id,
                'title': data.get('title', data.get('destination', 'Tour Request') + ' Tour'),
                'destination': data['destination'],
                'startDate': data['startDate'],
                'endDate': data['endDate'],
                'budget': float(data['budget']),
                'numberOfPeople': int(data['numberOfPeople']),
                'tourType': data['tourType'],
                'languages': data.get('languages', []),
                'description': data['description'],
                'requirements': data.get('requirements', ''),
                'touristId': data['touristId'],
                'touristName': data.get('touristName'),
                'applicationCount': 0,
                'status': 'open',
                'createdAt': datetime.utcnow(),
                'updatedAt': datetime.utcnow()
            }
            
            # Save to Firebase
            created = self.repository.create_tour_request(tour_request)
            
            return created
            
        except Exception as e:
            print(f"Error in create_tour_request: {e}")
            raise
    
    def update_tour_request(
        self,
        request_id: str,
        data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update a tour request"""
        try:
            # Add updated timestamp
            data['updatedAt'] = datetime.utcnow()
            
            return self.repository.update_tour_request(request_id, data)
            
        except Exception as e:
            print(f"Error in update_tour_request: {e}")
            raise
    
    def cancel_tour_request(self, request_id: str) -> bool:
        """Cancel a tour request"""
        try:
            return self.repository.cancel_tour_request(request_id)
        except Exception as e:
            print(f"Error in cancel_tour_request: {e}")
            raise
    
    def parse_tour_request_text(self, text: str) -> Dict[str, Any]:
        """
        Parse natural language tour request text into structured data.
        This is a fallback parser if AI parsing fails.
        
        Args:
            text: Natural language description of the tour request
            
        Returns:
            Dictionary with structured tour request data
        """
        # Basic regex patterns for extraction
        patterns = {
            'destination': r'(?:to|in|at)\s+([A-Z][a-zA-Z\s,]+?)(?:,|\.|from|for|with|$)',
            'budget': r'\$?(\d+(?:,\d{3})*(?:\.\d{2})?)',
            'people': r'(\d+)\s+(?:people|person|travelers|tourists)',
            'startDate': r'(?:from|starting|begin|June|July|August|January|February|March|April|May|September|October|November|December)\s+(\d{1,2}(?:st|nd|rd|th)?(?:\s+[A-Za-z]+\s+\d{4})?)',
            'endDate': r'(?:to|until|ending)\s+(\d{1,2}(?:st|nd|rd|th)?(?:\s+[A-Za-z]+\s+\d{4})?)',
            'tourType': r'(cultural|adventure|beach|mountain|city|historical|religious|food|wine|nature|safari)',
        }
        
        extracted = {}
        
        # Extract destination
        dest_match = re.search(patterns['destination'], text, re.IGNORECASE)
        if dest_match:
            extracted['destination'] = dest_match.group(1).strip()
        
        # Extract budget (first number that looks like money)
        budget_matches = re.findall(patterns['budget'], text)
        if budget_matches:
            try:
                budget_str = budget_matches[-1].replace(',', '')
                extracted['budget'] = float(budget_str)
            except:
                pass
        
        # Extract number of people
        people_match = re.search(patterns['people'], text, re.IGNORECASE)
        if people_match:
            extracted['numberOfPeople'] = int(people_match.group(1))
        else:
            # Try alternative patterns
            people_alt = re.search(r'(?:for|with)\s+(\d+)', text, re.IGNORECASE)
            if people_alt:
                extracted['numberOfPeople'] = int(people_alt.group(1))
        
        # Extract tour type
        type_match = re.search(patterns['tourType'], text, re.IGNORECASE)
        if type_match:
            extracted['tourType'] = type_match.group(1).lower()
        
        # Extract dates (basic pattern)
        date_pattern = r'(\d{4}-\d{2}-\d{2})|([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})'
        dates = re.findall(date_pattern, text)
        if len(dates) >= 1:
            extracted['startDate'] = dates[0][0] or dates[0][1]
        if len(dates) >= 2:
            extracted['endDate'] = dates[1][0] or dates[1][1]
        
        # Extract name
        name_pattern = r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s+(?:is planning|wants|needs|would like)'
        name_match = re.search(name_pattern, text)
        if name_match:
            extracted['touristName'] = name_match.group(1)
        
        # Extract languages
        lang_match = re.search(r'(?:in|speaks?|language[s]?)\s+([A-Z][a-z]+(?:\s+and\s+[A-Z][a-z]+)?)', text, re.IGNORECASE)
        if lang_match:
            langs_str = lang_match.group(1)
            extracted['languages'] = [l.strip() for l in re.split(r'\s+and\s+|\s*,\s*', langs_str)]
        
        # Set defaults
        result = {
            'title': extracted.get('destination', 'Tour Request') + ' Tour',
            'destination': extracted.get('destination', ''),
            'startDate': extracted.get('startDate', datetime.now().strftime('%Y-%m-%d')),
            'endDate': extracted.get('endDate', datetime.now().strftime('%Y-%m-%d')),
            'budget': extracted.get('budget', 0),
            'numberOfPeople': extracted.get('numberOfPeople', 1),
            'tourType': extracted.get('tourType', 'general'),
            'languages': extracted.get('languages', ['English']),
            'description': text,
            'requirements': '',
            'touristName': extracted.get('touristName', ''),
            'touristEmail': ''
        }
        
        return result
    
    def parse_update_text(self, text: str) -> Dict[str, Any]:
        """
        Parse update instructions from natural language text.
        
        Args:
            text: Natural language update instructions
            
        Returns:
            Dictionary with fields to update
        """
        update_data = {}
        
        # Extract budget changes
        budget_match = re.search(r'(?:budget|price|cost).*?\$?(\d+(?:,\d{3})*)', text, re.IGNORECASE)
        if budget_match:
            try:
                update_data['budget'] = float(budget_match.group(1).replace(',', ''))
            except:
                pass
        
        # Extract date changes
        if 'extend' in text.lower() or 'longer' in text.lower():
            # This would need current end date to calculate, handled by AI parsing
            pass
        
        # Extract number of people changes
        people_match = re.search(r'(\d+)\s+(?:people|person)', text, re.IGNORECASE)
        if people_match:
            update_data['numberOfPeople'] = int(people_match.group(1))
        
        # Extract destination changes
        dest_match = re.search(r'(?:to|change.*?to)\s+([A-Z][a-zA-Z\s,]+?)(?:,|\.|$)', text, re.IGNORECASE)
        if dest_match:
            update_data['destination'] = dest_match.group(1).strip()
        
        return update_data
    
    def get_bookings(
        self,
        search: Optional[str] = None,
        status: Optional[str] = None,
        guideId: Optional[str] = None,
        touristId: Optional[str] = None,
        minPrice: Optional[float] = None,
        maxPrice: Optional[float] = None,
        startDateFrom: Optional[str] = None,
        startDateTo: Optional[str] = None,
        sortBy: str = 'createdAt',
        sortOrder: str = 'desc',
        page: int = 1,
        limit: int = 10
    ) -> Dict[str, Any]:
        """Get bookings with filters and pagination"""
        try:
            filters = {}
            if search:
                filters['search'] = search
            if status:
                filters['status'] = status
            if guideId:
                filters['guideId'] = guideId
            if touristId:
                filters['touristId'] = touristId
            if minPrice is not None:
                filters['minPrice'] = minPrice
            if maxPrice is not None:
                filters['maxPrice'] = maxPrice
            if startDateFrom:
                filters['startDateFrom'] = startDateFrom
            if startDateTo:
                filters['startDateTo'] = startDateTo
            
            bookings, total = self.repository.get_bookings(
                filters=filters,
                sort_by=sortBy,
                sort_order=sortOrder,
                page=page,
                limit=limit
            )
            
            total_pages = (total + limit - 1) // limit
            
            return {
                'success': True,
                'code': 200,
                'data': bookings,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total,
                    'totalPages': total_pages,
                    'hasNextPage': page < total_pages,
                    'hasPreviousPage': page > 1
                }
            }
            
        except Exception as e:
            print(f"Error in get_bookings: {e}")
            raise
    
    def get_applications(
        self,
        requestId: str,
        status: Optional[str] = None,
        minPrice: Optional[float] = None,
        maxPrice: Optional[float] = None,
        sortBy: str = 'createdAt',
        sortOrder: str = 'desc',
        page: int = 1,
        limit: int = 10
    ) -> Dict[str, Any]:
        """Get applications for a tour request"""
        try:
            filters = {'requestId': requestId}
            if status:
                filters['status'] = status
            if minPrice is not None:
                filters['minPrice'] = minPrice
            if maxPrice is not None:
                filters['maxPrice'] = maxPrice
            
            applications, total = self.repository.get_applications(
                filters=filters,
                sort_by=sortBy,
                sort_order=sortOrder,
                page=page,
                limit=limit
            )
            
            total_pages = (total + limit - 1) // limit
            
            return {
                'success': True,
                'code': 200,
                'data': applications,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total,
                    'totalPages': total_pages,
                    'hasNextPage': page < total_pages,
                    'hasPreviousPage': page > 1
                }
            }
            
        except Exception as e:
            print(f"Error in get_applications: {e}")
            raise
    
    def accept_application(
        self,
        application_id: str,
        request_id: str
    ) -> Optional[Dict[str, Any]]:
        """Accept an application and create a booking"""
        try:
            # Get application
            application = self.repository.get_application(application_id)
            if not application:
                return None
            
            # Get tour request
            tour_request = self.repository.get_tour_request(request_id)
            if not tour_request:
                return None
            
            # Create booking
            booking_id = str(uuid.uuid4())
            booking = {
                'id': booking_id,
                'requestId': request_id,
                'touristId': tour_request['touristId'],
                'touristName': tour_request.get('touristName'),
                'guideId': application['guideId'],
                'guideName': application['guideName'],
                'title': tour_request['title'],
                'destination': tour_request['destination'],
                'startDate': tour_request['startDate'],
                'endDate': tour_request['endDate'],
                'status': 'upcoming',
                'agreedPrice': application['proposedPrice'],
                'numberOfPeople': tour_request['numberOfPeople'],
                'budget': tour_request['budget'],
                'tourType': tour_request['tourType'],
                'createdAt': datetime.utcnow(),
                'updatedAt': datetime.utcnow()
            }
            
            # Save booking
            self.repository.create_booking(booking)
            
            # Update application status
            self.repository.update_application(application_id, {'status': 'selected'})
            
            # Update tour request status
            self.repository.update_tour_request(request_id, {'status': 'booked'})
            
            return {
                'bookingId': booking_id,
                'requestId': request_id,
                'applicationId': application_id
            }
            
        except Exception as e:
            print(f"Error in accept_application: {e}")
            raise


# Global service instance
tourist_service = TouristService()

