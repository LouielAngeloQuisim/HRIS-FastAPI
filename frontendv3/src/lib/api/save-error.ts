export function saveErrorMessage(error: unknown): string {
  const response = (error as { response?: { data?: { error?: { message?: string }; detail?: unknown } } })?.response?.data
  if (typeof response?.error?.message === 'string') return response.error.message
  if (typeof response?.detail === 'string') return response.detail
  return 'Could not save this record. Check the fields and try again.'
}
