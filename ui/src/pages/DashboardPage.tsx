import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { useTasks, useCreateTask, useRestartTask, useDeleteTask } from '../hooks/useTasks'
import { 
  RefreshCw, 
  Plus,
  Sparkles,
  TrendingUp,
  Clock,
  CheckCircle2,
  XCircle,
  Loader2,
  Activity,
  Search
} from 'lucide-react'
import { 
  Sidebar, 
  StatsCard, 
  TaskCardCompact, 
  useToast,
  Modal,
  Loading
} from '../components'
import { Header } from '../components/Header'
import { CreateTaskForm } from '../components/CreateTaskForm'
import type { TaskFilter, CreateTaskRequest } from '../types'

export const DashboardPage = () => {
  const { user } = useAuth()
  const { showToast } = useToast()
  const [searchParams, setSearchParams] = useSearchParams()
  
  const filterParam = (searchParams.get('filter') as TaskFilter) || 'my_tasks'
  const [filter, setFilter] = useState<TaskFilter>(filterParam)
  const [page, setPage] = useState(1)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  // Determine effective role
  const effectiveRole = user?.global_role || user?.user_role
  const canViewTeamTasks = effectiveRole && ['team_admin', 'org_admin', 'super_admin'].includes(effectiveRole)
  const canViewAllTasks = effectiveRole && ['org_admin', 'super_admin'].includes(effectiveRole)

  // Queries
  const { data: tasksData, isLoading, refetch } = useTasks({ page, page_size: 20, filter })
  const createTaskMutation = useCreateTask()
  const restartTaskMutation = useRestartTask()
  const deleteTaskMutation = useDeleteTask()

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      refetch()
    }, 30000)
    return () => clearInterval(interval)
  }, [refetch])

  // Update filter from URL params and validate permissions
  useEffect(() => {
    if (filterParam !== filter) {
      // Check if user has permission for the requested filter
      if (filterParam === 'team_tasks' && !canViewTeamTasks) {
        showToast({
          type: 'error',
          title: 'Access Denied',
          message: 'You need team_admin or higher role to view team tasks',
        })
        setSearchParams({ filter: 'my_tasks' })
        return
      }
      if (filterParam === 'all' && !canViewAllTasks) {
        showToast({
          type: 'error',
          title: 'Access Denied',
          message: 'You need org_admin or higher role to view all tasks',
        })
        setSearchParams({ filter: 'my_tasks' })
        return
      }
      setFilter(filterParam)
    }
  }, [filterParam, canViewTeamTasks, canViewAllTasks])

  const handleCreateTask = async (data: CreateTaskRequest) => {
    try {
      await createTaskMutation.mutateAsync(data)
      showToast({
        type: 'success',
        title: 'Task created successfully!',
        message: 'Your PR evaluation task has been queued.',
      })
      setShowCreateModal(false)
    } catch (error: any) {
      showToast({
        type: 'error',
        title: 'Failed to create task',
        message: error.response?.data?.detail || 'An error occurred',
      })
      throw error
    }
  }

  // Calculate stats
  const stats = {
    total: tasksData?.total || 0,
    queued: tasksData?.tasks.filter(t => t.status === 'queued').length || 0,
    running: tasksData?.tasks.filter(t => t.status === 'running').length || 0,
    completed: tasksData?.tasks.filter(t => t.status === 'done').length || 0,
    failed: tasksData?.tasks.filter(t => t.status === 'error').length || 0,
  }

  // Filter tasks by search query
  const filteredTasks = tasksData?.tasks.filter(task => {
    if (!searchQuery) return true
    const query = searchQuery.toLowerCase()
    return (
      task.repo.toLowerCase().includes(query) ||
      task.pr_number.toString().includes(query) ||
      task.created_by_name?.toLowerCase().includes(query) ||
      task.created_by_email?.toLowerCase().includes(query)
    )
  }) || []

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50 dark:bg-dark-950">
      {/* Sidebar */}
      <Sidebar />

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden ml-64">
        <Header />

        {/* Content Area */}
        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Page Header with Actions */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
                Dashboard
              </h1>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                Welcome back, {user?.name?.split(' ')[0] || 'User'}! Here's your task overview.
              </p>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={() => refetch()}
                className="flex items-center gap-2 px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-dark-800 transition-colors"
                disabled={isLoading}
              >
                <RefreshCw className={`w-5 h-5 text-gray-600 dark:text-gray-400 ${isLoading ? 'animate-spin' : ''}`} />
                <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Refresh</span>
              </button>
              <button
                onClick={() => setShowCreateModal(true)}
                className="btn-primary"
              >
                <Plus className="w-5 h-5" />
                <span>New Task</span>
              </button>
            </div>
          </div>

          {/* Stats Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatsCard
              title="Total Tasks"
              value={stats.total}
              icon={Activity}
              color="primary"
              loading={isLoading}
            />
            <StatsCard
              title="Running"
              value={stats.running}
              icon={Loader2}
              color="primary"
              loading={isLoading}
            />
            <StatsCard
              title="Completed"
              value={stats.completed}
              icon={CheckCircle2}
              color="success"
              loading={isLoading}
            />
            <StatsCard
              title="Failed"
              value={stats.failed}
              icon={XCircle}
              color="error"
              loading={isLoading}
            />
          </div>

          {/* Search Bar */}
          <div className="card p-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                type="text"
                placeholder="Search tasks by repo, PR number, or creator..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 bg-gray-50 dark:bg-dark-800 border-0 rounded-lg text-gray-900 dark:text-white placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>
          </div>

          {/* Tasks Section */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                {filter === 'my_tasks' && 'My Tasks'}
                {filter === 'team_tasks' && 'Team Tasks'}
                {filter === 'all' && 'All Tasks'}
              </h2>
              <span className="text-sm text-gray-500 dark:text-gray-400">
                {filteredTasks.length} {filteredTasks.length === 1 ? 'task' : 'tasks'}
              </span>
            </div>

            {/* Tasks Grid */}
            {isLoading ? (
              <div className="flex justify-center py-12">
                <Loading size="lg" text="Loading tasks..." />
              </div>
            ) : filteredTasks.length === 0 ? (
              <div className="card p-12 text-center">
                <div className="inline-flex items-center justify-center w-16 h-16 bg-gray-100 dark:bg-dark-800 rounded-full mb-4">
                  <TrendingUp className="w-8 h-8 text-gray-400" />
                </div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                  {searchQuery ? 'No tasks found' : 'No tasks yet'}
                </h3>
                <p className="text-gray-500 dark:text-gray-400 mb-6">
                  {searchQuery 
                    ? 'Try adjusting your search query'
                    : 'Create your first task to start evaluating AI agents'
                  }
                </p>
                {!searchQuery && (
                  <button
                    onClick={() => setShowCreateModal(true)}
                    className="btn-primary"
                  >
                    <Plus className="w-5 h-5" />
                    <span>Create Your First Task</span>
                  </button>
                )}
              </div>
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {filteredTasks.map((task) => (
                  <TaskCardCompact key={task.id} task={task} />
                ))}
              </div>
            )}
          </div>

          {/* Pagination */}
          {tasksData && tasksData.total > 20 && !searchQuery && (
            <div className="flex justify-center items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="btn-outline"
              >
                Previous
              </button>
              <span className="px-4 py-2 text-sm text-gray-700 dark:text-gray-300">
                Page {page} of {Math.ceil(tasksData.total / 20)}
              </span>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={page >= Math.ceil(tasksData.total / 20)}
                className="btn-outline"
              >
                Next
              </button>
            </div>
          )}
        </main>
      </div>

      {/* Create Task Modal */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="Create New Task"
      >
        <CreateTaskForm
          onSubmit={handleCreateTask}
          isLoading={createTaskMutation.isPending}
        />
      </Modal>
    </div>
  )
}
