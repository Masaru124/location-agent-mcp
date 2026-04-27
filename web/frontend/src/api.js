import axios from 'axios'

const API_BASE_URL = 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json'
  }
})

export const healthCheck = async () => {
  try {
    const response = await api.get('/health')
    return response.data
  } catch (error) {
    return { status: 'error', message: error.message }
  }
}

export const analyzeLocation = async (query) => {
  try {
    const response = await api.post('/analyze', { query })
    return response.data
  } catch (error) {
    throw error.response?.data?.detail || error.message
  }
}

export const getSampleData = async () => {
  try {
    const response = await api.get('/sample-data')
    return response.data
  } catch (error) {
    throw error.response?.data?.detail || error.message
  }
}
