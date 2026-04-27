"""Configuration management for the Location Intelligence Agent."""

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Configuration settings for the agent."""
    
    # Google Cloud
    GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    
    # Maps API
    MAPS_API_KEY = os.getenv("MAPS_API_KEY", "")
    
    # Default region settings
    DEFAULT_REGION = os.getenv("DEFAULT_REGION", "IN")
    DEFAULT_CITY = os.getenv("DEFAULT_CITY", "Bangalore")
    DEFAULT_CITY_CENTER_LAT = 12.9716
    DEFAULT_CITY_CENTER_LNG = 77.5946
    
    # BigQuery settings
    BIGQUERY_DATASET = "bigquery-public-data.geo_openstreetmap"
    
    # Agent settings
    AGENT_NAME = "location_intelligence_agent"
    AGENT_DESCRIPTION = "AI agent for location intelligence and business site selection"
    
    @classmethod
    def validate(cls):
        """Validate that required configuration is set."""
        missing = []
        
        if not cls.GOOGLE_CLOUD_PROJECT:
            missing.append("GOOGLE_CLOUD_PROJECT")
        
        if not cls.MAPS_API_KEY:
            missing.append("MAPS_API_KEY")
        
        if missing:
            raise ValueError(
                f"Missing required configuration: {', '.join(missing)}\n"
                f"Please set these in your .env file or environment variables."
            )
        
        return True

# Create config instance
config = Config()
