import { type ReactNode } from 'react'
import { render } from 'vitest-browser-react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

/**
 * Render `ui` wrapped in a fresh QueryClientProvider. Needed by tests that
 * exercise components using `useMutation` / `useQueryClient` (delete dialogs,
 * CRUD flows) because there is no global test setup file providing one.
 */
export async function renderWithClient(ui: ReactNode) {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  const screen = await render(
    <QueryClientProvider client={client}>{ui}</QueryClientProvider>
  )
  return { client, ...screen }
}
