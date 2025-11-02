import { useState, useEffect, useCallback } from 'react'
import { apiClient } from '../api/client'
import type { LogEntry } from '../types'

export const useLogs = (taskId: string | undefined) => {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!taskId) return

    let eventSource: EventSource | null = null

    try {
      eventSource = apiClient.createLogStream(taskId)

      eventSource.onopen = () => {
        setIsConnected(true)
        setError(null)
      }

      eventSource.onmessage = (event) => {
        try {
          const logEntry: LogEntry = JSON.parse(event.data)
          setLogs((prev) => [...prev, logEntry])
        } catch (err) {
          console.error('Failed to parse log entry:', err)
        }
      }

      eventSource.onerror = () => {
        setIsConnected(false)
        setError('Connection lost. Attempting to reconnect...')
      }
    } catch (err) {
      setError('Failed to connect to log stream')
      console.error('Log stream error:', err)
    }

    return () => {
      if (eventSource) {
        eventSource.close()
        setIsConnected(false)
      }
    }
  }, [taskId])

  const clearLogs = useCallback(() => {
    setLogs([])
  }, [])

  return {
    logs,
    isConnected,
    error,
    clearLogs,
  }
}

