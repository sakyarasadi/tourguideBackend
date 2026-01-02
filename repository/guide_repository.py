"""
Guide Repository
================
Data access layer for guide operations using Firebase Firestore.
Handles CRUD operations for guide profiles, applications, and bookings.
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from utils.firebase_client import firebase_client_manager


class GuideRepository:
    """
    Repository class for guide data operations.
    Provides methods to interact with Firebase Firestore for guide-related data.
    """
    
    def __init__(self):
        """Initialize the guide repository"""
        self.db = firebase_client_manager.db
    
    # ===== Application Operations =====
    
    def create_application(self, application: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new guide application in Firestore.
        Applications are stored as subcollections under tourRequests:
        tourRequests/{requestId}/applications/{applicationId}
        
        Args:
            application: Application data dictionary (must include requestId)
        
        Returns:
            Created application with metadata
        """
        try:
            if not self.db:
                raise Exception("Firestore client not available")
            
            application_id = application.get('id')
            request_id = application.get('requestId')
            
            if not application_id:
                raise ValueError("Application ID is required")
            if not request_id:
                raise ValueError("Request ID is required for nested application")
            
            # Reference to nested applications collection under tourRequests
            applications_ref = self.db.collection('tourRequests').document(request_id).collection('applications')
            
            # Convert datetime to Firestore timestamp
            if 'createdAt' in application and isinstance(application['createdAt'], datetime):
                from google.cloud.firestore import SERVER_TIMESTAMP
                application['createdAt'] = SERVER_TIMESTAMP
            if 'updatedAt' in application and isinstance(application['updatedAt'], datetime):
                from google.cloud.firestore import SERVER_TIMESTAMP
                application['updatedAt'] = SERVER_TIMESTAMP
            
            # Set document
            doc_ref = applications_ref.document(application_id)
            doc_ref.set(application)
            
            # Get the saved document back to get actual timestamps (not SERVER_TIMESTAMP)
            saved_doc = doc_ref.get()
            if saved_doc.exists:
                saved_data = saved_doc.to_dict()
                saved_data['id'] = saved_doc.id
                # Convert Firestore Timestamps to ISO format strings
                if 'createdAt' in saved_data and hasattr(saved_data['createdAt'], 'to_datetime'):
                    saved_data['createdAt'] = saved_data['createdAt'].to_datetime().isoformat() + 'Z'
                if 'updatedAt' in saved_data and hasattr(saved_data['updatedAt'], 'to_datetime'):
                    saved_data['updatedAt'] = saved_data['updatedAt'].to_datetime().isoformat() + 'Z'
                print(f"✅ Created application {application_id} in Firestore under request {request_id}")
                return saved_data
            else:
                # Fallback: return application with timestamps converted
                application['createdAt'] = datetime.utcnow().isoformat() + 'Z'
                application['updatedAt'] = datetime.utcnow().isoformat() + 'Z'
                print(f"✅ Created application {application_id} in Firestore under request {request_id}")
                return application
            
        except Exception as e:
            print(f"Error creating application in Firestore: {e}")
            raise
    
    def get_application(self, application_id: str, request_id: str = None) -> Optional[Dict[str, Any]]:
        """
        Get a single application by ID.
        If request_id is provided, searches in nested collection.
        Otherwise, searches all tourRequests for the application.
        
        Args:
            application_id: Application ID
            request_id: Optional request ID for nested lookup
        
        Returns:
            Application dictionary or None if not found
        """
        try:
            if not self.db:
                return None
            
            if request_id:
                # Direct nested collection lookup
                doc_ref = self.db.collection('tourRequests').document(request_id).collection('applications').document(application_id)
                doc = doc_ref.get()
                
                if doc.exists:
                    data = doc.to_dict()
                    data['id'] = doc.id
                    return data
            else:
                # Search through all tourRequests to find the application
                tour_requests = self.db.collection('tourRequests').stream()
                for tour_request in tour_requests:
                    app_ref = tour_request.reference.collection('applications').document(application_id)
                    app_doc = app_ref.get()
                    if app_doc.exists:
                        data = app_doc.to_dict()
                        data['id'] = app_doc.id
                        data['requestId'] = tour_request.id  # Add request ID
                        return data
            
            return None
            
        except Exception as e:
            print(f"Error getting application from Firestore: {e}")
            return None
    
    def get_applications(
        self,
        filters: Dict[str, Any],
        sort_by: str = 'createdAt',
        sort_order: str = 'desc',
        page: int = 1,
        limit: int = 10
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get applications with filters and pagination.
        Applications are stored as nested subcollections under tourRequests.
        
        Args:
            filters: Dictionary of filter criteria (guideId, requestId, status)
            sort_by: Field to sort by
            sort_order: 'asc' or 'desc'
            page: Page number
            limit: Items per page
        
        Returns:
            Tuple of (list of applications, total count)
        """
        try:
            if not self.db:
                return [], 0
            
            applications = []
            
            # If requestId is provided, query that specific request's applications
            if 'requestId' in filters:
                request_id = filters['requestId']
                query = self.db.collection('tourRequests').document(request_id).collection('applications')
                
                # Apply other filters
                if 'guideId' in filters:
                    query = query.where('guideId', '==', filters['guideId'])
                if 'status' in filters:
                    query = query.where('status', '==', filters['status'])
                
                docs = list(query.stream())
                for doc in docs:
                    data = doc.to_dict()
                    data['id'] = doc.id
                    data['requestId'] = request_id
                    applications.append(data)
            
            # If guideId is provided, search through all requests
            elif 'guideId' in filters:
                guide_id = filters['guideId']
                tour_requests = self.db.collection('tourRequests').stream()
                
                for tour_request in tour_requests:
                    apps_query = tour_request.reference.collection('applications').where('guideId', '==', guide_id)
                    
                    if 'status' in filters:
                        apps_query = apps_query.where('status', '==', filters['status'])
                    
                    apps_docs = list(apps_query.stream())
                    for app_doc in apps_docs:
                        data = app_doc.to_dict()
                        data['id'] = app_doc.id
                        data['requestId'] = tour_request.id
                        applications.append(data)
            
            else:
                # No specific filter - get all applications from all requests
                tour_requests = self.db.collection('tourRequests').stream()
                
                for tour_request in tour_requests:
                    apps_query = tour_request.reference.collection('applications')
                    
                    if 'status' in filters:
                        apps_query = apps_query.where('status', '==', filters['status'])
                    
                    apps_docs = list(apps_query.stream())
                    for app_doc in apps_docs:
                        data = app_doc.to_dict()
                        data['id'] = app_doc.id
                        data['requestId'] = tour_request.id
                        applications.append(data)
            
            # Sort applications
            applications.sort(
                key=lambda x: x.get(sort_by, ''),
                reverse=(sort_order.lower() == 'desc')
            )
            
            total = len(applications)
            
            # Apply pagination
            start_idx = (page - 1) * limit
            end_idx = start_idx + limit
            paginated = applications[start_idx:end_idx]
            
            return paginated, total
            
        except Exception as e:
            print(f"Error getting applications from Firestore: {e}")
            return [], 0
    
    def update_application(
        self,
        application_id: str,
        data: Dict[str, Any],
        request_id: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Update an application in nested subcollection.
        
        Args:
            application_id: Application ID
            data: Fields to update
            request_id: Request ID (required for nested structure)
        
        Returns:
            Updated application or None if not found
        """
        try:
            if not self.db:
                return None
            
            # First, find the application if request_id not provided
            if not request_id:
                # Search through all tourRequests to find the application
                tour_requests = self.db.collection('tourRequests').stream()
                for tour_request in tour_requests:
                    app_ref = tour_request.reference.collection('applications').document(application_id)
                    if app_ref.get().exists:
                        request_id = tour_request.id
                        break
                
                if not request_id:
                    return None
            
            doc_ref = self.db.collection('tourRequests').document(request_id).collection('applications').document(application_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return None
            
            # Convert datetime to Firestore timestamp
            if 'updatedAt' in data and isinstance(data['updatedAt'], datetime):
                from google.cloud.firestore import SERVER_TIMESTAMP
                data['updatedAt'] = SERVER_TIMESTAMP
            
            # Update document
            doc_ref.update(data)
            
            # Get updated document
            updated_doc = doc_ref.get()
            result = updated_doc.to_dict()
            result['id'] = updated_doc.id
            result['requestId'] = request_id
            # Convert Firestore Timestamps to ISO format strings
            if 'createdAt' in result and hasattr(result['createdAt'], 'to_datetime'):
                result['createdAt'] = result['createdAt'].to_datetime().isoformat() + 'Z'
            if 'updatedAt' in result and hasattr(result['updatedAt'], 'to_datetime'):
                result['updatedAt'] = result['updatedAt'].to_datetime().isoformat() + 'Z'
            
            print(f"✅ Updated application {application_id} in Firestore under request {request_id}")
            return result
            
        except Exception as e:
            print(f"Error updating application in Firestore: {e}")
            return None
    
    def delete_application(self, application_id: str, request_id: str = None) -> bool:
        """
        Delete an application from nested subcollection.
        
        Args:
            application_id: Application ID
            request_id: Request ID (if not provided, will search for it)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.db:
                return False
            
            # First, find the application if request_id not provided
            if not request_id:
                tour_requests = self.db.collection('tourRequests').stream()
                for tour_request in tour_requests:
                    app_ref = tour_request.reference.collection('applications').document(application_id)
                    if app_ref.get().exists:
                        request_id = tour_request.id
                        break
                
                if not request_id:
                    return False
            
            doc_ref = self.db.collection('tourRequests').document(request_id).collection('applications').document(application_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return False
            
            doc_ref.delete()
            print(f"✅ Deleted application {application_id} from Firestore under request {request_id}")
            return True
            
        except Exception as e:
            print(f"Error deleting application from Firestore: {e}")
            return False
    
    # ===== Guide Profile Operations =====
    
    def create_guide_profile(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a guide profile in Firestore.
        
        Args:
            profile: Guide profile data
        
        Returns:
            Created profile with metadata
        """
        try:
            if not self.db:
                raise Exception("Firestore client not available")
            
            guide_id = profile.get('id')
            if not guide_id:
                raise ValueError("Guide ID is required")
            
            # Reference to guides collection
            guides_ref = self.db.collection('guides')
            
            # Convert datetime to Firestore timestamp
            if 'createdAt' in profile and isinstance(profile['createdAt'], datetime):
                from google.cloud.firestore import SERVER_TIMESTAMP
                profile['createdAt'] = SERVER_TIMESTAMP
            if 'updatedAt' in profile and isinstance(profile['updatedAt'], datetime):
                from google.cloud.firestore import SERVER_TIMESTAMP
                profile['updatedAt'] = SERVER_TIMESTAMP
            
            # Set document
            guides_ref.document(guide_id).set(profile)
            
            print(f"✅ Created guide profile {guide_id} in Firestore")
            return profile
            
        except Exception as e:
            print(f"Error creating guide profile in Firestore: {e}")
            raise
    
    def get_guide_profile(self, guide_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a guide profile by ID.
        
        Args:
            guide_id: Guide ID
        
        Returns:
            Guide profile dictionary or None if not found
        """
        try:
            if not self.db:
                return None
            
            doc_ref = self.db.collection('guides').document(guide_id)
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                data['id'] = doc.id
                return data
            
            return None
            
        except Exception as e:
            print(f"Error getting guide profile from Firestore: {e}")
            return None
    
    def update_guide_profile(
        self,
        guide_id: str,
        data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Update a guide profile.
        
        Args:
            guide_id: Guide ID
            data: Fields to update
        
        Returns:
            Updated profile or None if not found
        """
        try:
            if not self.db:
                return None
            
            doc_ref = self.db.collection('guides').document(guide_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return None
            
            # Convert datetime to Firestore timestamp
            if 'updatedAt' in data and isinstance(data['updatedAt'], datetime):
                from google.cloud.firestore import SERVER_TIMESTAMP
                data['updatedAt'] = SERVER_TIMESTAMP
            
            # Update document
            doc_ref.update(data)
            
            # Get updated document
            updated_doc = doc_ref.get()
            result = updated_doc.to_dict()
            result['id'] = updated_doc.id
            
            print(f"✅ Updated guide profile {guide_id} in Firestore")
            return result
            
        except Exception as e:
            print(f"Error updating guide profile in Firestore: {e}")
            return None
    
    def get_all_guides(
        self,
        page: int = 1,
        limit: int = 10
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get all guide profiles with pagination.
        
        Args:
            page: Page number
            limit: Items per page
        
        Returns:
            Tuple of (list of guides, total count)
        """
        try:
            if not self.db:
                return [], 0
            
            query = self.db.collection('guides')
            
            # Get total count
            total = len(list(query.stream()))
            
            # Apply pagination
            offset = (page - 1) * limit
            query = query.limit(limit).offset(offset)
            
            # Execute query
            docs = query.stream()
            
            guides = []
            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id
                guides.append(data)
            
            return guides, total
            
        except Exception as e:
            print(f"Error getting guides from Firestore: {e}")
            return [], 0
    
    # ===== Booking Operations =====
    
    def get_booking(self, booking_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a single booking by ID.
        
        Args:
            booking_id: Booking ID
        
        Returns:
            Booking dictionary or None if not found
        """
        try:
            if not self.db:
                return None
            
            doc_ref = self.db.collection('bookings').document(booking_id)
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                data['id'] = doc.id
                return data
            
            return None
            
        except Exception as e:
            print(f"Error getting booking from Firestore: {e}")
            return None

