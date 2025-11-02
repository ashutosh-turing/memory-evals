import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { 
  ChevronDown, 
  ExternalLink, 
  Download, 
  Play, 
  X, 
  FileText,
  TrendingUp
} from 'lucide-react'
import { Badge, Button, Card } from './index'
import { 
  getTaskStatusVariant, 
  getTaskStatusLabel, 
  getAgentDisplayName,
  isTaskInProgress 
} from '../utils/status'
import { formatRelativeTime, formatScore } from '../utils/format'
import type { Task, AgentRun, LeaderboardEntry } from '../types'

interface TaskCardProps {
  task: Task
  agents?: AgentRun[]
  leaderboard?: LeaderboardEntry[]
  onRestart?: (taskId: string) => void
  onCancel?: (taskId: string) => void
  onLoadDetails?: (taskId: string) => void
}

export const TaskCard: React.FC<TaskCardProps> = ({
  task,
  agents,
  leaderboard,
  onRestart,
  onCancel,
  onLoadDetails,
}) => {
  const [isExpanded, setIsExpanded] = useState(false)
  const navigate = useNavigate()

  const handleToggle = () => {
    const newExpanded = !isExpanded
    setIsExpanded(newExpanded)
    
    // Load details when expanding
    if (newExpanded && onLoadDetails && task.status !== 'queued') {
      onLoadDetails(task.id)
    }
  }

  const handleDownloadBundle = () => {
    window.open(`/api/v1/artifacts/${task.id}/bundle`, '_blank')
  }

  const handleViewLogs = () => {
    navigate(`/tasks/${task.id}`)
  }

  return (
    <div className="bg-white/80 dark:bg-gray-800/80 backdrop-blur-sm rounded-2xl border border-gray-200/50 dark:border-gray-700/50 shadow-lg hover:shadow-xl transition-all overflow-hidden">
      {/* Header - Clickable */}
      <div
        onClick={handleToggle}
        className="px-6 py-4 flex items-center justify-between cursor-pointer hover:bg-gradient-to-r hover:from-blue-50/50 hover:to-indigo-50/50 dark:hover:from-blue-900/20 dark:hover:to-indigo-900/20 transition-all border-b border-gray-200/50 dark:border-gray-700/50"
      >
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <span className="font-mono text-xs bg-gray-100 dark:bg-gray-700 px-2.5 py-1 rounded-full text-gray-700 dark:text-gray-300 flex-shrink-0">
            {task.id.substring(0, 8)}...
          </span>
          <Badge variant={getTaskStatusVariant(task.status)} dot>
            {getTaskStatusLabel(task.status)}
          </Badge>
          <span className="text-sm text-gray-600 dark:text-gray-400 truncate">
            {task.repo} #{task.pr_number}
          </span>
        </div>
        <ChevronDown
          className={`w-5 h-5 text-gray-400 transition-transform flex-shrink-0 ml-2 ${
            isExpanded ? 'rotate-180' : ''
          }`}
        />
      </div>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="px-6 py-4 space-y-4">
          {/* Task Info Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase mb-1">
                Repository
              </div>
              <a
                href={task.pr_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary-600 dark:text-primary-400 hover:text-primary-700 dark:hover:text-primary-300 font-medium text-sm flex items-center gap-1"
              >
                {task.repo} #{task.pr_number}
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
            <div>
              <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase mb-1">
                Agents
              </div>
              <div className="text-sm font-medium text-gray-900 dark:text-gray-100">
                {task.agents.map(getAgentDisplayName).join(', ')}
              </div>
            </div>
            <div>
              <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase mb-1">
                Created
              </div>
              <div className="text-sm text-gray-900 dark:text-gray-100">
                {formatRelativeTime(task.created_at)}
              </div>
            </div>
            {task.changed_files.length > 0 && (
              <div>
                <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase mb-1">
                  Changed Files
                </div>
                <div className="text-sm text-gray-900 dark:text-gray-100">
                  {task.changed_files.length} files
                </div>
              </div>
            )}
          </div>

          {/* User Context (if available) */}
          {task.created_by_email && (
            <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3">
              <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase mb-2">
                Created By
              </div>
              <div className="text-sm text-gray-900 dark:text-gray-100">
                {task.created_by_name} ({task.created_by_email})
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex flex-wrap gap-2">
            {task.status === 'error' && onRestart && (
              <Button
                variant="warning"
                size="sm"
                icon={<Play className="w-4 h-4" />}
                onClick={() => onRestart(task.id)}
              >
                Restart Task
              </Button>
            )}

            <Button
              variant="primary"
              size="sm"
              icon={<Download className="w-4 h-4" />}
              onClick={handleDownloadBundle}
              disabled={task.status === 'queued' || task.status === 'running'}
            >
              Download Bundle
            </Button>

            <Button
              variant="secondary"
              size="sm"
              icon={<FileText className="w-4 h-4" />}
              onClick={handleViewLogs}
            >
              View Details
            </Button>

            {isTaskInProgress(task.status) && onCancel && (
              <Button
                variant="error"
                size="sm"
                icon={<X className="w-4 h-4" />}
                onClick={() => {
                  if (window.confirm('Are you sure you want to cancel this task?')) {
                    onCancel(task.id)
                  }
                }}
              >
                Cancel
              </Button>
            )}
          </div>

          {/* Leaderboard */}
          {leaderboard && leaderboard.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <TrendingUp className="w-4 h-4 text-gray-600 dark:text-gray-400" />
                <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 uppercase">
                  Leaderboard
                </h4>
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                  <thead className="bg-gray-50 dark:bg-gray-700">
                    <tr>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                        Rank
                      </th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                        Agent
                      </th>
                      <th className="px-3 py-2 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                        Overall
                      </th>
                      <th className="px-3 py-2 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                        AR
                      </th>
                      <th className="px-3 py-2 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                        TTL
                      </th>
                      <th className="px-3 py-2 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                        LRU
                      </th>
                      <th className="px-3 py-2 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                        SF
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                    {leaderboard.map((entry, index) => (
                      <tr
                        key={entry.agent}
                        className={index === 0 ? 'bg-yellow-50 dark:bg-yellow-900/20' : ''}
                      >
                        <td className="px-3 py-2 whitespace-nowrap text-center">
                          {index === 0 && <span className="text-xl">🥇</span>}
                          {index === 1 && <span className="text-xl">🥈</span>}
                          {index === 2 && <span className="text-xl">🥉</span>}
                          {index > 2 && (
                            <span className="text-sm text-gray-500">{index + 1}</span>
                          )}
                        </td>
                        <td className="px-3 py-2 whitespace-nowrap">
                          <span className="font-semibold text-gray-800 dark:text-gray-200 uppercase text-sm">
                            {getAgentDisplayName(entry.agent)}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-center">
                          <span
                            className={`font-bold text-sm ${
                              entry.overall_score >= 0.7
                                ? 'text-success-600'
                                : entry.overall_score >= 0.5
                                ? 'text-warning-600'
                                : 'text-error-600'
                            }`}
                          >
                            {formatScore(entry.overall_score)}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-center text-sm text-gray-700 dark:text-gray-300">
                          {formatScore(entry.scores.AR)}
                        </td>
                        <td className="px-3 py-2 text-center text-sm text-gray-700 dark:text-gray-300">
                          {formatScore(entry.scores.TTL)}
                        </td>
                        <td className="px-3 py-2 text-center text-sm text-gray-700 dark:text-gray-300">
                          {formatScore(entry.scores.LRU)}
                        </td>
                        <td className="px-3 py-2 text-center text-sm text-gray-700 dark:text-gray-300">
                          {formatScore(entry.scores.SF)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Agent Results */}
          {agents && agents.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 uppercase mb-3">
                Agent Results
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {agents.map((agent) => (
                  <div
                    key={agent.id}
                    className="bg-gray-50 dark:bg-gray-700/50 border border-gray-200 dark:border-gray-600 rounded-lg p-3"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <h5 className="font-semibold text-gray-800 dark:text-gray-200 uppercase text-sm">
                        {getAgentDisplayName(agent.agent)}
                      </h5>
                      <Badge variant={getTaskStatusVariant(agent.status as any)}>
                        {agent.status}
                      </Badge>
                    </div>

                    {agent.stats && Object.keys(agent.stats).length > 0 && (
                      <div className="text-xs space-y-1 text-gray-600 dark:text-gray-400">
                        {Object.entries(agent.stats).map(([key, value]) => (
                          <div key={key} className="flex justify-between">
                            <span className="font-medium">{key}:</span>
                            <span>{value}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

