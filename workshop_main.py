"""
Location Intelligence Agent - Terminal Version
==============================================

AI-powered location recommendations for businesses in Bangalore.
Uses BigQuery OpenStreetMap data, Google Maps APIs, and Ollama LLM.
"""

import os
import sys
import json
import requests
import math
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Ollama LLM Configuration
ollama_base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
ollama_model = os.getenv('OLLAMA_MODEL', 'llama2')

# Import Google Cloud libraries
try:
    from google.cloud import bigquery
    from google.oauth2 import service_account
    BIGQUERY_AVAILABLE = True
except ImportError:
    BIGQUERY_AVAILABLE = False
    print("⚠️  Google Cloud libraries not installed. Install with: pip install google-cloud-bigquery")

# Environment variables
project_id = os.getenv('GOOGLE_CLOUD_PROJECT', 'location-494614')
maps_key = os.getenv('MAPS_API_KEY', 'your-maps-api-key')


class BigQueryTool:
    """Tool for querying BigQuery OpenStreetMap data."""
    
    def __init__(self, project_id: str):
        if not BIGQUERY_AVAILABLE:
            raise ImportError("Google Cloud libraries not installed")
        
        self.project_id = project_id
        self.dataset = "bigquery-public-data.geo_openstreetmap"
        
        # Try service account first, then default credentials
        service_account_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if service_account_path and os.path.exists(service_account_path):
            self.client = bigquery.Client.from_service_account_json(service_account_path)
        else:
            self.client = bigquery.Client(project=project_id)
        
        # Bangalore bounding box
        self.bangalore_bbox = {
            'min_lat': 12.85, 'max_lat': 13.05,
            'min_lng': 77.45, 'max_lng': 77.75
        }
    
    def _get_osm_tags(self, category: str) -> str:
        """Map business category to OSM SQL conditions."""
        category_map = {
            "cafe": "(SELECT value FROM UNNEST(all_tags) WHERE key = 'amenity' LIMIT 1) = 'cafe'",
            "coffee": "(SELECT value FROM UNNEST(all_tags) WHERE key = 'amenity' LIMIT 1) = 'cafe'",
            "restaurant": "(SELECT value FROM UNNEST(all_tags) WHERE key = 'amenity' LIMIT 1) = 'restaurant'",
            "food": "(SELECT value FROM UNNEST(all_tags) WHERE key = 'amenity' LIMIT 1) IN ('restaurant', 'cafe', 'fast_food')",
            "gym": "(SELECT value FROM UNNEST(all_tags) WHERE key = 'leisure' LIMIT 1) IN ('fitness_centre', 'gym')",
            "fitness": "(SELECT value FROM UNNEST(all_tags) WHERE key = 'leisure' LIMIT 1) IN ('fitness_centre', 'gym', 'sports_centre')",
            "office": "(SELECT value FROM UNNEST(all_tags) WHERE key = 'office' LIMIT 1) IS NOT NULL",
            "coworking": "(SELECT value FROM UNNEST(all_tags) WHERE key = 'office' LIMIT 1) = 'coworking'",
            "shop": "(SELECT value FROM UNNEST(all_tags) WHERE key = 'shop' LIMIT 1) IS NOT NULL",
            "retail": "(SELECT value FROM UNNEST(all_tags) WHERE key = 'shop' LIMIT 1) IS NOT NULL",
            "bank": "(SELECT value FROM UNNEST(all_tags) WHERE key = 'amenity' LIMIT 1) = 'bank'",
            "atm": "(SELECT value FROM UNNEST(all_tags) WHERE key = 'amenity' LIMIT 1) IN ('atm', 'bank')",
            "pharmacy": "(SELECT value FROM UNNEST(all_tags) WHERE key = 'amenity' LIMIT 1) = 'pharmacy'",
            "clinic": ["clinic", "hospital", "doctor", "healthcare"],
            "salon": ["salon", "hairdresser", "beauty", "spa"],
        }
        
        default_condition = f"(SELECT value FROM UNNEST(all_tags) WHERE key = 'name' LIMIT 1) LIKE '%{category}%'"
        return category_map.get(category.lower(), default_condition)
    
    def query_pois(self, category: str, limit: int = 20) -> List[Dict]:
        """Query points of interest for a category in Bangalore."""
        tag_condition = self._get_osm_tags(category)
        
        # Build polygon string
        min_lng = self.bangalore_bbox['min_lng']
        min_lat = self.bangalore_bbox['min_lat']
        max_lng = self.bangalore_bbox['max_lng']
        max_lat = self.bangalore_bbox['max_lat']
        
        polygon_wkt = f"POLYGON(({min_lng} {min_lat}, {max_lng} {min_lat}, {max_lng} {max_lat}, {min_lng} {max_lat}, {min_lng} {min_lat}))"
        
        query = f"""
        SELECT 
            (SELECT value FROM UNNEST(all_tags) WHERE key = 'name' LIMIT 1) AS name,
            ST_Y(geometry) AS lat,
            ST_X(geometry) AS lng,
            '{category}' AS category
        FROM `{self.dataset}.planet_features`
        WHERE ST_WITHIN(
            geometry,
            ST_GEOGFROMTEXT('{polygon_wkt}')
        )
        AND ST_GEOMETRYTYPE(geometry) = 'ST_Point'
        AND (
            {tag_condition}
        )
        AND (SELECT value FROM UNNEST(all_tags) WHERE key = 'name' LIMIT 1) IS NOT NULL
        LIMIT {limit}
        """
        
        try:
            df = self.client.query(query).to_dataframe()
            return df.to_dict('records')
        except Exception as e:
            print(f"BigQuery error: {e}")
            return []


