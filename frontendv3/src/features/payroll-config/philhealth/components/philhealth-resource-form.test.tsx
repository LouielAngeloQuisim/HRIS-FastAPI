import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import { PhilHealthResourceForm } from './philhealth-resource-form'

const { createMock, updateMock } = vi.hoisted(() => ({
  createMock: vi.fn(),
  updateMock: vi.fn(),
}))

vi.mock('@/lib/api/payroll-config', () => ({
  useCreatePhilHealthBracket: () => ({ mutateAsync: createMock, isPending: false }),
  useUpdatePhilHealthBracket: () => ({ mutateAsync: updateMock, isPending: false }),
}))

describe('PhilHealthResourceForm validation', () => {
  it('renders form fields when open', async () => {
    const screen = await render(<PhilHealthResourceForm item={null} open={true} onClose={() => {}} />)
    await expect.element(screen.getByRole('dialog')).toBeInTheDocument()
    await expect.element(screen.getByLabelText(/Salary Min/i)).toBeInTheDocument()
    await expect.element(screen.getByLabelText(/Total Rate/i)).toBeInTheDocument()
  })

  it('blocks submission when required fields are empty', async () => {
    const screen = await render(<PhilHealthResourceForm item={null} open={true} onClose={() => {}} />)

    await userEvent.click(screen.getByRole('button', { name: /Create/i }))
    expect(createMock).not.toHaveBeenCalled()
    await expect.element(screen.getByText('Select an effective date.')).toBeVisible()
  })

  it('submits create mutation when form is valid', async () => {
    createMock.mockResolvedValue({})
    const screen = await render(<PhilHealthResourceForm item={null} open={true} onClose={() => {}} />)

    await userEvent.fill(screen.getByLabelText(/Salary Min/i), '10000')
    await userEvent.fill(screen.getByLabelText(/Salary Max/i), '100000')
    await userEvent.fill(screen.getByLabelText(/Total Rate/i), '5')
    await userEvent.fill(screen.getByLabelText(/Employer Share/i), '2.5')
    await userEvent.fill(screen.getByLabelText(/Employee Share/i), '2.5')
    await userEvent.fill(screen.getByLabelText(/Effective Date/i), '2025-01-01')
    await userEvent.click(screen.getByRole('button', { name: /Create/i }))

    expect(createMock).toHaveBeenCalled()
  })

  it('submits update mutation when editing an existing item', async () => {
    updateMock.mockResolvedValue({})
    const screen = await render(
      <PhilHealthResourceForm
        item={{
          id: '1',
          salary_min: '10000',
          salary_max: '100000',
          rate: '5',
          employer_share: '2.5',
          employee_share: '2.5',
          effective_date: '2025-01-01',
          is_active: true,
          is_deleted: false,
          created_at: null,
          updated_at: null,
        }}
        open={true}
        onClose={() => {}}
      />
    )

    await userEvent.fill(screen.getByLabelText(/Total Rate/i), '4')
    await userEvent.click(screen.getByRole('button', { name: /Update/i }))

    expect(updateMock).toHaveBeenCalled()
  })

  it('does not call onClose when mutation throws', async () => {
    createMock.mockRejectedValue(new Error('fail'))
    const onClose = vi.fn()
    const screen = await render(<PhilHealthResourceForm item={null} open={true} onClose={onClose} />)

    await userEvent.fill(screen.getByLabelText(/Salary Min/i), '10000')
    await userEvent.fill(screen.getByLabelText(/Salary Max/i), '100000')
    await userEvent.fill(screen.getByLabelText(/Total Rate/i), '5')
    await userEvent.fill(screen.getByLabelText(/Employer Share/i), '2.5')
    await userEvent.fill(screen.getByLabelText(/Employee Share/i), '2.5')
    await userEvent.fill(screen.getByLabelText(/Effective Date/i), '2025-01-01')
    await userEvent.click(screen.getByRole('button', { name: /Create/i }))

    expect(onClose).not.toHaveBeenCalled()
    await expect.element(screen.getByRole('alert')).toBeInTheDocument()
    await expect.element(screen.getByLabelText(/Effective Date/i)).toHaveValue('2025-01-01')
  })
})


it('shows a clear numeric error, preserves the value and prevents a rejected submission', async () => {
  createMock.mockClear()
  const screen = await render(<PhilHealthResourceForm item={null} open={true} onClose={() => {}} />)
  await userEvent.fill(screen.getByTestId('philhealth-salary_min-input'), '-1')
  await userEvent.fill(screen.getByTestId('philhealth-effective-date-input'), '2028-01-01')
  await userEvent.click(screen.getByRole('button', { name: /Create/i }))
  await expect.element(screen.getByText('Enter 0 or a positive value.')).toBeVisible()
  await expect.element(screen.getByTestId('philhealth-salary_min-input')).toHaveValue(-1)
  expect(createMock).not.toHaveBeenCalled()
})
