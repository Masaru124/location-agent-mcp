"""
🗺️ Location Intelligence AI Agent - Workshop Script
====================================================

Build an AI agent that answers: "Where should I open a business in Bangalore?"

Uses:
- ADK (Agent Development Kit)
- BigQuery with OpenStreetMap data
- Google Maps Platform APIs
- Model Context Protocol (MCP)

Run this script step by step following the workshop flow.
"""

# =============================================================================
# HOUR 0-1: SETUP & DEMO
# =============================================================================

print("=" * 70)
print("🗺️  LOCATION INTELLIGENCE AI AGENT - 6 HOUR WORKSHOP")
print("=" * 70)
print()
print("📋 Workshop Overview:")
print("   Build an AI agent that recommends business locations in Bangalore")
print()
print("⏱️  Schedule:")
print("   Hour 0-1: Setup & Demo")
print("   Hour 1-2: Build BigQuery Tool (OpenStreetMap data)")
print("   Hour 2-3: Build Maps API Tool")
print("   Hour 3-4: Build ADK Agent")
print("   Hour 4-5: Add Intelligence (ranking, reasoning)")
print("   Hour 5-6: Challenge - Find best gym location")
print()
print("=" * 70)

# -----------------------------------------------------------------------------
# STEP 1: Environment Setup
# -----------------------------------------------------------------------------

print("\n🚀 STEP 1: Environment Setup")
print("-" * 70)

import os
import sys
import json
from typing import List, Dict, Any

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Override any stale shell variables from prior sessions.
    load_dotenv(override=True)
    print("✅ Loaded environment from .env file")
except ImportError:
    print("⚠️  python-dotenv not installed, using manual configuration")

# Check for service account key (alternative to gcloud auth)
if os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
    print(f"✅ Using service account: {os.getenv('GOOGLE_APPLICATION_CREDENTIALS')}")

print(f"✅ Python version: {sys.version}")
print(f"📁 Working directory: {os.getcwd()}")

# Set API Keys from environment or manually
print("\n🔑 Setting API Keys...")

# If not loaded from .env, set manually (EDIT THESE LINES!)
if not os.getenv('GOOGLE_CLOUD_PROJECT') or os.getenv('GOOGLE_CLOUD_PROJECT') == 'your-project-id':
    os.environ['GOOGLE_CLOUD_PROJECT'] = 'location-494614'

if not os.getenv('MAPS_API_KEY') or os.getenv('MAPS_API_KEY') == 'your-maps-api-key-here':
    os.environ['MAPS_API_KEY'] = 'AIzaSyA_ZVus71NBW-juuVDk7VQh8NO7ZTviRDc'

project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
maps_key = os.getenv('MAPS_API_KEY')

if project_id and project_id != 'your-project-id':
    print(f"✅ Project ID: {project_id}")
else:
    print("⚠️  WARNING: Please set your GOOGLE_CLOUD_PROJECT!")

if maps_key and maps_key != 'your-maps-api-key':
    print(f"✅ Maps API Key: {maps_key[:10]}...")
else:
    print("⚠️  WARNING: Please set your MAPS_API_KEY!")

# -----------------------------------------------------------------------------
# DEMO: What We'll Build
# -----------------------------------------------------------------------------

print("\n" + "=" * 70)
print("🎬 DEMO: Final Agent Output")
print("=" * 70)

demo_response = """
🎯 LOCATION INTELLIGENCE REPORT
Query: "Where should I open a premium gym in Bangalore?"
Business Type: Gym

📍 TOP 5 RECOMMENDED LOCATIONS:

1. Fitness First Koramangala
   📍 Coordinates: (12.9352, 77.6245)
   🏪 Nearby Businesses: 45
   ⚔️  Competitors: 3
   ⭐ Score: 0.85/1.0
   💡 Why: High foot traffic with 45 nearby businesses; Low competition

2. Gold's Gym Indiranagar
   📍 Coordinates: (12.9716, 77.6412)
   🏪 Nearby Businesses: 62
   ⚔️  Competitors: 5
   ⭐ Score: 0.78/1.0
   💡 Why: High foot traffic with 62 businesses; Excellent accessibility

3. Cult Whitefield
   📍 Coordinates: (12.9698, 77.7500)
   🏪 Nearby Businesses: 38
   ⚔️  Competitors: 2
   ⭐ Score: 0.72/1.0
   💡 Why: Growing tech hub; Low competition indicates opportunity

✅ This is what you'll build today!
"""

