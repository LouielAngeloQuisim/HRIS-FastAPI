// JWT subject is only a cache partition, never an authorization decision.
// A full reload restores the token before the optional auth.user object.
export function relationshipOwner(userId: string | undefined, token: string) {
  if (userId) return userId
  try {
    const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'))) as { sub?: unknown }
    return typeof payload.sub === 'string' && payload.sub ? payload.sub : undefined
  } catch { return undefined }
}

export function relationshipLabel(labels: Record<string, string> | undefined, id: string | null | undefined) {
  return id ? labels?.[id] ?? 'Unavailable record' : '—'
}
