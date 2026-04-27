# Location Intelligence Agent - Web Interface

A React + FastAPI web application for the Location Intelligence AI Agent.

## Architecture

```
web/
├── backend/           # FastAPI backend
│   ├── main.py        # FastAPI app with agent logic
│   └── requirements.txt # Python dependencies
│
└── frontend/          # React frontend (Vite)
    ├── src/
    │   ├── App.jsx    # Main React component
    │   ├── api.js     # API service
    │   └── ...
    ├── package.json
    └── vite.config.js
```

## Prerequisites

- Python 3.9+
- Node.js 18+
- Google Cloud Project with BigQuery access
- Google Maps API Key (Places API + Distance Matrix API enabled)

## Setup

### 1. Backend Setup

```bash
cd web/backend

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate
# Activate (Mac/Linux)
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Frontend Setup

```bash
cd web/frontend

# Install dependencies
npm install
```

### 3. Environment Variables

Create a `.env` file in the `web/backend/` folder:

```env
GOOGLE_CLOUD_PROJECT=your-project-id
MAPS_API_KEY=your-maps-api-key
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account-key.json
```

## Running the Application

### Start Backend (Terminal 1)

```bash
cd web/backend
venv\Scripts\activate  # if not already activated
python main.py
```

Backend will start at: http://localhost:8000

### Start Frontend (Terminal 2)

```bash
cd web/frontend
npm run dev
```

Frontend will start at: http://localhost:5173

## Usage

1. Open browser and go to http://localhost:5173
2. Type your query in the search box (e.g., "Where should I open a premium gym in Bangalore?")
3. Click "Analyze" to get recommendations
4. View top 3 location recommendations with:
   - Coordinates
   - Competitor analysis
   - Reasoning for recommendation
   - Nearby competitors

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API info |
| `/health` | GET | Health check |
| `/analyze` | POST | Analyze location query |
| `/sample-data` | GET | Get sample BigQuery data |

## Example API Call

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"query": "Where should I open a cafe in Bangalore?"}'
```

## Features

- **Interactive UI**: Clean React interface for queries
- **Real-time Analysis**: FastAPI backend processes requests
- **Competition Analysis**: Shows competitor count and ratings
- **Top 3 Recommendations**: Ranked by competition level
- **Mobile Responsive**: Works on desktop and mobile

## Troubleshooting

**Backend won't start**: Check that `GOOGLE_CLOUD_PROJECT` and `MAPS_API_KEY` are set

**CORS errors**: Ensure frontend URL is in CORS allow_origins in `main.py`

**BigQuery errors**: Verify service account has BigQuery Data Viewer role

**Maps API errors**: Check that Places API (New) and Distance Matrix API are enabled
