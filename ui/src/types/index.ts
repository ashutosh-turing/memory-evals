// User and Authentication Types
export interface UserContext {
  user_id: string
  email: string
  name: string
  picture?: string
  org_id: string
  org_name?: string
  team_id: string
  team_name?: string
  project_id?: string
  project_name?: string
  user_role: 'super_admin' | 'org_admin' | 'team_admin' | 'member' | 'viewer'
  global_role?: 'super_admin' | 'org_admin' | 'team_admin' | 'member' | 'viewer'
}

// Task Types
export type TaskStatus = 'queued' | 'running' | 'judging' | 'done' | 'error'

export type AgentName = 'iflow' | 'claude' | 'gemini'

export type RubricDimension = 'AR' | 'TTL' | 'LRU' | 'SF'

export interface Task {
  id: string
  pr_url: string
  repo: string
  pr_number: number
  agents: AgentName[]
  rubric: RubricDimension[]
  status: TaskStatus
  max_files: number
  created_at: string
  updated_at: string
  started_at?: string
  completed_at?: string
  changed_files: string[]
  error_message?: string
  // User context fields
  created_by_user_id?: string
  created_by_email?: string
  created_by_name?: string
  org_id?: string
  team_id?: string
  project_id?: string
}

export interface CreateTaskRequest {
  pr_url: string
  agents: AgentName[]
  rubric?: RubricDimension[]
  max_files?: number
}

export interface TaskListResponse {
  tasks: Task[]
  total: number
  page: number
  page_size: number
}

// Agent Run Types
export type AgentRunStatus = 'queued' | 'running' | 'memory_only' | 'evaluating' | 'done' | 'error'

export interface AgentRun {
  id: string
  task_id: string
  agent: AgentName
  status: AgentRunStatus
  milestones: Record<string, string>
  artifacts: Record<string, string>
  stats: Record<string, string>
  created_at: string
  updated_at: string
  started_at?: string
  completed_at?: string
  error_message?: string
  retry_count: number
}

// Score Types
export interface Score {
  AR: number
  TTL: number
  LRU: number
  SF: number
}

export interface LeaderboardEntry {
  agent: AgentName
  status: AgentRunStatus
  overall_score: number
  scores: Score
  dimension_scores?: Record<string, number>
  passed: boolean
  execution_time: number
  compression_detected: boolean
  breaking_dimensions?: string[]
  breaking_details?: Record<string, string>
  thresholds_used?: Record<string, number>
}

export interface Leaderboard {
  task_id: string
  leaderboard: LeaderboardEntry[]
}

// Log Types
export interface LogEntry {
  timestamp: string
  level: 'INFO' | 'WARNING' | 'ERROR'
  type: string
  message: string
  agent?: string
  [key: string]: unknown
}

// Filter Types
export type TaskFilter = 'my_tasks' | 'team_tasks' | 'all'

// API Response Types
export interface ApiError {
  error: string
  detail?: string
  status_code?: number
}

