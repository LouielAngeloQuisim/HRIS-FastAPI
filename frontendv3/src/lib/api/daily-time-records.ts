import { keepPreviousData, useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { DailyTimeRecordList, DailyTimeRecordPublic } from './types'

export const dtrKey = (page: number, pageSize: number, employeeId?: string, dateFrom?: string, dateTo?: string, employeeCode?: string) =>
  ['daily-time-records', page, pageSize, employeeId, dateFrom, dateTo, employeeCode]

export interface DtrInterval {
  id: string
  daily_time_record_id: string
  revision: number
  sequence: number
  start_at: string
  end_at: string
  original_row: Record<string, unknown>
  created_by: string | null
  created_at: string | null
}

export interface DtrIntervalInput {
  start_at: string
  end_at: string
  original_row: Record<string, unknown>
}

export function useDtrIntervals(recordId: string, includeHistory = false, enabled = true) {
  return useQuery({
    queryKey: ['daily-time-records', recordId, 'intervals', includeHistory],
    queryFn: () => api.get<DtrInterval[]>(`/daily-time-records/${recordId}/intervals`, { params: { include_history: includeHistory } }).then(r => r.data),
    enabled: Boolean(recordId) && enabled,
  })
}

export function useReplaceDtrIntervals(recordId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (intervals: DtrIntervalInput[]) => api.put<DtrInterval[]>(`/daily-time-records/${recordId}/intervals`, { intervals }).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['daily-time-records'] }),
  })
}

export async function fetchDailyTimeRecords(
  page: number,
  pageSize: number,
  employeeId?: string,
  dateFrom?: string,
  dateTo?: string,
  employeeCode?: string,
): Promise<DailyTimeRecordList> {
  const skip = (page - 1) * pageSize
  const params: Record<string, unknown> = { skip, limit: pageSize }
  if (employeeId) params['employee_id'] = employeeId
  if (dateFrom) params['date_from'] = dateFrom
  if (dateTo) params['date_to'] = dateTo
  if (employeeCode) params['employee_code'] = employeeCode
  const { data } = await api.get<DailyTimeRecordList>('/daily-time-records', { params })
  return data
}

export function useDailyTimeRecords(page: number, pageSize: number, employeeId?: string, dateFrom?: string, dateTo?: string, employeeCode?: string) {
  return useQuery({
    queryKey: dtrKey(page, pageSize, employeeId, dateFrom, dateTo, employeeCode),
    queryFn: () => fetchDailyTimeRecords(page, pageSize, employeeId, dateFrom, dateTo, employeeCode),
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
    mutationFn: ({ id, approved_minutes, reason }: { id: string; approved_minutes: number; reason: string }) =>
      api.post(`/daily-time-records/${id}/approve-overtime`, { approved_minutes, reason }).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['daily-time-records'] }),
  })
}

export function useRejectOvertime() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      api.post(`/daily-time-records/${id}/reject-overtime`, { reason }).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['daily-time-records'] }),
  })
}

export function useUpdateDailyTimeRecord() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: { login_date: string; logout_date: string } }) => api.patch<DailyTimeRecordPublic>('/daily-time-records/' + id, data).then(response => response.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['daily-time-records'] }),
  })
}

export function useDeleteDailyTimeRecord() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.delete('/daily-time-records/' + id).then(response => response.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['daily-time-records'] }),
  })
}
