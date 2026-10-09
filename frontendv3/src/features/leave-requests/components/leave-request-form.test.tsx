vi.mock('@/lib/api/employees', () => ({ useEmployees: () => ({ data: { data: [] }, isPending: false }) }))
vi.mock('@/lib/api/leave-policies', () => ({ useLeavePolicies: () => ({ data: { data: [] }, isPending: false }) }))
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import { LeaveRequestForm } from './leave-request-form'

const { submitMock } = vi.hoisted(() => ({
  submitMock: vi.fn(),
}))

vi.mock('@/lib/api/leave-requests', () => ({
  useSubmitLeaveRequest: () => ({ mutateAsync: submitMock, isPending: false }),
}))

describe('LeaveRequestForm', () => {
  beforeEach(() => {
    submitMock.mockReset()
  })

  it('renders form fields when open', async () => {
    const screen = await render(<LeaveRequestForm open={true} onClose={vi.fn()} />)
    await expect.element(screen.getByLabelText(/Employee/i)).toBeInTheDocument()
    await expect.element(screen.getByLabelText(/Policy/i)).toBeInTheDocument()
    await expect.element(screen.getByLabelText(/Date Start/i)).toBeInTheDocument()
    await expect.element(screen.getByLabelText(/Date End/i)).toBeInTheDocument()
  })

  it('calls onClose when cancelled', async () => {
    const onClose = vi.fn()
    const screen = await render(<LeaveRequestForm open={true} onClose={onClose} />)
    await userEvent.click(screen.getByRole('button', { name: /Cancel/i }))
    await vi.waitFor(() => expect(onClose).toHaveBeenCalled())
  })

  it('rejects partial-hour leave spanning multiple dates', async () => {
    const screen = await render(<LeaveRequestForm open={true} onClose={vi.fn()} />)
    await userEvent.fill(screen.getByLabelText(/Date Start/i), '2026-09-07')
    await userEvent.fill(screen.getByLabelText(/Date End/i), '2026-09-08')
    await userEvent.fill(screen.getByLabelText(/Requested Hours/i), '3')
    await userEvent.click(screen.getByRole('button', { name: /Submit Request/i }))

    await expect.element(screen.getByText(/Hourly leave requests must cover a single date/i)).toBeInTheDocument()
    expect(submitMock).not.toHaveBeenCalled()
  })
})
