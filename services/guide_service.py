"""
Guide Service
=============
Service layer for guide operations including applications, bookings, and profile management.
Handles business logic and coordinates with repositories and Firebase.
"""

import uuid
import json
import re
from datetime import datetime
from typing import Dict, Any, Optional, List
from flask import current_app
from repository.guide_repository import GuideRepository


class GuideService:
    """
    Service class for guide operations.
    Provides high-level methods for managing applications, bookings, and guide profiles.
    """
    
    def __init__(self):
        """Initialize the guide service with repository"""
        self.repository = GuideRepository()
    
    def apply_to_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply to a tour request.
        
        Args:
            data: Application data including requestId, guideId, proposedPrice, etc.
        
        Returns:
            Created application dictionary
        """
        try:
            # Use guideId as application ID (matches frontend pattern)
            application_id = data.get('id') or data.get('guideId')
            
            # Get guide details from users collection
            guide_email = data.get('guideEmail', '')
            guide_name = data.get('guideName', '')
            
            if not guide_email or not guide_name:
                try:
                    from utils.firebase_client import firebase_client_manager
                    user_doc = firebase_client_manager.db.collection('users').document(data['guideId']).get()
                    if user_doc.exists:
                        user_data = user_doc.to_dict()
                        if not guide_email:
                            guide_email = user_data.get('email', '')
                        if not guide_name:
                            first_name = user_data.get('firstName', '')
                            last_name = user_data.get('lastName', '')
                            guide_name = f"{first_name} {last_name}".strip() or user_data.get('email', '').split('@')[0]
                except Exception as e:
                    print(f"Error fetching guide user details: {e}")
                    if not guide_name:
                        guide_name = data.get('guideName', 'Unknown Guide')
            
            # Prepare application document
            application = {
                'id': application_id,
                'requestId': data['requestId'],
                'guideId': data['guideId'],
                'guideEmail': guide_email,
                'guideName': guide_name,
                'proposedPrice': float(data.get('proposedPrice', 0)),
                'coverLetter': data.get('coverLetter', ''),
                'status': 'pending',
                'createdAt': datetime.utcnow(),
                'updatedAt': datetime.utcnow()
            }
            
            # Add tour request details if provided
            if data.get('tourTitle'):
                application['tourTitle'] = data['tourTitle']
            if data.get('destination'):
                application['destination'] = data['destination']
            if data.get('startDate'):
                application['startDate'] = data['startDate']
            if data.get('endDate'):
                application['endDate'] = data['endDate']
            if data.get('tourType'):
                application['tourType'] = data['tourType']
            if data.get('touristId'):
                application['touristId'] = data['touristId']
            if data.get('touristName'):
                application['touristName'] = data['touristName']
            if data.get('touristBudget') is not None:
                application['touristBudget'] = float(data['touristBudget'])
            
            # Save to Firebase
            created = self.repository.create_application(application)
            
            # Update tour request application count
            self._increment_application_count(data['requestId'])
            
            return created
            
        except Exception as e:
            print(f"Error in apply_to_request: {e}")
            raise
    
    def get_my_applications(
        self,
        guideId: str,
        status: Optional[str] = None,
        requestId: Optional[str] = None,
        page: int = 1,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Get guide's applications with filters and pagination.
        
        Args:
            guideId: Guide identifier
            status: Filter by status
            requestId: Filter by specific request
            page: Page number
            limit: Items per page
        
        Returns:
            Dictionary with paginated results
        """
        try:
            filters = {'guideId': guideId}
            if status:
                filters['status'] = status
            if requestId:
                filters['requestId'] = requestId
            
            applications, total = self.repository.get_applications(
                filters=filters,
                sort_by='createdAt',
                sort_order='desc',
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
            print(f"Error in get_my_applications: {e}")
            raise
    
    def get_application(self, application_id: str, request_id: str = None) -> Optional[Dict[str, Any]]:
        """Get a single application by ID"""
        try:
            return self.repository.get_application(application_id, request_id)
        except Exception as e:
            print(f"Error in get_application: {e}")
            raise
    
    def update_application(
        self,
        application_id: str,
        data: Dict[str, Any],
        request_id: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Update a guide application.
        
        Args:
            application_id: Application ID
            data: Fields to update
            request_id: Optional request ID for faster lookup
        
        Returns:
            Updated application or None if not found
        """
        try:
            # Add updated timestamp
            data['updatedAt'] = datetime.utcnow()
            
            return self.repository.update_application(application_id, data, request_id)
            
        except Exception as e:
            print(f"Error in update_application: {e}")
            raise
    
    def withdraw_application(self, application_id: str, request_id: str = None) -> bool:
        """
        Withdraw a guide application.
        
        Args:
            application_id: Application ID
            request_id: Optional request ID for faster lookup
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Update status to withdrawn
            result = self.repository.update_application(
                application_id,
                {
                    'status': 'withdrawn',
                    'updatedAt': datetime.utcnow()
                },
                request_id
            )
            return result is not None
            
        except Exception as e:
            print(f"Error in withdraw_application: {e}")
            raise
    
    def get_booking(self, booking_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a single booking by ID.
        
        Args:
            booking_id: Booking ID
        
        Returns:
            Booking dictionary or None if not found
        """
        try:
            return self.repository.get_booking(booking_id)
        except Exception as e:
            print(f"Error in get_booking: {e}")
            raise
    
    def get_guide_profile(self, guide_id: str) -> Optional[Dict[str, Any]]:
        """
        Get guide profile information.
        
        Args:
            guide_id: Guide identifier
        
        Returns:
            Guide profile dictionary or None if not found
        """
        try:
            return self.repository.get_guide_profile(guide_id)
        except Exception as e:
            print(f"Error in get_guide_profile: {e}")
            raise
    
    def create_guide_profile(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a guide profile.
        
        Args:
            data: Guide profile data
        
        Returns:
            Created guide profile
        """
        try:
            guide_id = data.get('id') or str(uuid.uuid4())
            
            profile = {
                'id': guide_id,
                'name': data.get('name', ''),
                'email': data.get('email', ''),
                'phone': data.get('phone', ''),
                'bio': data.get('bio', ''),
                'experience': data.get('experience', ''),
                'specializations': data.get('specializations', []),
                'languages': data.get('languages', []),
                'certifications': data.get('certifications', []),
                'rating': 0.0,
                'totalTours': 0,
                'createdAt': datetime.utcnow(),
                'updatedAt': datetime.utcnow()
            }
            
            return self.repository.create_guide_profile(profile)
            
        except Exception as e:
            print(f"Error in create_guide_profile: {e}")
            raise
    
    def update_guide_profile(
        self,
        guide_id: str,
        data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Update guide profile.
        
        Args:
            guide_id: Guide identifier
            data: Fields to update
        
        Returns:
            Updated profile or None if not found
        """
        try:
            data['updatedAt'] = datetime.utcnow()
            return self.repository.update_guide_profile(guide_id, data)
        except Exception as e:
            print(f"Error in update_guide_profile: {e}")
            raise
    
    def _increment_application_count(self, request_id: str):
        """
        Increment the application count for a tour request.
        
        Args:
            request_id: Tour request ID
        """
        try:
            from services.tourist_service import tourist_service
            
            # Get current request
            tour_request = tourist_service.get_tour_request(request_id)
            if tour_request:
                current_count = tour_request.get('applicationCount', 0)
                tourist_service.update_tour_request(
                    request_id,
                    {'applicationCount': current_count + 1}
                )
        except Exception as e:
            print(f"Warning: Could not increment application count: {e}")
    
    def parse_application_text(self, text: str) -> Dict[str, Any]:
        """
        Parse natural language application text into structured data.
        This is a fallback parser if AI parsing fails.
        
        Args:
            text: Natural language description of the application
        
        Returns:
            Dictionary with structured application data
        """
        # Basic regex patterns for extraction
        patterns = {
            'price': r'\$?(\d+(?:,\d{3})*(?:\.\d{2})?)',
            'experience': r'(\d+)\s+(?:years?|yrs?)\s+(?:of\s+)?(?:experience|exp)',
            'languages': r'(?:speak|language[s]?|fluent in)\s+([A-Z][a-z]+(?:,?\s+and\s+[A-Z][a-z]+)*)',
        }
        
        extracted = {}
        
        # Extract proposed price
        price_matches = re.findall(patterns['price'], text)
        if price_matches:
            try:
                price_str = price_matches[0].replace(',', '')
                extracted['proposedPrice'] = float(price_str)
            except:
                pass
        
        # Extract experience years
        exp_match = re.search(patterns['experience'], text, re.IGNORECASE)
        if exp_match:
            years = int(exp_match.group(1))
            extracted['experience'] = f"{years} years of experience"
        
        # Extract languages
        lang_match = re.search(patterns['languages'], text, re.IGNORECASE)
        if lang_match:
            langs_str = lang_match.group(1)
            extracted['languages'] = [l.strip() for l in re.split(r'\s+and\s+|\s*,\s*', langs_str)]
        
        # Extract specializations (keywords)
        specializations = []
        keywords = ['cultural', 'adventure', 'historical', 'food', 'wine', 'nature', 'museum', 'art']
        for keyword in keywords:
            if keyword.lower() in text.lower():
                specializations.append(keyword)
        if specializations:
            extracted['specializations'] = specializations
        
        # Set defaults
        result = {
            'proposedPrice': extracted.get('proposedPrice', 0),
            'coverLetter': text,
            'experience': extracted.get('experience', ''),
            'specializations': extracted.get('specializations', []),
            'languages': extracted.get('languages', ['English'])
        }
        
        return result


# Global service instance
guide_service = GuideService()

