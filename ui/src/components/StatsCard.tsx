import { LucideIcon } from 'lucide-react'
import { ReactNode } from 'react'

interface StatsCardProps {
  title: string
  value: string | number
  icon: LucideIcon
  trend?: {
    value: number
    label: string
  }
  color?: 'primary' | 'success' | 'warning' | 'error' | 'purple'
  loading?: boolean
  children?: ReactNode
}

export const StatsCard = ({
  title,
  value,
  icon: Icon,
  trend,
  color = 'primary',
  loading = false,
  children,
}: StatsCardProps) => {
  const colorStyles = {
    primary: {
      bg: 'bg-primary-50 dark:bg-primary-900/20',
      icon: 'text-primary-600 dark:text-primary-400',
      trend: 'text-primary-600 dark:text-primary-400',
    },
    success: {
      bg: 'bg-success-50 dark:bg-success-900/20',
      icon: 'text-success-600 dark:text-success-400',
      trend: 'text-success-600 dark:text-success-400',
    },
    warning: {
      bg: 'bg-warning-50 dark:bg-warning-900/20',
      icon: 'text-warning-600 dark:text-warning-400',
      trend: 'text-warning-600 dark:text-warning-400',
    },
    error: {
      bg: 'bg-error-50 dark:bg-error-900/20',
      icon: 'text-error-600 dark:text-error-400',
      trend: 'text-error-600 dark:text-error-400',
    },
    purple: {
      bg: 'bg-purple-50 dark:bg-purple-900/20',
      icon: 'text-purple-600 dark:text-purple-400',
      trend: 'text-purple-600 dark:text-purple-400',
    },
  }

  const styles = colorStyles[color]

  if (loading) {
    return (
      <div className="card p-6 animate-pulse">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="h-4 w-24 bg-gray-200 dark:bg-gray-800 rounded mb-3"></div>
            <div className="h-8 w-32 bg-gray-200 dark:bg-gray-800 rounded"></div>
          </div>
          <div className={`w-12 h-12 rounded-lg ${styles.bg}`}></div>
        </div>
      </div>
    )
  }

  return (
    <div className="card p-6 hover:shadow-lg transition-all duration-200">
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">
            {title}
          </p>
          <p className="text-3xl font-bold text-gray-900 dark:text-white">
            {value}
          </p>
        </div>
        <div className={`w-12 h-12 rounded-lg ${styles.bg} flex items-center justify-center`}>
          <Icon className={`w-6 h-6 ${styles.icon}`} />
        </div>
      </div>

      {trend && (
        <div className="flex items-center gap-1">
          <span className={`text-sm font-medium ${styles.trend}`}>
            {trend.value > 0 ? '+' : ''}{trend.value}%
          </span>
          <span className="text-sm text-gray-500 dark:text-gray-400">
            {trend.label}
          </span>
        </div>
      )}

      {children}
    </div>
  )
}

