import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import { type EmployeeRecordsCreate, type EmployeeRecordsList, type EmployeeRecordsPublic, type EmployeeRecordsUpdate } from './types'

export const employeesKey = (page: number, pageSize: number) => [
  'employees',
  page,
  pageSize,
]

export async function fetchEmployees(
  page: number,
  pageSize: number
): Promise<EmployeeRecordsList> {
  const skip = (page - 1) * pageSize
  const { data } = await api.get<EmployeeRecordsList>('/employees', {
    params: { skip, limit: pageSize },
  })
  return data
}

export function useEmployees(page: number, pageSize: number) {
  return useQuery({
    queryKey: employeesKey(page, pageSize),
    queryFn: () => fetchEmployees(page, pageSize),
    placeholderData: keepPreviousData,
  })
}

export async function fetchEmployee(id: string): Promise<EmployeeRecordsPublic> {
  const { data } = await api.get<EmployeeRecordsPublic>(`/employees/${id}`)
  return data
}

export function useEmployee(id: string | undefined) {
  return useQuery({
    queryKey: ['employee', id],
    queryFn: () => fetchEmployee(id as string),
    enabled: Boolean(id),
  })
}

// -----------------------------------------------------------------------------
// Create / update / soft-archive (QA-05)
// -----------------------------------------------------------------------------

export function useCreateEmployee() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: EmployeeRecordsCreate) =>
      api.post<EmployeeRecordsPublic>('/employees', data).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['employees'] }),
  })
}

export function useUpdateEmployee() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: EmployeeRecordsUpdate }) =>
      api.patch<EmployeeRecordsPublic>(`/employees/${id}`, data).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['employees'] }),
  })
}

export function useDeleteEmployee() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      api.delete(`/employees/${id}`).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['employees'] }),
  })
}
