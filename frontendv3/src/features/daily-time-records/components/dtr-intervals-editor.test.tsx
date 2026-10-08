import { describe, expect, it, vi } from 'vitest'
import { userEvent } from 'vitest/browser'
import { renderWithClient as render } from '@/test-utils/providers'
import type { DailyTimeRecordPublic } from '@/lib/api/types'
import { DtrIntervalsEditor } from './dtr-intervals-editor'

const interval = {
  start_at: '2026-10-08T00:00:00Z',
  end_at: '2026-10-08T09:00:00Z',
  revision: 1,
}

const { useDtrIntervalsMock } = vi.hoisted(() => ({
  useDtrIntervalsMock: vi.fn(),
}))

vi.mock('@/lib/api/daily-time-records', () => ({
  useDtrIntervals: (...args: unknown[]) => useDtrIntervalsMock(...args),
  useReplaceDtrIntervals: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

describe('DtrIntervalsEditor', () => {
  it('shows persisted intervals in Manila time and lets the user edit them', async () => {
    useDtrIntervalsMock.mockReturnValue({ data: [interval], isPending: false, isError: false })

    const record = {
      id: 'dtr-1',
      login_date: '2026-10-08T00:00:00Z',
      logout_date: '2026-10-08T09:00:00Z',
    } as DailyTimeRecordPublic
    const screen = await render(<DtrIntervalsEditor record={record} onClose={vi.fn()} />)
    const start = screen.getByLabelText('Start')
    const end = screen.getByLabelText('End')

    await expect.element(start).toHaveValue('2026-10-08T08:00')
    await expect.element(end).toHaveValue('2026-10-08T17:00')
    await userEvent.fill(start, '2026-10-08T09:00')
    await expect.element(start).toHaveValue('2026-10-08T09:00')
  })
})
