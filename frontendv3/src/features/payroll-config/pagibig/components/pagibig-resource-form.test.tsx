import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import { PagIBIGResourceForm } from './pagibig-resource-form'

const { createMock, updateMock } = vi.hoisted(() => ({
  createMock: vi.fn(),
  updateMock: vi.fn(),
}))

vi.mock('@/lib/api/payroll-config', () => ({
  useCreatePagIBIGBracket: () => ({ mutateAsync: createMock, isPending: false }),
  useUpdatePagIBIGBracket: () => ({ mutateAsync: updateMock, isPending: false }),
}))

describe('PagIBIGResourceForm validation', () => {
  it('renders form fields when open', async () => {
    const screen = await render(<PagIBIGResourceForm item={null} open={true} onClose={() => {}} />)
    await expect.element(screen.getByRole('dialog')).toBeInTheDocument()
    await expect.element(screen.getByLabelText(/Salary Min/i)).toBeInTheDocument()
    await expect.element(screen.getByLabelText(/Employee Rate/i)).toBeInTheDocument()
  })

  it('blocks submission when required fields are empty', async () => {
    const screen = await render(<PagIBIGResourceForm item={null} open={true} onClose={() => {}} />)

    await userEvent.click(screen.getByRole('button', { name: /Create/i }))
    expect(createMock).not.toHaveBeenCalled()
  })

  it('submits create mutation when form is valid', async () => {
    createMock.mockResolvedValue({})
    const screen = await render(<PagIBIGResourceForm item={null} open={true} onClose={() => {}} />)

    await userEvent.fill(screen.getByLabelText(/Salary Min/i), '0')
    await userEvent.fill(screen.getByLabelText(/Salary Max/i), '10000')
    await userEvent.fill(screen.getByLabelText(/Employee Rate/i), '2')
    await userEvent.fill(screen.getByLabelText(/Employer Rate/i), '2')
    await userEvent.fill(screen.getByLabelText(/Effective Date/i), '2025-01-01')
    await userEvent.click(screen.getByRole('button', { name: /Create/i }))

    expect(createMock).toHaveBeenCalled()
  })

  it('submits update mutation when editing an existing item', async () => {
    updateMock.mockResolvedValue({})
    const screen = await render(
      <PagIBIGResourceForm
        item={{
          id: '1',
          salary_min: '0',
          salary_max: '10000',
          employee_rate: '2',
          employer_rate: '2',
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

    await userEvent.fill(screen.getByLabelText(/Employee Rate/i), '3')
    await userEvent.click(screen.getByRole('button', { name: /Update/i }))

    expect(updateMock).toHaveBeenCalled()
  })

  it('does not call onClose when mutation throws', async () => {
    createMock.mockRejectedValue(new Error('fail'))
    const onClose = vi.fn()
    const screen = await render(<PagIBIGResourceForm item={null} open={true} onClose={onClose} />)

    await userEvent.fill(screen.getByLabelText(/Salary Min/i), '0')
    await userEvent.fill(screen.getByLabelText(/Salary Max/i), '10000')
    await userEvent.fill(screen.getByLabelText(/Employee Rate/i), '2')
    await userEvent.fill(screen.getByLabelText(/Employer Rate/i), '2')
    await userEvent.fill(screen.getByLabelText(/Effective Date/i), '2025-01-01')
    await userEvent.click(screen.getByRole('button', { name: /Create/i }))

    expect(onClose).not.toHaveBeenCalled()
    await expect.element(screen.getByRole('alert')).toBeInTheDocument()
    await expect.element(screen.getByLabelText(/Effective Date/i)).toHaveValue('2025-01-01')
  })
})
