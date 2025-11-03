import axios, { AxiosInstance, AxiosError } from 'axios'
import { getApiBaseUrl } from '../lib/api'
import type { 
  Task, 
  TaskListResponse, 
  CreateTaskRequest, 
  AgentRun, 
  Leaderboard,
  TaskFilter,
  TaskStatus
} from '../types'

class ApiClient {
  private client: AxiosInstance
  private baseUrl: string

  constructor() {
    this.baseUrl = getApiBaseUrl()
    
    this.client = axios.create({
      baseURL: this.baseUrl,
      headers: {
        'Content-Type': 'application/json',
      },
    })

    // Request interceptor to add auth token
    this.client.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('auth_token')
        if (token) {
          config.headers.Authorization = `Bearer ${token}`
        }
        return config
      },
      (error) => Promise.reject(error)
    )

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        if (error.response?.status === 401) {
          // Unauthorized - redirect to login
          localStorage.removeItem('auth_token')
          localStorage.removeItem('user_context')
          window.location.href = '/login'
        }
        return Promise.reject(error)
      }
    )
  }

  // Task endpoints
  async getTasks(params?: {
    page?: number
    page_size?: number
    status?: TaskStatus
    filter?: TaskFilter
  }): Promise<TaskListResponse> {
    const response = await this.client.get<TaskListResponse>('/tasks', { params })
    return response.data
  }

  async getTask(taskId: string): Promise<Task> {
    const response = await this.client.get<Task>(`/tasks/${taskId}`)
    return response.data
  }

  async createTask(data: CreateTaskRequest): Promise<Task> {
    const response = await this.client.post<Task>('/tasks', data)
    return response.data
  }

  async deleteTask(taskId: string): Promise<void> {
    await this.client.delete(`/tasks/${taskId}`)
  }

  async restartTask(taskId: string): Promise<Task> {
    const response = await this.client.post<Task>(`/tasks/${taskId}/run`)
    return response.data
  }

  // Agent endpoints
  async getAgentRuns(taskId: string): Promise<AgentRun[]> {
    const response = await this.client.get<AgentRun[]>(`/tasks/${taskId}/agents`)
    return response.data
  }

  async getAgentRun(taskId: string, agent: string): Promise<AgentRun> {
    const response = await this.client.get<AgentRun>(`/tasks/${taskId}/agents/${agent}`)
    return response.data
  }

  // Leaderboard endpoint
  async getLeaderboard(taskId: string): Promise<Leaderboard> {
    const response = await this.client.get<Leaderboard>(`/tasks/${taskId}/leaderboard`)
    return response.data
  }

  // Get detailed agent run with judge rationale
  async getAgentDetails(taskId: string, agentName: string): Promise<{
    agent_run: {
      id: string
      agent: string
      status: string
      error_message: string | null
      stats: Record<string, any>
      milestones: Record<string, any>
      created_at: string
      updated_at: string
      started_at: string | null
      completed_at: string | null
    }
    scores: {
      overall_score: number
      dimension_scores: Record<string, number>
      rationale: string
      breaking_dimensions: string[]
      breaking_details: Record<string, string>
      thresholds_used: Record<string, number>
      passed: boolean
      judge_type: string | null
      judge_model: string | null
    } | null
  }> {
    const response = await this.client.get(`/tasks/${taskId}/agents/${agentName}/details`)
    return response.data
  }

  // Retry failed agents or entire task
  async retryTask(taskId: string, agents?: string[]): Promise<{
    status: string
    message: string
  }> {
    const response = await this.client.post(`/tasks/${taskId}/retry`, { agents })
    return response.data
  }

  // Poll task logs with ETag caching
  async pollTaskLogs(taskId: string, etag?: string): Promise<{
    logs: any[]
    status: string
    etag: string | null
    log_count: number
    has_log_file: boolean
  } | null> {
    const token = localStorage.getItem('auth_token')
    const url = `${this.baseUrl}/logs/${taskId}/poll`
    
    const headers: Record<string, string> = {
      'Authorization': `Bearer ${token}`,
    }
    
    // Add ETag header if we have one
    if (etag) {
      headers['If-None-Match'] = etag
    }
    
    const response = await fetch(url, { headers })
    
    // 304 Not Modified - no new content
    if (response.status === 304) {
      return null
    }
    
    if (!response.ok) {
      throw new Error(`Poll failed: ${response.statusText}`)
    }
    
    const data = await response.json()
    const newEtag = response.headers.get('ETag')
    
    return {
      ...data,
      etag: newEtag
    }
  }

  // Artifacts
  getArtifactUrl(taskId: string, agent: string, artifactName: string): string {
    return `${this.baseUrl}/artifacts/${taskId}/${agent}/${artifactName}`
  }

  getBundleUrl(taskId: string): string {
    return `${this.baseUrl}/artifacts/${taskId}/bundle`
  }

  async downloadTaskJSONL(taskId: string): Promise<void> {
    const token = localStorage.getItem('auth_token')
    const response = await fetch(`${this.baseUrl}/artifacts/${taskId}/evaluation.jsonl`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })
    
    if (!response.ok) {
      throw new Error(`Failed to download JSONL: ${response.statusText}`)
    }
    
    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${taskId}_evaluation.jsonl`
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
  }

  // Health check
  async checkHealth(): Promise<{ status: string; version: string }> {
    const response = await this.client.get('/info')
    return response.data
  }
}

export const apiClient = new ApiClient()

