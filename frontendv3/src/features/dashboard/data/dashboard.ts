import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api/client'
import { type DashboardStats } from '@/lib/api/types'

export async function fetchDashboard(): Promise<DashboardStats> {
  const { data } = await api.get<DashboardStats>('/dashboard')
  return data
}

export function useDashboard() {
  return useQuery({
    queryKey: ['dashboard'],
    queryFn: fetchDashboard,
  })
}
