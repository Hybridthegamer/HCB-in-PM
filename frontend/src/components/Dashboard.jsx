import React from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchStats } from '../api/client.js'

function StatCard({ label, value, color = 'text-blue-400' }) {
  return (
    <div className="card flex flex-col gap-1">
      <span className="text-xs text-gray-400 uppercase tracking-wider">{label}</span>
      <span className={`text-2xl font-bold ${color}`}>
        {value ?? <span className="animate-pulse text-gray-600">--</span>}
      </span>
    </div>
  )
}

const navItems = [
  { to: '/leaderboard',   label: 'Leaderboard',  icon: '🏆' },
  { to: '/alerts',        label: 'Alerts',        icon: '🔔' },
  { to: '/alert-rules',   label: 'Alert Rules',   icon: '⚙️' },
]

export default function Dashboard() {
  const { data: stats } = useQuery({
    queryKey: ['stats'],
    queryFn: fetchStats,
    refetchInterval: 30_000,
  })

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-60 flex-shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col">
        {/* Brand */}
        <div className="p-6 border-b border-gray-800">
          <h1 className="text-lg font-bold text-white tracking-tight">HCB Monitor</h1>
          <p className="text-xs text-gray-500 mt-1">Prediction Market Intelligence</p>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 space-y-1">
          {navItems.map(({ to, label, icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-600/20 text-blue-400 border border-blue-600/30'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800'
                }`
              }
            >
              <span>{icon}</span>
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-gray-800 text-xs text-gray-600">
          Polymarket CLOB Monitor
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        {/* Stats bar */}
        {stats && (
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 p-6 border-b border-gray-800">
            <StatCard label="Wallets" value={stats.total_wallets} />
            <StatCard label="Trades" value={stats.total_trades.toLocaleString()} />
            <StatCard label="Markets" value={stats.total_markets} />
            <StatCard label="Alerts Today" value={stats.alerts_today} color="text-yellow-400" />
            <StatCard label="Anomalies" value={stats.anomaly_wallets} color="text-red-400" />
          </div>
        )}

        {/* Page content */}
        <div className="p-6">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
