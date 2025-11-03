import { useState, useEffect, useCallback, useRef } from 'react'
import { apiClient } from '../api/client'
import type { LogEntry } from '../types'

export const useLogs = (taskId: string | undefined) => {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const etagRef = useRef<string | null>(null)
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!taskId) return

    let active = true
    let taskCompleted = false

    const pollLogs = async () => {
      try {
        const result = await apiClient.pollTaskLogs(taskId, etagRef.current || undefined)
        
        if (!active) return
        
        // If result is null, it means 304 Not Modified (no new content)
        if (result === null) {
          setIsConnected(true)
          return
        }
        
        // Update ETag for next poll
        if (result.etag) {
          etagRef.current = result.etag
        }
        
        // Update logs
        setLogs(result.logs)
        setIsConnected(true)
        setError(null)
        
        // Check if task is completed
        if (result.status === 'done' || result.status === 'error') {
          taskCompleted = true
          // Stop polling after task completes
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current)
            pollIntervalRef.current = null
          }
        }
      } catch (err) {
        if (active) {
          setIsConnected(false)
          setError('Failed to fetch logs')
          console.error('Poll logs error:', err)
        }
      }
    }

    // Initial poll
    pollLogs()
    
    // Set up polling interval (poll every 2 seconds)
    pollIntervalRef.current = setInterval(() => {
      if (!taskCompleted) {
        pollLogs()
      }
    }, 2000)

    return () => {
      active = false
      setIsConnected(false)
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
        pollIntervalRef.current = null
      }
      etagRef.current = null
    }
  }, [taskId])

  const clearLogs = useCallback(() => {
    setLogs([])
    etagRef.current = null
  }, [])

  return {
    logs,
    isConnected,
    error,
    clearLogs,
  }
}
