import { keepPreviousData, useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { ShiftsPublic, ShiftsList, ShiftsCreate, ShiftsUpdate } from './types'

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
