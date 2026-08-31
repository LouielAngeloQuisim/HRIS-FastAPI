import { keepPreviousData, useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { DivisionPublic, DivisionList, DivisionCreate, DivisionUpdate } from './types'

export const divisionsKey = (page: number, pageSize: number) => ['divisions', page, pageSize]

export async function fetchDivisions(page: number, pageSize: number): Promise<DivisionList> {
  const skip = (page - 1) * pageSize
  const { data } = await api.get<DivisionList>('/divisions', { params: { skip, limit: pageSize } })
  return data
}

export function useDivisions(page: number, pageSize: number) {
  return useQuery({ queryKey: divisionsKey(page, pageSize), queryFn: () => fetchDivisions(page, pageSize), placeholderData: keepPreviousData })
}

export function useDivision(id: string | undefined) {
  return useQuery({ queryKey: ['division', id], queryFn: () => api.get<DivisionPublic>(`/divisions/${id}`).then(r => r.data), enabled: Boolean(id) })
}

export function useCreateDivision() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (data: DivisionCreate) => api.post('/divisions', data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['divisions'] }) })
}

export function useUpdateDivision() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: ({ id, data }: { id: string; data: DivisionUpdate }) => api.patch(`/divisions/${id}`, data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['divisions'] }) })
}

export function useDeleteDivision() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (id: string) => api.delete(`/divisions/${id}`).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['divisions'] }) })
}