class MapsTool:
    """Tool for Google Maps Platform APIs."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.places_api_disabled = False
        self.places_api_error = ""
    
    def _get_place_types(self, keyword: str) -> list:
        """Map business keyword to Places API types."""
        type_map = {
            "gym": ["gym", "fitness_center"],
            "fitness": ["gym", "fitness_center"],
            "workout": ["gym", "fitness_center"],
            "exercise": ["gym", "fitness_center"],
            "cafe": ["cafe", "coffee_shop"],
            "coffee": ["cafe", "coffee_shop"],
            "coffeeshop": ["cafe", "coffee_shop"],
            "restaurant": ["restaurant"],
            "food": ["restaurant", "cafe"],
            "dining": ["restaurant"],
            "eat": ["restaurant"],
            "pharmacy": ["pharmacy"],
            "drugstore": ["pharmacy"],
            "medicine": ["pharmacy"],
            "medical": ["pharmacy"],
            "coworking": ["office"],
            "office": ["office"],
            "workspace": ["office"],
            "work": ["office"],
            "shop": ["store"],
            "retail": ["store"],
            "store": ["store"],
            "bank": ["bank"],
            "atm": ["atm"],
            "salon": ["hair_care"],
            "spa": ["spa"],
            "clinic": ["clinic"],
            "hospital": ["hospital"],
            "doctor": ["clinic"],
        }
        keyword_lower = keyword.lower()
        return type_map.get(keyword_lower, [])
    
    def nearby_search(self, lat: float, lng: float, keyword: str, radius: int = 2000) -> List[Dict]:
        """Search for nearby places using Places API (New)."""
        if self.places_api_disabled:
            return []

        url = "https://places.googleapis.com/v1/places:searchNearby"
        
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "places.displayName,places.location,places.rating,places.userRatingCount"
        }
        
        # Get appropriate place types for the keyword
        place_types = self._get_place_types(keyword)
        
        body = {
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": min(radius, 50000)
                }
            },
            "maxResultCount": 20
        }
        
        # Only add includedTypes if we have a mapping for this keyword
        if place_types:
            body["includedTypes"] = place_types
        
        try:
            response = requests.post(url, headers=headers, json=body, timeout=60)
            
            if response.status_code >= 400:
                error_msg = ""
                try:
                    error_msg = response.json().get("error", {}).get("message", "")
                except:
                    error_msg = response.text[:100]
                print(f"⚠️  Places API returned {response.status_code}: {error_msg}")
                self.places_api_disabled = True
                return []
            
            response.raise_for_status()
            data = response.json()
            
            places = []
            for place in data.get("places", []):
                location = place.get("location", {})
                display_name = place.get("displayName", {})
                places.append({
                    "name": display_name.get("text", "Unknown"),
                    "lat": location.get("latitude"),
                    "lng": location.get("longitude"),
                    "rating": place.get("rating"),
                    "user_ratings_total": place.get("userRatingCount")
                })
            return places
            
        except requests.exceptions.Timeout:
            print("⚠️  Places API timeout - disabling Places calls for this run")
            self.places_api_disabled = True
            return []
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Places API error: {e}")
            print("⚠️  Places API access denied; disabling Places calls for this run. Enable Places API (New), ensure billing is active, and check API key restrictions.")
            self.places_api_disabled = True
            return []
            return []
    
    def distance_matrix(self, origins: List[tuple], destinations: List[tuple], mode: str = "driving") -> Dict[str, Any]:
        """Calculate distances between points."""
        origins_str = "|".join([f"{lat},{lng}" for lat, lng in origins])
        destinations_str = "|".join([f"{lat},{lng}" for lat, lng in destinations])
        
        url = f"https://maps.googleapis.com/maps/api/distancematrix/json"
        params = {
            "origins": origins_str,
            "destinations": destinations_str,
            "mode": mode,
            "key": self.api_key
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data.get("status") == "OK":
                results = []
                rows = data.get("rows", [])
                
                for i, row in enumerate(rows):
                    elements = row.get("elements", [])
                    for j, element in enumerate(elements):
                        if element.get("status") == "OK":
                            distance = element.get("distance", {})
                            duration = element.get("duration", {})
                            
                            results.append({
                                "origin_index": i,
                                "destination_index": j,
                                "distance_meters": distance.get("value"),
                                "distance_text": distance.get("text"),
                                "duration_seconds": duration.get("value"),
                                "duration_text": duration.get("text")
                            })
                
                return {
                    "origin_addresses": data.get("origin_addresses", []),
                    "destination_addresses": data.get("destination_addresses", []),
                    "results": results
                }
            
            return {"error": data.get("status", "Unknown error")}
            
        except Exception as e:
            return {"error": str(e)}


class LocationIntelligenceAgent:
    """Agent that combines BigQuery and Maps data for recommendations."""
    
    def __init__(self, bq_tool: BigQueryTool, maps_tool: MapsTool):
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


def main():
    """Main function to run the Location Intelligence Agent."""
    print("🎯 Location Intelligence Agent - Terminal Version")
    print("=" * 50)
    
    # Initialize tools
    try:
        bq_tool = BigQueryTool(project_id)
        print("✅ BigQuery tool initialized")
    except Exception as e:
        print(f"❌ Failed to initialize BigQuery tool: {e}")
        return
    
    maps_tool = MapsTool(maps_key)
    print("✅ Maps tool initialized")
    
    # Initialize agent
    agent = LocationIntelligenceAgent(bq_tool, maps_tool)
    print("✅ Agent initialized")
    print()
    
    # Interactive mode
    print("🎯 LOCATION INTELLIGENCE AGENT - INTERACTIVE MODE")
    print("=" * 50)
    print("Type 'quit' to exit")
    print()
    
    while True:
        try:
            query = input("🔍 Enter your query: ").strip()
            
            if query.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break
            
            if not query:
                print("⚠️  Please enter a query")
                continue
            
            print()
            result = agent.run(query)
            print(result)
            print()
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            print()


if __name__ == "__main__":
    main()
