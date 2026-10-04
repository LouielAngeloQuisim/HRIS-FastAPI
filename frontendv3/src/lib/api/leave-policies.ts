import { keepPreviousData, useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type {
  LeavePolicyList,
  LeavePolicyPublic,
  LeavePolicyCreate,
  LeavePolicyUpdate,
  EmployeeLeaveEnrollmentPublic,
  EmployeeLeaveEnrollmentList,
  EmployeeLeaveEnrollmentCreate,
  LeaveRequestList,
  LeaveRequestPublic,
} from './types'

// -----------------------------------------------------------------------------
// Leave Policies (QA-04)
// -----------------------------------------------------------------------------

export const leavePoliciesKey = (page: number, pageSize: number) => [
  'leave-policies',
  page,
  pageSize,
]

export async function fetchLeavePolicies(page: number, pageSize: number): Promise<LeavePolicyList> {
  const skip = (page - 1) * pageSize
  const { data } = await api.get<LeavePolicyList>('/leave-policies', {
    params: { skip, limit: pageSize },
  })
  return data
}

export function useLeavePolicies(page: number, pageSize: number) {
  return useQuery({
    queryKey: leavePoliciesKey(page, pageSize),
    queryFn: () => fetchLeavePolicies(page, pageSize),
    placeholderData: keepPreviousData,
  })
}

export async function fetchLeavePolicy(id: string): Promise<LeavePolicyPublic> {
  const { data } = await api.get<LeavePolicyPublic>(`/leave-policies/${id}`)
  return data
}

export function useLeavePolicy(id: string | undefined) {
  return useQuery({
    queryKey: ['leave-policy', id],
    queryFn: () => fetchLeavePolicy(id as string),
    enabled: Boolean(id),
  })
}

export function useCreateLeavePolicy() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: LeavePolicyCreate) =>
      api.post<LeavePolicyPublic>('/leave-policies', data).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['leave-policies'] }),
  })
}

export function useUpdateLeavePolicy() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: LeavePolicyUpdate }) =>
      api.patch<LeavePolicyPublic>(`/leave-policies/${id}`, data).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['leave-policies'] }),
  })
}

export function useDeleteLeavePolicy() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.delete(`/leave-policies/${id}`).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['leave-policies'] }),
  })
}

// -----------------------------------------------------------------------------
// Leave Enrollment (QA-04)
// -----------------------------------------------------------------------------

export const enrollmentKey = (employeeId: string, leaveYear: number) => [
  'leave-enrollment',
  employeeId,
  leaveYear,
]

export async function fetchLeaveEnrollments(employeeId: string, leaveYear: number): Promise<EmployeeLeaveEnrollmentList> {
  const { data } = await api.get<EmployeeLeaveEnrollmentList>(
    `/employees/${employeeId}/leave-enrollments`,
    { params: { leave_year: leaveYear } }
  )
  return data
}

export function useLeaveEnrollments(employeeId: string | undefined, leaveYear: number = 2026) {
  return useQuery({
    queryKey: enrollmentKey(employeeId ?? 'none', leaveYear),
    queryFn: () => fetchLeaveEnrollments(employeeId as string, leaveYear),
    enabled: Boolean(employeeId),
    placeholderData: keepPreviousData,
  })
}

export function useEnrollEmployee() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ employee_id, data }: { employee_id: string; data: EmployeeLeaveEnrollmentCreate }) =>
      api.post<EmployeeLeaveEnrollmentPublic>(`/employees/${employee_id}/leave-enrollments`, data).then(r => r.data),
    onSuccess: (_, { employee_id, data }) =>
      qc.invalidateQueries({ queryKey: enrollmentKey(employee_id, data.leave_year ?? 2026) }),
  })
}

// -----------------------------------------------------------------------------
// Leave Requests (QA-04)
// -----------------------------------------------------------------------------

export function useLeaveRequests() {
  return useQuery({
    queryKey: ['leave-requests'],
    queryFn: async () => {
      const { data } = await api.get<LeaveRequestList>('/leave-requests')
      return data
    },
  })
}

export function useSubmitLeaveRequest() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: LeaveRequestCreate) =>
      api.post<LeaveRequestPublic>('/leave-requests', data).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['leave-requests'] }),
  })
}

export function useManageLeaveRequest(requestId: string | undefined) {
  const qc = useQueryClient()
  return {
    approve: useMutation({
      mutationFn: () => api.post<LeaveRequestPublic>(`/leave-requests/${requestId}/approve`).then(r => r.data),
      onSuccess: () => qc.invalidateQueries({ queryKey: ['leave-requests'] }),
    }),
    reject: useMutation({
      mutationFn: ({ note }: { note?: string }) =>
        api.post<LeaveRequestPublic>(`/leave-requests/${requestId}/reject`, note ? { note } : undefined).then(r => r.data),
      onSuccess: () => qc.invalidateQueries({ queryKey: ['leave-requests'] }),
    }),
    cancel: useMutation({
      mutationFn: ({ note }: { note?: string }) =>
        api.post<LeaveRequestPublic>(`/leave-requests/${requestId}/cancel`, note ? { note } : undefined).then(r => r.data),
      onSuccess: () => qc.invalidateQueries({ queryKey: ['leave-requests'] }),
    }),
  }
}
