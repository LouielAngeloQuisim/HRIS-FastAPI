import { keepPreviousData, useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { LotsPublic, LotsList, LotsCreate, LotsUpdate } from './types'

export const lotsKey = (page: number, pageSize: number) => ['lots', page, pageSize]

export async function fetchLots(page: number, pageSize: number): Promise<LotsList> {
  const skip = (page - 1) * pageSize
  const { data } = await api.get<LotsList>('/lots', { params: { skip, limit: pageSize } })
  return data
}

export function useLots(page: number, pageSize: number) {
  return useQuery({ queryKey: lotsKey(page, pageSize), queryFn: () => fetchLots(page, pageSize), placeholderData: keepPreviousData })
}

export function useLotsByBlock(blockId: string | undefined) {
  return useQuery({ queryKey: ['lots', 'block', blockId], queryFn: async () => { const { data } = await api.get<LotsList>('/lots', { params: { blocks_id: blockId } }); return data; }, enabled: Boolean(blockId) })
}

export function useLot(id: string | undefined) {
  return useQuery({ queryKey: ['lot', id], queryFn: () => api.get<LotsPublic>(`/lots/${id}`).then(r => r.data), enabled: Boolean(id) })
}

export function useCreateLot() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (data: LotsCreate) => api.post('/lots', data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['lots'] }) })
}

export function useUpdateLot() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: ({ id, data }: { id: string; data: LotsUpdate }) => api.patch(`/lots/${id}`, data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['lots'] }) })
}

export function useDeleteLot() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (id: string) => api.delete(`/lots/${id}`).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['lots'] }) })
}
