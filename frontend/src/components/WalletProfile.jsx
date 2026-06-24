import React from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend
} from 'recharts'
import { fetchWallet, fetchWalletScores } from '../api/client.js'

function ScoreBar({ label, value, color = 'bg-blue-500' }) {
  const pct = value != null ? Math.round(value * 100) : 0
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span className="text-gray-400">{label}</span>
        <span className="font-mono text-gray-200">{value != null ? `${pct}%` : 'N/A'}</span>
      </div>
      <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function truncateWallet(addr) {
  if (!addr) return ''
  return `${addr.slice(0, 8)}...${addr.slice(-6)}`
}

function formatDate(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  })
}

const SCORE_COLORS = {
  composite_score: '#3b82f6',
  win_rate: '#10b981',
  timing_score: '#f59e0b',
  consistency_score: '#8b5cf6',
  position_size_score: '#ec4899',
}

export default function WalletProfile() {
  const { walletId } = useParams()
  const navigate = useNavigate()

  const { data: wallet, isLoading, isError } = useQuery({
    queryKey: ['wallet', walletId],
    queryFn: () => fetchWallet(walletId, { trade_limit: 100 }),
  })

  const { data: scores = [] } = useQuery({
    queryKey: ['wallet-scores', walletId],
    queryFn: () => fetchWalletScores(walletId, { days: 30 }),
  })

  if (isLoading) {
    return <div className="text-gray-400 py-12 text-center">Loading wallet profile...</div>
  }
  if (isError || !wallet) {
    return (
      <div className="py-12 text-center">
        <p className="text-red-400 mb-4">Wallet not found or API unavailable.</p>
        <button className="btn-secondary" onClick={() => navigate(-1)}>Go Back</button>
      </div>
    )
  }

  const chartData = scores.map(s => ({
    time: new Date(s.computed_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    CBS: s.composite_score != null ? +(s.composite_score * 100).toFixed(1) : null,
    'Win Rate': s.win_rate != null ? +(s.win_rate * 100).toFixed(1) : null,
    'Timing': s.timing_score != null ? +(s.timing_score * 100).toFixed(1) : null,
  }))

  const cbs = wallet.composite_score
  const cbsColor = cbs == null ? 'text-gray-500'
    : cbs >= 0.7 ? 'text-green-400'
    : cbs >= 0.4 ? 'text-yellow-400'
    : 'text-red-400'

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start gap-4">
        <button
          onClick={() => navigate(-1)}
          className="text-gray-400 hover:text-gray-200 mt-1"
        >
          &larr; Back
        </button>
        <div>
          <h2 className="text-xl font-bold text-white font-mono break-all">
            {wallet.wallet_id}
          </h2>
          <p className="text-sm text-gray-400 mt-1">
            First seen: {formatDate(wallet.first_seen)} &middot; {wallet.total_trades} trades
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Score breakdown */}
        <div className="card space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-white">Score Breakdown</h3>
            <span className={`text-3xl font-bold font-mono ${cbsColor}`}>
              {cbs != null ? (cbs * 100).toFixed(1) : 'N/A'}
            </span>
          </div>
          {wallet.label && (
            <span className="badge bg-red-900/50 text-red-300 border border-red-700/50">
              {wallet.label}
            </span>
          )}
          <div className="space-y-3 pt-2">
            <ScoreBar label="Win Rate (35%)" value={wallet.win_rate} color="bg-green-500" />
            <ScoreBar label="Position Size (25%)" value={null} color="bg-pink-500" />
            <ScoreBar label="Timing (25%)" value={null} color="bg-amber-500" />
            <ScoreBar label="Consistency (15%)" value={null} color="bg-violet-500" />
          </div>
          <div className="text-xs text-gray-500 border-t border-gray-800 pt-3">
            CBS = 0.35·WR + 0.25·PS + 0.25·TS + 0.15·CS
          </div>
        </div>

        {/* Score history chart */}
        <div className="card lg:col-span-2">
          <h3 className="font-semibold text-white mb-4">Score History (30 days)</h3>
          {chartData.length === 0 ? (
            <p className="text-gray-500 text-sm py-8 text-center">
              No score history yet. Scores are computed after at least 10 resolved trades.
            </p>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="time" tick={{ fill: '#9ca3af', fontSize: 11 }} />
                <YAxis
                  domain={[0, 100]}
                  tick={{ fill: '#9ca3af', fontSize: 11 }}
                  tickFormatter={v => `${v}%`}
                />
                <Tooltip
                  contentStyle={{ background: '#111827', border: '1px solid #374151' }}
                  labelStyle={{ color: '#e5e7eb' }}
                  formatter={v => [`${v}%`]}
                />
                <Legend />
                <Line
                  type="monotone" dataKey="CBS" stroke="#3b82f6"
                  strokeWidth={2} dot={false} name="CBS"
                />
                <Line
                  type="monotone" dataKey="Win Rate" stroke="#10b981"
                  strokeWidth={1.5} dot={false} strokeDasharray="4 2"
                />
                <Line
                  type="monotone" dataKey="Timing" stroke="#f59e0b"
                  strokeWidth={1.5} dot={false} strokeDasharray="4 2"
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Trade history */}
      <div className="card p-0 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-800">
          <h3 className="font-semibold text-white">Trade History</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead>
              <tr className="border-b border-gray-800">
                <th className="table-header">Time</th>
                <th className="table-header">Market</th>
                <th className="table-header">Outcome</th>
                <th className="table-header">Amount</th>
                <th className="table-header">Entry Price</th>
                <th className="table-header">Shares</th>
                <th className="table-header">Result</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/50">
              {wallet.trades?.length === 0 && (
                <tr>
                  <td colSpan={7} className="table-cell text-center text-gray-500 py-8">
                    No trades found.
                  </td>
                </tr>
              )}
              {wallet.trades?.map(trade => (
                <tr key={trade.trade_id} className="hover:bg-gray-800/30">
                  <td className="table-cell text-xs text-gray-400 whitespace-nowrap">
                    {formatDate(trade.tx_timestamp)}
                  </td>
                  <td className="table-cell font-mono text-xs text-gray-400 max-w-xs truncate">
                    {trade.market_id}
                  </td>
                  <td className="table-cell">
                    <span className={`badge ${
                      trade.outcome === 'YES'
                        ? 'bg-green-900/40 text-green-400'
                        : 'bg-red-900/40 text-red-400'
                    }`}>
                      {trade.outcome}
                    </span>
                  </td>
                  <td className="table-cell font-mono">
                    ${Number(trade.amount_usd).toLocaleString('en-US', { maximumFractionDigits: 2 })}
                  </td>
                  <td className="table-cell font-mono">
                    {(trade.price_at_entry * 100).toFixed(1)}%
                  </td>
                  <td className="table-cell font-mono">
                    {Number(trade.shares).toFixed(2)}
                  </td>
                  <td className="table-cell">
                    {!trade.resolved ? (
                      <span className="badge bg-gray-700 text-gray-400">Open</span>
                    ) : trade.won ? (
                      <span className="badge bg-green-900/50 text-green-400">Won</span>
                    ) : (
                      <span className="badge bg-red-900/50 text-red-400">Lost</span>
                    )}
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
