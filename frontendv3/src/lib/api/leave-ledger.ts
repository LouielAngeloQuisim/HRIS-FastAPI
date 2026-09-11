import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { api } from './client'
import type { LeaveLedgerResponse, LeaveCalendarEvent } from './types'

export const leaveLedgerKey = (
  employeeId: string,
  policyId?: string,
  leaveYear?: number,
) => ['leave-ledger', employeeId, policyId, leaveYear]

export async function fetchLeaveLedger(
  employeeId: string,
  policyId?: string,
  leaveYear?: number,
): Promise<LeaveLedgerResponse> {
  const params: Record<string, string | number> = {}
  if (policyId) params['policy_id'] = policyId
  if (leaveYear) params['leave_year'] = leaveYear
  const { data } = await api.get<LeaveLedgerResponse>(
    `/employees/${employeeId}/leave-ledger`,
    { params },
  )
  return data
}

export function useLeaveLedger(employeeId: string, policyId?: string, leaveYear?: number) {
  return useQuery({
    queryKey: leaveLedgerKey(employeeId, policyId, leaveYear),
    queryFn: () => fetchLeaveLedger(employeeId, policyId, leaveYear),
    placeholderData: keepPreviousData,
    enabled: Boolean(employeeId) && Boolean(policyId),
  })
}

export const leaveCalendarKey = (
  employeeId: string,
  fromDate: string,
  toDate: string,
) => ['leave-calendar', employeeId, fromDate, toDate]

export async function fetchLeaveCalendar(
  employeeId: string,
  fromDate: string,
  toDate: string,
): Promise<LeaveCalendarEvent[]> {
  const { data } = await api.get<LeaveCalendarEvent[]>(
    `/employees/${employeeId}/leave-calendar`,
    { params: { from_date: fromDate, to_date: toDate } },
  )
  return data
}

export function useLeaveCalendar(employeeId: string, fromDate: string, toDate: string) {
  return useQuery({
    queryKey: leaveCalendarKey(employeeId, fromDate, toDate),
    queryFn: () => fetchLeaveCalendar(employeeId, fromDate, toDate),
    placeholderData: keepPreviousData,
    enabled: Boolean(employeeId) && Boolean(fromDate) && Boolean(toDate),
  })
}
