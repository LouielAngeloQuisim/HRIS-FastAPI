import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import { DtrAdjustmentForm } from './dtr-adjustment-form'

const { submitMock } = vi.hoisted(() => ({
  submitMock: vi.fn(),
}))

vi.mock('@/lib/api/dtr-adjustments', () => ({
  useCreateDtrAdjustment: () => ({ mutateAsync: submitMock, isPending: false }),
}))

describe('DtrAdjustmentForm', () => {
  it('renders form fields when open', async () => {
    const screen = await render(<DtrAdjustmentForm open={true} onClose={vi.fn()} />)
    await expect.element(screen.getByLabelText(/Daily Time Record ID/i)).toBeInTheDocument()
    await expect.element(screen.getByLabelText(/Adjusted Login Date/i)).toBeInTheDocument()
    await expect.element(screen.getByLabelText(/Adjusted Logout Date/i)).toBeInTheDocument()
  })

  it('calls onClose when cancelled', async () => {
    const onClose = vi.fn()
    const screen = await render(<DtrAdjustmentForm open={true} onClose={onClose} />)
    await userEvent.click(screen.getByRole('button', { name: /Cancel/i }))
    await vi.waitFor(() => expect(onClose).toHaveBeenCalled())
  })
})