print(demo_response)

# =============================================================================
# HOUR 1-2: BUILD TOOL 1 - BIGQUERY WITH OPENSTREETMAP
# =============================================================================

print("\n" + "=" * 70)
print("🔧 HOUR 1-2: Building BigQuery Tool")
print("=" * 70)
print()
print("📚 Using: OpenStreetMap public dataset in BigQuery")
print("   Dataset: bigquery-public-data.geo_openstreetmap")
print("   Tables: planet_features, planet_geometry")
print()

# Install and import dependencies
print("📦 Installing dependencies...")
try:
    from google.cloud import bigquery
    print("✅ google-cloud-bigquery already installed")
except ImportError:
    print("Installing google-cloud-bigquery...")
    os.system("pip install -q google-cloud-bigquery")
    from google.cloud import bigquery

# -----------------------------------------------------------------------------
# BigQuery Tool Class
# -----------------------------------------------------------------------------

print("\n🏗️  Building BigQueryTool class...")

class BigQueryTool:
    """
    MCP Tool for querying OpenStreetMap geospatial data from BigQuery.
    
    Uses the public OpenStreetMap dataset to find businesses in Bangalore.
    """
    
    def __init__(self, project_id: str):
        """Initialize BigQuery client."""
        self.project_id = project_id
        self.client = bigquery.Client(project=project_id)
        self.dataset = "bigquery-public-data.geo_openstreetmap"
        
        # Bangalore bounding box (approximate)
        self.bangalore_bbox = {
            "min_lat": 12.85,
            "max_lat": 13.05,
            "min_lng": 77.45,
            "max_lng": 77.75
        }
    
    def query_pois(self, category: str, limit: int = 20) -> List[Dict]:
        """
        Query Points of Interest from OpenStreetMap data.
        
        Args:
            category: Type of business (cafe, gym, restaurant)
            limit: Maximum number of results
        
        Returns:
            List of POI dictionaries with name, lat, lng
        """
        # Map category to OSM tags
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
        AND ({tag_condition})
        AND (SELECT value FROM UNNEST(all_tags) WHERE key = 'name' LIMIT 1) IS NOT NULL
        LIMIT {limit}
        """
        
        try:
            results = self.client.query(query, project=self.project_id).result()
            pois = []
            for row in results:
                pois.append({
                    "name": row.name if row.name else "Unknown",
                    "lat": row.lat,
                    "lng": row.lng,
                    "category": row.category
                })
            return pois
            
        except Exception as e:
            print(f"❌ BigQuery error: {e}")
            return []
    
    def _get_osm_tags(self, category: str) -> str:
        """Map business category to OSM SQL conditions using all_tags array."""
        
        # OSM tags are stored in all_tags array as key-value pairs
        # We check for the 'amenity', 'leisure', 'office' tags
        category_map = {
            "cafe": "(SELECT value FROM UNNEST(all_tags) WHERE key = 'amenity' LIMIT 1) = 'cafe'",
            "coffee": "(SELECT value FROM UNNEST(all_tags) WHERE key = 'amenity' LIMIT 1) = 'cafe'",
            "restaurant": "(SELECT value FROM UNNEST(all_tags) WHERE key = 'amenity' LIMIT 1) = 'restaurant'",
            "gym": "(SELECT value FROM UNNEST(all_tags) WHERE key = 'leisure' LIMIT 1) IN ('fitness_centre', 'gym', 'sports_centre')",
            "fitness": "(SELECT value FROM UNNEST(all_tags) WHERE key = 'leisure' LIMIT 1) IN ('fitness_centre', 'gym', 'sports_centre')",
            "office": "(SELECT value FROM UNNEST(all_tags) WHERE key = 'office' LIMIT 1) IS NOT NULL",
            "coworking": "(SELECT value FROM UNNEST(all_tags) WHERE key = 'office' LIMIT 1) = 'coworking'",
            "pharmacy": "(SELECT value FROM UNNEST(all_tags) WHERE key = 'amenity' LIMIT 1) = 'pharmacy'",
            "bank": "(SELECT value FROM UNNEST(all_tags) WHERE key = 'amenity' LIMIT 1) = 'bank'",
            "atm": "(SELECT value FROM UNNEST(all_tags) WHERE key = 'amenity' LIMIT 1) IN ('atm', 'bank')",
        }
        
        # Default: search in name tag
        default_condition = f"(SELECT value FROM UNNEST(all_tags) WHERE key = 'name' LIMIT 1) LIKE '%{category}%'"
        
        return category_map.get(category.lower(), default_condition)
    
    def count_by_category(self) -> Dict[str, int]:
        """Count businesses by category in Bangalore."""
        
        # Build polygon string
        min_lng = self.bangalore_bbox['min_lng']
        min_lat = self.bangalore_bbox['min_lat']
        max_lng = self.bangalore_bbox['max_lng']
        max_lat = self.bangalore_bbox['max_lat']
        polygon_wkt = f"POLYGON(({min_lng} {min_lat}, {max_lng} {min_lat}, {max_lng} {max_lat}, {min_lng} {max_lat}, {min_lng} {min_lat}))"
        
        query = f"""
        SELECT 
            (SELECT value FROM UNNEST(all_tags) WHERE key = 'amenity' LIMIT 1) AS category,
            COUNT(*) as count
        FROM `{self.dataset}.planet_features`
        WHERE ST_WITHIN(
            geometry,
            ST_GEOGFROMTEXT('{polygon_wkt}')
        )
        AND (SELECT value FROM UNNEST(all_tags) WHERE key = 'amenity' LIMIT 1) IS NOT NULL
        GROUP BY category
        ORDER BY count DESC
        LIMIT 10
        """
        
        try:
            results = self.client.query(query, project=self.project_id).result()
            return {row.category: row.count for row in results}
        except Exception as e:
            print(f"❌ Count query error: {e}")
            return {}

print("✅ BigQueryTool class defined!")

# -----------------------------------------------------------------------------
# Checkpoint 1: Test BigQuery Connection
# -----------------------------------------------------------------------------

print("\n✅ CHECKPOINT 1: Testing BigQuery Connection")
print("-" * 70)

def test_bigquery_connection():
    """Test that we can connect to BigQuery and query OpenStreetMap data."""
    
    if project_id == 'your-project-id':
        print("⚠️  Skipping test - please set your GOOGLE_CLOUD_PROJECT first!")
        return False
    
    try:
        print(f"Connecting to BigQuery (Project: {project_id})...")
        client = bigquery.Client(project=project_id)
        
        # Test query
        query = """
        SELECT COUNT(*) as total 
        FROM `bigquery-public-data.geo_openstreetmap.planet_features` 
        LIMIT 1
        """
        result = client.query(query, project=project_id).result()
        
        for row in result:
            print(f"✅ Connection successful!")
            print(f"   Total OpenStreetMap features globally: {row.total:,}")
        
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

# Run the test (will skip if no valid project ID)
if project_id != 'your-project-id':
    test_bigquery_connection()
else:
    print("⚠️  Set GOOGLE_CLOUD_PROJECT to test BigQuery connection")

# -----------------------------------------------------------------------------
# Checkpoint 2: Test BigQuery Tool
# -----------------------------------------------------------------------------

print("\n✅ CHECKPOINT 2: Testing BigQueryTool")
print("-" * 70)

def test_bigquery_tool():
    """Test the BigQueryTool with actual queries."""
    
    if project_id == 'your-project-id':
        print("⚠️  Skipping - set your GOOGLE_CLOUD_PROJECT first!")
        return
    
    print("Initializing BigQueryTool...")
    bq_tool = BigQueryTool(project_id)
    
    # Test 1: Query cafes
    print("\n🔍 Querying cafes in Bangalore...")
    cafes = bq_tool.query_pois("cafe", limit=10)
    print(f"✅ Found {len(cafes)} cafes!")
    
    if cafes:
        print("\nSample results:")
        for i, cafe in enumerate(cafes[:3], 1):
            print(f"   {i}. {cafe['name']}")
            print(f"      📍 ({cafe['lat']:.4f}, {cafe['lng']:.4f})")
    
    # Test 2: Count by category
    print("\n📊 Counting businesses by category...")
    counts = bq_tool.count_by_category()
    print("   Business counts in Bangalore:")
    for category, count in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"   • {category}: {count}")

# Run the test
if project_id != 'your-project-id':
    test_bigquery_tool()
else:
    print("⚠️  Set GOOGLE_CLOUD_PROJECT to test BigQueryTool")

print("\n🎉 AHA MOMENT #1: You just queried real OpenStreetMap data from BigQuery!")

# =============================================================================
# HOUR 2-3: BUILD TOOL 2 - GOOGLE MAPS API
# =============================================================================

print("\n" + "=" * 70)
print("🗺️  HOUR 2-3: Building Google Maps Tool")
print("=" * 70)
print()
print("📚 Using: Google Maps Platform APIs")
print("   - Places API (New): Find nearby businesses, ratings")
print("   - Distance Matrix API: Calculate distances and times")
print()

# Import dependencies
print("📦 Importing Maps API dependencies...")
try:
    import requests
    print("✅ requests already installed")
except ImportError:
    os.system("pip install -q requests")
    import requests

# -----------------------------------------------------------------------------
# Maps Tool Class
# -----------------------------------------------------------------------------

print("\n🏗️  Building MapsTool class...")

class MapsTool:
    """
    MCP Tool for Google Maps Platform APIs.
    
    Provides real-time location intelligence via:
    - Places API (New)
    - Distance Matrix API
    """
    
    def __init__(self, api_key: str):
        """Initialize with Maps API key."""
        self.api_key = api_key
        self.places_api_disabled = False
        self.places_api_error = ""
    
    def nearby_search(self, lat: float, lng: float, keyword: str, radius: int = 2000) -> List[Dict]:
        """
        Search for nearby places using Places API (New).
        
        Args:
            lat, lng: Search center coordinates
            keyword: Search term (e.g., 'gym', 'cafe')
            radius: Search radius in meters (max 50000)
        
        Returns:
            List of place dictionaries
        """
        if self.places_api_disabled:
            return []

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
            "maxResultCount": 20
        }
        
        try:
            response = requests.post(url, headers=headers, json=body, timeout=10)

            if response.status_code in (401, 403):
                details = ""
                try:
                    details = response.json().get("error", {}).get("message", "")
                except Exception:
                    details = response.text[:200]

                self.places_api_disabled = True
                self.places_api_error = details or f"HTTP {response.status_code}"
                print(
                    "⚠️  Places API access denied; disabling Places calls for this run. "
                    "Enable Places API (New), ensure billing is active, and check API key restrictions."
                )
                if self.places_api_error:
                    print(f"⚠️  Places API details: {self.places_api_error}")
                return []

            response.raise_for_status()
            data = response.json()
            
            places = []
            for place in data.get("places", []):
                location = place.get("location", {})
                name = place.get("displayName", {}).get("text", "Unknown")
                
                places.append({
                    "name": name,
                    "lat": location.get("latitude"),
                    "lng": location.get("longitude"),
                    "rating": place.get("rating"),
                    "user_ratings_total": place.get("userRatingCount"),
                    "source": "places_api"
                })
            
            return places
            
        except requests.exceptions.Timeout:
            print("⚠️  Places API timeout - returning empty list")
            return []
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Places API error: {e}")
            return []
    
    def distance_matrix(self, origin: tuple, destination: tuple, mode: str = "driving") -> Dict:
        """
        Calculate distance and duration between two points.
        
        Args:
            origin: (lat, lng) tuple
            destination: (lat, lng) tuple
            mode: Travel mode (driving, walking, transit)
        
        Returns:
            Dictionary with distance_km and duration_min
        """
        url = "https://maps.googleapis.com/maps/api/distancematrix/json"
        
        params = {
            "origins": f"{origin[0]},{origin[1]}",
            "destinations": f"{destination[0]},{destination[1]}",
            "mode": mode,
            "key": self.api_key
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data.get("status") == "OK":
                element = data["rows"][0]["elements"][0]
                if element.get("status") == "OK":
                    return {
                        "distance_km": round(element["distance"]["value"] / 1000, 2),
                        "duration_min": round(element["duration"]["value"] / 60, 1),
                        "duration_text": element["duration"]["text"]
                    }
            
            return {"error": data.get("status", "Unknown error")}
            
        except Exception as e:
            return {"error": str(e)}
    
    def calculate_distances_to_multiple(self, origin: tuple, destinations: List[Dict]) -> List[Dict]:
        """Calculate distances from origin to multiple destinations."""
        results = []
        for dest in destinations:
            distance = self.distance_matrix(origin, (dest["lat"], dest["lng"]))
            dest_copy = dest.copy()
            dest_copy.update(distance)
            results.append(dest_copy)
        return results

print("✅ MapsTool class defined!")

# -----------------------------------------------------------------------------
# Checkpoint 3: Test Maps Tool
# -----------------------------------------------------------------------------

print("\n✅ CHECKPOINT 3: Testing MapsTool")
print("-" * 70)

def test_maps_tool():
    """Test the MapsTool with actual API calls."""
    
    if maps_key == 'your-maps-api-key':
        print("⚠️  Skipping - set your MAPS_API_KEY first!")
        return
    
    print("Initializing MapsTool...")
    maps_tool = MapsTool(maps_key)
    
    # Test 1: Nearby search
    center_lat, center_lng = 12.9716, 77.5946  # Bangalore city center
    
    print(f"\n🔍 Searching for gyms near Bangalore City Center...")
    gyms = maps_tool.nearby_search(center_lat, center_lng, "gym", radius=5000)
    print(f"✅ Found {len(gyms)} gyms!")
    
    if gyms:
        print("\nSample results:")
        for i, gym in enumerate(gyms[:3], 1):
            print(f"   {i}. {gym['name']}")
            print(f"      ⭐ Rating: {gym.get('rating', 'N/A')}")
            print(f"      📍 ({gym['lat']:.4f}, {gym['lng']:.4f})")
    
    # Test 2: Distance calculation
    if len(gyms) >= 2:
        print(f"\n🚗 Calculating distance between first two gyms...")
        origin = (gyms[0]["lat"], gyms[0]["lng"])
        dest = (gyms[1]["lat"], gyms[1]["lng"])
        
        distance = maps_tool.distance_matrix(origin, dest)
        print(f"   Distance: {distance.get('distance_km', 'N/A')} km")
        print(f"   Duration: {distance.get('duration_text', 'N/A')}")

# Run the test
if maps_key != 'your-maps-api-key':
    test_maps_tool()
else:
    print("⚠️  Set MAPS_API_KEY to test MapsTool")

print("\n🎉 AHA MOMENT #2: You now have real-time data from Google Maps!")

# =============================================================================
# HOUR 3-4: BUILD THE AGENT WITH ADK
# =============================================================================

print("\n" + "=" * 70)
print("🤖 HOUR 3-4: Building the ADK Agent")
print("=" * 70)
print()
print("📚 What is ADK?")
print("   ADK = Agent Development Kit")
print("   Purpose: Orchestrate tools and handle agent reasoning")
print()

# For this workshop, we'll build a simplified agent without full ADK
# (ADK requires additional setup - we'll simulate the concept)

print("🏗️  Building LocationIntelligenceAgent...")

class LocationIntelligenceAgent:
    """
    Agent that combines BigQuery and Maps tools for location intelligence.
    
    This simulates ADK-style agent behavior with tool orchestration.
    """
    
    def __init__(self, bq_tool: BigQueryTool, maps_tool: MapsTool):
        self.bq_tool = bq_tool
        self.maps_tool = maps_tool
    
    def analyze_location(self, lat: float, lng: float, business_type: str) -> Dict:
        """
        Analyze a specific location for business viability.
        
        Returns metrics including:
        - Competitor count
        - Nearby business density
        - Accessibility score
        """
        # Find competitors nearby
        competitors = self.maps_tool.nearby_search(lat, lng, business_type, radius=2000)
        competitor_count = len(competitors)
        
        # Find nearby businesses (foot traffic proxy)
        nearby = self.maps_tool.nearby_search(lat, lng, "restaurant", radius=1000)
        nearby_count = len(nearby)
        
        return {
            "lat": lat,
            "lng": lng,
            "business_type": business_type,
            "competitor_count": competitor_count,
            "nearby_businesses_count": nearby_count,
            "competitors": competitors[:5]  # Top 5 competitors
        }
    
    def rank_locations(self, locations: List[Dict], business_type: str) -> List[Dict]:
        """
        Rank locations based on multiple criteria.
        
        Scoring:
        - Low competition: +0.3
        - High foot traffic: +0.4
        - Good rating nearby: +0.1
        """
        scored_locations = []
        
        for loc in locations:
            score = 0.0
            
            # Competition score (fewer competitors = higher score)
            comp_count = loc.get("competitor_count", 0)
            competition_score = max(0, 1 - (comp_count / 10))
            score += competition_score * 0.3
            
            # Density score (more nearby businesses = higher foot traffic)
            nearby_count = loc.get("nearby_businesses_count", 0)
            density_score = min(1, nearby_count / 20)
            score += density_score * 0.4
            
            # Rating bonus
            if loc.get("rating", 0) > 4:
                score += 0.1
            
            loc_copy = loc.copy()
            loc_copy["score"] = round(score, 3)
            scored_locations.append(loc_copy)
        
        # Sort by score (descending)
        scored_locations.sort(key=lambda x: x["score"], reverse=True)
        return scored_locations
    
    def create_explanation(self, location: Dict, business_type: str) -> str:
        """Create natural language explanation for a recommendation."""
        reasons = []
        
        if location.get("nearby_businesses_count", 0) > 10:
            reasons.append(f"High foot traffic area with {location['nearby_businesses_count']} nearby businesses")
        
        if location.get("competitor_count", 0) < 3:
            reasons.append("Low competition in immediate area")
        elif location.get("competitor_count", 0) > 10:
            reasons.append("Established market with high competition")
        
        if location.get("rating", 0) > 4:
            reasons.append("High-quality businesses nearby indicate affluent area")
        
        if not reasons:
            reasons.append("Balanced location with moderate accessibility")
        
        return "; ".join(reasons)
    
    def run(self, query: str) -> str:
        """
        Run the agent with a user query.
        
        Example queries:
        - "Where should I open a premium gym in Bangalore?"
        - "Find best cafe locations near tech parks"
        """
        # Extract business type from query
        business_type = self._extract_business_type(query)
        
        print(f"\n🔍 Analyzing: {query}")
        print(f"📍 Business Type: {business_type}")
        
        # Step 1: Get existing business data from BigQuery
        print(f"\n📊 Step 1: Querying OpenStreetMap data for {business_type}s...")
        pois = self.bq_tool.query_pois(business_type, limit=30)
        print(f"   Found {len(pois)} existing {business_type}s in BigQuery")
        
        # Step 2: Analyze locations with Maps API
        print(f"\n🗺️  Step 2: Using Maps API to analyze locations...")
        
        analyzed_locations = []
        for poi in pois[:15]:  # Analyze top 15
            analysis = self.analyze_location(poi["lat"], poi["lng"], business_type)
            analysis["name"] = poi.get("name", "Unknown")
            analyzed_locations.append(analysis)
        
        print(f"   Analyzed {len(analyzed_locations)} locations")
        
        # Step 3: Rank locations
        print(f"\n🏆 Step 3: Ranking locations...")
        ranked = self.rank_locations(analyzed_locations, business_type)
        
        # Step 4: Generate response
        return self._format_response(query, business_type, ranked)
    
    def _extract_business_type(self, query: str) -> str:
        """Extract business type from natural language query."""
        keywords = ["gym", "fitness", "cafe", "coffee", "restaurant", 
                   "coworking", "office", "retail", "pharmacy", "bank"]
        query_lower = query.lower()
        
        for keyword in keywords:
            if keyword in query_lower:
                return keyword
        
        return "business"
    
    def _format_response(self, query: str, business_type: str, recommendations: List[Dict]) -> str:
        """Format the final response."""
        
        if not recommendations:
            return f"❌ Couldn't find suitable locations for {business_type}"
        
        response = f"""
