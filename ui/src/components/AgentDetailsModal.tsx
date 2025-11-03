import React, { useEffect } from 'react'
import { X, MessageSquare, Award, Activity, AlertCircle, Loader2, Code } from 'lucide-react'
import { useAgentDetails } from '../hooks/useAgents'

// Helper function to detect and format code blocks
const formatTextWithCode = (text: string) => {
  // Split by code blocks (```language\ncode\n```)
  const codeBlockRegex = /```(\w+)?\n([\s\S]*?)```/g
  const parts: Array<{ type: 'text' | 'code', content: string, language?: string }> = []
  let lastIndex = 0
  let match

  while ((match = codeBlockRegex.exec(text)) !== null) {
    // Add text before code block
    if (match.index > lastIndex) {
      parts.push({ type: 'text', content: text.slice(lastIndex, match.index) })
    }
    // Add code block
    parts.push({ 
      type: 'code', 
      content: match[2].trim(), 
      language: match[1] || 'text' 
    })
    lastIndex = match.index + match[0].length
  }

  // Add remaining text
  if (lastIndex < text.length) {
    parts.push({ type: 'text', content: text.slice(lastIndex) })
  }

  return parts.length > 0 ? parts : [{ type: 'text', content: text }]
}

// Component to render formatted text with code highlighting
const FormattedText: React.FC<{ text: string }> = ({ text }) => {
  const parts = formatTextWithCode(text)

  return (
    <div className="space-y-3">
      {parts.map((part, idx) => {
        if (part.type === 'code') {
          return (
            <div key={idx} className="relative group">
              <div className="flex items-center justify-between bg-gray-800 dark:bg-gray-900 px-4 py-2 rounded-t-lg">
                <div className="flex items-center gap-2">
                  <Code className="w-4 h-4 text-gray-400" />
                  <span className="text-xs font-mono text-gray-400">{part.language}</span>
                </div>
                <button
                  onClick={() => navigator.clipboard.writeText(part.content)}
                  className="text-xs text-gray-400 hover:text-white transition-colors"
                >
                  Copy
                </button>
              </div>
              <pre className="bg-gray-900 dark:bg-black rounded-b-lg p-4 overflow-x-auto">
                <code className="text-sm font-mono text-gray-100 dark:text-gray-200">
                  {part.content}
                </code>
              </pre>
            </div>
          )
        }
        return (
          <p key={idx} className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
            {part.content}
          </p>
        )
      })}
    </div>
  )
}

interface AgentDetailsModalProps {
  isOpen: boolean
  onClose: () => void
  taskId: string
  agentName: string
}

