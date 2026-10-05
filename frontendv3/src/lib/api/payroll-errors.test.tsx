import { expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { api } from './client'
import { useGeneratePayroll } from './payroll'

it('leaves a failed generation to the page without the default duplicate error notification', async () => {
  const duplicateNotification = vi.fn()
  const pageError = vi.fn()
  vi.spyOn(api, 'post').mockRejectedValueOnce(new Error('Response lost'))
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false, onError: duplicateNotification } } })
  function Generate() {
    const generate = useGeneratePayroll()
    return <button onClick={() => generate.mutateAsync({ request_id: 'qa-request', cutoff_type: 'monthly', date_from: '2026-10-01', date_to: '2026-10-31' }).catch(pageError)}>Generate</button>
  }
  const screen = await render(<QueryClientProvider client={client}><Generate /></QueryClientProvider>)
  await userEvent.click(screen.getByRole('button', { name: 'Generate' }))
  await vi.waitFor(() => expect(pageError).toHaveBeenCalledTimes(1))
  expect(duplicateNotification).not.toHaveBeenCalled()
  vi.restoreAllMocks()
})
