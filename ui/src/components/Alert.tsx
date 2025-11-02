import React from 'react'
import clsx from 'clsx'
import { AlertCircle, CheckCircle, Info, XCircle, X } from 'lucide-react'

export type AlertVariant = 'info' | 'success' | 'warning' | 'error'

interface AlertProps {
  variant?: AlertVariant
  title?: string
  children: React.ReactNode
  onClose?: () => void
  className?: string
}

export const Alert: React.FC<AlertProps> = ({
  variant = 'info',
  title,
  children,
  onClose,
  className,
}) => {
  const variantConfig = {
    info: {
      container: 'bg-primary-50 border-primary-200 dark:bg-primary-900/20 dark:border-primary-800',
      icon: Info,
      iconColor: 'text-primary-600 dark:text-primary-400',
      title: 'text-primary-900 dark:text-primary-100',
      text: 'text-primary-800 dark:text-primary-200',
    },
    success: {
      container: 'bg-success-50 border-success-200 dark:bg-success-900/20 dark:border-success-800',
      icon: CheckCircle,
      iconColor: 'text-success-600 dark:text-success-400',
      title: 'text-success-900 dark:text-success-100',
      text: 'text-success-800 dark:text-success-200',
    },
    warning: {
      container: 'bg-warning-50 border-warning-200 dark:bg-warning-900/20 dark:border-warning-800',
      icon: AlertCircle,
      iconColor: 'text-warning-600 dark:text-warning-400',
      title: 'text-warning-900 dark:text-warning-100',
      text: 'text-warning-800 dark:text-warning-200',
    },
    error: {
      container: 'bg-error-50 border-error-200 dark:bg-error-900/20 dark:border-error-800',
      icon: XCircle,
      iconColor: 'text-error-600 dark:text-error-400',
      title: 'text-error-900 dark:text-error-100',
      text: 'text-error-800 dark:text-error-200',
    },
  }

  const config = variantConfig[variant]
  const Icon = config.icon

  return (
    <div
      className={clsx(
        'rounded-lg border p-4',
        config.container,
        className
      )}
    >
      <div className="flex">
        <div className="flex-shrink-0">
          <Icon className={clsx('w-5 h-5', config.iconColor)} />
        </div>
        <div className="ml-3 flex-1">
          {title && (
            <h3 className={clsx('text-sm font-medium mb-1', config.title)}>
              {title}
            </h3>
          )}
          <div className={clsx('text-sm', config.text)}>
            {children}
          </div>
        </div>
        {onClose && (
          <div className="ml-auto pl-3">
            <button
              onClick={onClose}
              className={clsx(
                'inline-flex rounded-md p-1.5 focus:outline-none focus:ring-2 focus:ring-offset-2',
                config.iconColor
              )}
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

