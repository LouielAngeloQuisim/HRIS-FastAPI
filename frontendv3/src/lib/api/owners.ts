import { keepPreviousData, useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { OwnerPublic, OwnerList, OwnerCreate, OwnerUpdate } from './types'

export const ownersKey = (page: number, pageSize: number) => ['owners', page, pageSize]

export async function fetchOwners(page: number, pageSize: number): Promise<OwnerList> {
  const skip = (page - 1) * pageSize
  const { data } = await api.get<OwnerList>('/owners', { params: { skip, limit: pageSize } })
  return data
}

export function useOwners(page: number, pageSize: number) {
  return useQuery({ queryKey: ownersKey(page, pageSize), queryFn: () => fetchOwners(page, pageSize), placeholderData: keepPreviousData })
}

export function useOwner(id: string | undefined) {
  return useQuery({ queryKey: ['owner', id], queryFn: () => api.get<OwnerPublic>(`/owners/${id}`).then(r => r.data), enabled: Boolean(id) })
}

export function useCreateOwner() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (data: OwnerCreate) => api.post('/owners', data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['owners'] }) })
}

export function useUpdateOwner() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: ({ id, data }: { id: string; data: OwnerUpdate }) => api.patch(`/owners/${id}`, data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['owners'] }) })
}

export function useDeleteOwner() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (id: string) => api.delete(`/owners/${id}`).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['owners'] }) })
}
