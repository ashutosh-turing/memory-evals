import type { TaskStatus, AgentRunStatus, BadgeVariant } from '../types'

/**
 * Map task status to badge variant
 */
export const getTaskStatusVariant = (status: TaskStatus): BadgeVariant => {
  const mapping: Record<TaskStatus, BadgeVariant> = {
    queued: 'gray',
    running: 'primary',
    judging: 'warning',
    done: 'success',
    error: 'error',
  }
  return mapping[status] || 'gray'
}

/**
 * Map agent run status to badge variant
 */
export const getAgentStatusVariant = (status: AgentRunStatus): BadgeVariant => {
  const mapping: Record<AgentRunStatus, BadgeVariant> = {
    queued: 'gray',
    running: 'primary',
    memory_only: 'warning',
    evaluating: 'warning',
    done: 'success',
    error: 'error',
  }
  return mapping[status] || 'gray'
}

/**
 * Get human-readable task status label
 */
export const getTaskStatusLabel = (status: TaskStatus): string => {
  const mapping: Record<TaskStatus, string> = {
    queued: 'Queued',
    running: 'Running',
    judging: 'Judging',
    done: 'Completed',
    error: 'Failed',
  }
  return mapping[status] || status
}

/**
 * Get human-readable agent status label
 */
export const getAgentStatusLabel = (status: AgentRunStatus): string => {
  const mapping: Record<AgentRunStatus, string> = {
    queued: 'Queued',
    running: 'Running',
    memory_only: 'Memory Only',
    evaluating: 'Evaluating',
    done: 'Completed',
    error: 'Failed',
  }
  return mapping[status] || status
}

/**
 * Check if task is in progress
 */
export const isTaskInProgress = (status: TaskStatus): boolean => {
  return ['queued', 'running', 'judging'].includes(status)
}

/**
 * Check if agent run is in progress
 */
export const isAgentInProgress = (status: AgentRunStatus): boolean => {
  return ['queued', 'running', 'memory_only', 'evaluating'].includes(status)
}

/**
 * Get agent display name
 */
export const getAgentDisplayName = (agent: string): string => {
  const mapping: Record<string, string> = {
    iflow: 'iFlow',
    claude: 'Claude',
    gemini: 'Gemini',
  }
  return mapping[agent] || agent
}

/**
 * Get rubric dimension display name
 */
export const getRubricDisplayName = (dimension: string): string => {
  const mapping: Record<string, string> = {
    AR: 'Accuracy & Relevance',
    TTL: 'Task-to-Log Alignment',
    LRU: 'Log Readability & Usability',
    SF: 'Structural Fidelity',
  }
  return mapping[dimension] || dimension
}

