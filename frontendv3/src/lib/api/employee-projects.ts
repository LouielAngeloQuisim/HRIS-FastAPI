import { keepPreviousData, useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { EmployeeProjectsPublic, EmployeeProjectsList, EmployeeProjectsCreate, EmployeeProjectsUpdate } from './types'

export const employeeProjectsKey = (page: number, pageSize: number) => ['employee-projects', page, pageSize]

export async function fetchEmployeeProjects(page: number, pageSize: number): Promise<EmployeeProjectsList> {
  const skip = (page - 1) * pageSize
  const { data } = await api.get<EmployeeProjectsList>('/employee-projects', { params: { skip, limit: pageSize } })
  return data
}

export function useEmployeeProjects(page: number, pageSize: number) {
  return useQuery({ queryKey: employeeProjectsKey(page, pageSize), queryFn: () => fetchEmployeeProjects(page, pageSize), placeholderData: keepPreviousData })
}

export function useEmployeeProject(id: string | undefined) {
  return useQuery({ queryKey: ['employee-project', id], queryFn: () => api.get<EmployeeProjectsPublic>(`/employee-projects/${id}`).then(r => r.data), enabled: Boolean(id) })
}

export function useCreateEmployeeProject() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (data: EmployeeProjectsCreate) => api.post('/employee-projects', data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['employee-projects'] }) })
}

export function useUpdateEmployeeProject() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: ({ id, data }: { id: string; data: EmployeeProjectsUpdate }) => api.patch(`/employee-projects/${id}`, data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['employee-projects'] }) })
}

export function useDeleteEmployeeProject() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (id: string) => api.delete(`/employee-projects/${id}`).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['employee-projects'] }) })
}

export function useUnassignEmployeeProject() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (id: string) => api.post(`/employee-projects/${id}/unassign`).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['employee-projects'] }) })
}
