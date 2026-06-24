import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { fetchWallets } from '../api/client.js'

function ScoreBadge({ score }) {
  if (score == null) return <span className="text-gray-600">N/A</span>
  const pct = (score * 100).toFixed(1)
  const color =
    score >= 0.7
      ? 'bg-green-900/40 text-green-400 border-green-700/40'
      : score >= 0.4
      ? 'bg-yellow-900/40 text-yellow-400 border-yellow-700/40'
      : 'bg-red-900/40 text-red-400 border-red-700/40'
  return (
    <span className={`badge border ${color} font-mono`}>{pct}%</span>
  )
}

function LabelBadge({ label }) {
  if (!label) return null
  const color =
    label === 'anomaly-high'
      ? 'bg-red-900/50 text-red-300 border-red-700/50'
      : 'bg-blue-900/50 text-blue-300 border-blue-700/50'
  return (
    <span className={`badge border ${color}`}>{label}</span>
  )
}

function truncateWallet(addr) {
  if (!addr) return ''
  return `${addr.slice(0, 6)}...${addr.slice(-4)}`
}

function formatDate(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

export default function Leaderboard() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const PAGE_SIZE = 50

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['wallets', page, search],
    queryFn: () => fetchWallets({ page, page_size: PAGE_SIZE, search: search || undefined }),
    keepPreviousData: true,
  })

  const wallets = data?.items ?? []
  const total = data?.total ?? 0
  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-white">Wallet Leaderboard</h2>
        <button onClick={() => refetch()} className="btn-secondary text-sm">
          Refresh
        </button>
      </div>

      {/* Search */}
      <div className="flex gap-3">
        <input
          className="input max-w-xs"
          placeholder="Search wallet address..."
          value={search}
          onChange={e => { setSearch(e.target.value); setPage(1) }}
        />
        <span className="text-sm text-gray-400 self-center">
          {total.toLocaleString()} wallets
        </span>
      </div>

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead>
              <tr className="border-b border-gray-800">
                <th className="table-header">#</th>
                <th className="table-header">Wallet</th>
                <th className="table-header">CBS Score</th>
                <th className="table-header">Win Rate</th>
                <th className="table-header">Avg Position</th>
                <th className="table-header">Trades</th>
                <th className="table-header">Label</th>
                <th className="table-header">First Seen</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/50">
              {isLoading && (
                <tr>
                  <td colSpan={8} className="table-cell text-center text-gray-500 py-12">
                    Loading...
                  </td>
                </tr>
              )}
              {isError && (
                <tr>
                  <td colSpan={8} className="table-cell text-center text-red-400 py-12">
                    Failed to load wallets. Is the backend running?
                  </td>
                </tr>
              )}
              {!isLoading && wallets.length === 0 && (
                <tr>
                  <td colSpan={8} className="table-cell text-center text-gray-500 py-12">
                    No wallets found. Trades will appear as Polymarket activity is detected.
                  </td>
                </tr>
              )}
              {wallets.map((w, idx) => (
                <tr
                  key={w.wallet_id}
                  className="hover:bg-gray-800/40 cursor-pointer transition-colors"
                  onClick={() => navigate(`/wallet/${w.wallet_id}`)}
                >
                  <td className="table-cell text-gray-500 font-mono">
                    {(page - 1) * PAGE_SIZE + idx + 1}
                  </td>
                  <td className="table-cell">
                    <span className="font-mono text-blue-400 hover:text-blue-300">
                      {truncateWallet(w.wallet_id)}
                    </span>
                  </td>
                  <td className="table-cell">
                    <ScoreBadge score={w.composite_score} />
                  </td>
                  <td className="table-cell font-mono">
                    {w.win_rate != null ? `${(w.win_rate * 100).toFixed(1)}%` : 'N/A'}
                  </td>
                  <td className="table-cell font-mono">
                    {w.avg_position_usd != null
                      ? `$${Number(w.avg_position_usd).toLocaleString('en-US', { maximumFractionDigits: 0 })}`
                      : 'N/A'}
                  </td>
                  <td className="table-cell font-mono">{w.total_trades}</td>
                  <td className="table-cell"><LabelBadge label={w.label} /></td>
                  <td className="table-cell text-gray-400 text-xs">{formatDate(w.first_seen)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-800">
            <button
              className="btn-secondary text-sm"
              disabled={page === 1}
              onClick={() => setPage(p => p - 1)}
            >
              Previous
            </button>
            <span className="text-sm text-gray-400">
              Page {page} of {totalPages}
            </span>
            <button
              className="btn-secondary text-sm"
              disabled={page >= totalPages}
              onClick={() => setPage(p => p + 1)}
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
