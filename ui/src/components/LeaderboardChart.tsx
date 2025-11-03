import { useState } from 'react'
import { Trophy, Clock, CheckCircle2, XCircle, Loader2, ChevronDown, ChevronUp, RotateCcw, Info } from 'lucide-react'
import type { LeaderboardEntry, RubricDimension } from '../types'
import { useAgentDetails } from '../hooks/useAgents'
import { apiClient } from '../api/client'
import { useToast } from './Toast'

interface LeaderboardChartProps {
  leaderboard: LeaderboardEntry[]
  rubric: RubricDimension[]
  taskId?: string
}

const DIMENSION_LABELS: Record<string, string> = {
  'AR': 'Accuracy & Relevance',
  'TTL': 'Time to Live',
  'LRU': 'Least Recently Used',
  'SF': 'Success Factor'
}

export const LeaderboardChart = ({ leaderboard, rubric, taskId }: LeaderboardChartProps) => {
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null)
  const { data: agentDetails } = useAgentDetails(taskId, expandedAgent)
  const { showToast } = useToast()
  
  const handleRetry = async (agentName: string) => {
    if (!taskId) return
    
    try {
      await apiClient.retryTask(taskId, [agentName])
      showToast({
        type: 'success',
        title: 'Agent Retry',
        message: `${agentName} has been re-queued for evaluation`
      })
      // Refresh the page or invalidate queries
      window.location.reload()
    } catch (error) {
      showToast({
        type: 'error',
        title: 'Retry Failed',
        message: `Failed to retry ${agentName}`
      })
    }
  }
  const getRankBadge = (index: number) => {
    const badges = [
      { bg: 'bg-gradient-to-br from-yellow-400 to-yellow-600', text: 'text-white', label: '1st' },
      { bg: 'bg-gradient-to-br from-gray-300 to-gray-500', text: 'text-white', label: '2nd' },
      { bg: 'bg-gradient-to-br from-amber-600 to-amber-800', text: 'text-white', label: '3rd' },
    ]
    
    if (index < 3) {
      const badge = badges[index]
      return (
        <div className={`${badge.bg} ${badge.text} w-12 h-12 rounded-full flex items-center justify-center font-bold text-lg shadow-lg`}>
          {badge.label}
        </div>
      )
    }
    
    return (
      <div className="w-12 h-12 rounded-full bg-gray-100 dark:bg-gray-700 flex items-center justify-center font-bold text-gray-600 dark:text-gray-300">
        {index + 1}
      </div>
    )
  }

  const getStatusBadge = (entry: LeaderboardEntry) => {
    if (entry.status === 'running' || entry.status === 'evaluating') {
      return (
        <div className="flex items-center gap-2 px-3 py-1 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 rounded-full text-sm font-medium">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span>Evaluating...</span>
        </div>
      )
    }
    
    if (entry.status === 'queued' || entry.status === 'memory_only') {
      return (
        <div className="flex items-center gap-2 px-3 py-1 bg-gray-50 dark:bg-gray-700 text-gray-600 dark:text-gray-300 rounded-full text-sm font-medium">
          <Clock className="w-4 h-4" />
          <span>Waiting...</span>
        </div>
      )
    }
    
    if (entry.passed) {
      return (
        <div className="flex items-center gap-2 px-3 py-1 bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300 rounded-full text-sm font-medium">
          <CheckCircle2 className="w-4 h-4" />
          <span>Passed</span>
        </div>
      )
    }
    
    return (
      <div className="flex items-center gap-2 px-3 py-1 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 rounded-full text-sm font-medium">
        <XCircle className="w-4 h-4" />
        <span>Failed</span>
      </div>
    )
  }

  const getScoreColor = (score: number, failed: boolean = false) => {
    if (failed) return 'text-red-600 dark:text-red-400'
    if (score >= 0.9) return 'text-green-600 dark:text-green-400'
    if (score >= 0.8) return 'text-emerald-600 dark:text-emerald-400'
    if (score >= 0.7) return 'text-blue-600 dark:text-blue-400'
    if (score >= 0.6) return 'text-yellow-600 dark:text-yellow-400'
    return 'text-orange-600 dark:text-orange-400'
  }

  const getProgressBarColor = (score: number, failed: boolean = false) => {
    if (failed) return 'bg-gradient-to-r from-red-500 to-red-600'
    if (score >= 0.9) return 'bg-gradient-to-r from-green-500 to-emerald-500'
    if (score >= 0.8) return 'bg-gradient-to-r from-emerald-500 to-teal-500'
    if (score >= 0.7) return 'bg-gradient-to-r from-blue-500 to-cyan-500'
    if (score >= 0.6) return 'bg-gradient-to-r from-yellow-500 to-amber-500'
    return 'bg-gradient-to-r from-orange-500 to-red-500'
  }

  return (
    <div className="space-y-6">
      {leaderboard.map((entry, index) => {
        const isWinner = index === 0
        
        return (
          <div
            key={entry.agent}
            className={`
              relative overflow-hidden rounded-xl transition-all duration-300 hover:shadow-xl
              ${isWinner 
                ? 'bg-gradient-to-br from-yellow-50 to-amber-50 dark:from-yellow-900/10 dark:to-amber-900/10 ring-2 ring-yellow-400 dark:ring-yellow-600 shadow-lg' 
                : 'bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700'
              }
            `}
          >
            {/* Winner Crown Effect */}
            {isWinner && (
              <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-yellow-400/20 to-transparent rounded-bl-full" />
            )}
            
            <div className="relative p-6">
              {/* Header Section */}
              <div className="flex items-start justify-between mb-6">
                <div className="flex items-center gap-4">
                  {getRankBadge(index)}
                  
                  <div>
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-2xl font-bold text-gray-900 dark:text-white uppercase tracking-wide">
                        {entry.agent}
                      </h3>
                      {isWinner && <Trophy className="w-6 h-6 text-yellow-500 animate-pulse" />}
                    </div>
                    {getStatusBadge(entry)}
                  </div>
                </div>

                {/* Overall Score Circle */}
                <div className="flex flex-col items-center">
                  <div className={`
                    relative w-24 h-24 rounded-full flex items-center justify-center
                    ${isWinner 
                      ? 'bg-gradient-to-br from-yellow-400 to-amber-500 shadow-lg' 
                      : 'bg-gradient-to-br from-gray-100 to-gray-200 dark:from-gray-700 dark:to-gray-600'
                    }
                  `}>
                    <div className="absolute inset-2 bg-white dark:bg-gray-800 rounded-full flex items-center justify-center">
                      <div className="text-center">
                        <div className={`text-2xl font-bold ${getScoreColor(entry.overall_score, !entry.passed)}`}>
                          {(entry.overall_score * 100).toFixed(0)}
                        </div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">score</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Failed Dimensions Alert */}
              {!entry.passed && entry.breaking_dimensions && entry.breaking_dimensions.length > 0 && (
                <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
                  <div className="flex items-start gap-2">
                    <XCircle className="w-5 h-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm font-semibold text-red-900 dark:text-red-100 mb-1">
                        Failed Dimensions
                      </p>
                      <p className="text-sm text-red-700 dark:text-red-300">
                        {entry.breaking_dimensions.map(dim => DIMENSION_LABELS[dim] || dim).join(', ')}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Metrics Grid */}
              <div className="grid grid-cols-2 gap-4">
                {rubric.map((dimension) => {
                  const score = entry.scores[dimension as keyof typeof entry.scores] || 0
                  const threshold = entry.thresholds_used?.[dimension] ?? 0.7
                  const failed = score < threshold
                  const label = DIMENSION_LABELS[dimension] || dimension
                  
                  return (
                    <div 
                      key={dimension}
                      className={`
                        p-4 rounded-lg transition-all
                        ${failed 
                          ? 'bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-800' 
                          : 'bg-gray-50 dark:bg-gray-700/50 border border-gray-200 dark:border-gray-600'
                        }
                      `}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className={`text-xs font-bold uppercase tracking-wider ${failed ? 'text-red-700 dark:text-red-300' : 'text-gray-600 dark:text-gray-300'}`}>
                            {dimension}
                          </span>
                          {failed ? (
                            <XCircle className="w-4 h-4 text-red-500" />
                          ) : (
                            <CheckCircle2 className="w-4 h-4 text-green-500" />
                          )}
                        </div>
                        <span className={`text-lg font-bold ${getScoreColor(score, failed)}`}>
                          {(score * 100).toFixed(0)}%
                        </span>
                      </div>
                      
                      <p className="text-xs text-gray-600 dark:text-gray-400 mb-2">{label}</p>
                      
                      {/* Progress Bar */}
                      <div className="relative h-2 bg-gray-200 dark:bg-gray-600 rounded-full overflow-hidden">
                        {failed && (
                          <div 
                            className="absolute inset-y-0 left-0 bg-red-300 dark:bg-red-700 opacity-50"
                            style={{ width: `${threshold * 100}%` }}
                          />
                        )}
                        <div
                          className={`h-full ${getProgressBarColor(score, failed)} transition-all duration-700 ease-out rounded-full`}
                          style={{ width: `${score * 100}%` }}
                        />
                      </div>
                      
                      {failed && (
                        <p className="text-xs text-red-600 dark:text-red-400 mt-1">
                          Threshold: {(threshold * 100).toFixed(0)}%
                        </p>
                      )}
                    </div>
                  )
                })}
              </div>

              {/* Expandable Details Section */}
              {taskId && (
                <div className="mt-4 border-t border-gray-200 dark:border-gray-700 pt-4">
                  <button
                    onClick={() => setExpandedAgent(expandedAgent === entry.agent ? null : entry.agent)}
                    className="flex items-center gap-2 text-sm font-medium text-primary-600 dark:text-primary-400 hover:text-primary-700 dark:hover:text-primary-300 transition-colors"
                  >
                    {expandedAgent === entry.agent ? (
                      <>
                        <ChevronUp className="w-4 h-4" />
                        <span>Hide Details</span>
                      </>
                    ) : (
                      <>
                        <ChevronDown className="w-4 h-4" />
                        <span>View Details</span>
                      </>
                    )}
                  </button>

                  {expandedAgent === entry.agent && agentDetails && (
                    <div className="mt-4 space-y-4">
                      {/* Error Details (if failed) */}
                      {entry.status === 'error' && agentDetails.agent_run.error_message && (
                        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
                          <div className="flex items-start gap-3">
                            <XCircle className="w-5 h-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
                            <div className="flex-1">
                              <h4 className="text-sm font-semibold text-red-900 dark:text-red-100 mb-2">
                                Error Details
                              </h4>
                              <p className="text-sm text-red-700 dark:text-red-300 whitespace-pre-wrap">
                                {agentDetails.agent_run.error_message}
                              </p>
                              <button
                                onClick={() => handleRetry(entry.agent)}
                                className="mt-3 inline-flex items-center gap-2 px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded-md transition-colors"
                              >
                                <RotateCcw className="w-4 h-4" />
                                Retry Agent
                              </button>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Judge Rationale (if completed) */}
                      {agentDetails.scores && entry.status === 'done' && (
                        <div className="bg-gray-50 dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                          <div className="flex items-start gap-3">
                            <Info className="w-5 h-5 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5" />
                            <div className="flex-1">
                              <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-2">
                                Judge Rationale
                              </h4>
                              <p className="text-sm text-gray-700 dark:text-gray-300 mb-3 whitespace-pre-wrap">
                                {agentDetails.scores.rationale}
                              </p>
                              
                              {/* Judge Metadata */}
                              <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400">
                                {agentDetails.scores.judge_type && (
                                  <span>Judge: {agentDetails.scores.judge_type}</span>
                                )}
                                {agentDetails.scores.judge_model && (
                                  <span>Model: {agentDetails.scores.judge_model}</span>
                                )}
                              </div>

                              {/* Breaking Details */}
                              {!entry.passed && agentDetails.scores.breaking_details && Object.keys(agentDetails.scores.breaking_details).length > 0 && (
                                <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
                                  <h5 className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2">
                                    Why Each Dimension Failed:
                                  </h5>
                                  <div className="space-y-2">
                                    {Object.entries(agentDetails.scores.breaking_details).map(([dim, reason]) => (
                                      <div key={dim} className="text-xs">
                                        <span className="font-medium text-red-600 dark:text-red-400">{dim}:</span>
                                        <span className="text-gray-600 dark:text-gray-400 ml-2">{reason}</span>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Compression Detection Info */}
                      {entry.compression_detected && agentDetails.agent_run.stats && (
                        <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                          <div className="flex items-start gap-3">
                            <Trophy className="w-5 h-5 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5" />
                            <div className="flex-1">
                              <h4 className="text-sm font-semibold text-blue-900 dark:text-blue-100 mb-2">
                                Memory Compression Detected ✓
                              </h4>
                              <div className="text-sm text-blue-700 dark:text-blue-300 space-y-1">
                                <p>Detection Method: {agentDetails.agent_run.stats.detection_method || 'Unknown'}</p>
                                {agentDetails.agent_run.stats.total_tokens_estimate && (
                                  <p>Total Tokens: {parseInt(agentDetails.agent_run.stats.total_tokens_estimate).toLocaleString()}</p>
                                )}
                              </div>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

