"""
Location Intelligence Agent - FastAPI Backend (Clean Version)
"""

import os
import sys
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Ollama LLM Configuration
ollama_base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
ollama_model = os.getenv('OLLAMA_MODEL', 'llama2')

# Import agent components from parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = FastAPI(title="Location Intelligence Agent API", version="1.0")

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import tools
import pandas as pd
from google.cloud import bigquery
import requests


class BigQueryTool:
    """Tool for querying BigQuery OpenStreetMap data."""
    
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.dataset = "bigquery-public-data.geo_openstreetmap"
        self.client = bigquery.Client(project=project_id)
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
    
    def query_pois(self, category: str, limit: int = 20) -> pd.DataFrame:
        """Query points of interest for a category in Bangalore."""
        tag_condition = self._get_osm_tags(category)
        
        # Build polygon string separately to avoid SQL syntax issues
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
            return df
        except Exception as e:
            print(f"BigQuery error: {e}")
            return pd.DataFrame()


class MapsTool:
    """Tool for Google Maps Platform APIs with BigQuery fallback."""
    
    def __init__(self, api_key: str, bq_tool: 'BigQueryTool' = None):
        self.api_key = api_key
        self.base_url = "https://maps.googleapis.com/maps/api"
        self.places_api_disabled = False
        self.places_api_error = ""
        self.bq_tool = bq_tool
    
    def _fallback_nearby_search(self, lat: float, lng: float, keyword: str, 
                                radius: int = 5000, max_results: int = 10) -> List[Dict]:
        """Use BigQuery as fallback to find nearby places."""
        if not self.bq_tool:
            return []
        
        import math
        
        try:
            # Query nearby POIs from BigQuery
            df = self.bq_tool.query_pois(keyword, limit=max_results * 10)
            
            if df.empty:
                return []
            
            # Calculate distances using Haversine formula
            def haversine(lat1, lng1, lat2, lng2):
                r = 6371  # Earth's radius in km
                dlat = math.radians(lat2 - lat1)
                dlng = math.radians(lng2 - lng1)
                a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
                c = 2 * math.asin(math.sqrt(a))
                return r * c * 1000  # Return in meters
            
            df['distance'] = df.apply(
                lambda row: haversine(lat, lng, row['lat'], row['lng']),
                axis=1
            )
            
            # Filter by radius and sort by distance
            df_filtered = df[df['distance'] <= radius].sort_values('distance')
            
            # Convert to list of dicts
            places = []
            for _, row in df_filtered.head(max_results).iterrows():
                places.append({
                    "name": row['name'],
                    "lat": row['lat'],
                    "lng": row['lng'],
                    "rating": None,
                    "user_ratings_total": None,
                    "source": "bigquery_fallback"
                })
            
            return places
            
        except Exception as e:
            print(f"BigQuery fallback error: {e}")
            return []
    
    def _get_place_types(self, keyword: str) -> list:
        """Map business keyword to Places API types."""
        type_map = {
            "gym": ["gym", "fitness_center"],
            "fitness": ["gym", "fitness_center"],
            "cafe": ["cafe", "coffee_shop"],
            "coffee": ["cafe", "coffee_shop"],
            "restaurant": ["restaurant"],
            "food": ["restaurant", "cafe"],
            "pharmacy": ["pharmacy"],
            "bank": ["bank", "atm"],
            "atm": ["atm", "bank"],
            "office": ["office"],
            "coworking": ["office"],
            "shop": ["store"],
            "retail": ["store"],
            "salon": ["hair_care", "beauty_salon"],
            "spa": ["spa"],
            "clinic": ["clinic", "doctor"],
            "hospital": ["hospital"],
        }
        return type_map.get(keyword.lower(), [])
    
    def _try_legacy_places_api(self, lat: float, lng: float, keyword: str,
                               radius: int = 5000, max_results: int = 10) -> List[Dict]:
        """Try the legacy Places Nearby Search API as fallback."""
        url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        
        params = {
            "location": f"{lat},{lng}",
            "radius": min(radius, 50000),
            "keyword": keyword,
            "key": self.api_key,
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data.get("status") == "OK":
                places = []
                for place in data.get("results", [])[:max_results]:
                    geometry = place.get("geometry", {}).get("location", {})
                    places.append({
                        "name": place.get("name", "Unknown"),
                        "lat": geometry.get("lat"),
                        "lng": geometry.get("lng"),
                        "rating": place.get("rating"),
                        "user_ratings_total": place.get("user_ratings_total"),
                        "source": "places_api_legacy"
                    })
                return places
            else:
                print(f"⚠️  Legacy Places API status: {data.get('status')}")
                return []
        except Exception as e:
            print(f"⚠️  Legacy Places API error: {e}")
            return []
    
    def nearby_search(self, lat: float, lng: float, keyword: str, 
                      radius: int = 5000, max_results: int = 10) -> List[Dict]:
        """Search for places near a location using Places API with multiple fallbacks."""
        if self.places_api_disabled:
            # Use BigQuery fallback if Places API is disabled
            return self._fallback_nearby_search(lat, lng, keyword, radius, max_results)
        
        url = "https://places.googleapis.com/v1/places:searchNearby"
        
        # Get place types for this keyword
        place_types = self._get_place_types(keyword)
        
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "places.displayName,places.location,places.rating,places.userRatingCount,places.types"
        }
        
        # Only include includedTypes if we have a mapping for this keyword
        body = {
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": min(radius, 50000)
                }
            },
            "maxResultCount": min(max_results, 20)
        }
        
        if place_types:
            body["includedTypes"] = place_types
        
        try:
            response = requests.post(url, headers=headers, json=body, timeout=10)
            
            # If we get a 4xx error, try legacy API
            if response.status_code >= 400:
                error_details = ""
                try:
                    error_details = response.json().get("error", {}).get("message", "")
                except:
                    pass
                print(f"⚠️  Places API (New) returned {response.status_code}: {error_details or response.text[:100]}")
                print("⚠️  Trying legacy Places API...")
                
                legacy_results = self._try_legacy_places_api(lat, lng, keyword, radius, max_results)
                if legacy_results:
                    return legacy_results
                
                print("⚠️  All Places APIs failed - using BigQuery fallback")
                self.places_api_disabled = True
                return self._fallback_nearby_search(lat, lng, keyword, radius, max_results)
            
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
                    "user_ratings_total": place.get("userRatingCount"),
                    "source": "places_api_new"
                })
            return places
            
        except requests.exceptions.Timeout:
            print("⚠️  Places API timeout - trying legacy API")
            legacy_results = self._try_legacy_places_api(lat, lng, keyword, radius, max_results)
            if legacy_results:
                return legacy_results
            
            print("⚠️  Using BigQuery fallback")
            self.places_api_disabled = True
            return self._fallback_nearby_search(lat, lng, keyword, radius, max_results)
            
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Places API error: {e}")
            print("⚠️  Trying legacy Places API...")
            legacy_results = self._try_legacy_places_api(lat, lng, keyword, radius, max_results)
            if legacy_results:
                return legacy_results
            
            print("⚠️  Using BigQuery fallback")
            self.places_api_disabled = True
            return self._fallback_nearby_search(lat, lng, keyword, radius, max_results)


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
            f"{i+1}. {loc['name']} - {loc['competitor_count']} competitors"
            for i, loc in enumerate(locations[:5])
        ])
        
        prompt = f"""
Analyze locations for {business_type} in Bangalore:

{location_summary}

Recommend best location and key factors (max 150 words):
"""
        
        return self._call_llm(prompt, max_tokens=200)
    
    def run(self, query: str) -> Dict[str, Any]:
        """Run the agent with a query."""
        business_type = self._extract_business_type(query)
        
        # Get existing businesses from BigQuery
        pois = self.bq_tool.query_pois(business_type, limit=20)
        
        if pois.empty:
            return {
                "query": query,
                "business_type": business_type,
                "recommendations": [],
                "total_analyzed": 0,
                "error": "No existing data found for this business type in Bangalore"
            }
        
        # Analyze top locations
        analyzed_locations = []
        for _, row in pois.head(5).iterrows():
            location_data = self._analyze_location(row['lat'], row['lng'], business_type)
            location_data['name'] = row['name']
            location_data['reasoning'] = self._generate_reasoning(location_data, business_type)
            analyzed_locations.append(location_data)
        
        # Rank by low competition
        ranked = sorted(analyzed_locations, key=lambda x: x['competitor_count'])
        
        # Generate AI insights
        print("🤖 Step 4: Generating AI insights...")
        ai_insights = self._generate_llm_insights(query, business_type, ranked)
        print(f"🤖 AI insights generated: {ai_insights[:100]}...")
        
        return {
            "query": query,
            "business_type": business_type,
            "recommendations": ranked[:3],
            "total_analyzed": len(pois),
            "ai_insights": ai_insights
        }


