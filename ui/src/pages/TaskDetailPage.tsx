import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  Download,
  ExternalLink,
  GitPullRequest,
  FileCode,
  User,
  Calendar,
  Trophy
} from 'lucide-react'
import { useTask } from '../hooks/useTasks'
import { useLeaderboard } from '../hooks/useAgents'
import { useLogs } from '../hooks/useLogs'
import { apiClient } from '../api/client'
import { 
  Sidebar,
  Header,
  Loading, 
  LeaderboardChart, 
  LiveLogViewer,
  useToast 
} from '../components'
import { formatDistanceToNow, parseISO } from 'date-fns'

export const TaskDetailPage = () => {
  const { taskId } = useParams<{ taskId: string }>()
  const navigate = useNavigate()
  const { showToast } = useToast()
  
  // Queries
  const { data: task, isLoading: taskLoading } = useTask(taskId)
  const { data: leaderboardData } = useLeaderboard(taskId)
  const { logs, isConnected, clearLogs } = useLogs(taskId)

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'queued':
        return 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300'
      case 'running':
        return 'bg-primary-100 dark:bg-primary-900/20 text-primary-700 dark:text-primary-400'
      case 'done':
        return 'bg-success-100 dark:bg-success-900/20 text-success-700 dark:text-success-400'
      case 'error':
        return 'bg-error-100 dark:bg-error-900/20 text-error-700 dark:text-error-400'
      default:
        return 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300'
    }
  }

  const handleDownloadBundle = async () => {
    try {
      const token = localStorage.getItem('auth_token')
      const bundleUrl = apiClient.getBundleUrl(taskId!)
      
      const response = await fetch(bundleUrl, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      
      if (!response.ok) {
        throw new Error('Download failed')
      }
      
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `task-${taskId}-bundle.zip`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      
      showToast({
        type: 'success',
        title: 'Download started',
        message: 'Your artifact bundle is being downloaded',
      })
    } catch (error) {
      showToast({
        type: 'error',
        title: 'Download failed',
        message: 'Failed to download artifact bundle',
      })
    }
  }

  if (taskLoading) {
    return (
      <div className="flex h-screen overflow-hidden bg-gray-50 dark:bg-dark-950">
        <Sidebar />
        <div className="flex-1 flex items-center justify-center ml-64">
          <Loading size="lg" text="Loading task details..." />
        </div>
      </div>
    )
  }

  if (!task) {
    return (
      <div className="flex h-screen overflow-hidden bg-gray-50 dark:bg-dark-950">
        <Sidebar />
        <div className="flex-1 flex items-center justify-center ml-64">
          <div className="card p-8 text-center">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
              Task not found
            </h2>
            <p className="text-gray-500 dark:text-gray-400 mb-6">
              The task you're looking for doesn't exist or has been deleted.
            </p>
            <button onClick={() => navigate('/')} className="btn-primary">
              <ArrowLeft className="w-4 h-4" />
              <span>Back to Dashboard</span>
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50 dark:bg-dark-950">
      {/* Sidebar */}
      <Sidebar />

      {/* Main Content - Split Screen */}
      <div className="flex-1 flex flex-col overflow-hidden ml-64">
        <Header />
        
        {/* Page Header */}
        <div className="bg-white dark:bg-dark-900 border-b border-gray-200 dark:border-gray-800 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                onClick={() => navigate('/')}
                className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-dark-800 transition-colors"
              >
                <ArrowLeft className="w-5 h-5 text-gray-600 dark:text-gray-400" />
              </button>
              <div>
                <h1 className="text-xl font-bold text-gray-900 dark:text-white">
                  Task Details
                </h1>
                <p className="text-sm text-gray-500 dark:text-gray-400 font-mono">
                  {task.id.substring(0, 8)}...
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <span className={`px-3 py-1.5 rounded-full text-sm font-medium ${getStatusColor(task.status)}`}>
                {task.status}
              </span>
              <button
                onClick={handleDownloadBundle}
                disabled={task.status === 'queued' || task.status === 'running'}
                className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Download className="w-4 h-4" />
                <span>Download Bundle</span>
              </button>
              <button
                onClick={async () => {
                  try {
                    await apiClient.downloadTaskJSONL(taskId!)
                  } catch (error) {
                    console.error('Failed to download JSONL:', error)
                  }
                }}
                disabled={task.status === 'queued' || task.status === 'running'}
                className="btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Download className="w-4 h-4" />
                <span>Download JSONL</span>
              </button>
            </div>
          </div>
        </div>

        {/* Split Screen Content */}
        <div className="flex-1 flex overflow-hidden">
          {/* Left Panel - Task Info & Leaderboard */}
          <div className="w-1/2 border-r border-gray-200 dark:border-gray-800 overflow-y-auto p-6 space-y-6">
            {/* Task Info Card */}
            <div className="card p-6">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                Task Information
              </h2>
              <div className="space-y-4">
                {/* PR Info */}
                <div>
                  <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400 uppercase mb-2">
                    <GitPullRequest className="w-4 h-4" />
                    <span>Pull Request</span>
                  </div>
                  <a
                    href={task.pr_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 text-primary-600 dark:text-primary-400 hover:underline font-medium"
                  >
                    <span>{task.repo} #{task.pr_number}</span>
                    <ExternalLink className="w-4 h-4" />
                  </a>
                </div>

                {/* Agents */}
                <div>
                  <div className="text-xs text-gray-500 dark:text-gray-400 uppercase mb-2">
                    Agents ({task.agents.length})
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {task.agents.map((agent) => (
                      <span
                        key={agent}
                        className="px-3 py-1 rounded-lg text-sm font-medium bg-primary-100 dark:bg-primary-900/20 text-primary-700 dark:text-primary-400"
                      >
                        {agent}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Metadata */}
                <div className="grid grid-cols-2 gap-4 pt-4 border-t border-gray-200 dark:border-gray-800">
                  <div>
                    <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400 mb-1">
                      <Calendar className="w-3 h-3" />
                      <span>Created</span>
                    </div>
                    <p className="text-sm font-medium text-gray-900 dark:text-white">
                      {formatDistanceToNow(parseISO(task.created_at), { addSuffix: true })}
                    </p>
                  </div>
                  <div>
                    <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400 mb-1">
                      <FileCode className="w-3 h-3" />
                      <span>Changed Files</span>
                    </div>
                    <p className="text-sm font-medium text-gray-900 dark:text-white">
                      {task.changed_files.length} files
                    </p>
                  </div>
                  {task.created_by_name && (
                    <div className="col-span-2">
                      <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400 mb-1">
                        <User className="w-3 h-3" />
                        <span>Created By</span>
                      </div>
                      <p className="text-sm font-medium text-gray-900 dark:text-white">
                        {task.created_by_name}
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        {task.created_by_email}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Leaderboard */}
            {leaderboardData && leaderboardData.leaderboard.length > 0 ? (
              <div>
                <div className="flex items-center gap-2 mb-4">
                  <Trophy className="w-5 h-5 text-yellow-500" />
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                    Leaderboard
                  </h2>
                </div>
                <LeaderboardChart
                  leaderboard={leaderboardData.leaderboard}
                  rubric={task.rubric}
                  taskId={taskId}
                />
              </div>
            ) : (
              <div className="card p-12 text-center">
                <Trophy className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Leaderboard will appear once agents complete their evaluations
                </p>
              </div>
            )}
          </div>

          {/* Right Panel - Live Logs */}
          <div className="w-1/2 flex flex-col">
            <LiveLogViewer
              logs={logs}
              isConnected={isConnected}
              onClear={clearLogs}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
