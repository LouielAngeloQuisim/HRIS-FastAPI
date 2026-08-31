import { keepPreviousData, useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { ProjectTypePublic, ProjectTypeList, ProjectTypeCreate, ProjectTypeUpdate } from './types'

export const projectTypesKey = (page: number, pageSize: number) => ['project-types', page, pageSize]

export async function fetchProjectTypes(page: number, pageSize: number): Promise<ProjectTypeList> {
  const skip = (page - 1) * pageSize
  const { data } = await api.get<ProjectTypeList>('/project-types', { params: { skip, limit: pageSize } })
  return data
}

export function useProjectTypes(page: number, pageSize: number) {
  return useQuery({ queryKey: projectTypesKey(page, pageSize), queryFn: () => fetchProjectTypes(page, pageSize), placeholderData: keepPreviousData })
}

export function useProjectType(id: string | undefined) {
  return useQuery({ queryKey: ['project-type', id], queryFn: () => api.get<ProjectTypePublic>(`/project-types/${id}`).then(r => r.data), enabled: Boolean(id) })
}

export function useCreateProjectType() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (data: ProjectTypeCreate) => api.post('/project-types', data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['project-types'] }) })
}

export function useUpdateProjectType() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: ({ id, data }: { id: string; data: ProjectTypeUpdate }) => api.patch(`/project-types/${id}`, data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['project-types'] }) })
}

export function useDeleteProjectType() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (id: string) => api.delete(`/project-types/${id}`).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['project-types'] }) })
}
