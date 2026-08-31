import { keepPreviousData, useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { DepartmentPublic, DepartmentList, DepartmentCreate, DepartmentUpdate } from './types'

export const departmentsKey = (page: number, pageSize: number) => ['departments', page, pageSize]

export async function fetchDepartments(page: number, pageSize: number): Promise<DepartmentList> {
  const skip = (page - 1) * pageSize
  const { data } = await api.get<DepartmentList>('/departments', { params: { skip, limit: pageSize } })
  return data
}

export function useDepartments(page: number, pageSize: number) {
  return useQuery({ queryKey: departmentsKey(page, pageSize), queryFn: () => fetchDepartments(page, pageSize), placeholderData: keepPreviousData })
}

export function useDepartment(id: string | undefined) {
  return useQuery({ queryKey: ['department', id], queryFn: () => api.get<DepartmentPublic>(`/departments/${id}`).then(r => r.data), enabled: Boolean(id) })
}

export function useCreateDepartment() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (data: DepartmentCreate) => api.post('/departments', data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['departments'] }) })
}

export function useUpdateDepartment() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: ({ id, data }: { id: string; data: DepartmentUpdate }) => api.patch(`/departments/${id}`, data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['departments'] }) })
}

export function useDeleteDepartment() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (id: string) => api.delete(`/departments/${id}`).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['departments'] }) })
}
