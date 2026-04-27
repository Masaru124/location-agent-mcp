# Location Intelligence AI Agent Workshop

A complete 6-hour workshop for building an AI agent that answers real-world location questions like "Where should I open a gym in Bangalore?" using Google Cloud ADK, BigQuery, and Google Maps Platform.

## 🎯 What You Will Build

An AI agent that:
- Understands natural language queries about business locations
- Queries BigQuery for geospatial data (OpenStreetMap)
- Uses Google Maps Platform for real-time location intelligence
- Combines data to rank and explain location recommendations

## 🛠️ Prerequisites

### Google Cloud Setup
1. Google Cloud project with billing enabled
2. APIs enabled:
   - BigQuery API
   - Places API (New)
   - Distance Matrix API
3. API keys created for Maps Platform

### Local Setup
```bash
# 1. Clone/Copy this project
cd location-intelligence-agent

# 2. Create virtual environment
python -m venv venv

# 3. Activate it
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Set up environment
cp .env.example .env
# Edit .env with your API keys
```

## 🚀 Quick Start

### For Workshop Lead (Before Event)
1. Run through `workshop_notebook.ipynb` to verify everything works
2. Test with your API keys
3. Share notebook with participants

### For Participants (During Workshop)
1. Open `workshop_notebook.ipynb` in Jupyter/Colab/Vertex AI
2. Add your API keys in the first cell
3. Run cells sequentially
4. By the end: You'll have a working Location Intelligence Agent!

## 📁 Project Structure

```
.
├── README.md                          # This file
├── requirements.txt                   # Python dependencies
├── .env.example                      # Environment template
├── workshop_notebook.ipynb           # Main workshop notebook ⭐
├── src/
│   ├── __init__.py
│   ├── agent.py                     # ADK Agent definition
│   ├── config.py                    # Configuration
│   └── utils.py                     # Helper functions
├── tools/
│   ├── __init__.py
│   ├── bigquery_tool.py             # BigQuery MCP tool
│   └── maps_tool.py                 # Google Maps MCP tool
└── data/
    └── sample_queries.sql           # Example SQL queries
```

## 📚 APIs Used

### BigQuery (Data Layer)
- Public dataset: `bigquery-public-data.geo_openstreetmap`
- Queries geospatial features in Bangalore
- No data upload needed!

### Google Maps Platform (Intelligence Layer)
- **Places API (New)**: Find nearby businesses, ratings
- **Distance Matrix API**: Calculate distances, travel times

### ADK (Agent Framework)
- Google Cloud Agent Development Kit
- Orchestrates tool usage
- Handles conversation flow

## 🎓 Workshop Flow (6 Hours)

| Hour | Focus | What Participants Do |
|------|-------|---------------------|
| 0-1 | Setup & Demo | Environment setup, see final agent work |
| 1-2 | Tool 1 | Build BigQuery tool, query Bangalore POIs |
| 2-3 | Tool 2 | Build Maps tool, get real-time data |
| 3-4 | Agent Core | Connect tools with ADK, basic reasoning |
| 4-5 | Intelligence | Ranking, combining data, explanations |
| 5-6 | Challenge | "Find best gym location" competition |

## 💡 Example Queries

Your agent will handle:
- "Where should I open a premium gym in Bangalore?"
- "Find best cafe locations near tech parks"
- "Which areas have high office density but low competition?"
- "Best location for a co-working space with good connectivity"

## 🔧 Troubleshooting

### BigQuery Access Issues
- Ensure BigQuery API is enabled
- Check your Google Cloud project has billing
- Verify you have BigQuery Data Viewer role

### Maps API Issues
- Check API key is valid and not restricted
- Ensure Places API (New) and Distance Matrix API are enabled
- Verify billing is enabled for project

### Python Import Errors
- Make sure you're in the virtual environment
- Reinstall: `pip install -r requirements.txt --force-reinstall`

## 📖 Key Concepts

### What is MCP?
Model Context Protocol (MCP) is how the agent "talks" to tools. Think of it as giving your AI the ability to:
- Query databases
- Call APIs
- Make calculations

### What is ADK?
Agent Development Kit is Google's framework for building AI agents. It handles:
- Tool orchestration
- Conversation management
- Reasoning loops

### Why Location Intelligence?
Location intelligence combines:
- **Data**: What's already there (BigQuery)
- **Context**: How do people move (Maps API)
- **Reasoning**: What makes a good location (AI)

## 🎓 Learning Outcomes

After this workshop, you will:
1. Build tool-using AI agents (not just prompt engineering)
2. Query geospatial data with BigQuery
3. Integrate Google Maps Platform APIs
4. Understand MCP-style tool orchestration
5. Create agents that make real-world recommendations

## 📧 Support

For workshop-specific questions, contact the instructor.
For technical issues with APIs, check Google Cloud documentation.

## 📝 License

This workshop material is provided for educational purposes.

## 🙏 Credits

- Google Cloud ADK Team
- BigQuery Public Datasets (OpenStreetMap)
- Google Maps Platform

---

**Ready to build? Open `workshop_notebook.ipynb` and let's go! 🚀**
