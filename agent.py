"""
Agent Module - Location Intelligence Agent
========================================

Contains the main LocationIntelligenceAgent class that orchestrates
BigQuery and Maps tools for location analysis.
"""

import os
import requests
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Ollama LLM Configuration
ollama_base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
ollama_model = os.getenv('OLLAMA_MODEL', 'llama2')


class LocationIntelligenceAgent:
    """Agent that combines BigQuery and Maps data for recommendations."""
    
    def __init__(self, bq_tool, maps_tool):
        self.bq_tool = bq_tool
        self.maps_tool = maps_tool
        self.ollama_url = ollama_base_url
        self.ollama_model = ollama_model
    
    def _extract_business_type(self, query: str) -> str:
        """Extract business type from query."""
        query_lower = query.lower()
        keywords = {
            "gym": ["gym", "fitness", "workout", "exercise"],
            "cafe": ["cafe", "coffee", "coffeeshop"],
            "restaurant": ["restaurant", "food", "dining"],
            "pharmacy": ["pharmacy", "medical", "medicine", "drugstore"],
            "office": ["office", "coworking", "workspace"],
            "shop": ["shop", "retail", "store"],
            "bank": ["bank", "atm", "financial"],
            "salon": ["salon", "hairdresser", "beauty", "spa"],
            "clinic": ["clinic", "hospital", "doctor", "healthcare"]
        }
        
        for business_type, terms in keywords.items():
            if any(term in query_lower for term in terms):
                return business_type
        return "business"
    
    def _analyze_location(self, lat: float, lng: float, business_type: str) -> Dict:
        """Analyze a specific location."""
        nearby_places = self.maps_tool.nearby_search(lat, lng, business_type, radius=2000)
        competitor_count = len(nearby_places)
        avg_rating = sum(p.get("rating", 0) for p in nearby_places if p.get("rating")) / max(len([p for p in nearby_places if p.get("rating")]), 1)
        competitors = nearby_places[:5]
        
        return {
            "lat": lat,
            "lng": lng,
            "competitor_count": competitor_count,
            "avg_competitor_rating": round(avg_rating, 1),
            "competitors": competitors
        }
    
    def _generate_reasoning(self, location: Dict, business_type: str) -> str:
        """Generate reasoning for recommendation."""
        reasons = []
        
        competitors = location.get("competitor_count", 0)
        if competitors == 0:
            reasons.append("No competitors nearby - excellent opportunity")
        elif competitors < 3:
            reasons.append("Low competition - few similar businesses nearby")
        elif competitors > 10:
            reasons.append("High competition but established market")
        else:
            reasons.append("Moderate competition - balanced market")
        
        rating = location.get("avg_competitor_rating", 0)
        if rating > 4 and competitors > 0:
            reasons.append("High-quality competitors indicate affluent customer base")
        elif rating < 3 and competitors > 0:
            reasons.append("Opportunity to offer better quality than existing options")
        elif rating == 0:
            reasons.append("Based on OpenStreetMap data analysis")
        
        if not reasons:
            reasons.append("Balanced location with growth potential")
        
        return "; ".join(reasons)
    
    def _call_llm(self, prompt: str, max_tokens: int = 300) -> str:
        """Call Ollama LLM for natural language generation."""
        for attempt in range(3):
            try:
                payload = {
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "max_tokens": max_tokens,
                        "num_predict": max_tokens
                    }
                }
                
                response = requests.post(
                    f"{self.ollama_url}/api/generate",
                    json=payload,
                    timeout=60
                )
                
                if response.status_code == 200:
                    result = response.json().get("response", "").strip()
                    if result:
                        return result
                    else:
                        if attempt < 2:
                            continue
                        return "Unable to generate AI insights at the moment."
                else:
                    if attempt < 2:
                        continue
                    return "Unable to generate AI insights at the moment."
                    
            except requests.exceptions.Timeout:
                if attempt < 2:
                    continue
                return "AI insights unavailable - using fallback analysis."
            except Exception as e:
                return "AI insights unavailable - using fallback analysis."
        
        return "AI insights unavailable - using fallback analysis."
    
    def _generate_llm_insights(self, query: str, business_type: str, locations: List[Dict]) -> str:
        """Generate AI-powered insights using LLM."""
        location_summary = "\n".join([
            f"{i+1}. {loc['name']} - {loc['competitor_count']} competitors, "
            f"{loc.get('nearby_businesses_count', 0)} nearby businesses"
            for i, loc in enumerate(locations[:5])
        ])
        
        prompt = f"""
Analyze locations for {business_type} in Bangalore:

{location_summary}

Recommend best location and key factors (max 150 words):
"""
        
        return self._call_llm(prompt, max_tokens=200)
    
    def _estimate_nearby_businesses_bigquery(self, lat: float, lng: float, radius: int = 1000) -> int:
        """Estimate nearby business density using BigQuery as fallback."""
        try:
            # Create a simple bounding box around the point
            radius_deg = radius / 111000  # Rough conversion from meters to degrees
            min_lat = lat - radius_deg
            max_lat = lat + radius_deg
            min_lng = lng - radius_deg
            max_lng = lng + radius_deg
            
            polygon_wkt = f"POLYGON(({min_lng} {min_lat}, {max_lng} {min_lat}, {max_lng} {max_lat}, {min_lng} {max_lat}, {min_lng} {min_lat}))"
            
            query = f"""
            SELECT COUNT(*) as count
            FROM `{self.bq_tool.dataset}.planet_features`
            WHERE ST_WITHIN(
                geometry,
                ST_GEOGFROMTEXT('{polygon_wkt}')
            )
            AND ST_GEOMETRYTYPE(geometry) = 'ST_Point'
            AND (SELECT value FROM UNNEST(all_tags) WHERE key = 'amenity' LIMIT 1) IS NOT NULL
            """
            
            result = self.bq_tool.client.query(query).to_dataframe()
            return int(result.iloc[0]['count']) if not result.empty else 0
            
        except Exception as e:
            print(f"BigQuery fallback error: {e}")
            return 0
    
    def run(self, query: str) -> Dict[str, Any]:
        """Run the agent with a query."""
        business_type = self._extract_business_type(query)
        
        print(f"🔍 Querying for category: {business_type}, tag_condition: {self.bq_tool._get_osm_tags(business_type)}...")
        
        # Get existing businesses from BigQuery
        pois = self.bq_tool.query_pois(business_type, limit=20)
        
        if not pois:
            return {
                "query": query,
                "business_type": business_type,
                "recommendations": [],
                "total_analyzed": 0,
                "error": "No existing data found for this business type in Bangalore"
            }
        
        print(f"BigQuery query returned {len(pois)} rows for category: {business_type}")
        
        # Analyze top locations
        analyzed_locations = []
        for _, row in enumerate(pois[:5]):
            location_data = self._analyze_location(row['lat'], row['lng'], business_type)
            location_data['name'] = row['name']
            location_data['reasoning'] = self._generate_reasoning(location_data, business_type)
            analyzed_locations.append(location_data)
        
        # Rank by low competition
        ranked = sorted(analyzed_locations, key=lambda x: x['competitor_count'])
        
        # Generate AI insights
        print("🤖 Step 4: Generating AI insights...")
        ai_insights = self._generate_llm_insights(query, business_type, ranked)
        
        return self._format_response(query, business_type, ranked, len(pois), ai_insights)
    
    def _format_response(self, query: str, business_type: str, recommendations: List[Dict], 
                        total_analyzed: int, ai_insights: str) -> str:
        """Format the final response."""
        response = []
        response.append("🎯 LOCATION INTELLIGENCE REPORT")
        response.append(f"Query: \"{query}\"")
        response.append(f"Business Type: {business_type}")
        response.append("")
        
        response.append("📍 TOP RECOMMENDED LOCATIONS:")
        response.append("")
        
        for i, rec in enumerate(recommendations[:3], 1):
            response.append(f"{i}. {rec['name']}")
            response.append(f"   📍 Coordinates: ({rec['lat']:.4f}, {rec['lng']:.4f})")
            response.append(f"   🏪 Nearby Businesses: {rec.get('nearby_businesses_count', 'N/A')}")
            response.append(f"   ⚔️  Competitors: {rec['competitor_count']}")
            response.append(f"   ⭐ Avg Competitor Rating: {rec['avg_competitor_rating']}/5")
            response.append(f"   💡 Why: {rec['reasoning']}")
            
            if rec.get('competitors'):
                response.append("   🏢 Nearby Competitors:")
                for comp in rec['competitors'][:3]:
                    rating = f" ({comp['rating']}⭐)" if comp.get('rating') else ""
                    response.append(f"      • {comp['name']}{rating}")
            response.append("")
        
        response.append("🤖 AI-POWERED INSIGHTS:")
        response.append(ai_insights)
        response.append("")
        
        response.append("📋 NEXT STEPS:")
        response.append("1. Visit top locations during business hours")
        response.append("2. Check foot traffic and parking availability")
        response.append("3. Survey local demographics and income levels")
        response.append("4. Research local regulations and permits")
        response.append("5. Analyze competitor pricing and services")
        
        return "\n".join(response)
