import { keepPreviousData, useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { ShiftsPublic, ShiftsList, ShiftsCreate, ShiftsUpdate } from './types'

export interface EmployeeShiftAssignment {
  id: string
  employee_id: string
  shift_id: string
  effective_from: string
  effective_to: string | null
  assigned_by: string | null
}

export const shiftsKey = (page: number, pageSize: number) => ['shifts', page, pageSize]

export async function fetchShifts(page: number, pageSize: number): Promise<ShiftsList> {
  const skip = (page - 1) * pageSize
  const { data } = await api.get<ShiftsList>('/shifts', { params: { skip, limit: pageSize } })
  return data
}

export function useShifts(page: number, pageSize: number) {
  return useQuery({ queryKey: shiftsKey(page, pageSize), queryFn: () => fetchShifts(page, pageSize), placeholderData: keepPreviousData })
}

export function useShift(id: string | undefined) {
  return useQuery({ queryKey: ['shift', id], queryFn: () => api.get<ShiftsPublic>(`/shifts/${id}`).then(r => r.data), enabled: Boolean(id) })
}

export function useCreateShift() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (data: ShiftsCreate) => api.post('/shifts', data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['shifts'] }) })
}

export function useUpdateShift() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: ({ id, data }: { id: string; data: ShiftsUpdate }) => api.patch(`/shifts/${id}`, data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['shifts'] }) })
}

export function useDeleteShift() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (id: string) => api.delete(`/shifts/${id}`).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['shifts'] }) })
}

export function useEmployeeShiftAssignments() {
  return useQuery({
    queryKey: ['employee-shift-assignments'],
    queryFn: () => api.get<{ data: EmployeeShiftAssignment[]; count: number }>('/employee-shift-assignments', { params: { limit: 500 } }).then(r => r.data),
  })
}

export function useCreateEmployeeShiftAssignment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: { employee_id: string; shift_id: string; effective_from: string; effective_to?: string | null }) => api.post<EmployeeShiftAssignment>('/employee-shift-assignments', payload).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['employee-shift-assignments'] }),
  })
}

export function useCloseEmployeeShiftAssignment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, effective_to }: { id: string; effective_to: string }) => api.patch<EmployeeShiftAssignment>(`/employee-shift-assignments/${id}`, { effective_to }).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['employee-shift-assignments'] }),
  })
}
