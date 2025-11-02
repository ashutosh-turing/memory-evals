import { Trophy, Medal, Award } from 'lucide-react'
import type { LeaderboardEntry, RubricDimension } from '../types'

interface LeaderboardChartProps {
  leaderboard: LeaderboardEntry[]
  rubric: RubricDimension[]
}

export const LeaderboardChart = ({ leaderboard, rubric }: LeaderboardChartProps) => {
  const getRankIcon = (index: number) => {
    switch (index) {
      case 0:
        return <Trophy className="w-6 h-6 text-yellow-500" />
      case 1:
        return <Medal className="w-6 h-6 text-gray-400" />
      case 2:
        return <Award className="w-6 h-6 text-amber-600" />
      default:
        return <span className="text-lg font-bold text-gray-500">#{index + 1}</span>
    }
  }

  const getScoreColor = (score: number) => {
    if (score >= 0.8) return 'text-success-600 dark:text-success-400'
    if (score >= 0.6) return 'text-primary-600 dark:text-primary-400'
    if (score >= 0.4) return 'text-warning-600 dark:text-warning-400'
    return 'text-error-600 dark:text-error-400'
  }

  const getScoreBg = (score: number) => {
    if (score >= 0.8) return 'bg-success-100 dark:bg-success-900/20'
    if (score >= 0.6) return 'bg-primary-100 dark:bg-primary-900/20'
    if (score >= 0.4) return 'bg-warning-100 dark:bg-warning-900/20'
    return 'bg-error-100 dark:bg-error-900/20'
  }

  return (
    <div className="space-y-4">
      {leaderboard.map((entry, index) => (
        <div
          key={entry.agent}
          className={`
            card p-6 transition-all duration-200
            ${index === 0 ? 'ring-2 ring-yellow-500 shadow-lg' : ''}
          `}
        >
          {/* Header */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-4">
              <div className="flex-shrink-0">
                {getRankIcon(index)}
              </div>
              <div>
                <h3 className="text-lg font-bold text-gray-900 dark:text-white uppercase">
                  {entry.agent}
                </h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  {entry.passed ? 'Passed' : 'Failed'} evaluation
                </p>
              </div>
            </div>

            {/* Overall Score */}
            <div className="text-right">
              <div className="text-xs text-gray-500 dark:text-gray-400 uppercase mb-1">
                Overall Score
              </div>
              <div className={`text-3xl font-bold ${getScoreColor(entry.overall_score)}`}>
                {(entry.overall_score * 100).toFixed(0)}%
              </div>
            </div>
          </div>

          {/* Score Breakdown */}
          <div className="space-y-3">
            {rubric.map((dimension) => {
              const score = entry.scores[dimension as keyof typeof entry.scores] || 0
              return (
                <div key={dimension}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      {dimension}
                    </span>
                    <span className={`text-sm font-bold ${getScoreColor(score)}`}>
                      {(score * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                    <div
                      className={`h-full ${getScoreBg(score)} transition-all duration-500`}
                      style={{ width: `${score * 100}%` }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}

