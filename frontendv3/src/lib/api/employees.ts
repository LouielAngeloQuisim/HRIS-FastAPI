import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { api } from './client'
import { type EmployeeRecordsList, type EmployeeRecordsPublic } from './types'

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
