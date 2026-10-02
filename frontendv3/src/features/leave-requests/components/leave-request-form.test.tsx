vi.mock('@/lib/api/employees', () => ({ useEmployees: () => ({ data: { data: [] }, isPending: false }) }))
vi.mock('@/lib/api/leave-policies', () => ({ useLeavePolicies: () => ({ data: { data: [] }, isPending: false }) }))
import { describe, expect, it, vi } from 'vitest'
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
})
