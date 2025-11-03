import { useQuery } from '@tanstack/react-query'
import { apiClient } from '../api/client'

export const useAgentRuns = (taskId: string | undefined) => {
  return useQuery({
    queryKey: ['agents', taskId],
    queryFn: () => apiClient.getAgentRuns(taskId!),
    enabled: !!taskId,
  })
}

export const useAgentRun = (taskId: string | undefined, agent: string | undefined) => {
  return useQuery({
    queryKey: ['agent', taskId, agent],
    queryFn: () => apiClient.getAgentRun(taskId!, agent!),
    enabled: !!taskId && !!agent,
  })
}

export const useLeaderboard = (taskId: string | undefined) => {
  return useQuery({
    queryKey: ['leaderboard', taskId],
    queryFn: () => apiClient.getLeaderboard(taskId!),
    enabled: !!taskId,
  })
}

export const useAgentDetails = (taskId: string | undefined, agentName: string | null) => {
  return useQuery({
    queryKey: ['agent-details', taskId, agentName],
    queryFn: () => apiClient.getAgentDetails(taskId!, agentName!),
    enabled: !!taskId && !!agentName,
  })
}