🎯 LOCATION INTELLIGENCE REPORT
Query: "{query}"
Business Type: {business_type.title()}

📍 TOP 5 RECOMMENDED LOCATIONS:

"""
        
        for i, loc in enumerate(recommendations[:5], 1):
            response += f"""{i}. {loc.get('name', f'Location {i}')}
   📍 Coordinates: ({loc.get('lat', 'N/A'):.4f}, {loc.get('lng', 'N/A'):.4f})
   🏪 Nearby Businesses: {loc.get('nearby_businesses_count', 'N/A')}
   ⚔️  Competitors: {loc.get('competitor_count', 'N/A')}
   ⭐ Score: {loc.get('score', 'N/A')}/1.0
   💡 Why: {self.create_explanation(loc, business_type)}

"""
        
        response += """✅ NEXT STEPS:
1. Visit these locations in person
2. Check foot traffic during different times
3. Verify rent/lease availability
4. Check zoning regulations
5. Analyze local demographics

Want me to analyze a specific location in more detail? Just ask!
"""
        
        return response

print("✅ LocationIntelligenceAgent class defined!")

# =============================================================================
# HOUR 4-5: TEST THE FULL AGENT
# =============================================================================

print("\n" + "=" * 70)
print("🧪 HOUR 4-5: Testing the Full Agent")
print("=" * 70)

def run_full_demo():
    """Run a complete demo of the agent."""
    
    if project_id == 'your-project-id' or maps_key == 'your-maps-api-key':
        print("⚠️  Please set both GOOGLE_CLOUD_PROJECT and MAPS_API_KEY!")
        print()
        print("   Add your keys and run again:")
        print("   os.environ['GOOGLE_CLOUD_PROJECT'] = 'your-actual-project-id'")
        print("   os.environ['MAPS_API_KEY'] = 'your-actual-api-key'")
        return
    
    print("🚀 Initializing agent with tools...")
    bq_tool = BigQueryTool(project_id)
    maps_tool = MapsTool(maps_key)
    agent = LocationIntelligenceAgent(bq_tool, maps_tool)
    
    # Test query
    query = "Where should I open a premium gym in Bangalore?"
    print(f"\n{'='*70}")
    print(f"Query: {query}")
    print('='*70)
    
    result = agent.run(query)
    print(result)

# Run the demo (will show instructions if keys not set)
print("\nReady to test! Running demo...\n")
run_full_demo()

# =============================================================================
# HOUR 5-6: CHALLENGE
# =============================================================================

print("\n" + "=" * 70)
print("🏆 HOUR 5-6: Workshop Challenge")
print("=" * 70)

challenge = """
🎯 CHALLENGE: Find the Best Location for a Specific Business

