import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchAlertRules,
  createAlertRule,
  updateAlertRule,
  deleteAlertRule,
} from '../api/client.js'

const METRICS = [
  'composite_score',
  'win_rate',
  'position_size_score',
  'timing_score',
  'consistency_score',
  'avg_position_usd',
  'total_trades',
]

const OPERATORS = ['>', '>=', '<', '<=', '==', '!=']

const EMPTY_FORM = {
  rule_name: '',
  metric: 'composite_score',
  operator: '>',
  threshold: '',
  active: true,
}

function RuleForm({ initial = EMPTY_FORM, onSubmit, onCancel, loading }) {
  const [form, setForm] = useState(initial)

  const handleChange = e => {
    const { name, value, type, checked } = e.target
    setForm(f => ({ ...f, [name]: type === 'checkbox' ? checked : value }))
  }

  const handleSubmit = e => {
    e.preventDefault()
    onSubmit({ ...form, threshold: parseFloat(form.threshold) })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm text-gray-400 mb-1">Rule Name</label>
        <input
          className="input"
          name="rule_name"
          value={form.rule_name}
          onChange={handleChange}
          placeholder="e.g. High CBS Alert"
          required
        />
      </div>
      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className="block text-sm text-gray-400 mb-1">Metric</label>
          <select
            className="input"
            name="metric"
            value={form.metric}
            onChange={handleChange}
          >
            {METRICS.map(m => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Operator</label>
          <select
            className="input"
            name="operator"
            value={form.operator}
            onChange={handleChange}
          >
            {OPERATORS.map(op => (
              <option key={op} value={op}>{op}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Threshold</label>
          <input
            className="input"
            name="threshold"
            type="number"
            step="0.0001"
            value={form.threshold}
            onChange={handleChange}
            placeholder="e.g. 0.8"
            required
          />
        </div>
      </div>
      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          id="active"
          name="active"
          checked={form.active}
          onChange={handleChange}
          className="w-4 h-4 rounded"
        />
        <label htmlFor="active" className="text-sm text-gray-300">Active</label>
      </div>
      <div className="flex gap-3 pt-2">
        <button type="submit" className="btn-primary" disabled={loading}>
          {loading ? 'Saving...' : 'Save Rule'}
        </button>
        {onCancel && (
          <button type="button" className="btn-secondary" onClick={onCancel}>
            Cancel
          </button>
        )}
      </div>
    </form>
  )
}

export default function AlertRulesConfig() {
  const qc = useQueryClient()
  const [editingId, setEditingId] = useState(null)
  const [showCreate, setShowCreate] = useState(false)

  const { data: rules = [], isLoading, isError } = useQuery({
    queryKey: ['alert-rules'],
    queryFn: fetchAlertRules,
  })

  const createMutation = useMutation({
    mutationFn: createAlertRule,
    onSuccess: () => {
      qc.invalidateQueries(['alert-rules'])
      setShowCreate(false)
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => updateAlertRule(id, data),
    onSuccess: () => {
      qc.invalidateQueries(['alert-rules'])
      setEditingId(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteAlertRule,
    onSuccess: () => qc.invalidateQueries(['alert-rules']),
  })

  const handleDelete = (ruleId, ruleName) => {
    if (window.confirm(`Delete rule "${ruleName}"?`)) {
      deleteMutation.mutate(ruleId)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-white">Alert Rules</h2>
        <button
          className="btn-primary text-sm"
          onClick={() => setShowCreate(v => !v)}
        >
          {showCreate ? 'Cancel' : '+ New Rule'}
        </button>
      </div>

      {/* Create form */}
      {showCreate && (
        <div className="card">
          <h3 className="font-medium text-white mb-4">Create Alert Rule</h3>
          <RuleForm
            onSubmit={data => createMutation.mutate(data)}
            onCancel={() => setShowCreate(false)}
            loading={createMutation.isPending}
          />
          {createMutation.isError && (
            <p className="text-red-400 text-sm mt-2">
              Failed to create rule. Check the API.
            </p>
          )}
        </div>
      )}

      {/* Rules table */}
      <div className="card p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead>
              <tr className="border-b border-gray-800">
                <th className="table-header">ID</th>
                <th className="table-header">Name</th>
                <th className="table-header">Condition</th>
                <th className="table-header">Status</th>
                <th className="table-header">Created</th>
                <th className="table-header">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/50">
              {isLoading && (
                <tr>
                  <td colSpan={6} className="table-cell text-center text-gray-500 py-8">
                    Loading rules...
                  </td>
                </tr>
              )}
              {isError && (
                <tr>
                  <td colSpan={6} className="table-cell text-center text-red-400 py-8">
                    Failed to load rules.
                  </td>
                </tr>
              )}
              {!isLoading && rules.length === 0 && (
                <tr>
                  <td colSpan={6} className="table-cell text-center text-gray-500 py-8">
                    No alert rules. Create one above.
                  </td>
                </tr>
              )}
              {rules.map(rule => (
                <React.Fragment key={rule.rule_id}>
                  <tr className="hover:bg-gray-800/20">
                    <td className="table-cell font-mono text-gray-500">#{rule.rule_id}</td>
                    <td className="table-cell font-medium text-gray-200">{rule.rule_name}</td>
                    <td className="table-cell font-mono text-sm">
                      <span className="text-blue-300">{rule.metric}</span>
                      {' '}
                      <span className="text-yellow-400">{rule.operator}</span>
                      {' '}
                      <span className="text-green-300">{rule.threshold}</span>
                    </td>
                    <td className="table-cell">
                      {rule.active ? (
                        <span className="badge bg-green-900/40 text-green-400 border border-green-700/40">
                          Active
                        </span>
                      ) : (
                        <span className="badge bg-gray-700 text-gray-400">
                          Inactive
                        </span>
                      )}
                    </td>
                    <td className="table-cell text-xs text-gray-400">
                      {new Date(rule.created_at).toLocaleDateString()}
                    </td>
                    <td className="table-cell">
                      <div className="flex gap-2">
                        <button
                          className="text-xs text-blue-400 hover:text-blue-300"
                          onClick={() => setEditingId(editingId === rule.rule_id ? null : rule.rule_id)}
                        >
                          Edit
                        </button>
                        <button
                          className="text-xs text-red-400 hover:text-red-300"
                          onClick={() => handleDelete(rule.rule_id, rule.rule_name)}
                          disabled={deleteMutation.isPending}
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                  {editingId === rule.rule_id && (
                    <tr>
                      <td colSpan={6} className="px-6 py-4 bg-gray-800/50 border-b border-gray-700">
                        <RuleForm
                          initial={{
                            rule_name: rule.rule_name,
                            metric: rule.metric,
                            operator: rule.operator,
                            threshold: rule.threshold,
                            active: rule.active,
                          }}
                          onSubmit={data =>
                            updateMutation.mutate({ id: rule.rule_id, data })
                          }
                          onCancel={() => setEditingId(null)}
                          loading={updateMutation.isPending}
                        />
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
