import { keepPreviousData, useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { ProjectPublic, ProjectList, ProjectCreate, ProjectUpdate } from './types'

export const projectsKey = (page: number, pageSize: number) => ['projects', page, pageSize]

export async function fetchProjects(page: number, pageSize: number): Promise<ProjectList> {
  const skip = (page - 1) * pageSize
  const { data } = await api.get<ProjectList>('/projects', { params: { skip, limit: pageSize } })
  return data
}

export function useProjects(page: number, pageSize: number) {
  return useQuery({ queryKey: projectsKey(page, pageSize), queryFn: () => fetchProjects(page, pageSize), placeholderData: keepPreviousData })
}

export function useProject(id: string | undefined) {
  return useQuery({ queryKey: ['project', id], queryFn: () => api.get<ProjectPublic>(`/projects/${id}`).then(r => r.data), enabled: Boolean(id) })
}

export function useCreateProject() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (data: ProjectCreate) => api.post('/projects', data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['projects'] }) })
}

export function useUpdateProject() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: ({ id, data }: { id: string; data: ProjectUpdate }) => api.patch(`/projects/${id}`, data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['projects'] }) })
}

export function useDeleteProject() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (id: string) => api.delete(`/projects/${id}`).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['projects'] }) })
}
