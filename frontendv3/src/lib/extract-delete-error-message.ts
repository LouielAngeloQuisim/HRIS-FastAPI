export function extractDeleteErrorMessage(
  err: unknown,
  resourceType: string
): string {
  try {
    if (err && typeof err === 'object' && 'response' in err) {
      const data = (err as { response?: { data?: unknown } }).response?.data as
        | { error?: { message?: string }; detail?: string | string[] }
        | undefined
      const msg =
        data?.error?.message ??
        (Array.isArray(data?.detail) ? data.detail[0] : data?.detail)
      if (typeof msg === 'string' && msg.length > 0) return msg
    }
  } catch {
    /* fall through to generic */
  }
  return `Failed to delete ${resourceType}`
}
