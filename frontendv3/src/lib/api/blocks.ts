import { keepPreviousData, useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { BlocksPublic, BlocksList, BlocksCreate, BlocksUpdate } from './types'

export const blocksKey = (page: number, pageSize: number) => ['blocks', page, pageSize]

export async function fetchBlocks(page: number, pageSize: number): Promise<BlocksList> {
  const skip = (page - 1) * pageSize
  const { data } = await api.get<BlocksList>('/blocks', { params: { skip, limit: pageSize } })
  return data
}

export function useBlocks(page: number, pageSize: number) {
  return useQuery({ queryKey: blocksKey(page, pageSize), queryFn: () => fetchBlocks(page, pageSize), placeholderData: keepPreviousData })
}

export function useBlocksByPhase(phaseId: string | undefined) {
  return useQuery({ queryKey: ['blocks', 'phase', phaseId], queryFn: async () => { const { data } = await api.get<BlocksList>('/blocks', { params: { phase_id: phaseId } }); return data; }, enabled: Boolean(phaseId) })
}

export function useBlock(id: string | undefined) {
  return useQuery({ queryKey: ['block', id], queryFn: () => api.get<BlocksPublic>(`/blocks/${id}`).then(r => r.data), enabled: Boolean(id) })
}

export function useCreateBlock() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (data: BlocksCreate) => api.post('/blocks', data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['blocks'] }) })
}

export function useUpdateBlock() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: ({ id, data }: { id: string; data: BlocksUpdate }) => api.patch(`/blocks/${id}`, data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['blocks'] }) })
}

export function useDeleteBlock() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (id: string) => api.delete(`/blocks/${id}`).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['blocks'] }) })
}
