"""
Guide Query Parser
==================
Service for parsing natural language queries from guides browsing tour requests.
Handles filter extraction, validation, and question generation.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import re


def parse_browse_query(text: str) -> Dict[str, Any]:
    """
    Parse natural language query into structured filters for browsing tour requests.
    
    Args:
        text: Natural language query from guide
        
    Returns:
        Dictionary with extracted filters
    """
    text_lower = text.lower()
    filters = {}
    
    # Extract destination/location
    # Improved patterns to catch destinations like "Japan", "Sri Lanka", "Paris, France", etc.
    location_patterns = [
        # Pattern for "find tours in Japan" or "tours in Japan"
        r'(?:tours?|find|search|show|browse|looking for).*?(?:in|to|at|near|for)\s+([A-Z][a-zA-Z\s,]+?)(?:\.|,|$|\s+(?:for|with|starting|from|tour|tours|that|with|please))',
        # Pattern for "in Japan" or "to Japan"
        r'(?:in|to|at|near|for)\s+([A-Z][a-zA-Z\s,]+?)(?:\.|,|$|\s+(?:for|with|starting|from|tour|tours))',
        # Common country/city names (case-insensitive word boundary)
        r'\b(japan|sri lanka|india|thailand|france|paris|london|tokyo|bangkok|singapore|malaysia|indonesia|vietnam|china|korea|australia|new zealand|usa|united states|canada|mexico|brazil|argentina|chile|peru|egypt|morocco|south africa|kenya|tanzania|zimbabwe|botswana|namibia|madagascar|mauritius|seychelles|maldives|dubai|uae|qatar|oman|jordan|israel|turkey|greece|italy|spain|portugal|germany|austria|switzerland|netherlands|belgium|denmark|sweden|norway|finland|iceland|ireland|scotland|england|wales|russia|poland)\b',
        # Sri Lankan cities
        r'\b(kandy|nuwara eliya|colombo|galle|anuradhapura|sigiriya|ella|mirissa|polonnaruwa|negombo|trincomalee|jaffna|bentota|dambulla|hikkaduwa|unawatuna|matara|ratnapura)\b',
    ]
    
    for pattern in location_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            destination = match.group(1).strip() if match.groups() else match.group(0).strip()
            # Clean up common words
            destination = re.sub(r'\s+(for|with|starting|from|tour|tours)', '', destination, flags=re.IGNORECASE).strip()
            # Capitalize first letter of each word
            if destination:
                destination = ' '.join(word.capitalize() for word in destination.split())
            if destination and len(destination) > 2:
                filters['destination'] = destination
                # Only set search if destination is a single word or short phrase
                if len(destination.split()) <= 3:
                    filters['search'] = destination
                break
    
    # Extract budget filters
    # Pattern for minimum budget
    min_budget_match = re.search(r'(?:budget|price|cost).*?(?:above|over|more than|minimum|min)\s*\$?(\d+(?:,\d{3})*)', text_lower)
    if min_budget_match:
        try:
            filters['minBudget'] = float(min_budget_match.group(1).replace(',', ''))
        except:
            pass
    
    # Pattern for maximum budget
    max_budget_match = re.search(r'(?:budget|price|cost).*?(?:below|under|less than|maximum|max)\s*\$?(\d+(?:,\d{3})*)', text_lower)
    if max_budget_match:
        try:
            filters['maxBudget'] = float(max_budget_match.group(1).replace(',', ''))
        except:
            pass
    
    # Pattern for budget range
    budget_range_match = re.search(r'(?:budget|price|cost).*?\$?(\d+(?:,\d{3})*)\s*(?:to|-)\s*\$?(\d+(?:,\d{3})*)', text_lower)
    if budget_range_match and 'minBudget' not in filters and 'maxBudget' not in filters:
        try:
            filters['minBudget'] = float(budget_range_match.group(1).replace(',', ''))
            filters['maxBudget'] = float(budget_range_match.group(2).replace(',', ''))
        except:
            pass
    
    # Extract tour type
    tour_types = ['cultural', 'adventure', 'beach', 'mountain', 'city', 'historical', 
                  'religious', 'food', 'wine', 'nature', 'safari', 'heritage', 'family']
    for tour_type in tour_types:
        if tour_type in text_lower:
            filters['tourType'] = tour_type
            break
    
    # Extract date filters
    date_patterns = [
        r'(?:next week|this week|upcoming week)',
        r'(?:june|july|august|september|october|november|december|january|february|march|april|may)\s+(\d{4})',
        r'(\d{4})-(\d{2})',  # YYYY-MM
        r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})',  # MM/DD/YYYY
    ]
    
    for pattern in date_patterns:
        if 'next week' in text_lower or 'upcoming week' in text_lower:
            # Calculate next week dates
            today = datetime.now()
            from datetime import timedelta
            days_until_next_monday = (7 - today.weekday()) % 7
            if days_until_next_monday == 0:
                days_until_next_monday = 7
            next_monday = today + timedelta(days=days_until_next_monday)
            filters['startDateFrom'] = next_monday.strftime('%Y-%m-%d')
            filters['startDateTo'] = (next_monday + timedelta(days=7)).strftime('%Y-%m-%d')
            break
        elif 'june' in text_lower or 'july' in text_lower:
            # Extract year if mentioned
            year_match = re.search(r'(\d{4})', text)
            year = year_match.group(1) if year_match else str(datetime.now().year)
            month_map = {
                'january': '01', 'february': '02', 'march': '03', 'april': '04',
                'may': '05', 'june': '06', 'july': '07', 'august': '08',
                'september': '09', 'october': '10', 'november': '11', 'december': '12'
            }
            for month_name, month_num in month_map.items():
                if month_name in text_lower:
                    filters['startDateFrom'] = f"{year}-{month_num}-01"
                    # Get last day of month (approximate)
                    if month_num in ['01', '03', '05', '07', '08', '10', '12']:
                        filters['startDateTo'] = f"{year}-{month_num}-31"
                    elif month_num == '02':
                        filters['startDateTo'] = f"{year}-{month_num}-28"
                    else:
                        filters['startDateTo'] = f"{year}-{month_num}-30"
                    break
    
    # Extract language requirements
    languages = ['english', 'sinhala', 'tamil', 'french', 'german', 'spanish', 'chinese', 'japanese']
    extracted_languages = []
    for lang in languages:
        if lang in text_lower:
            extracted_languages.append(lang.capitalize())
    if extracted_languages:
        filters['languages'] = extracted_languages
    
    # Extract group size
    people_patterns = [
        r'(\d+)\s+(?:people|person|travelers|tourists)',
        r'(?:for|with)\s+(\d+)',
        r'(?:solo|single)\s+traveler',
    ]
    for pattern in people_patterns:
        match = re.search(pattern, text_lower)
        if match:
            if 'solo' in pattern or 'single' in pattern:
                filters['numberOfPeople'] = 1
            else:
                try:
                    filters['numberOfPeople'] = int(match.group(1))
                except:
                    pass
            break
    
    # Extract accessibility/special requirements
    if any(term in text_lower for term in ['wheelchair', 'accessible', 'accessibility', 'disability', 'special needs']):
        filters['requirements'] = 'accessibility'
    
    # Extract urgency
    if any(term in text_lower for term in ['urgent', 'soon', 'last minute', 'asap', 'immediately']):
        filters['urgent'] = True
    
    # Extract application status keywords
    if any(term in text_lower for term in ['no applications', 'no competition', 'least competition', "haven't applied"]):
        filters['applicationStatus'] = 'none'
    
    return filters


def validate_browse_query(filters: Dict[str, Any], query_text: str) -> Dict[str, Any]:
    """
    Validate if the browse query is clear enough to execute, or if questions are needed.
    
    Args:
        filters: Extracted filters from parse_browse_query
        query_text: Original query text
        
    Returns:
        Dictionary with:
            'is_clear': bool - Whether query is clear enough
            'confidence': float - Confidence score 0-1
            'missing_clarity': List[str] - Areas that need clarification
            'filters': Dict - Validated filters
    """
    query_lower = query_text.lower()
    
    # Check if it's a very vague query
    vague_indicators = ['all', 'everything', 'show me', 'give me', 'list', 'browse', 'available']
    is_vague = any(indicator in query_lower for indicator in vague_indicators) and len(filters) == 0
    
    # Check confidence based on filter specificity
    confidence = 0.5  # Base confidence
    missing_clarity = []
    
    # If very vague and no filters, confidence is low
    if is_vague:
        confidence = 0.2
        missing_clarity.append('filters')
    
    # If has specific filters, confidence increases
    if filters.get('destination'):
        confidence += 0.2
    if filters.get('tourType'):
        confidence += 0.15
    if filters.get('minBudget') or filters.get('maxBudget'):
        confidence += 0.15
    if filters.get('startDateFrom') or filters.get('startDateTo'):
        confidence += 0.1
    if filters.get('languages'):
        confidence += 0.1
    
    confidence = min(1.0, confidence)
    
    # Determine if query is clear enough (threshold: 0.4)
    is_clear = confidence >= 0.4
    
    return {
        'is_clear': is_clear,
        'confidence': confidence,
        'missing_clarity': missing_clarity,
        'filters': filters
    }


def generate_clarifying_questions(filters: Dict[str, Any], query_text: str) -> str:
    """
    Generate natural language questions to clarify a vague browse query.
    
    Args:
        filters: Already extracted filters
        query_text: Original query text
        
    Returns:
        Natural language questions string
    """
    questions = []
    
    # If no filters at all, ask general questions
    if not filters or len(filters) == 0:
        questions.append("What type of tours are you interested in? (e.g., cultural, adventure, beach)")
        questions.append("Are you looking for tours in a specific location or region?")
        questions.append("Do you have a budget range in mind?")
        questions.append("When are you available for tours? (dates or time period)")
    else:
        # Ask about missing important filters
        if not filters.get('destination') and not filters.get('search'):
            questions.append("Which location or region are you interested in? (e.g., Kandy, Nuwara Eliya, Colombo)")
        
        if not filters.get('tourType'):
            questions.append("What type of tour are you looking for? (cultural, adventure, beach, historical, etc.)")
        
        if not filters.get('minBudget') and not filters.get('maxBudget'):
            questions.append("Do you have a budget preference? (e.g., above $1000, between $500-$1000)")
        
        if not filters.get('startDateFrom') and not filters.get('startDateTo'):
            questions.append("When are you looking for tours? (specific dates, month, or time period)")
    
    if len(questions) == 1:
        return f"To help you find the best tour requests, I need one more detail: {questions[0]}"
    elif len(questions) > 1:
        question_text = "To help you find the best tour requests, I'd like to know a few more details:\n\n"
        for i, q in enumerate(questions[:4], 1):  # Limit to 4 questions
            question_text += f"{i}. {q}\n"
        question_text += "\nYou can answer all at once, or I can search with whatever filters you've provided."
        return question_text
    else:
        return "I found some tour requests based on your query. Would you like to refine the search with more specific filters?"

