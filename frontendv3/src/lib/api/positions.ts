import { keepPreviousData, useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { PositionPublic, PositionList, PositionCreate, PositionUpdate } from './types'

export const positionsKey = (page: number, pageSize: number) => ['positions', page, pageSize]

export async function fetchPositions(page: number, pageSize: number): Promise<PositionList> {
  const skip = (page - 1) * pageSize
  const { data } = await api.get<PositionList>('/positions', { params: { skip, limit: pageSize } })
  return data
}

export function usePositions(page: number, pageSize: number) {
  return useQuery({ queryKey: positionsKey(page, pageSize), queryFn: () => fetchPositions(page, pageSize), placeholderData: keepPreviousData })
}

export function usePosition(id: string | undefined) {
  return useQuery({ queryKey: ['position', id], queryFn: () => api.get<PositionPublic>(`/positions/${id}`).then(r => r.data), enabled: Boolean(id) })
}

export function useCreatePosition() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (data: PositionCreate) => api.post('/positions', data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['positions'] }) })
}

export function useUpdatePosition() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: ({ id, data }: { id: string; data: PositionUpdate }) => api.patch(`/positions/${id}`, data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['positions'] }) })
}

export function useDeletePosition() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (id: string) => api.delete(`/positions/${id}`).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['positions'] }) })
}
