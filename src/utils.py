"""Utility functions for the Location Intelligence Agent."""

import json
from typing import Dict, List, Any

def format_location_result(result: Dict[str, Any]) -> str:
    """Format a location result for display."""
    return f"""
Location: {result.get('name', 'Unknown')}
- Coordinates: ({result.get('lat', 'N/A')}, {result.get('lng', 'N/A')})
- Category: {result.get('category', 'N/A')}
- Rating: {result.get('rating', 'N/A')}/5
- Distance: {result.get('distance', 'N/A')} km
- Reason: {result.get('reason', 'N/A')}
"""

def rank_locations(locations: List[Dict[str, Any]], criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Rank locations based on multiple criteria.
    
    Args:
        locations: List of location dictionaries
        criteria: Dict with weights like {'density': 0.4, 'accessibility': 0.3, 'competition': 0.3}
    
    Returns:
        Ranked list of locations with scores
    """
    scored_locations = []
    
    for loc in locations:
        score = 0
        
        # Density score (higher is better)
        if 'nearby_count' in loc:
            score += loc['nearby_count'] * criteria.get('density', 0.3)
        
        # Accessibility score (lower distance is better)
        if 'avg_distance' in loc:
            max_dist = 20  # Assume 20km is max
            accessibility = max(0, 1 - (loc['avg_distance'] / max_dist))
            score += accessibility * criteria.get('accessibility', 0.3)
        
        # Competition score (lower competition is better for some businesses)
        if 'competitor_count' in loc:
            # Fewer competitors = higher score
            competition_score = max(0, 1 - (loc['competitor_count'] / 20))
            score += competition_score * criteria.get('competition', 0.3)
        
        # Rating bonus
        if 'rating' in loc and loc['rating']:
            score += (loc['rating'] / 5) * 0.1
        
        loc_with_score = loc.copy()
        loc_with_score['score'] = round(score, 3)
        scored_locations.append(loc_with_score)
    
    # Sort by score (descending)
    scored_locations.sort(key=lambda x: x['score'], reverse=True)
    
    return scored_locations

def create_explanation(location: Dict[str, Any], business_type: str) -> str:
    """Create a natural language explanation for why this location is recommended."""
    reasons = []
    
    if location.get('nearby_count', 0) > 10:
        reasons.append(f"High foot traffic area with {location['nearby_count']} nearby businesses")
    
    if location.get('avg_distance', 100) < 5:
        reasons.append("Excellent accessibility, close to major hubs")
    
    if location.get('competitor_count', 0) < 3:
        reasons.append("Low competition in immediate area")
    elif location.get('competitor_count', 0) > 10:
        reasons.append("High competition but established market")
    
    if location.get('rating', 0) > 4:
        reasons.append("High-quality businesses nearby indicate affluent area")
    
    if not reasons:
        reasons.append("Balanced location with moderate accessibility")
    
    return "; ".join(reasons)

def safe_json_dumps(data: Any) -> str:
    """Safely convert data to JSON string."""
    try:
        return json.dumps(data, indent=2, default=str)
    except Exception as e:
        return f"Error serializing data: {str(e)}"

def extract_business_type(query: str) -> str:
    """Extract business type from natural language query."""
    business_keywords = [
        "gym", "fitness", "cafe", "coffee", "restaurant", "coworking",
        "office", "retail", "store", "shop", "pharmacy", "clinic",
        "salon", "spa", "bank", "atm"
    ]
    
    query_lower = query.lower()
    
    for keyword in business_keywords:
        if keyword in query_lower:
            return keyword
    
    return "business"  # default

def extract_preferences(query: str) -> Dict[str, Any]:
    """Extract preferences from query like 'premium', 'budget', 'near tech parks'."""
    preferences = {
        "premium": "premium" in query.lower() or "high-end" in query.lower(),
        "budget": "budget" in query.lower() or "affordable" in query.lower(),
        "near_tech": any(x in query.lower() for x in ["tech", "it park", "office", "corporate"]),
        "near_residential": any(x in query.lower() for x in ["residential", "apartment", "housing"]),
    }
    return preferences
