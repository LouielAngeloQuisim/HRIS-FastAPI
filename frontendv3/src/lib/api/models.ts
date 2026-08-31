import { keepPreviousData, useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { ModelPublic, ModelList, ModelCreate, ModelUpdate } from './types'

export const modelsKey = (page: number, pageSize: number) => ['models', page, pageSize]

export async function fetchModels(page: number, pageSize: number): Promise<ModelList> {
  const skip = (page - 1) * pageSize
  const { data } = await api.get<ModelList>('/models', { params: { skip, limit: pageSize } })
  return data
}

export function useModels(page: number, pageSize: number) {
  return useQuery({ queryKey: modelsKey(page, pageSize), queryFn: () => fetchModels(page, pageSize), placeholderData: keepPreviousData })
}

export function useModel(id: string | undefined) {
  return useQuery({ queryKey: ['model', id], queryFn: () => api.get<ModelPublic>(`/models/${id}`).then(r => r.data), enabled: Boolean(id) })
}

export function useCreateModel() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (data: ModelCreate) => api.post('/models', data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['models'] }) })
}

export function useUpdateModel() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: ({ id, data }: { id: string; data: ModelUpdate }) => api.patch(`/models/${id}`, data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['models'] }) })
}

export function useDeleteModel() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (id: string) => api.delete(`/models/${id}`).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['models'] }) })
}
