import { keepPreviousData, useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { LeaveRequestList, LeaveRequestPublic, LeaveRequestCreate } from './types'

export const leaveRequestsKey = (
  page: number,
  pageSize: number,
  filters?: Record<string, unknown>,
) => ['leave-requests', page, pageSize, filters]

export async function fetchLeaveRequests(
  page: number,
  pageSize: number,
  filters?: { status?: string; employee_id?: string; leave_year?: number },
): Promise<LeaveRequestList> {
  const skip = (page - 1) * pageSize
  const params: Record<string, unknown> = { skip, limit: pageSize }
  if (filters?.status) params['status'] = filters.status
  if (filters?.employee_id) params['employee_id'] = filters.employee_id
  if (filters?.leave_year) params['leave_year'] = filters.leave_year
  const { data } = await api.get<LeaveRequestList>('/leave-requests', { params })
  return data
}

export function useLeaveRequests(
  page: number,
  pageSize: number,
  filters?: { status?: string; employee_id?: string; leave_year?: number },
) {
  return useQuery({
    queryKey: leaveRequestsKey(page, pageSize, filters),
    queryFn: () => fetchLeaveRequests(page, pageSize, filters),
    placeholderData: keepPreviousData,
  })
}

export function useLeaveRequest(id: string | undefined) {
  return useQuery({
    queryKey: ['leave-request', id],
    queryFn: () => api.get<LeaveRequestPublic>(`/leave-requests/${id}`).then(r => r.data),
    enabled: Boolean(id),
  })
}

export function useSubmitLeaveRequest() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: LeaveRequestCreate) =>
      api.post('/leave-requests', data).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['leave-requests'] }),
  })
}

export function useApproveLeaveRequest() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      api.post(`/leave-requests/${id}/approve`).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['leave-requests'] }),
  })
}

export function useRejectLeaveRequest() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, note }: { id: string; note?: string }) =>
      api.post(`/leave-requests/${id}/reject`, { note }).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['leave-requests'] }),
  })
}
