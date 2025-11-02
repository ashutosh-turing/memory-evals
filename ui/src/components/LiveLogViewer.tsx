import { useState, useEffect, useRef } from 'react'
import { 
  Play, 
  Pause, 
  Trash2, 
  Search, 
  Download,
  AlertCircle,
  Info,
  CheckCircle2,
  Terminal
} from 'lucide-react'

interface LogEntry {
  timestamp: string
  level: string
  message: string
  agent?: string
}

interface LiveLogViewerProps {
  logs: LogEntry[]
  isConnected: boolean
  onClear: () => void
}

export const LiveLogViewer = ({ logs, isConnected, onClear }: LiveLogViewerProps) => {
  const [autoScroll, setAutoScroll] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedLevel, setSelectedLevel] = useState<string>('')
  const [selectedAgent, setSelectedAgent] = useState<string>('')
  const logsEndRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs, autoScroll])

  // Filter logs
  const filteredLogs = logs.filter((log) => {
    if (selectedLevel && log.level !== selectedLevel) return false
    if (selectedAgent && log.agent !== selectedAgent) return false
    if (searchQuery && !log.message.toLowerCase().includes(searchQuery.toLowerCase())) return false
    return true
  })

  // Get unique agents
  const availableAgents = Array.from(new Set(logs.map((log) => log.agent).filter(Boolean)))

  const getLogIcon = (level: string) => {
    switch (level) {
      case 'ERROR':
        return <AlertCircle className="w-4 h-4 text-error-500" />
      case 'WARNING':
        return <AlertCircle className="w-4 h-4 text-warning-500" />
      case 'SUCCESS':
        return <CheckCircle2 className="w-4 h-4 text-success-500" />
      case 'INFO':
      default:
        return <Info className="w-4 h-4 text-primary-500" />
    }
  }

  const getLogColor = (level: string) => {
    switch (level) {
      case 'ERROR':
        return 'text-error-400 bg-error-900/20 border-l-error-500'
      case 'WARNING':
        return 'text-warning-400 bg-warning-900/20 border-l-warning-500'
      case 'SUCCESS':
        return 'text-success-400 bg-success-900/20 border-l-success-500'
      case 'INFO':
      default:
        return 'text-primary-400 bg-primary-900/20 border-l-primary-500'
    }
  }

  const handleDownload = () => {
    const logText = logs.map(log => 
      `[${new Date(log.timestamp).toISOString()}] [${log.level}] ${log.agent ? `[${log.agent}] ` : ''}${log.message}`
    ).join('\n')
    
    const blob = new Blob([logText], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `logs-${Date.now()}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-800">
        <div className="flex items-center gap-3">
          <Terminal className="w-5 h-5 text-gray-600 dark:text-gray-400" />
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            Live Logs
          </h3>
          <div className="flex items-center gap-2">
            <div
              className={`w-2 h-2 rounded-full ${
                isConnected ? 'bg-success-500 animate-pulse' : 'bg-error-500'
              }`}
            />
            <span className="text-xs text-gray-500 dark:text-gray-400">
              {isConnected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setAutoScroll(!autoScroll)}
            className={`p-2 rounded-lg transition-colors ${
              autoScroll
                ? 'bg-primary-100 dark:bg-primary-900/30 text-primary-600 dark:text-primary-400'
                : 'hover:bg-gray-100 dark:hover:bg-dark-800 text-gray-600 dark:text-gray-400'
            }`}
            title={autoScroll ? 'Disable auto-scroll' : 'Enable auto-scroll'}
          >
            {autoScroll ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
          </button>
          <button
            onClick={handleDownload}
            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-dark-800 text-gray-600 dark:text-gray-400 transition-colors"
            title="Download logs"
          >
            <Download className="w-4 h-4" />
          </button>
          <button
            onClick={onClear}
            className="p-2 rounded-lg hover:bg-error-100 dark:hover:bg-error-900/30 text-error-600 dark:text-error-400 transition-colors"
            title="Clear logs"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-800 space-y-3">
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search logs..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-gray-50 dark:bg-dark-800 border-0 rounded-lg text-sm text-gray-900 dark:text-white placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>

        {/* Level and Agent filters */}
        <div className="flex gap-2">
          <select
            value={selectedLevel}
            onChange={(e) => setSelectedLevel(e.target.value)}
            className="flex-1 px-3 py-2 bg-gray-50 dark:bg-dark-800 border-0 rounded-lg text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="">All Levels</option>
            <option value="INFO">INFO</option>
            <option value="SUCCESS">SUCCESS</option>
            <option value="WARNING">WARNING</option>
            <option value="ERROR">ERROR</option>
          </select>

          <select
            value={selectedAgent}
            onChange={(e) => setSelectedAgent(e.target.value)}
            className="flex-1 px-3 py-2 bg-gray-50 dark:bg-dark-800 border-0 rounded-lg text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="">All Agents</option>
            {availableAgents.map((agent) => (
              <option key={agent} value={agent}>
                {agent}
              </option>
            ))}
          </select>
        </div>

        {/* Stats */}
        <div className="flex gap-2 text-xs">
          <span className="text-gray-500 dark:text-gray-400">
            Total: <span className="font-semibold text-gray-900 dark:text-white">{logs.length}</span>
          </span>
          <span className="text-gray-500 dark:text-gray-400">•</span>
          <span className="text-gray-500 dark:text-gray-400">
            Displayed: <span className="font-semibold text-gray-900 dark:text-white">{filteredLogs.length}</span>
          </span>
        </div>
      </div>

      {/* Logs Container */}
      <div className="flex-1 overflow-y-auto bg-dark-950 p-4 font-mono text-sm">
        {filteredLogs.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-500">
            <Terminal className="w-12 h-12 mb-3 opacity-50" />
            <p className="text-sm">
              {logs.length === 0 ? 'No logs yet. Waiting for task to start...' : 'No logs match your filters'}
            </p>
          </div>
        ) : (
          <div className="space-y-1">
            {filteredLogs.map((log, index) => (
              <div
                key={index}
                className={`flex gap-3 py-2 px-3 rounded border-l-2 ${getLogColor(log.level)}`}
              >
                <span className="flex-shrink-0 mt-0.5">{getLogIcon(log.level)}</span>
                <span className="text-gray-500 flex-shrink-0 text-xs mt-0.5">
                  {new Date(log.timestamp).toLocaleTimeString()}
                </span>
                {log.agent && (
                  <span className="text-primary-400 flex-shrink-0 text-xs font-semibold mt-0.5">
                    [{log.agent}]
                  </span>
                )}
                <span className="text-gray-300 flex-1 break-words">
                  {log.message}
                </span>
              </div>
            ))}
            <div ref={logsEndRef} />
          </div>
        )}
      </div>
    </div>
  )
}