export const AgentDetailsModal: React.FC<AgentDetailsModalProps> = ({
  isOpen,
  onClose,
  taskId,
  agentName,
}) => {
  const { data: agentDetails, isLoading, error } = useAgentDetails(
    isOpen ? taskId : undefined,
    isOpen ? agentName : null
  )

  // Handle ESC key
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    if (isOpen) {
      window.addEventListener('keydown', handleEsc)
      return () => window.removeEventListener('keydown', handleEsc)
    }
  }, [isOpen, onClose])

  if (!isOpen) return null

  const getScoreColor = (score: number) => {
    if (score >= 0.8) return 'text-green-600 dark:text-green-400'
    if (score >= 0.6) return 'text-yellow-600 dark:text-yellow-400'
    return 'text-red-600 dark:text-red-400'
  }

  const getProgressColor = (score: number) => {
    if (score >= 0.8) return 'bg-green-500'
    if (score >= 0.6) return 'bg-yellow-500'
    return 'bg-red-500'
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-white dark:bg-dark-900 rounded-xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 bg-white dark:bg-dark-900 border-b border-gray-200 dark:border-gray-800 px-6 py-4 flex items-center justify-between">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
            {agentName} - Evaluation Details
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Content */}
        <div className="overflow-y-auto p-6 space-y-6 max-h-[calc(90vh-80px)]">
          {isLoading && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
            </div>
          )}

          {error && (
            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-sm font-semibold text-red-900 dark:text-red-100 mb-1">
                    Failed to load agent details
                  </h4>
                  <p className="text-sm text-red-700 dark:text-red-300">
                    {error instanceof Error ? error.message : 'Unknown error'}
                  </p>
                </div>
              </div>
            </div>
          )}

          {agentDetails && (
            <>
              {/* Error Details (if failed) */}
              {agentDetails.agent_run.status === 'error' && agentDetails.agent_run.error_message && (
                <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
                  <div className="flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
                    <div className="flex-1">
                      <h4 className="text-sm font-semibold text-red-900 dark:text-red-100 mb-2">
                        Execution Error
                      </h4>
                      <p className="text-sm text-red-700 dark:text-red-300 whitespace-pre-wrap">
                        {agentDetails.agent_run.error_message}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Agent Stats */}
              <div className="bg-gray-50 dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-3">
                  <Activity className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                    Agent Statistics
                  </h3>
                </div>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">Status:</span>
                    <span className="ml-2 font-medium text-gray-900 dark:text-white">
                      {agentDetails.agent_run.status}
                    </span>
                  </div>
                  {agentDetails.agent_run.started_at && agentDetails.agent_run.completed_at && (
                    <div>
                      <span className="text-gray-500 dark:text-gray-400">Execution Time:</span>
                      <span className="ml-2 font-medium text-gray-900 dark:text-white">
                        {Math.round(
                          (new Date(agentDetails.agent_run.completed_at).getTime() -
                            new Date(agentDetails.agent_run.started_at).getTime()) /
                            1000
                        )}s
                      </span>
                    </div>
                  )}
                  {agentDetails.agent_run.stats.total_tokens_estimate && (
                    <div>
                      <span className="text-gray-500 dark:text-gray-400">Tokens Used:</span>
                      <span className="ml-2 font-medium text-gray-900 dark:text-white">
                        {parseInt(agentDetails.agent_run.stats.total_tokens_estimate).toLocaleString()}
                      </span>
                    </div>
                  )}
                  {agentDetails.agent_run.stats.compression_detected && (
                    <div>
                      <span className="text-gray-500 dark:text-gray-400">Compression:</span>
                      <span className="ml-2 font-medium text-green-600 dark:text-green-400">
                        Detected ({agentDetails.agent_run.stats.detection_method})
                      </span>
                    </div>
                  )}
                </div>
              </div>

              {/* Q&A Interactions */}
              {agentDetails.agent_run.stats.evaluation_qa && 
               agentDetails.agent_run.stats.evaluation_qa.length > 0 && (
                <div className="space-y-4">
                  <div className="flex items-center gap-2">
                    <MessageSquare className="w-5 h-5 text-purple-600 dark:text-purple-400" />
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                      Evaluation Q&A
                    </h3>
                  </div>
                  <div className="space-y-4">
                    {agentDetails.agent_run.stats.evaluation_qa.map((qa: any, idx: number) => (
                      <div
                        key={idx}
                        className="bg-white dark:bg-dark-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4"
                      >
                        <div className="flex items-start gap-3">
                          <div className="flex-shrink-0 w-8 h-8 bg-purple-100 dark:bg-purple-900/30 rounded-full flex items-center justify-center">
                            <span className="text-sm font-semibold text-purple-600 dark:text-purple-400">
                              {qa.turn || idx + 1}
                            </span>
                          </div>
                          <div className="flex-1 space-y-3">
                            <div>
                              <p className="text-sm font-semibold text-gray-900 dark:text-white mb-1">
                                Question:
                              </p>
                              <p className="text-sm text-gray-700 dark:text-gray-300">
                                {qa.question}
                              </p>
                            </div>
                            <div>
                              <p className="text-sm font-semibold text-gray-900 dark:text-white mb-1">
                                Answer:
                              </p>
                              <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3">
                                <FormattedText text={qa.answer} />
                              </div>
                            </div>
                            {qa.ground_truth && (
                              <div>
                                <p className="text-sm font-semibold text-gray-900 dark:text-white mb-1">
                                  Ground Truth:
                                </p>
                                <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3">
                                  <p className="text-sm text-blue-700 dark:text-blue-300">
                                    {qa.ground_truth}
                                  </p>
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Judge Scores & Rationale */}
              {agentDetails.scores && agentDetails.agent_run.status === 'done' && (
                <div className="space-y-4">
                  <div className="flex items-center gap-2">
                    <Award className="w-5 h-5 text-yellow-600 dark:text-yellow-400" />
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                      Judge Evaluation
                    </h3>
                  </div>

                  {/* Overall Score */}
                  <div className="bg-white dark:bg-dark-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                        Overall Score
                      </span>
                      <span className={`text-2xl font-bold ${getScoreColor(agentDetails.scores.overall_score)}`}>
                        {(agentDetails.scores.overall_score * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3">
                      <div
                        className={`h-3 rounded-full transition-all ${getProgressColor(agentDetails.scores.overall_score)}`}
                        style={{ width: `${agentDetails.scores.overall_score * 100}%` }}
                      />
                    </div>
                    <div className="mt-2 flex items-center gap-2">
                      <span className={`text-sm font-medium ${agentDetails.scores.passed ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                        {agentDetails.scores.passed ? '✓ Passed' : '✗ Failed'}
                      </span>
                      {agentDetails.scores.judge_type && (
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                          • Judge: {agentDetails.scores.judge_type}
                        </span>
                      )}
                      {agentDetails.scores.judge_model && (
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                          • Model: {agentDetails.scores.judge_model}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Dimension Scores */}
                  {agentDetails.scores.dimension_scores && 
                   Object.keys(agentDetails.scores.dimension_scores).length > 0 && (
                    <div className="bg-white dark:bg-dark-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                      <h4 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">
                        Dimension Scores
                      </h4>
                      <div className="space-y-3">
                        {Object.entries(agentDetails.scores.dimension_scores).map(([dim, score]) => {
                          const threshold = agentDetails.scores.thresholds_used?.[dim] || 0.7
                          const isFailed = agentDetails.scores.breaking_dimensions?.includes(dim)
                          return (
                            <div key={dim}>
                              <div className="flex items-center justify-between mb-1">
                                <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                                  {dim}
                                  {isFailed && (
                                    <span className="ml-2 text-xs text-red-600 dark:text-red-400">
                                      (Below threshold: {(threshold * 100).toFixed(0)}%)
                                    </span>
                                  )}
                                </span>
                                <span className={`text-sm font-bold ${getScoreColor(score as number)}`}>
                                  {((score as number) * 100).toFixed(1)}%
                                </span>
                              </div>
                              <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                                <div
                                  className={`h-2 rounded-full transition-all ${
                                    isFailed ? 'bg-red-500' : getProgressColor(score as number)
                                  }`}
                                  style={{ width: `${(score as number) * 100}%` }}
                                />
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  )}

                  {/* Breaking Details */}
                  {!agentDetails.scores.passed && 
                   agentDetails.scores.breaking_details && 
                   Object.keys(agentDetails.scores.breaking_details).length > 0 && (
                    <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
                      <h4 className="text-sm font-semibold text-red-900 dark:text-red-100 mb-3">
                        Why Each Dimension Failed:
                      </h4>
                      <div className="space-y-2">
                        {Object.entries(agentDetails.scores.breaking_details).map(([dim, reason]) => (
                          <div key={dim} className="text-sm">
                            <span className="font-medium text-red-600 dark:text-red-400">{dim}:</span>
                            <span className="text-red-700 dark:text-red-300 ml-2">{reason as string}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Judge Rationale */}
                  {agentDetails.scores.rationale && (
                    <div className="bg-white dark:bg-dark-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                      <h4 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">
                        Judge Rationale
                      </h4>
                      <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4">
                        <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
                          {agentDetails.scores.rationale}
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

