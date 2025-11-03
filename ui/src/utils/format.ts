import { formatDistanceToNow, format, parseISO } from 'date-fns'

/**
 * Format a date string to relative time (e.g., "2 hours ago")
 */
export const formatRelativeTime = (dateString: string): string => {
  try {
    return formatDistanceToNow(parseISO(dateString), { addSuffix: true })
  } catch {
    return 'Unknown'
  }
}

/**
 * Format a date string to a readable format
 */
export const formatDate = (dateString: string, formatStr: string = 'PPpp'): string => {
  try {
    return format(parseISO(dateString), formatStr)
  } catch {
    return 'Invalid date'
  }
}

/**
 * Format duration in seconds to human readable format
 */
export const formatDuration = (seconds: number): string => {
  if (seconds < 60) {
    return `${Math.round(seconds)}s`
  } else if (seconds < 3600) {
    const minutes = Math.floor(seconds / 60)
    const remainingSeconds = Math.round(seconds % 60)
    return `${minutes}m ${remainingSeconds}s`
  } else {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    return `${hours}h ${minutes}m`
  }
}

/**
 * Format file size in bytes to human readable format
 */
export const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 Bytes'

  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))

  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i]
}

/**
 * Truncate text to a maximum length
 */
export const truncate = (text: string, maxLength: number): string => {
  if (text.length <= maxLength) return text
  return text.slice(0, maxLength) + '...'
}

/**
 * Format score as percentage
 */
export const formatScore = (score: number): string => {
  return `${Math.round(score * 100)}%`
}

