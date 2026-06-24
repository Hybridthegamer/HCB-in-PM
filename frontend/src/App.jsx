import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Dashboard from './components/Dashboard.jsx'
import Leaderboard from './components/Leaderboard.jsx'
import WalletProfile from './components/WalletProfile.jsx'
import AlertsPanel from './components/AlertsPanel.jsx'
import AlertRulesConfig from './components/AlertRulesConfig.jsx'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />}>
        <Route index element={<Navigate to="/leaderboard" replace />} />
        <Route path="leaderboard" element={<Leaderboard />} />
        <Route path="wallet/:walletId" element={<WalletProfile />} />
        <Route path="alerts" element={<AlertsPanel />} />
        <Route path="alert-rules" element={<AlertRulesConfig />} />
      </Route>
    </Routes>
  )
}
