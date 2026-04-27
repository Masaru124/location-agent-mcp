"""
Location Intelligence Agent - FastAPI Backend
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

# Import tools (copied from workshop_main.py)
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
            "clinic": "(SELECT value FROM UNNEST(all_tags) WHERE key = 'amenity' LIMIT 1) IN ('clinic', 'hospital', 'doctors')",
            "salon": "(SELECT value FROM UNNEST(all_tags) WHERE key = 'shop' LIMIT 1) IN ('hairdresser', 'beauty')",
        }
        default = f"(SELECT value FROM UNNEST(all_tags) WHERE key = 'name' LIMIT 1) LIKE '%{category}%'"
        return category_map.get(category.lower(), default)
    
    def query_pois(self, category: str, limit: int = 20) -> pd.DataFrame:
        """Query points of interest from OpenStreetMap."""
        min_lng = self.bangalore_bbox['min_lng']
        min_lat = self.bangalore_bbox['min_lat']
        max_lng = self.bangalore_bbox['max_lng']
        max_lat = self.bangalore_bbox['max_lat']
        polygon_wkt = f"POLYGON(({min_lng} {min_lat}, {max_lng} {min_lat}, {max_lng} {max_lat}, {min_lng} {max_lat}, {min_lng} {min_lat}))"
        
        tag_condition = self._get_osm_tags(category)
        print(f"Querying for category: {category}, tag_condition: {tag_condition[:100]}...")
        
        query = f"""
        SELECT 
            (SELECT value FROM UNNEST(all_tags) WHERE key = 'name' LIMIT 1) AS name,
            ST_Y(geometry) AS lat,
            ST_X(geometry) AS lng,
            '{category}' AS category
        FROM `{self.dataset}.planet_features`
        WHERE ST_WITHIN(geometry, ST_GEOGFROMTEXT('{polygon_wkt}'))
        AND ST_GEOMETRYTYPE(geometry) = 'ST_Point'
        AND ({tag_condition})
        AND (SELECT value FROM UNNEST(all_tags) WHERE key = 'name' LIMIT 1) IS NOT NULL
        LIMIT {limit}
        """
        
        try:
            df = self.client.query(query).to_dataframe()
            print(f"BigQuery query returned {len(df)} rows for category: {category}")
            return df
        except Exception as e:
            print(f"BigQuery error: {e}")
            print(f"Query: {query}")
            return pd.DataFrame()
    
    def get_sample_data(self, limit: int = 5) -> pd.DataFrame:
        """Get sample data to verify connection."""
        min_lng = self.bangalore_bbox['min_lng']
        min_lat = self.bangalore_bbox['min_lat']
        max_lng = self.bangalore_bbox['max_lng']
        max_lat = self.bangalore_bbox['max_lat']
        polygon_wkt = f"POLYGON(({min_lng} {min_lat}, {max_lng} {min_lat}, {max_lng} {max_lat}, {min_lng} {max_lat}, {min_lng} {min_lat}))"
        
        query = f"""
        SELECT 
            (SELECT value FROM UNNEST(all_tags) WHERE key = 'name' LIMIT 1) AS name,
            ST_Y(geometry) AS lat,
            ST_X(geometry) AS lng
        FROM `{self.dataset}.planet_features`
        WHERE ST_WITHIN(geometry, ST_GEOGFROMTEXT('{polygon_wkt}'))
        AND ST_GEOMETRYTYPE(geometry) = 'ST_Point'
        AND (SELECT value FROM UNNEST(all_tags) WHERE key = 'name' LIMIT 1) IS NOT NULL
        LIMIT {limit}
        """
        
        try:
            return self.client.query(query).to_dataframe()
        except Exception as e:
            print(f"BigQuery error: {e}")
            return pd.DataFrame()


class MapsTool:
    """Tool for Google Maps Platform APIs."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://maps.googleapis.com/maps/api"
    
    def nearby_search(self, lat: float, lng: float, keyword: str, 
                      radius: int = 5000, max_results: int = 10) -> List[Dict]:
        """Search for places near a location using Places API (New)."""
        url = "https://places.googleapis.com/v1/places:searchNearby"
        
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "places.displayName,places.location,places.rating,places.userRatingCount"
        }
        
        body = {
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": min(radius, 50000)
                }
            },
            "keyword": keyword,
            "maxResultCount": min(max_results, 20)
        }
        
        try:
            response = requests.post(url, headers=headers, json=body, timeout=10)
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
            print("⚠️  Places API timeout - returning empty list")
            return []
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Places API error: {e}")
            return []
    
    def distance_matrix(self, origins: List[tuple], destinations: List[tuple], 
                        mode: str = "driving") -> Dict[str, Any]:
        """Calculate distances between points."""
        origins_str = "|".join([f"{lat},{lng}" for lat, lng in origins])
        destinations_str = "|".join([f"{lat},{lng}" for lat, lng in destinations])
        
        url = f"{self.base_url}/distancematrix/json"
        params = {
            "origins": origins_str,
            "destinations": destinations_str,
            "mode": mode,
            "key": self.api_key
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") != "OK":
                return {"error": data.get("status")}
            
            results = []
            for i, row in enumerate(data.get("rows", [])):
                for j, element in enumerate(row.get("elements", [])):
                    if element.get("status") == "OK":
                        results.append({
                            "origin_index": i,
                            "destination_index": j,
                            "distance_meters": element.get("distance", {}).get("value"),
                            "duration_seconds": element.get("duration", {}).get("value")
                        })
            
            return {
                "origin_addresses": data.get("origin_addresses", []),
                "destination_addresses": data.get("destination_addresses", []),
                "results": results
            }
        except Exception as e:
            return {"error": str(e)}


class LocationIntelligenceAgent:
    """Agent that combines BigQuery and Maps data for recommendations."""
    
    def __init__(self, bq_tool: BigQueryTool, maps_tool: MapsTool):
        self.bq_tool = bq_tool
        self.maps_tool = maps_tool
    
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
        
        return {
            "query": query,
            "business_type": business_type,
            "recommendations": ranked[:3],
            "total_analyzed": len(pois)
        }


# Initialize tools and agent
project_id = os.getenv('GOOGLE_CLOUD_PROJECT', 'your-project-id')
maps_key = os.getenv('MAPS_API_KEY', 'your-maps-api-key')

agent = None
if project_id != 'your-project-id' and maps_key != 'your-maps-api-key':
    bq_tool = BigQueryTool(project_id)
    maps_tool = MapsTool(maps_key)
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
    error: Optional[str] = None


# API endpoints
@app.get("/")
def read_root():
    return {"message": "Location Intelligence Agent API", "status": "active"}


@app.get("/health")
def health_check():
    if agent is None:
        return {"status": "not_configured", "message": "API keys not set"}
    return {"status": "healthy", "agent": "ready"}


@app.post("/analyze", response_model=QueryResponse)
def analyze_location(request: QueryRequest):
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not configured. Set GOOGLE_CLOUD_PROJECT and MAPS_API_KEY")
    
    try:
        result = agent.run(request.query)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sample-data")
def get_sample_data():
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not configured")
    
    try:
        df = agent.bq_tool.get_sample_data(limit=5)
        return {"data": df.to_dict('records')}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
