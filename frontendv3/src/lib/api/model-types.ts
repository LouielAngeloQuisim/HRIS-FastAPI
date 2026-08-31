import { keepPreviousData, useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { ModelTypesPublic, ModelTypesList, ModelTypesCreate, ModelTypesUpdate } from './types'

export const modelTypesKey = (page: number, pageSize: number) => ['model-types', page, pageSize]

export async function fetchModelTypes(page: number, pageSize: number): Promise<ModelTypesList> {
  const skip = (page - 1) * pageSize
  const { data } = await api.get<ModelTypesList>('/model-types', { params: { skip, limit: pageSize } })
  return data
}

export function useModelTypes(page: number, pageSize: number) {
  return useQuery({ queryKey: modelTypesKey(page, pageSize), queryFn: () => fetchModelTypes(page, pageSize), placeholderData: keepPreviousData })
}

export function useModelType(id: string | undefined) {
  return useQuery({ queryKey: ['model-type', id], queryFn: () => api.get<ModelTypesPublic>(`/model-types/${id}`).then(r => r.data), enabled: Boolean(id) })
}

export function useCreateModelType() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (data: ModelTypesCreate) => api.post('/model-types', data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['model-types'] }) })
}

export function useUpdateModelType() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: ({ id, data }: { id: string; data: ModelTypesUpdate }) => api.patch(`/model-types/${id}`, data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['model-types'] }) })
}

export function useDeleteModelType() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (id: string) => api.delete(`/model-types/${id}`).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['model-types'] }) })
}
