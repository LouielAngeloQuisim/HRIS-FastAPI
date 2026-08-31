import { keepPreviousData, useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { PhasePublic, PhaseList, PhaseCreate, PhaseUpdate } from './types'

export const phasesKey = (page: number, pageSize: number) => ['phases', page, pageSize]

export async function fetchPhases(page: number, pageSize: number): Promise<PhaseList> {
  const skip = (page - 1) * pageSize
  const { data } = await api.get<PhaseList>('/phases', { params: { skip, limit: pageSize } })
  return data
}

export function usePhases(page: number, pageSize: number) {
  return useQuery({ queryKey: phasesKey(page, pageSize), queryFn: () => fetchPhases(page, pageSize), placeholderData: keepPreviousData })
}

export function usePhase(id: string | undefined) {
  return useQuery({ queryKey: ['phase', id], queryFn: () => api.get<PhasePublic>(`/phases/${id}`).then(r => r.data), enabled: Boolean(id) })
}

export function useCreatePhase() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (data: PhaseCreate) => api.post('/phases', data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['phases'] }) })
}

export function useUpdatePhase() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: ({ id, data }: { id: string; data: PhaseUpdate }) => api.patch(`/phases/${id}`, data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['phases'] }) })
}

export function useDeletePhase() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (id: string) => api.delete(`/phases/${id}`).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['phases'] }) })
}
