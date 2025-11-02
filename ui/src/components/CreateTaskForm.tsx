import React, { useState } from 'react'
import { Plus } from 'lucide-react'
import { Button, Input, Card, Alert } from './index'
import type { AgentName, CreateTaskRequest } from '../types'

interface CreateTaskFormProps {
  onSubmit: (data: CreateTaskRequest) => Promise<void>
  isLoading?: boolean
}

export const CreateTaskForm: React.FC<CreateTaskFormProps> = ({
  onSubmit,
  isLoading = false,
}) => {
  const [prUrl, setPrUrl] = useState('')
  const [selectedAgents, setSelectedAgents] = useState<AgentName[]>(['iflow'])
  const [maxFiles, setMaxFiles] = useState(50)
  const [error, setError] = useState<string | null>(null)

  const agents: { value: AgentName; label: string }[] = [
    { value: 'iflow', label: 'iFlow' },
    { value: 'claude', label: 'Claude' },
    { value: 'gemini', label: 'Gemini' },
  ]

  const handleAgentToggle = (agent: AgentName) => {
    setSelectedAgents((prev) =>
      prev.includes(agent)
        ? prev.filter((a) => a !== agent)
        : [...prev, agent]
    )
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    // Validation
    if (!prUrl) {
      setError('Please provide a GitHub PR URL')
      return
    }

    if (selectedAgents.length === 0) {
      setError('Please select at least one agent')
      return
    }

    try {
      await onSubmit({
        pr_url: prUrl,
        agents: selectedAgents,
        max_files: maxFiles,
      })

      // Reset form on success
      setPrUrl('')
      setSelectedAgents(['iflow'])
      setMaxFiles(50)
    } catch (err: any) {
      setError(err.message || 'Failed to create task')
    }
  }

  return (
    <div>
      {error && (
        <Alert variant="error" className="mb-4" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* PR URL Input */}
        <Input
          label="GitHub PR URL"
          type="url"
          placeholder="https://github.com/owner/repo/pull/123"
          value={prUrl}
          onChange={(e) => setPrUrl(e.target.value)}
          required
        />

        {/* Agent Selection */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
            Select Agents
          </label>
          <div className="flex flex-wrap gap-4">
            {agents.map((agent) => (
              <label
                key={agent.value}
                className="flex items-center space-x-2 cursor-pointer"
              >
                <input
                  type="checkbox"
                  checked={selectedAgents.includes(agent.value)}
                  onChange={() => handleAgentToggle(agent.value)}
                  className="w-4 h-4 text-primary-600 bg-gray-100 border-gray-300 rounded focus:ring-primary-500"
                />
                <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  {agent.label}
                </span>
              </label>
            ))}
          </div>
        </div>

        {/* Max Files Input */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Max Files
          </label>
          <input
            type="number"
            min="1"
            max="1000"
            value={maxFiles}
            onChange={(e) => setMaxFiles(parseInt(e.target.value) || 50)}
            className="w-24 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
          />
        </div>

        {/* Submit Button */}
        <Button
          type="submit"
          variant="primary"
          size="lg"
          loading={isLoading}
          icon={<Plus className="w-5 h-5" />}
          className="w-full sm:w-auto bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700"
        >
          {isLoading ? 'Creating...' : 'Create Task'}
        </Button>
      </form>
    </div>
  )
}