# Initialize tools and agent
project_id = os.getenv('GOOGLE_CLOUD_PROJECT', 'your-project-id')
maps_key = os.getenv('MAPS_API_KEY', 'your-maps-api-key')

agent = None
if project_id != 'your-project-id' and maps_key != 'your-maps-api-key':
    bq_tool = BigQueryTool(project_id)
    maps_tool = MapsTool(maps_key, bq_tool=bq_tool)
    agent = LocationIntelligenceAgent(bq_tool, maps_tool)


# Pydantic models
class QueryRequest(BaseModel):
    query: str


class Recommendation(BaseModel):
    name: str
    lat: float
    lng: float
    competitor_count: int
    avg_competitor_rating: float
    reasoning: str
    competitors: List[Dict]


class QueryResponse(BaseModel):
    query: str
    business_type: str
    recommendations: List[Recommendation]
    total_analyzed: int
    ai_insights: Optional[str] = None
    error: Optional[str] = None


# API endpoints
@app.get("/")
def read_root():
    return {"message": "Location Intelligence Agent API", "status": "active"}


@app.get("/health")
def health_check():
    if agent:
        return {"status": "healthy", "components": {"bigquery": "ok", "maps": "ok", "llm": "ok"}}
    else:
        return {"status": "not_configured", "error": "API keys not configured"}


@app.post("/analyze", response_model=QueryResponse)
def analyze_location(request: QueryRequest):
    """Analyze a location query."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized - check API keys")
    
    try:
        result = agent.run(request.query)
        return QueryResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
