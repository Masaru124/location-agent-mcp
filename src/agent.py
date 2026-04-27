"""ADK Agent for Location Intelligence."""

from typing import Dict, Any, List
import json

from google.adk import Agent
from google.adk.tools import ToolContext

from src.config import config
from src.utils import (
    rank_locations, 
    create_explanation, 
    extract_business_type,
    extract_preferences,
    format_location_result
)
from tools.bigquery_tool import BigQueryTool, create_bigquery_tool
from tools.maps_tool import MapsTool, create_maps_tool

class LocationIntelligenceAgent:
    """
    ADK Agent for location intelligence and business site selection.
    
    This agent combines BigQuery geospatial data with Google Maps Platform
    APIs to recommend optimal business locations.
    """
    
    def __init__(self):
        """Initialize the agent with tools."""
        # Validate config
        config.validate()
        
        # Initialize tools
        self.bigquery_tool = create_bigquery_tool(config.GOOGLE_CLOUD_PROJECT)
        self.maps_tool = create_maps_tool(config.MAPS_API_KEY)
        
        # Create ADK Agent
        self.agent = Agent(
            name=config.AGENT_NAME,
            description=config.AGENT_DESCRIPTION,
            tools=[
                self._query_bigquery_pois,
                self._search_nearby_places,
                self._analyze_location,
                self._rank_recommendations
            ],
            instruction=self._get_system_instruction()
        )
    
    def _get_system_instruction(self) -> str:
        """Get the system instruction for the agent."""
        return """You are a Location Intelligence Agent specializing in helping businesses find optimal locations in Bangalore.

Your capabilities:
1. Query BigQuery for geospatial data about existing businesses
2. Use Google Maps Platform to find real-time location data
3. Analyze locations based on:
   - Competition density
   - Accessibility
   - Foot traffic potential
   - Proximity to target demographics

When given a query:
1. Understand what business type and preferences the user has
2. Use BigQuery to find potential locations and existing business density
3. Use Maps API to get real-time data and validate locations
4. Rank locations based on multiple criteria
5. Provide specific recommendations with clear reasoning

Always explain your recommendations in business terms, not just data terms.
"""
    
    def _query_bigquery_pois(self, 
                             category: str, 
                             limit: int = 20) -> str:
        """
        Tool: Query Points of Interest from BigQuery.
        
        Args:
            category: Type of business (cafe, gym, restaurant, etc.)
            limit: Maximum number of results
        
        Returns:
            JSON string of POI data
        """
        results = self.bigquery_tool.query_pois(category, limit)
        return json.dumps(results, indent=2)
    
    def _search_nearby_places(self,
                              lat: float,
                              lng: float,
                              keyword: str,
                              radius: int = 2000) -> str:
        """
        Tool: Search for nearby places using Maps API.
        
        Args:
            lat: Search center latitude
            lng: Search center longitude
            keyword: Search term (gym, cafe, etc.)
            radius: Search radius in meters
        
        Returns:
            JSON string of nearby places
        """
        results = self.maps_tool.nearby_search(lat, lng, keyword, radius)
        return json.dumps(results, indent=2)
    
    def _analyze_location(self,
                        lat: float,
                        lng: float,
                        business_type: str) -> str:
        """
        Tool: Analyze a specific location for business viability.
        
        Args:
            lat: Location latitude
            lng: Location longitude
            business_type: Type of business to analyze
        
        Returns:
            JSON string with location metrics
        """
        results = self.maps_tool.get_location_score(lat, lng, business_type)
        return json.dumps(results, indent=2)
    
    def _rank_recommendations(self,
                             locations_json: str,
                             business_type: str,
                             preferences_json: str = "{}") -> str:
        """
        Tool: Rank locations based on business criteria.
        
        Args:
            locations_json: JSON string of location data
            business_type: Type of business
            preferences_json: JSON string of preferences
        
        Returns:
            JSON string of ranked locations with explanations
        """
        try:
            locations = json.loads(locations_json)
            preferences = json.loads(preferences_json)
            
            # Default criteria weights
            criteria = {
                "density": 0.3,
                "accessibility": 0.4,
                "competition": 0.3
            }
            
            # Adjust based on preferences
            if preferences.get("premium"):
                criteria["competition"] = 0.2  # Less worried about competition
                criteria["density"] = 0.4  # More focused on foot traffic
            
            # Rank locations
            ranked = rank_locations(locations, criteria)
            
            # Add explanations
            for loc in ranked:
                loc["explanation"] = create_explanation(loc, business_type)
            
            return json.dumps(ranked[:5], indent=2)  # Return top 5
            
        except json.JSONDecodeError as e:
            return json.dumps({"error": f"Invalid JSON: {str(e)}"})
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    def run(self, query: str) -> str:
        """
        Run the agent with a user query.
        
        Args:
            query: Natural language query about business location
        
        Returns:
            Agent response with recommendations
        """
        # Extract business type and preferences
        business_type = extract_business_type(query)
        preferences = extract_preferences(query)
        
        print(f"🔍 Analyzing: {query}")
        print(f"📍 Business Type: {business_type}")
        print(f"⚙️  Preferences: {preferences}")
        
        # Step 1: Get existing business data from BigQuery
        print("\n📊 Step 1: Querying BigQuery for existing businesses...")
        pois_json = self._query_bigquery_pois(business_type, limit=30)
        pois = json.loads(pois_json)
        print(f"   Found {len(pois)} existing {business_type}s in Bangalore")
        
        # Step 2: Search for competitors near potential areas
        print("\n🗺️  Step 2: Using Maps API to find competitors and assess areas...")
        
        # Use city center as starting point
        center_lat = config.DEFAULT_CITY_CENTER_LAT
        center_lng = config.DEFAULT_CITY_CENTER_LNG
        
        nearby_places_json = self._search_nearby_places(center_lat, center_lng, business_type)
        nearby_places = json.loads(nearby_places_json)
        print(f"   Found {len(nearby_places)} {business_type}s near city center")
        
        # Step 3: Analyze top locations
        print("\n🔬 Step 3: Analyzing specific locations...")
        
        # Combine data from both sources
        all_locations = pois[:15] + nearby_places[:10]
        
        # Get metrics for each location
        for loc in all_locations[:10]:
            analysis_json = self._analyze_location(
                loc.get("lat", center_lat),
                loc.get("lng", center_lng),
                business_type
            )
            analysis = json.loads(analysis_json)
            loc["nearby_count"] = analysis.get("nearby_businesses_count", 0)
            loc["competitor_count"] = analysis.get("competitor_count", 0)
        
        # Step 4: Rank recommendations
        print("\n🏆 Step 4: Ranking recommendations...")
        
        ranked_json = self._rank_recommendations(
            json.dumps(all_locations),
            business_type,
            json.dumps(preferences)
        )
        ranked = json.loads(ranked_json)
        
        # Format final response
        response = self._format_response(query, business_type, ranked)
        
        return response
    
    def _format_response(self, 
                        query: str, 
                        business_type: str, 
                        recommendations: List[Dict]) -> str:
        """Format the final response."""
        
        if not recommendations:
            return f"I couldn't find suitable locations for a {business_type} based on your query. Please try different criteria."
        
        response = f"""
🎯 LOCATION INTELLIGENCE REPORT
Query: "{query}"
Business Type: {business_type.title()}

📍 TOP 5 RECOMMENDED LOCATIONS:

"""
        
        for i, loc in enumerate(recommendations[:5], 1):
            response += f"""
{i}. {loc.get('name', f'Location {i}')}
   📍 Coordinates: ({loc.get('lat', 'N/A'):.4f}, {loc.get('lng', 'N/A'):.4f})
   🏪 Nearby Businesses: {loc.get('nearby_count', 'N/A')}
   ⚔️  Competitors: {loc.get('competitor_count', 'N/A')}
   ⭐ Score: {loc.get('score', 'N/A')}/1.0
   💡 Why: {loc.get('explanation', 'Good location potential')}

"""
        
        response += """
✅ NEXT STEPS:
1. Visit these locations in person
2. Check foot traffic during different times
3. Verify rent/lease availability
4. Check zoning regulations
5. Analyze local demographics

Would you like me to analyze a specific location in more detail?
"""
        
        return response

# Convenience function for quick usage
def run_agent(query: str) -> str:
    """Quick function to run the agent."""
    agent = LocationIntelligenceAgent()
    return agent.run(query)
