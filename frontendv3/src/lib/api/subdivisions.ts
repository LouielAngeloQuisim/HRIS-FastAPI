import { keepPreviousData, useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { SubdivisionPublic, SubdivisionList, SubdivisionCreate, SubdivisionUpdate } from './types'

export const subdivisionsKey = (page: number, pageSize: number) => ['subdivisions', page, pageSize]

export async function fetchSubdivisions(page: number, pageSize: number): Promise<SubdivisionList> {
  const skip = (page - 1) * pageSize
  const { data } = await api.get<SubdivisionList>('/subdivisions', { params: { skip, limit: pageSize } })
  return data
}

export function useSubdivisions(page: number, pageSize: number) {
  return useQuery({ queryKey: subdivisionsKey(page, pageSize), queryFn: () => fetchSubdivisions(page, pageSize), placeholderData: keepPreviousData })
}

export function useSubdivision(id: string | undefined) {
  return useQuery({ queryKey: ['subdivision', id], queryFn: () => api.get<SubdivisionPublic>(`/subdivisions/${id}`).then(r => r.data), enabled: Boolean(id) })
}

export function useCreateSubdivision() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (data: SubdivisionCreate) => api.post('/subdivisions', data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['subdivisions'] }) })
}

export function useUpdateSubdivision() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: ({ id, data }: { id: string; data: SubdivisionUpdate }) => api.patch(`/subdivisions/${id}`, data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['subdivisions'] }) })
}

export function useDeleteSubdivision() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (id: string) => api.delete(`/subdivisions/${id}`).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['subdivisions'] }) })
}
