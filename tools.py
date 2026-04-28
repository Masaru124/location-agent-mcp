"""
Tools Module - BigQuery and Maps API Tools
==========================================

Contains BigQueryTool and MapsTool classes for data access.
"""

import os
import requests
from typing import List, Dict, Any

# Import Google Cloud libraries
try:
    from google.cloud import bigquery
    from google.oauth2 import service_account
    BIGQUERY_AVAILABLE = True
except ImportError:
    BIGQUERY_AVAILABLE = False
    print("⚠️  Google Cloud libraries not installed. Install with: pip install google-cloud-bigquery")


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
