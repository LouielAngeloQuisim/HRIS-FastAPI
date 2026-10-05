import { useQuery } from '@tanstack/react-query'
import { useAuthStore } from '@/stores/auth-store'
import { api } from './client'

// JWT subject is only a cache partition, never an authorization decision.
// A full reload restores the token before the optional auth.user object.
export function relationshipOwner(userId: string | undefined, token: string) {
  if (userId) return userId
  try {
    const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'))) as { sub?: unknown }
    return typeof payload.sub === 'string' && payload.sub ? payload.sub : undefined
  } catch { return undefined }
}

export function useRelationshipLabels(resource: string, ids: Array<string | null | undefined>) {
  const ownerId = useAuthStore(state => relationshipOwner(state.auth.user?.id, state.auth.accessToken))
  const keys = [...new Set(ids.filter((id): id is string => Boolean(id)))].sort()
  return useQuery({
    queryKey: ['relationship-labels', ownerId, resource, keys],
    enabled: Boolean(ownerId) && keys.length > 0,
    staleTime: 30_000,
    retry: false,
    queryFn: async () => {
      const labels: Record<string, string> = {}
      for (let start = 0; start < keys.length; start += 200) {
        const params = new URLSearchParams()
        keys.slice(start, start + 200).forEach(id => params.append('ids', id))
        const response = await api.get<Record<string, string>>(`/${resource}/labels?${params}`)
        Object.assign(labels, response.data)
      }
      return labels
    },
  })
}

export function relationshipLabel(labels: Record<string, string> | undefined, id: string | null | undefined) {
  return id ? labels?.[id] ?? 'Unavailable record' : '—'
}
