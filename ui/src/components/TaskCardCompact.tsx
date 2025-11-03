import { Link } from 'react-router-dom'
import { 
  Clock, 
  CheckCircle2, 
  XCircle, 
  Loader2,
  Activity,
  ExternalLink,
  User,
  Calendar
} from 'lucide-react'
import { formatDistanceToNow, parseISO } from 'date-fns'

interface Task {
  id: string
  pr_url: string
  repo: string
  pr_number: number
  status: string
  agents: string[]
  created_at: string
  created_by_name?: string
  created_by_email?: string
}

interface TaskCardCompactProps {
  task: Task
}

export const TaskCardCompact = ({ task }: TaskCardCompactProps) => {
  const statusConfig = {
    queued: {
      icon: Clock,
      color: 'text-gray-500 dark:text-gray-400',
      bg: 'bg-gray-100 dark:bg-gray-800',
      border: 'border-l-gray-400 dark:border-l-gray-600',
      label: 'Queued',
    },
    running: {
      icon: Loader2,
      color: 'text-primary-600 dark:text-primary-400',
      bg: 'bg-primary-50 dark:bg-primary-900/20',
      border: 'border-l-primary-500',
      label: 'Running',
      animate: 'animate-spin',
    },
    judging: {
      icon: Activity,
      color: 'text-purple-600 dark:text-purple-400',
      bg: 'bg-purple-50 dark:bg-purple-900/20',
      border: 'border-l-purple-500',
      label: 'Judging',
      animate: 'animate-pulse',
    },
    done: {
      icon: CheckCircle2,
      color: 'text-success-600 dark:text-success-400',
      bg: 'bg-success-50 dark:bg-success-900/20',
      border: 'border-l-success-500',
      label: 'Completed',
    },
    completed: {
      icon: CheckCircle2,
      color: 'text-success-600 dark:text-success-400',
      bg: 'bg-success-50 dark:bg-success-900/20',
      border: 'border-l-success-500',
      label: 'Completed',
    },
    error: {
      icon: XCircle,
      color: 'text-error-600 dark:text-error-400',
      bg: 'bg-error-50 dark:bg-error-900/20',
      border: 'border-l-error-500',
      label: 'Failed',
    },
    failed: {
      icon: XCircle,
      color: 'text-error-600 dark:text-error-400',
      bg: 'bg-error-50 dark:bg-error-900/20',
      border: 'border-l-error-500',
      label: 'Failed',
    },
  }

  const config = statusConfig[task.status as keyof typeof statusConfig] || statusConfig.queued
  const StatusIcon = config.icon

  return (
    <Link
      to={`/tasks/${task.id}`}
      className={`
        block card border-l-4 ${config.border} p-4
        hover:shadow-lg hover:scale-[1.01] transition-all duration-200
        group
      `}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white truncate">
              {task.repo}
            </h3>
            <span className="text-sm text-gray-500 dark:text-gray-400">
              #{task.pr_number}
            </span>
          </div>
          <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
            <Calendar className="w-3 h-3" />
            <span>
              {formatDistanceToNow(parseISO(task.created_at), { addSuffix: true })}
            </span>
            {task.created_by_name && (
              <>
                <span>•</span>
                <User className="w-3 h-3" />
                <span>{task.created_by_name}</span>
              </>
            )}
          </div>
        </div>

        {/* Status badge */}
        <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full ${config.bg}`}>
          <StatusIcon className={`w-3.5 h-3.5 ${config.color} ${config.animate || ''}`} />
          <span className={`text-xs font-medium ${config.color}`}>
            {config.label}
          </span>
        </div>
      </div>

      {/* Agent badges */}
      <div className="flex flex-wrap gap-1.5 mb-3">
        {task.agents.map((agent) => (
          <span
            key={agent}
            className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-gray-100 dark:bg-dark-800 text-gray-700 dark:text-gray-300"
          >
            {agent}
          </span>
        ))}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between pt-3 border-t border-gray-200 dark:border-gray-800">
        <a
          href={task.pr_url}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          className="inline-flex items-center gap-1 text-xs text-primary-600 dark:text-primary-400 hover:text-primary-700 dark:hover:text-primary-300 transition-colors"
        >
          <ExternalLink className="w-3 h-3" />
          <span>View PR</span>
        </a>

        <span className="text-xs text-gray-500 dark:text-gray-400 group-hover:text-primary-600 dark:group-hover:text-primary-400 transition-colors">
          View details →
        </span>
      </div>
    </Link>
  )
}

