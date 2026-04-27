import { useState, useEffect } from 'react'
import { healthCheck, analyzeLocation } from './api.js'
import './App.css'

function App() {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [agentStatus, setAgentStatus] = useState('checking')

  useEffect(() => {
    checkAgentStatus()
  }, [])

  const checkAgentStatus = async () => {
    const status = await healthCheck()
    setAgentStatus(status.status === 'healthy' ? 'ready' : 'not_configured')
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!query.trim()) return

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const data = await analyzeLocation(query)
      setResult(data)
    } catch (err) {
      setError(err.toString())
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <header className="header">
        <h1>🎯 Location Intelligence Agent</h1>
        <p>AI-powered location recommendations for your business</p>
        <div className={`status-badge ${agentStatus}`}>
          {agentStatus === 'ready' ? '🟢 Agent Ready' : agentStatus === 'checking' ? '🟡 Checking...' : '🔴 Not Configured'}
        </div>
      </header>

      <main className="main">
        <div className="query-section">
          <form onSubmit={handleSubmit} className="query-form">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Where should I open a premium gym in Bangalore?"
              className="query-input"
              disabled={loading}
            />
            <button 
              type="submit" 
              className="submit-btn"
              disabled={loading || !query.trim()}
            >
              {loading ? 'Analyzing...' : 'Analyze'}
            </button>
          </form>
        </div>

        {loading && (
          <div className="loading">
            <div className="spinner"></div>
            <p>Analyzing location data...</p>
          </div>
        )}

        {error && (
          <div className="error">
            <h3>❌ Error</h3>
            <p>{error}</p>
          </div>
        )}

        {result && (
          <div className="results">
            <div className="result-header">
              <h2>📊 Analysis Results</h2>
              <div className="query-display">
                <strong>Query:</strong> {result.query}
              </div>
              <div className="business-type">
                <strong>Business Type:</strong> {result.business_type}
              </div>
              <div className="analyzed-count">
                <strong>Locations Analyzed:</strong> {result.total_analyzed}
              </div>
            </div>

            {result.error ? (
              <div className="error">{result.error}</div>
            ) : (
              <>
                {/* Debug: Check if AI insights exist */}
                {console.log("Frontend result:", result)}
                {console.log("AI insights exists:", !!result.ai_insights)}
                {console.log("AI insights value:", result.ai_insights)}
                
                {result.ai_insights && (
                  <div className="ai-insights">
                    <h3>🤖 AI-Powered Insights</h3>
                    <div className="insights-content">
                      <p>{result.ai_insights}</p>
                    </div>
                  </div>
                )}
                
                <div className="recommendations">
                  <h3>🏆 Top Recommendations</h3>
                  {result.recommendations?.map((rec, index) => (
                    <div key={index} className="recommendation-card">
                      <div className="card-header">
                        <span className="rank">#{index + 1}</span>
                        <h4>{rec.name}</h4>
                      </div>
                      
                      <div className="coordinates">
                        📍 {rec.lat.toFixed(6)}, {rec.lng.toFixed(6)}
                      </div>

                      <div className="stats">
                        <div className="stat">
                          <span className="stat-label">Competitors Nearby:</span>
                          <span className={`stat-value ${rec.competitor_count < 3 ? 'good' : rec.competitor_count > 10 ? 'bad' : 'medium'}`}>
                            {rec.competitor_count}
                          </span>
                        </div>
                        <div className="stat">
                          <span className="stat-label">Avg Competitor Rating:</span>
                          <span className="stat-value">{rec.avg_competitor_rating}/5</span>
                        </div>
                      </div>

                      <div className="reasoning">
                        <strong>💡 Why this location?</strong>
                        <p>{rec.reasoning}</p>
                      </div>

                      {rec.competitors?.length > 0 && (
                        <div className="competitors">
                          <strong>🏢 Nearby Competitors:</strong>
                          <ul>
                            {rec.competitors.map((comp, i) => (
                              <li key={i}>
                                {comp.name}
                                {comp.rating && ` (${comp.rating}⭐)`}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
      </main>

      <footer className="footer">
        <p>Powered by BigQuery OpenStreetMap & Google Maps Platform</p>
      </footer>
    </div>
  )
}

export default App