Choose ONE of these scenarios and build a query for your agent:

Scenario A: Premium Gym
   "Where should I open a premium gym in Bangalore?"
   Focus: Low competition, high foot traffic, affluent area

Scenario B: Cafe Near Tech Parks
   "Best location for a cafe near tech parks in Bangalore?"
   Focus: Proximity to offices, lunch crowd, accessibility

Scenario C: Co-working Space
   "Where to open a co-working space in Bangalore?"
   Focus: Central location, transport links, existing offices nearby

Scenario D: Pharmacy
   "Best location for a 24/7 pharmacy in Bangalore?"
   Focus: Residential areas, low competition, accessibility

🏅 BONUS: Add visualization with Folium to show locations on a map!

📝 SUBMISSION:
Present your:
1. Query used
2. Top 3 recommendations with reasoning
3. Any insights about Bangalore business locations

"""

print(challenge)

# =============================================================================
# FINAL NOTES
# =============================================================================

print("=" * 70)
print("📚 What You've Learned")
print("=" * 70)

summary = """
✅ BigQuery OpenStreetMap Integration
   - Query geospatial data using SQL
   - Use BigQuery GIS functions (ST_WITHIN, ST_GEOGPOINT)
   - Leverage public datasets

✅ Google Maps Platform APIs
   - Places API (New) for real-time business data
   - Distance Matrix API for accessibility analysis

✅ Agent Architecture (MCP-style)
   - Tool-based agent design
   - BigQuery tool for data
   - Maps tool for intelligence
   - Agent for orchestration and reasoning

✅ Location Intelligence
   - Competition analysis
   - Foot traffic estimation
   - Multi-criteria ranking
   - Natural language explanations

🚀 NEXT STEPS:
1. Deploy this agent to Cloud Run
2. Add more data sources (demographics, traffic)
3. Build a web UI with Streamlit
4. Add memory for multi-turn conversations

"""

print(summary)

print("=" * 70)
print("🎉 Workshop Complete! You built a Location Intelligence AI Agent!")
print("=" * 70)

# -----------------------------------------------------------------------------
# Quick Test Runner (at the bottom for easy access)
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n💡 To run the full demo:")
    print("   1. Set your API keys at the top of this file")
    print("   2. Save the file")
    print("   3. Run: python workshop_main.py")
