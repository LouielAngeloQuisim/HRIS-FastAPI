import { keepPreviousData, useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { CategoryPublic, CategoryList, CategoryCreate, CategoryUpdate } from './types'

export const categoriesKey = (page: number, pageSize: number) => ['categories', page, pageSize]

export async function fetchCategories(page: number, pageSize: number): Promise<CategoryList> {
  const skip = (page - 1) * pageSize
  const { data } = await api.get<CategoryList>('/categories', { params: { skip, limit: pageSize } })
  return data
}

export function useCategories(page: number, pageSize: number) {
  return useQuery({ queryKey: categoriesKey(page, pageSize), queryFn: () => fetchCategories(page, pageSize), placeholderData: keepPreviousData })
}

export function useCategory(id: string | undefined) {
  return useQuery({ queryKey: ['category', id], queryFn: () => api.get<CategoryPublic>(`/categories/${id}`).then(r => r.data), enabled: Boolean(id) })
}

export function useCreateCategory() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (data: CategoryCreate) => api.post('/categories', data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['categories'] }) })
}

export function useUpdateCategory() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: ({ id, data }: { id: string; data: CategoryUpdate }) => api.patch(`/categories/${id}`, data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['categories'] }) })
}

export function useDeleteCategory() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (id: string) => api.delete(`/categories/${id}`).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['categories'] }) })
}
