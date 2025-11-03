import { Trophy, Medal, Star } from 'lucide-react'
import { Sidebar, Header, Loading } from '../components'
import { useTasks } from '../hooks/useTasks'
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '../api/client'

export const LeaderboardsPage = () => {
  // Leaderboard is public - always show all tasks
  const { data: tasksData, isLoading } = useTasks({ page: 1, page_size: 100, filter: 'all' })
  
  // Fetch leaderboard data for all done tasks
  const taskIds = tasksData?.tasks?.filter(t => t.status === 'done').map(t => t.id) || []
  const { data: leaderboardsData } = useQuery({
    queryKey: ['leaderboards', taskIds],
    queryFn: async () => {
      const results = await Promise.all(
        taskIds.map(async (taskId) => {
          try {
            const data = await apiClient.getLeaderboard(taskId)
            return { taskId, data }
          } catch (error) {
            console.error(`Failed to fetch leaderboard for task ${taskId}:`, error)
            return null
          }
        })
      )
      return results.filter(r => r !== null)
    },
    enabled: taskIds.length > 0
  })

  // Calculate agent statistics from completed tasks with real scores
  const calculateLeaderboard = () => {
    if (!tasksData?.tasks) return []

    const agentStats: Record<string, {
      name: string
      totalTasks: number
      completedTasks: number
      failedTasks: number
      avgScore: number
      totalScore: number
      scoreCount: number
      dimensionScores: Record<string, { total: number, count: number }>
    }> = {}

    tasksData.tasks.forEach(task => {
      task.agents.forEach(agent => {
        if (!agentStats[agent]) {
          agentStats[agent] = {
            name: agent,
            totalTasks: 0,
            completedTasks: 0,
            failedTasks: 0,
            avgScore: 0,
            totalScore: 0,
            scoreCount: 0,
            dimensionScores: {}
          }
        }
        
        agentStats[agent].totalTasks++
        
        if (task.status === 'done') {
          agentStats[agent].completedTasks++
          
          // Find real scores from leaderboard data
          const taskLeaderboard = leaderboardsData?.find(lb => lb.taskId === task.id)
          if (taskLeaderboard) {
            const agentEntry = taskLeaderboard.data.leaderboard.find(
              (entry: any) => entry.agent === agent
            )
            if (agentEntry && agentEntry.overall_score !== undefined) {
              agentStats[agent].totalScore += agentEntry.overall_score
              agentStats[agent].scoreCount++
              
              // Collect dimension scores
              if (agentEntry.dimension_scores) {
                Object.entries(agentEntry.dimension_scores).forEach(([dim, score]) => {
                  if (!agentStats[agent].dimensionScores[dim]) {
                    agentStats[agent].dimensionScores[dim] = { total: 0, count: 0 }
                  }
                  agentStats[agent].dimensionScores[dim].total += score as number
                  agentStats[agent].dimensionScores[dim].count++
                })
              }
            }
          }
        } else if (task.status === 'error') {
          agentStats[agent].failedTasks++
        }
        // Running/queued tasks are counted in totalTasks but not in completed/failed
      })
    })

    // Calculate averages and sort
    return Object.values(agentStats)
      .map(stat => ({
        ...stat,
        avgScore: stat.scoreCount > 0 ? stat.totalScore / stat.scoreCount : 0,
        successRate: stat.totalTasks > 0 ? (stat.completedTasks / stat.totalTasks) * 100 : 0,
        avgDimensionScores: Object.entries(stat.dimensionScores).reduce((acc, [dim, data]) => {
          acc[dim] = data.count > 0 ? data.total / data.count : 0
          return acc
        }, {} as Record<string, number>)
      }))
      .sort((a, b) => b.avgScore - a.avgScore)
  }

  const leaderboard = calculateLeaderboard()

  const getRankBadge = (index: number) => {
    switch (index) {
      case 0:
        return <Medal className="w-6 h-6 text-yellow-500" />
      case 1:
        return <Medal className="w-6 h-6 text-gray-400" />
      case 2:
        return <Medal className="w-6 h-6 text-amber-600" />
      default:
        return <span className="text-lg font-bold text-gray-500">#{index + 1}</span>
    }
  }

  const getScoreColor = (score: number) => {
    if (score >= 0.9) return 'text-success-600 dark:text-success-400'
    if (score >= 0.75) return 'text-primary-600 dark:text-primary-400'
    if (score >= 0.6) return 'text-warning-600 dark:text-warning-400'
    return 'text-error-600 dark:text-error-400'
  }

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50 dark:bg-dark-950">
      <Sidebar />

      <div className="flex-1 flex flex-col overflow-hidden ml-64">
        <Header />
        
        {/* Page Header */}
        <div className="bg-white dark:bg-dark-900 border-b border-gray-200 dark:border-gray-800 px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-3">
                <Trophy className="w-8 h-8 text-yellow-500" />
                <div>
                  <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                    Agent Leaderboards
                  </h1>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                    Compare agent performance across evaluations you can access
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Content */}
        <main className="flex-1 overflow-y-auto p-6 max-w-full">
          {isLoading ? (
            <Loading />
          ) : leaderboard.length === 0 ? (
            <div className="card p-12 text-center">
              <Trophy className="w-16 h-16 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                No Data Yet
              </h3>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Complete some tasks to see agent performance statistics
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Top 3 Podium */}
              {leaderboard.length >= 3 && (
                <div className="grid grid-cols-3 gap-4 mb-12">
                  {/* 2nd Place */}
                  <div className="card p-6 text-center">
                    <Medal className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                    <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-1">
                      {leaderboard[1].name}
                    </h3>
                    <p className={`text-3xl font-bold mb-2 ${getScoreColor(leaderboard[1].avgScore)}`}>
                      {(leaderboard[1].avgScore * 100).toFixed(1)}%
                    </p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      {leaderboard[1].completedTasks} tasks completed
                    </p>
                  </div>

                  {/* 1st Place */}
                  <div className="card p-6 text-center bg-gradient-to-br from-yellow-50 to-amber-50 dark:from-yellow-900/20 dark:to-amber-900/20 border-2 border-yellow-400 dark:border-yellow-600">
                    <div className="relative">
                      <Medal className="w-16 h-16 text-yellow-500 mx-auto mb-3" />
                      <Star className="w-6 h-6 text-yellow-500 absolute top-0 right-1/4 animate-pulse" />
                    </div>
                    <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-1">
                      {leaderboard[0].name}
                    </h3>
                    <p className={`text-4xl font-bold mb-2 ${getScoreColor(leaderboard[0].avgScore)}`}>
                      {(leaderboard[0].avgScore * 100).toFixed(1)}%
                    </p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      {leaderboard[0].completedTasks} tasks completed
                    </p>
                  </div>

                  {/* 3rd Place */}
                  <div className="card p-6 text-center">
                    <Medal className="w-10 h-10 text-amber-600 mx-auto mb-3" />
                    <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-1">
                      {leaderboard[2].name}
                    </h3>
                    <p className={`text-2xl font-bold mb-2 ${getScoreColor(leaderboard[2].avgScore)}`}>
                      {(leaderboard[2].avgScore * 100).toFixed(1)}%
                    </p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      {leaderboard[2].completedTasks} tasks completed
                    </p>
                  </div>
                </div>
              )}

              {/* Full Leaderboard Table */}
              <div className="w-full bg-white dark:bg-dark-900 rounded-lg shadow">
                <div className="overflow-x-auto">
                  <table className="w-full divide-y divide-gray-200 dark:divide-gray-800">
                    <thead className="bg-gray-50 dark:bg-dark-800">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                          Rank
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                          Agent
                        </th>
                        <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                          Avg Score
                        </th>
                        <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                          Success Rate
                        </th>
                        <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                          Total Tasks
                        </th>
                        <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                          Completed
                        </th>
                        <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                          Failed
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-white dark:bg-dark-900 divide-y divide-gray-200 dark:divide-gray-800">
                      {leaderboard.map((agent, index) => (
                        <tr key={agent.name} className="hover:bg-gray-50 dark:hover:bg-dark-800 transition-colors">
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="flex items-center justify-center w-10">
                              {getRankBadge(index)}
                            </div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="text-sm font-medium text-gray-900 dark:text-white">
                              {agent.name}
                            </div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-center">
                            <span className={`text-lg font-bold ${getScoreColor(agent.avgScore)}`}>
                              {(agent.avgScore * 100).toFixed(1)}%
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-center">
                            <span className="text-sm text-gray-900 dark:text-white">
                              {agent.successRate.toFixed(1)}%
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-center">
                            <span className="text-sm text-gray-900 dark:text-white">
                              {agent.totalTasks}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-center">
                            <span className="text-sm text-success-600 dark:text-success-400 font-medium">
                              {agent.completedTasks}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-center">
                            <span className="text-sm text-error-600 dark:text-error-400 font-medium">
                              {agent.failedTasks}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}

