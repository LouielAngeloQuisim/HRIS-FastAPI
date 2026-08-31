import { keepPreviousData, useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { EmpTaskPublic, EmpTaskList, EmpTaskCreate, EmpTaskUpdate } from './types'

export const empTasksKey = (page: number, pageSize: number) => ['emp-tasks', page, pageSize]

export async function fetchEmpTasks(page: number, pageSize: number): Promise<EmpTaskList> {
  const skip = (page - 1) * pageSize
  const { data } = await api.get<EmpTaskList>('/emp-tasks', { params: { skip, limit: pageSize } })
  return data
}

export function useEmpTasks(page: number, pageSize: number) {
  return useQuery({ queryKey: empTasksKey(page, pageSize), queryFn: () => fetchEmpTasks(page, pageSize), placeholderData: keepPreviousData })
}

export function useEmpTask(id: string | undefined) {
  return useQuery({ queryKey: ['emp-task', id], queryFn: () => api.get<EmpTaskPublic>(`/emp-tasks/${id}`).then(r => r.data), enabled: Boolean(id) })
}

export function useCreateEmpTask() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (data: EmpTaskCreate) => api.post('/emp-tasks', data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['emp-tasks'] }) })
}

export function useUpdateEmpTask() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: ({ id, data }: { id: string; data: EmpTaskUpdate }) => api.patch(`/emp-tasks/${id}`, data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['emp-tasks'] }) })
}

export function useDeleteEmpTask() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (id: string) => api.delete(`/emp-tasks/${id}`).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['emp-tasks'] }) })
}

export function useApproveEmpTask() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (id: string) => api.post(`/emp-tasks/${id}/approve`).then(r => r.data), onSuccess: () => { qc.invalidateQueries({ queryKey: ['emp-tasks'] }); qc.invalidateQueries({ queryKey: ['employee-projects'] }) } })
}

export function useDenyEmpTask() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (id: string) => api.post(`/emp-tasks/${id}/deny`).then(r => r.data), onSuccess: () => { qc.invalidateQueries({ queryKey: ['emp-tasks'] }); qc.invalidateQueries({ queryKey: ['employee-projects'] }) } })
}
