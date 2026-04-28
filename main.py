"""
Main Module - Location Intelligence Agent Entry Point
==================================================

Terminal interface for the Location Intelligence Agent.
Uses BigQuery OpenStreetMap data, Google Maps APIs, and Ollama LLM.
"""

import os
from dotenv import load_dotenv

# Import our modules
from tools import BigQueryTool, MapsTool
from agent import LocationIntelligenceAgent

# Load environment variables
load_dotenv()

# Environment variables
project_id = os.getenv('GOOGLE_CLOUD_PROJECT', 'location-494614')
maps_key = os.getenv('MAPS_API_KEY', 'your-maps-api-key')


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
