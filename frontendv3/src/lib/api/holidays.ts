import { keepPreviousData, useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { HolidayConfigList, HolidayConfigPublic, HolidayInstanceList, HolidayConfigCreate, HolidayConfigUpdate } from './types'

export const holidayConfigsKey = (page: number, pageSize: number) =>
  ['holiday-configs', page, pageSize]

export async function fetchHolidayConfigs(
  page: number,
  pageSize: number,
): Promise<HolidayConfigList> {
  const skip = (page - 1) * pageSize
  const { data } = await api.get<HolidayConfigList>('/holidays', {
    params: { skip, limit: pageSize },
  })
  return data
}

export function useHolidayConfigs(page: number, pageSize: number) {
  return useQuery({
    queryKey: holidayConfigsKey(page, pageSize),
    queryFn: () => fetchHolidayConfigs(page, pageSize),
    placeholderData: keepPreviousData,
  })
}

export async function fetchHolidayConfig(id: string): Promise<HolidayConfigPublic> {
  const { data } = await api.get<HolidayConfigPublic>(`/holidays/${id}`)
  return data
}

export const holidayInstancesKey = (leaveYear: number) => ['holiday-instances', leaveYear]

export async function fetchHolidayInstances(leaveYear: number): Promise<HolidayInstanceList> {
  const { data } = await api.get<HolidayInstanceList>('/holidays/instances', {
    params: { leave_year: leaveYear },
  })
  return data
}

export function useHolidayInstances(leaveYear: number) {
  return useQuery({
    queryKey: holidayInstancesKey(leaveYear),
    queryFn: () => fetchHolidayInstances(leaveYear),
    placeholderData: keepPreviousData,
  })
}

export function useHolidayConfig(id: string | undefined) {
  return useQuery({
    queryKey: ['holiday-config', id],
    queryFn: () => api.get<HolidayConfigPublic>(`/holidays/${id}`).then(r => r.data),
    enabled: Boolean(id),
  })
}

export function useCreateHolidayConfig() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: HolidayConfigCreate) =>
      api.post('/holidays', data).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['holiday-configs'] })
    },
  })
}

export function useUpdateHolidayConfig() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: HolidayConfigUpdate }) =>
      api.patch(`/holidays/${id}`, data).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['holiday-configs'] })
    },
  })
}

export function useDeleteHolidayConfig() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.delete(`/holidays/${id}`).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['holiday-configs'] })
    },
  })
}
