import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { fetchAlerts } from '../api/client.js'

function truncateWallet(addr) {
  if (!addr) return ''
  return `${addr.slice(0, 6)}...${addr.slice(-4)}`
}

function formatDate(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleString('en-US', {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit'
  })
}

export default function AlertsPanel() {
  const navigate = useNavigate()
  const [walletFilter, setWalletFilter] = useState('')

  const { data: alerts = [], isLoading, isError, refetch } = useQuery({
    queryKey: ['alerts', walletFilter],
    queryFn: () => fetchAlerts({ limit: 200, wallet_id: walletFilter || undefined }),
    refetchInterval: 30_000,
  })

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-white">Alerts</h2>
        <button onClick={() => refetch()} className="btn-secondary text-sm">
          Refresh
        </button>
      </div>

      <div className="flex gap-3">
        <input
          className="input max-w-xs"
          placeholder="Filter by wallet address..."
          value={walletFilter}
          onChange={e => setWalletFilter(e.target.value)}
        />
        <span className="text-sm text-gray-400 self-center">
          {alerts.length} alert{alerts.length !== 1 ? 's' : ''}
        </span>
      </div>

      <div className="card p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead>
              <tr className="border-b border-gray-800">
                <th className="table-header">Time</th>
                <th className="table-header">Wallet</th>
                <th className="table-header">Rule</th>
                <th className="table-header">Triggered Value</th>
                <th className="table-header">CBS</th>
                <th className="table-header">Channels</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/50">
              {isLoading && (
                <tr>
                  <td colSpan={6} className="table-cell text-center text-gray-500 py-12">
                    Loading alerts...
                  </td>
                </tr>
              )}
              {isError && (
                <tr>
                  <td colSpan={6} className="table-cell text-center text-red-400 py-12">
                    Failed to load alerts.
                  </td>
                </tr>
              )}
              {!isLoading && alerts.length === 0 && (
                <tr>
                  <td colSpan={6} className="table-cell text-center text-gray-500 py-12">
                    No alerts fired yet. Configure alert rules to start monitoring.
                  </td>
                </tr>
              )}
              {alerts.map(alert => (
                <tr
                  key={alert.alert_id}
                  className="hover:bg-gray-800/30"
                >
                  <td className="table-cell text-xs text-gray-400 whitespace-nowrap">
                    {formatDate(alert.dispatched_at)}
                  </td>
                  <td className="table-cell">
                    <button
                      className="font-mono text-blue-400 hover:text-blue-300 text-sm"
                      onClick={() => navigate(`/wallet/${alert.wallet_id}`)}
                    >
                      {truncateWallet(alert.wallet_id)}
                    </button>
                  </td>
                  <td className="table-cell">
                    <span className="text-gray-200">{alert.rule_name || `Rule #${alert.rule_id}`}</span>
                  </td>
                  <td className="table-cell font-mono">
                    {alert.triggered_metric != null
                      ? alert.triggered_metric.toFixed(4)
                      : 'N/A'}
                  </td>
                  <td className="table-cell font-mono">
                    {alert.composite_score != null
                      ? (alert.composite_score * 100).toFixed(1) + '%'
                      : 'N/A'}
                  </td>
                  <td className="table-cell">
                    <div className="flex gap-1 flex-wrap">
                      {(alert.channels_notified ?? []).map(ch => (
                        <span
                          key={ch}
                          className="badge bg-gray-700 text-gray-300 text-xs"
                        >
                          {ch}
                        </span>
                      ))}
                      {(!alert.channels_notified || alert.channels_notified.length === 0) && (
                        <span className="text-gray-600 text-xs">none</span>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
