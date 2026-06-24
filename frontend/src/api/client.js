import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || '/api'

const client = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 15_000,
})

// Wallets
export const fetchWallets = (params = {}) =>
  client.get('/wallets', { params }).then(r => r.data)

export const fetchWallet = (walletId, params = {}) =>
  client.get(`/wallets/${walletId}`, { params }).then(r => r.data)

export const fetchWalletScores = (walletId, params = {}) =>
  client.get(`/wallets/${walletId}/scores`, { params }).then(r => r.data)

// Trades
export const fetchTrades = (params = {}) =>
  client.get('/trades', { params }).then(r => r.data)

// Markets
export const fetchMarkets = (params = {}) =>
  client.get('/markets', { params }).then(r => r.data)

// Alerts
export const fetchAlerts = (params = {}) =>
  client.get('/alerts', { params }).then(r => r.data)

// Alert Rules
export const fetchAlertRules = () =>
  client.get('/alert-rules').then(r => r.data)

export const createAlertRule = (data) =>
  client.post('/alert-rules', data).then(r => r.data)

export const updateAlertRule = (id, data) =>
  client.put(`/alert-rules/${id}`, data).then(r => r.data)

export const deleteAlertRule = (id) =>
  client.delete(`/alert-rules/${id}`)

// Stats
export const fetchStats = () =>
  client.get('/stats').then(r => r.data)

// Backfill
export const triggerBackfill = (walletAddress) =>
  client.post('/backfill', { wallet_address: walletAddress }).then(r => r.data)

export default client
