import { beforeEach, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import { DailyTimeRecordForm } from './daily-time-record-form'
import type { DailyTimeRecordPublic } from '@/lib/api/types'
const { save } = vi.hoisted(() => ({ save: vi.fn() }))
vi.mock('@/lib/api/daily-time-records', () => ({ useUpdateDailyTimeRecord: () => ({ mutateAsync: save, isPending: false }), useDtrIntervals: () => ({ data: [], isPending: false, isError: false }), useReplaceDtrIntervals: () => ({ mutateAsync: vi.fn(), isPending: false }) }))
const item = { id: 'dtr-1', employee_id: 'emp-1', login_date: '2026-10-02T08:00:00Z', logout_date: '2026-10-02T17:00:00Z' } as DailyTimeRecordPublic
beforeEach(() => { save.mockReset().mockResolvedValue({}) })
it('saves explicit UTC timestamps independent of browser timezone', async () => {
 const close = vi.fn()
 const screen = await render(<DailyTimeRecordForm item={item} open onClose={close} />)
 await userEvent.fill(screen.getByLabelText('Logout Time (UTC)'), '2026-10-02T16:30')
 await userEvent.click(screen.getByRole('button', { name: 'Update', exact: true }))
 expect(save).toHaveBeenCalledWith({ id: 'dtr-1', data: { login_date: '2026-10-02T08:00:00.000Z', logout_date: '2026-10-02T16:30:00.000Z' } })
 expect(close).toHaveBeenCalledOnce()
})
it('prevents reversed punches', async () => {
 const screen = await render(<DailyTimeRecordForm item={item} open onClose={vi.fn()} />)
 await userEvent.fill(screen.getByLabelText('Logout Time (UTC)'), '2026-10-02T07:00')
 await userEvent.click(screen.getByRole('button', { name: 'Update', exact: true }))
 await expect.element(screen.getByText('Logout must be after login')).toBeVisible()
 expect(save).not.toHaveBeenCalled()
})
it('keeps an unsuccessful edit open with its server error', async () => {
 save.mockRejectedValue({ response: { data: { error: { message: 'Record has an approved adjustment' } } } })
 const close = vi.fn()
 const screen = await render(<DailyTimeRecordForm item={item} open onClose={close} />)
 await userEvent.click(screen.getByRole('button', { name: 'Update', exact: true }))
 await expect.element(screen.getByRole('alert')).toHaveTextContent('Record has an approved adjustment')
 expect(close).not.toHaveBeenCalled()
})
