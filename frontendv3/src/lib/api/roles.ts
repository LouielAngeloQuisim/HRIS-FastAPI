import { keepPreviousData, useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { RolePublic, RoleList, RoleCreate, RoleUpdate } from './types'

export const rolesKey = (page: number, pageSize: number) => ['roles', page, pageSize]

export async function fetchRoles(page: number, pageSize: number): Promise<RoleList> {
  const skip = (page - 1) * pageSize
  const { data } = await api.get<RoleList>('/rbac/roles', { params: { skip, limit: pageSize } })
  return data
}

export function useRoles(page: number, pageSize: number) {
  return useQuery({ queryKey: rolesKey(page, pageSize), queryFn: () => fetchRoles(page, pageSize), placeholderData: keepPreviousData })
}

export function useCreateRole() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (data: RoleCreate) => api.post('/rbac/roles', data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['roles'] }) })
}

export function useUpdateRole() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: ({ id, data }: { id: string; data: RoleUpdate }) => api.patch(`/rbac/roles/${id}`, data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['roles'] }) })
}

export function useDeleteRole() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (id: string) => api.delete(`/rbac/roles/${id}`).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['roles'] }) })
}

export async function fetchRolePermissions(id: string): Promise<string[]> {
  const { data } = await api.get<{ permissions: string[] }>(`/rbac/roles/${id}/permissions`)
  return data.permissions
}

export function useRolePermissions(id: string | null) {
  return useQuery({
    queryKey: ['role', id, 'permissions'],
    queryFn: () => fetchRolePermissions(id!),
    enabled: Boolean(id),
  })
}
