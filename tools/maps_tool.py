"""Google Maps Platform MCP Tool for location intelligence."""

import requests
import json
from typing import List, Dict, Any, Optional
from src.config import config

class MapsTool:
    """
    MCP Tool for Google Maps Platform APIs.
    
    Provides:
    - Places API (New): Find nearby businesses, details
    - Distance Matrix API: Calculate distances and times
    """
    
    def __init__(self, api_key: str):
        """
        Initialize Maps tool.
        
        Args:
            api_key: Google Maps Platform API key
        """
        self.api_key = api_key
        self.base_url = "https://maps.googleapis.com/maps/api"
    
    def nearby_search(self, 
                      lat: float, 
                      lng: float, 
                      keyword: str,
                      radius: int = 2000,
                      max_results: int = 20) -> List[Dict[str, Any]]:
        """
        Search for nearby places using Places API (New).
        
        Args:
            lat: Latitude of search center
            lng: Longitude of search center
            keyword: Search term (e.g., 'gym', 'cafe')
            radius: Search radius in meters (max 50000)
            max_results: Maximum results to return
        
        Returns:
            List of place dictionaries
        """
        url = "https://places.googleapis.com/v1/places:searchNearby"
        
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "places.displayName,places.location,places.rating,places.userRatingCount,places.types"
        }
        
        body = {
            "locationRestriction": {
                "circle": {
                    "center": {
                        "latitude": lat,
                        "longitude": lng
                    },
                    "radius": min(radius, 50000)  # Max 50km
                }
            },
            "includedTypes": ["gym"] if keyword == "gym" else None,
            "keyword": keyword,
            "maxResultCount": min(max_results, 20)  # API limit
        }
        
        # Remove None values
        body = {k: v for k, v in body.items() if v is not None}
        
        try:
            response = requests.post(url, headers=headers, json=body)
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
                    "types": place.get("types", []),
                    "source": "places_api"
                })
            
            return places
            
        except requests.exceptions.RequestException as e:
            print(f"Places API error: {str(e)}")
            return []
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            return []
    
    def distance_matrix(self,
                       origins: List[tuple],
                       destinations: List[tuple],
                       mode: str = "driving") -> Dict[str, Any]:
        """
        Calculate distances between multiple points.
        
        Args:
            origins: List of (lat, lng) tuples
            destinations: List of (lat, lng) tuples
            mode: Travel mode (driving, walking, transit)
        
        Returns:
            Distance matrix with distances and durations
        """
        # Format coordinates for API
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
                return {
                    "error": data.get("status"),
                    "message": data.get("error_message", "Unknown error")
                }
            
            # Parse results
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
            
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}
        except Exception as e:
            return {"error": f"Unexpected error: {str(e)}"}
    
    def calculate_distances_from_point(self,
                                       origin_lat: float,
                                       origin_lng: float,
                                       destinations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Calculate distances from one point to multiple destinations.
        
        Args:
            origin_lat: Origin latitude
            origin_lng: Origin longitude
            destinations: List of destination dictionaries with 'lat' and 'lng'
        
        Returns:
            Destinations with added distance/duration fields
        """
        if not destinations:
            return []
        
        # Batch destinations (API limit is 25 destinations per request)
        BATCH_SIZE = 25
        updated_destinations = []
        
        for i in range(0, len(destinations), BATCH_SIZE):
            batch = destinations[i:i + BATCH_SIZE]
            
            origins = [(origin_lat, origin_lng)]
            dests = [(d["lat"], d["lng"]) for d in batch]
            
            matrix = self.distance_matrix(origins, dests)
            
            if "error" in matrix:
                print(f"Distance calculation error: {matrix['error']}")
                continue
            
            results = matrix.get("results", [])
            
            for j, dest in enumerate(batch):
                # Find result for this destination
                result = next((r for r in results if r["destination_index"] == j), None)
                
                if result:
                    dest_copy = dest.copy()
                    dest_copy["distance_meters"] = result.get("distance_meters")
                    dest_copy["distance_km"] = round(result.get("distance_meters", 0) / 1000, 2)
                    dest_copy["duration_minutes"] = round(result.get("duration_seconds", 0) / 60, 1)
                    dest_copy["duration_text"] = result.get("duration_text")
                    updated_destinations.append(dest_copy)
                else:
                    updated_destinations.append(dest)
        
        return updated_destinations
    
    def find_competitors(self,
                        lat: float,
                        lng: float,
                        business_type: str,
                        radius_meters: int = 2000) -> int:
        """
        Count competitors near a location.
        
        Args:
            lat: Latitude
            lng: Longitude
            business_type: Type of business to search for
            radius_meters: Search radius
        
        Returns:
            Count of nearby competitors
        """
        places = self.nearby_search(lat, lng, business_type, radius_meters, max_results=20)
        return len(places)
    
    def get_location_score(self,
                         lat: float,
                         lng: float,
                         business_type: str,
                         reference_points: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Calculate a comprehensive location score.
        
        Args:
            lat: Location latitude
            lng: Location longitude
            business_type: Type of business
            reference_points: Points of interest to measure distance from
        
        Returns:
            Score and metrics for the location
        """
        score_data = {
            "lat": lat,
            "lng": lng,
            "business_type": business_type,
            "metrics": {}
        }
        
        # Get competitors count
        competitor_count = self.find_competitors(lat, lng, business_type)
        score_data["competitor_count"] = competitor_count
        
        # Get nearby places for foot traffic estimate
        nearby = self.nearby_search(lat, lng, "restaurant", radius=1000)
        score_data["nearby_businesses_count"] = len(nearby)
        
        # Calculate average distance to reference points if provided
        if reference_points:
            distances = self.calculate_distances_from_point(lat, lng, reference_points)
            if distances:
                avg_distance = sum(d.get("distance_km", 0) for d in distances) / len(distances)
                score_data["avg_distance_to_references"] = round(avg_distance, 2)
        
        return score_data

# MCP Tool interface functions
def create_maps_tool(api_key: str = None) -> MapsTool:
    """Factory function to create Maps tool."""
    if api_key is None:
        api_key = config.MAPS_API_KEY
    return MapsTool(api_key)

def nearby_search_tool(tool: MapsTool, lat: float, lng: float, keyword: str) -> str:
    """MCP-compatible interface for nearby search."""
    results = tool.nearby_search(lat, lng, keyword)
    return json.dumps(results, indent=2)

def distance_tool(tool: MapsTool, 
                  origin_lat: float, 
                  origin_lng: float,
                  dest_lat: float, 
                  dest_lng: float) -> str:
    """MCP-compatible interface for single distance calculation."""
    result = tool.distance_matrix(
        [(origin_lat, origin_lng)],
        [(dest_lat, dest_lng)]
    )
    return json.dumps(result, indent=2)
