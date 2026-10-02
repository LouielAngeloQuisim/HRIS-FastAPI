import { useQuery } from '@tanstack/react-query'
import { api } from './client'
import type { LeavePolicyList } from './types'

export function useLeavePolicies() {
  return useQuery({
    queryKey: ['leave-policies'],
    queryFn: () => api.get<LeavePolicyList>('/leave-policies', { params: { limit: 100 } }).then(response => response.data),
  })
}
