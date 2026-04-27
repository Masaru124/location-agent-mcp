"""BigQuery MCP Tool for querying geospatial data."""

from google.cloud import bigquery
from google.api_core import retry
from typing import List, Dict, Any, Optional
import pandas as pd

class BigQueryTool:
    """
    MCP Tool for querying BigQuery geospatial data.
    
    This tool queries OpenStreetMap data from BigQuery public datasets
    to find points of interest in Bangalore.
    """
    
    def __init__(self, project_id: str):
        """
        Initialize BigQuery client.
        
        Args:
            project_id: Google Cloud project ID
        """
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
    
    def query_pois(self, 
                   category: str, 
                   limit: int = 50,
                   area: str = "bangalore") -> List[Dict[str, Any]]:
        """
        Query Points of Interest from OpenStreetMap data.
        
        Args:
            category: Type of business (e.g., 'cafe', 'gym', 'restaurant')
            limit: Maximum number of results
            area: Area to search (default: bangalore)
        
        Returns:
            List of POI dictionaries with name, lat, lng, etc.
        """
        # Map common business types to OSM tags
        osm_tags = self._get_osm_tags(category)
        
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
            '{category}' AS category,
            CAST(NULL AS FLOAT64) AS rating
        FROM `{self.dataset}.planet_features`
        WHERE ST_WITHIN(
            geometry,
            ST_GEOGFROMTEXT('{polygon_wkt}')
        )
        AND ST_GEOMETRYTYPE(geometry) = 'ST_Point'
        AND (
            {osm_tags}
        )
        AND (SELECT value FROM UNNEST(all_tags) WHERE key = 'name' LIMIT 1) IS NOT NULL
        LIMIT {limit}
        """
        
        try:
            query_job = self.client.query(query, project=self.project_id)
            results = query_job.result()
            
            # Convert to list of dictionaries
            pois = []
            for row in results:
                pois.append({
                    "name": row.name if row.name else "Unknown",
                    "lat": row.lat,
                    "lng": row.lng,
                    "category": row.category,
                    "rating": row.rating if row.rating else None
                })
            
            return pois
            
        except Exception as e:
            print(f"BigQuery error: {str(e)}")
            return []
    
    def query_density_analysis(self,
                               center_lat: float,
                               center_lng: float,
                               radius_km: float = 2.0,
                               categories: List[str] = None) -> Dict[str, Any]:
        """
        Analyze business density around a specific point.
        
        Args:
            center_lat: Center latitude
            center_lng: Center longitude
            radius_km: Radius in kilometers
            categories: List of business categories to count
        
        Returns:
            Dictionary with density metrics
        """
        if categories is None:
            categories = ["cafe", "restaurant", "gym", "office"]
        
        # Simplified query - count businesses in radius
        query = f"""
        SELECT 
            COUNT(*) as total_count,
            AVG(ST_DISTANCE(
                geometry, 
                ST_GEOGPOINT({center_lng}, {center_lat})
            )) / 1000 as avg_distance_km
        FROM `{self.dataset}.planet_features`
        WHERE ST_DWITHIN(
            geometry,
            ST_GEOGPOINT({center_lng}, {center_lat}),
            {radius_km * 1000}
        )
        """
        
        try:
            query_job = self.client.query(query, project=self.project_id)
            result = list(query_job.result())[0]
            
            return {
                "total_businesses": result.total_count,
                "avg_distance_km": result.avg_distance_km,
                "radius_km": radius_km,
                "center": {"lat": center_lat, "lng": center_lng}
            }
            
        except Exception as e:
            print(f"Density analysis error: {str(e)}")
            return {
                "total_businesses": 0,
                "avg_distance_km": radius_km,
                "radius_km": radius_km,
                "center": {"lat": center_lat, "lng": center_lng},
                "error": str(e)
            }
    
    def _get_osm_tags(self, category: str) -> str:
        """Map business category to OSM conditions using all_tags array."""
        
        # OSM tags are stored in all_tags array as key-value pairs
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
        
        default_condition = f"(SELECT value FROM UNNEST(all_tags) WHERE key = 'name' LIMIT 1) LIKE '%{category}%'"
        
        return category_map.get(category.lower(), default_condition)
    
    def get_sample_data(self, limit: int = 10) -> pd.DataFrame:
        """Get sample data to verify connection."""
        # Build polygon string
        min_lng = self.bangalore_bbox['min_lng']
        min_lat = self.bangalore_bbox['min_lat']
        max_lng = self.bangalore_bbox['max_lng']
        max_lat = self.bangalore_bbox['max_lat']
        polygon_wkt = f"POLYGON(({min_lng} {min_lat}, {max_lng} {min_lat}, {max_lng} {max_lat}, {min_lng} {max_lat}, {min_lng} {min_lat}))"
        
        query = f"""
        SELECT 
            (SELECT value FROM UNNEST(all_tags) WHERE key = 'name' LIMIT 1) AS feature_name,
            feature_type,
            ST_Y(geometry) AS lat,
            ST_X(geometry) AS lng
        FROM `{self.dataset}.planet_features`
        WHERE ST_WITHIN(
            geometry,
            ST_GEOGFROMTEXT('{polygon_wkt}')
        )
        AND ST_GEOMETRYTYPE(geometry) = 'ST_Point'
        AND (SELECT value FROM UNNEST(all_tags) WHERE key = 'name' LIMIT 1) IS NOT NULL
        LIMIT {limit}
        """
        
        try:
            return self.client.query(query, project=self.project_id).to_dataframe()
        except Exception as e:
            print(f"Error fetching sample data: {str(e)}")
            return pd.DataFrame()

# MCP Tool interface functions
def create_bigquery_tool(project_id: str) -> BigQueryTool:
    """Factory function to create BigQuery tool."""
    return BigQueryTool(project_id)

def query_pois_tool(tool: BigQueryTool, category: str, limit: int = 20) -> str:
    """MCP-compatible interface for querying POIs."""
    results = tool.query_pois(category, limit)
    return json.dumps(results, indent=2)

def density_analysis_tool(tool: BigQueryTool, 
                          lat: float, 
                          lng: float, 
                          radius: float = 2.0) -> str:
    """MCP-compatible interface for density analysis."""
    results = tool.query_density_analysis(lat, lng, radius)
    return json.dumps(results, indent=2)

import json
