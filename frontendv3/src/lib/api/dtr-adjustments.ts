import { keepPreviousData, useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { DtrAdjustmentList, DtrAdjustmentPublic, DtrAdjustmentCreate } from './types'

export const dtrAdjustmentsKey = (page: number, pageSize: number) =>
  ['dtr-adjustments', page, pageSize]

export async function fetchDtrAdjustments(
  page: number,
  pageSize: number,
): Promise<DtrAdjustmentList> {
  const skip = (page - 1) * pageSize
  const { data } = await api.get<DtrAdjustmentList>('/dtr-adjustments', {
    params: { skip, limit: pageSize },
  })
  return data
}

export function useDtrAdjustments(page: number, pageSize: number) {
  return useQuery({
    queryKey: dtrAdjustmentsKey(page, pageSize),
    queryFn: () => fetchDtrAdjustments(page, pageSize),
    placeholderData: keepPreviousData,
  })
}

export function useDtrAdjustment(id: string | undefined) {
  return useQuery({
    queryKey: ['dtr-adjustment', id],
    queryFn: () => api.get<DtrAdjustmentPublic>(`/dtr-adjustments/${id}`).then(r => r.data),
    enabled: Boolean(id),
  })
}

export function useCreateDtrAdjustment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: DtrAdjustmentCreate) =>
      api.post('/dtr-adjustments', data).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['dtr-adjustments'] }),
  })
}

export function useApproveDtrAdjustment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      api.post(`/dtr-adjustments/${id}/approve`).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['dtr-adjustments'] }),
  })
}

export function useRejectDtrAdjustment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      api.post(`/dtr-adjustments/${id}/reject`).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['dtr-adjustments'] }),
  })
}
