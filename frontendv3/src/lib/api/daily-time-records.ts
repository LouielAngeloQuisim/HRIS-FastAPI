import { keepPreviousData, useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { DailyTimeRecordList, DailyTimeRecordPublic } from './types'

export const dtrKey = (page: number, pageSize: number, employeeId?: string) =>
  ['daily-time-records', page, pageSize, employeeId]

export async function fetchDailyTimeRecords(
  page: number,
  pageSize: number,
  employeeId?: string,
): Promise<DailyTimeRecordList> {
  const skip = (page - 1) * pageSize
  const params: Record<string, unknown> = { skip, limit: pageSize }
  if (employeeId) params['employee_id'] = employeeId
  const { data } = await api.get<DailyTimeRecordList>('/daily-time-records', { params })
  return data
}

export function useDailyTimeRecords(page: number, pageSize: number, employeeId?: string) {
  return useQuery({
    queryKey: dtrKey(page, pageSize, employeeId),
    queryFn: () => fetchDailyTimeRecords(page, pageSize, employeeId),
    placeholderData: keepPreviousData,
  })
}

export async function fetchDailyTimeRecord(id: string): Promise<DailyTimeRecordPublic> {
  const { data } = await api.get<DailyTimeRecordPublic>(`/daily-time-records/${id}`)
  return data
}

export function useApproveOvertime() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      api.post(`/daily-time-records/${id}/approve-overtime`).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['daily-time-records'] }),
  })
}

export function useRejectOvertime() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      api.post(`/daily-time-records/${id}/reject-overtime`).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['daily-time-records'] }),
  })
}
