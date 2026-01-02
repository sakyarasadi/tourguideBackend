"""
Tourist Repository
==================
Repository for managing tourist operations in Firebase Firestore.
Handles tour requests, bookings, and applications.
"""

from utils.firebase_client import firebase_client_manager
from datetime import datetime
from typing import List, Optional, Dict, Any
from google.cloud.firestore_v1 import SERVER_TIMESTAMP
from google.cloud import firestore


class TouristRepository:
    """
    Repository for tourist operations in Firestore.
    Provides CRUD operations for tour requests, bookings, and applications.
    """
    
    def __init__(self):
        """Initialize repository with Firestore database connection"""
        self.db = firebase_client_manager.db
        self._requests_collection = None
        self._bookings_collection = None
        self._applications_collection = None
    
    @property
    def requests_collection(self):
        """Get tour requests collection"""
        if self._requests_collection is None:
            self._requests_collection = self.db.collection('tourRequests')
        return self._requests_collection
    
    @property
    def bookings_collection(self):
        """Get bookings collection"""
        if self._bookings_collection is None:
            self._bookings_collection = self.db.collection('bookings')
        return self._bookings_collection
    
    @property
    def applications_collection(self):
        """Get applications collection"""
        if self._applications_collection is None:
            self._applications_collection = self.db.collection('applications')
        return self._applications_collection
    
    # ===== Tour Requests =====
    
    def get_tour_requests(
        self,
        filters: Dict[str, Any] = None,
        sort_by: str = 'createdAt',
        sort_order: str = 'desc',
        page: int = 1,
        limit: int = 10
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        Get tour requests with filters, sorting, and pagination.
        
        Returns:
            Tuple of (list of requests, total count)
        """
        try:
            # Fetch all documents first to avoid index requirements
            # We'll do filtering and sorting client-side
            all_docs = list(self.requests_collection.stream())
            
            # Convert to dictionaries first
            all_requests = []
            for doc in all_docs:
                data = doc.to_dict()
                data['id'] = doc.id
                # Convert timestamps to ISO format
                if 'createdAt' in data:
                    if hasattr(data['createdAt'], 'isoformat'):
                        data['createdAt'] = data['createdAt'].isoformat() + 'Z'
                    elif hasattr(data['createdAt'], 'timestamp'):
                        # Handle Firestore Timestamp
                        dt = data['createdAt'].to_datetime()
                        data['createdAt'] = dt.isoformat() + 'Z'
                if 'updatedAt' in data:
                    if hasattr(data['updatedAt'], 'isoformat'):
                        data['updatedAt'] = data['updatedAt'].isoformat() + 'Z'
                    elif hasattr(data['updatedAt'], 'timestamp'):
                        # Handle Firestore Timestamp
                        dt = data['updatedAt'].to_datetime()
                        data['updatedAt'] = dt.isoformat() + 'Z'
                all_requests.append(data)
            
            # Apply filters client-side
            filtered_requests = all_requests
            if filters:
                if filters.get('status'):
                    filtered_requests = [
                        req for req in filtered_requests
                        if req.get('status') == filters['status']
                    ]
                if filters.get('tourType'):
                    filtered_requests = [
                        req for req in filtered_requests
                        if req.get('tourType') == filters['tourType']
                    ]
                if filters.get('touristId'):
                    filtered_requests = [
                        req for req in filtered_requests
                        if req.get('touristId') == filters['touristId']
                    ]
                if filters.get('destination'):
                    # Exact destination matching (case-insensitive, supports partial match)
                    destination_term = filters['destination'].lower().strip()
                    filtered_requests = [
                        req for req in filtered_requests
                        if destination_term in req.get('destination', '').lower()
                    ]
                elif filters.get('search'):
                    # Only use search if destination is not specified
                    # This prevents search from overriding destination filtering
                    search_term = filters['search'].lower()
                    filtered_requests = [
                        req for req in filtered_requests
                        if search_term in req.get('title', '').lower() or
                        search_term in req.get('destination', '').lower() or
                        search_term in req.get('description', '').lower()
                    ]
                if filters.get('minBudget') is not None:
                    filtered_requests = [
                        req for req in filtered_requests
                        if req.get('budget', 0) >= filters['minBudget']
                    ]
                if filters.get('maxBudget') is not None:
                    filtered_requests = [
                        req for req in filtered_requests
                        if req.get('budget', float('inf')) <= filters['maxBudget']
                    ]
                if filters.get('minPeople') is not None:
                    filtered_requests = [
                        req for req in filtered_requests
                        if req.get('numberOfPeople', 0) >= filters['minPeople']
                    ]
                if filters.get('maxPeople') is not None:
                    filtered_requests = [
                        req for req in filtered_requests
                        if req.get('numberOfPeople', float('inf')) <= filters['maxPeople']
                    ]
                if filters.get('startDateFrom'):
                    filtered_requests = [
                        req for req in filtered_requests
                        if req.get('startDate', '') >= filters['startDateFrom']
                    ]
                if filters.get('startDateTo'):
                    filtered_requests = [
                        req for req in filtered_requests
                        if req.get('startDate', '') <= filters['startDateTo']
                    ]
                if filters.get('requirements'):
                    # Filter by requirements (e.g., wheelchair-accessible)
                    requirements_term = filters['requirements'].lower()
                    filtered_requests = [
                        req for req in filtered_requests
                        if requirements_term in req.get('requirements', '').lower() or
                        requirements_term in req.get('description', '').lower()
                    ]
            
            # Apply sorting client-side
            reverse_order = (sort_order == 'desc')
            try:
                if sort_by == 'createdAt':
                    filtered_requests.sort(
                        key=lambda x: x.get('createdAt', ''),
                        reverse=reverse_order
                    )
                elif sort_by == 'budget':
                    filtered_requests.sort(
                        key=lambda x: x.get('budget', 0),
                        reverse=reverse_order
                    )
                elif sort_by == 'startDate':
                    filtered_requests.sort(
                        key=lambda x: x.get('startDate', ''),
                        reverse=reverse_order
                    )
                else:
                    # Default sorting by createdAt
                    filtered_requests.sort(
                        key=lambda x: x.get('createdAt', ''),
                        reverse=reverse_order
                    )
            except Exception as sort_error:
                print(f"Error sorting: {sort_error}, using default sort")
                filtered_requests.sort(
                    key=lambda x: x.get('createdAt', ''),
                    reverse=reverse_order
                )
            
            total = len(filtered_requests)
            
            # Pagination
            start_idx = (page - 1) * limit
            end_idx = start_idx + limit
            paginated_requests = filtered_requests[start_idx:end_idx]
            
            return paginated_requests, total
            
        except Exception as e:
            print(f"Error getting tour requests: {e}")
            import traceback
            traceback.print_exc()
            return [], 0
    
    def get_tour_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get a single tour request by ID"""
        try:
            doc = self.requests_collection.document(request_id).get()
            if doc.exists:
                data = doc.to_dict()
                data['id'] = doc.id
                if 'createdAt' in data and hasattr(data['createdAt'], 'isoformat'):
                    data['createdAt'] = data['createdAt'].isoformat() + 'Z'
                if 'updatedAt' in data and hasattr(data['updatedAt'], 'isoformat'):
                    data['updatedAt'] = data['updatedAt'].isoformat() + 'Z'
                return data
            return None
        except Exception as e:
            print(f"Error getting tour request: {e}")
            return None
    
    def create_tour_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new tour request"""
        try:
            doc_ref = self.requests_collection.document(data['id'])
            # Convert datetime objects to SERVER_TIMESTAMP if needed
            doc_data = {**data}
            if 'createdAt' not in doc_data or isinstance(doc_data['createdAt'], datetime):
                doc_data['createdAt'] = SERVER_TIMESTAMP
            if 'updatedAt' not in doc_data or isinstance(doc_data['updatedAt'], datetime):
                doc_data['updatedAt'] = SERVER_TIMESTAMP
            
            doc_ref.set(doc_data)
            
            # Get the created document
            created_doc = doc_ref.get()
            result = created_doc.to_dict()
            result['id'] = created_doc.id
            return result
            
        except Exception as e:
            print(f"Error creating tour request: {e}")
            raise
    
    def update_tour_request(
        self,
        request_id: str,
        data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update a tour request"""
        try:
            doc_ref = self.requests_collection.document(request_id)
            
            # Add updated timestamp
            update_data = {**data}
            if 'updatedAt' not in update_data or isinstance(update_data.get('updatedAt'), datetime):
                update_data['updatedAt'] = SERVER_TIMESTAMP
            
            doc_ref.update(update_data)
            
            # Get updated document
            updated_doc = doc_ref.get()
            if updated_doc.exists:
                result = updated_doc.to_dict()
                result['id'] = updated_doc.id
                return result
            return None
            
        except Exception as e:
            print(f"Error updating tour request: {e}")
            raise
    
    def cancel_tour_request(self, request_id: str) -> bool:
        """Cancel a tour request (update status to cancelled)"""
        try:
            doc_ref = self.requests_collection.document(request_id)
            doc_ref.update({
                'status': 'cancelled',
                'updatedAt': SERVER_TIMESTAMP
            })
            return True
        except Exception as e:
            print(f"Error cancelling tour request: {e}")
            return False
    
    # ===== Bookings =====
    
    def get_bookings(
        self,
        filters: Dict[str, Any] = None,
        sort_by: str = 'createdAt',
        sort_order: str = 'desc',
        page: int = 1,
        limit: int = 10
    ) -> tuple[List[Dict[str, Any]], int]:
        """Get bookings with filters and pagination - uses client-side sorting to avoid index requirements"""
        try:
            # Build query with only where clauses (no order_by to avoid index requirements)
            query = self.bookings_collection
            
            if filters:
                if filters.get('status'):
                    query = query.where('status', '==', filters['status'])
                if filters.get('guideId'):
                    print(f"🔍 Filtering bookings by guideId: {filters['guideId']}")
                    query = query.where('guideId', '==', filters['guideId'])
                if filters.get('touristId'):
                    print(f"🔍 Filtering bookings by touristId: {filters['touristId']}")
                    query = query.where('touristId', '==', filters['touristId'])
            
            # Fetch all matching documents
            all_docs = list(query.stream())
            print(f"📊 Found {len(all_docs)} booking document(s) matching filters")
            
            # Client-side filtering for price range
            if filters:
                if filters.get('minPrice') is not None:
                    all_docs = [
                        doc for doc in all_docs
                        if doc.to_dict().get('agreedPrice', 0) >= filters['minPrice']
                    ]
                if filters.get('maxPrice') is not None:
                    all_docs = [
                        doc for doc in all_docs
                        if doc.to_dict().get('agreedPrice', float('inf')) <= filters['maxPrice']
                    ]
            
            # Client-side filtering for date range
            if filters:
                if filters.get('startDateFrom'):
                    all_docs = [
                        doc for doc in all_docs
                        if doc.to_dict().get('startDate', '') >= filters['startDateFrom']
                    ]
                if filters.get('startDateTo'):
                    all_docs = [
                        doc for doc in all_docs
                        if doc.to_dict().get('startDate', '') <= filters['startDateTo']
                    ]
            
            # Convert to list of dicts and handle timestamps
            bookings_list = []
            for doc in all_docs:
                data = doc.to_dict()
                data['id'] = doc.id
                # Convert Firestore Timestamps to ISO format strings
                if 'createdAt' in data:
                    if hasattr(data['createdAt'], 'isoformat'):
                        data['createdAt'] = data['createdAt'].isoformat() + 'Z'
                    elif hasattr(data['createdAt'], 'timestamp'):
                        # Handle SERVER_TIMESTAMP placeholder
                        from datetime import datetime
                        data['createdAt'] = datetime.now().isoformat() + 'Z'
                if 'updatedAt' in data:
                    if hasattr(data['updatedAt'], 'isoformat'):
                        data['updatedAt'] = data['updatedAt'].isoformat() + 'Z'
                    elif hasattr(data['updatedAt'], 'timestamp'):
                        from datetime import datetime
                        data['updatedAt'] = datetime.now().isoformat() + 'Z'
                bookings_list.append(data)
            
            # Client-side sorting
            reverse_order = (sort_order == 'desc')
            try:
                bookings_list.sort(
                    key=lambda x: self._get_sort_value(x, sort_by),
                    reverse=reverse_order
                )
            except Exception as sort_error:
                print(f"Warning: Error sorting bookings: {sort_error}. Using default order.")
                # Fallback: sort by createdAt if available
                try:
                    bookings_list.sort(
                        key=lambda x: x.get('createdAt', ''),
                        reverse=reverse_order
                    )
                except:
                    pass
            
            total = len(bookings_list)
            
            # Pagination
            start_idx = (page - 1) * limit
            end_idx = start_idx + limit
            paginated_bookings = bookings_list[start_idx:end_idx]
            
            print(f"📊 After processing: total={total}, page={page}, limit={limit}, returning={len(paginated_bookings)} bookings")
            if paginated_bookings:
                print(f"📊 First booking sample: id={paginated_bookings[0].get('id')}, title={paginated_bookings[0].get('title')}")
            
            return paginated_bookings, total
            
        except Exception as e:
            print(f"Error getting bookings: {e}")
            return [], 0
    
    def _get_sort_value(self, item: Dict[str, Any], sort_by: str) -> Any:
        """Helper to get sort value from booking item"""
        value = item.get(sort_by)
        if value is None:
            return '' if sort_by == 'createdAt' else 0
        # Handle timestamp strings
        if sort_by in ['createdAt', 'updatedAt', 'startDate', 'endDate']:
            return value if isinstance(value, str) else str(value)
        return value
    
    def create_booking(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new booking"""
        try:
            doc_ref = self.bookings_collection.document(data['id'])
            doc_data = {**data}
            if 'createdAt' not in doc_data or isinstance(doc_data['createdAt'], datetime):
                doc_data['createdAt'] = SERVER_TIMESTAMP
            if 'updatedAt' not in doc_data or isinstance(doc_data['updatedAt'], datetime):
                doc_data['updatedAt'] = SERVER_TIMESTAMP
            
            doc_ref.set(doc_data)
            
            created_doc = doc_ref.get()
            result = created_doc.to_dict()
            result['id'] = created_doc.id
            return result
            
        except Exception as e:
            print(f"Error creating booking: {e}")
            raise
    
    # ===== Applications =====
    
    def get_applications(
        self,
        filters: Dict[str, Any] = None,
        sort_by: str = 'createdAt',
        sort_order: str = 'desc',
        page: int = 1,
        limit: int = 10
    ) -> tuple[List[Dict[str, Any]], int]:
        """Get applications with filters and pagination"""
        try:
            query = self.applications_collection
            
            if filters and filters.get('requestId'):
                query = query.where('requestId', '==', filters['requestId'])
            if filters and filters.get('status'):
                query = query.where('status', '==', filters['status'])
            
            direction = firestore.Query.DESCENDING if sort_order == 'desc' else firestore.Query.ASCENDING
            query = query.order_by(sort_by, direction=direction)
            
            all_docs = list(query.stream())
            
            # Client-side filtering for price
            if filters:
                if filters.get('minPrice') is not None:
                    all_docs = [
                        doc for doc in all_docs
                        if doc.to_dict().get('proposedPrice', 0) >= filters['minPrice']
                    ]
                if filters.get('maxPrice') is not None:
                    all_docs = [
                        doc for doc in all_docs
                        if doc.to_dict().get('proposedPrice', float('inf')) <= filters['maxPrice']
                    ]
            
            total = len(all_docs)
            
            # Pagination
            start_idx = (page - 1) * limit
            end_idx = start_idx + limit
            paginated_docs = all_docs[start_idx:end_idx]
            
            applications = []
            for doc in paginated_docs:
                data = doc.to_dict()
                data['id'] = doc.id
                if 'createdAt' in data and hasattr(data['createdAt'], 'isoformat'):
                    data['createdAt'] = data['createdAt'].isoformat() + 'Z'
                if 'updatedAt' in data and hasattr(data['updatedAt'], 'isoformat'):
                    data['updatedAt'] = data['updatedAt'].isoformat() + 'Z'
                applications.append(data)
            
            return applications, total
            
        except Exception as e:
            print(f"Error getting applications: {e}")
            return [], 0
    
    def get_application(self, application_id: str) -> Optional[Dict[str, Any]]:
        """Get a single application by ID"""
        try:
            doc = self.applications_collection.document(application_id).get()
            if doc.exists:
                data = doc.to_dict()
                data['id'] = doc.id
                return data
            return None
        except Exception as e:
            print(f"Error getting application: {e}")
            return None
    
    def update_application(
        self,
        application_id: str,
        data: Dict[str, Any]
    ) -> bool:
        """Update an application"""
        try:
            doc_ref = self.applications_collection.document(application_id)
            update_data = {**data}
            update_data['updatedAt'] = SERVER_TIMESTAMP
            doc_ref.update(update_data)
            return True
        except Exception as e:
            print(f"Error updating application: {e}")
            return False

