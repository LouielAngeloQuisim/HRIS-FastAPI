import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import { SSSResourceForm } from './sss-resource-form'

const { createMock, updateMock } = vi.hoisted(() => ({
  createMock: vi.fn(),
  updateMock: vi.fn(),
}))

vi.mock('@/lib/api/payroll-config', () => ({
  useCreateSSSBracket: () => ({ mutateAsync: createMock, isPending: false }),
  useUpdateSSSBracket: () => ({ mutateAsync: updateMock, isPending: false }),
}))

describe('SSSResourceForm validation', () => {
  it('renders form fields when open', async () => {
    const screen = await render(<SSSResourceForm item={null} open={true} onClose={() => {}} />)
    await expect.element(screen.getByRole('dialog')).toBeInTheDocument()
    await expect.element(screen.getByLabelText(/MSC Min/i)).toBeInTheDocument()
    await expect.element(screen.getByLabelText(/MSC Max/i)).toBeInTheDocument()
  })

  it('blocks submission when required fields are empty', async () => {
    const screen = await render(<SSSResourceForm item={null} open={true} onClose={() => {}} />)

    await userEvent.click(screen.getByRole('button', { name: /Create/i }))
    expect(createMock).not.toHaveBeenCalled()
  })

  it('submits create mutation when form is valid', async () => {
    createMock.mockResolvedValue({})
    const screen = await render(<SSSResourceForm item={null} open={true} onClose={() => {}} />)

    await userEvent.fill(screen.getByLabelText(/MSC Min/i), '1000')
    await userEvent.fill(screen.getByLabelText(/MSC Max/i), '2000')
    await userEvent.fill(screen.getByLabelText(/Employer SS/i), '10')
    await userEvent.fill(screen.getByLabelText(/Employer EC/i), '30')
    await userEvent.fill(screen.getByLabelText(/Employer MPF/i), '0')
    await userEvent.fill(screen.getByLabelText(/Employee SS/i), '5')
    await userEvent.fill(screen.getByLabelText(/Employee MPF/i), '0')
    await userEvent.fill(screen.getByLabelText(/Effective Date/i), '2024-01-01')
    await userEvent.click(screen.getByRole('button', { name: /Create/i }))

    expect(createMock).toHaveBeenCalled()
  })

  it('submits update mutation when editing an existing item', async () => {
    updateMock.mockResolvedValue({})
    const screen = await render(
      <SSSResourceForm
        item={{
          id: '1',
          msc_min: '1000',
          msc_max: '2000',
          employer_ss: '10',
          employer_ec: '30',
          employer_mpf: '0',
          employee_ss: '5',
          employee_mpf: '0',
          effective_date: '2024-01-01',
          is_active: true,
          is_deleted: false,
          created_at: null,
          updated_at: null,
        }}
        open={true}
        onClose={() => {}}
      />
    )

    await userEvent.fill(screen.getByLabelText(/MSC Min/i), '1500')
    await userEvent.click(screen.getByRole('button', { name: /Update/i }))

    expect(updateMock).toHaveBeenCalled()
  })

  it('does not call onClose when mutation throws', async () => {
    createMock.mockRejectedValue(new Error('fail'))
    const onClose = vi.fn()
    const screen = await render(<SSSResourceForm item={null} open={true} onClose={onClose} />)

    await userEvent.fill(screen.getByLabelText(/MSC Min/i), '1000')
    await userEvent.fill(screen.getByLabelText(/MSC Max/i), '2000')
    await userEvent.fill(screen.getByLabelText(/Employer SS/i), '10')
    await userEvent.fill(screen.getByLabelText(/Employer EC/i), '30')
    await userEvent.fill(screen.getByLabelText(/Employer MPF/i), '0')
    await userEvent.fill(screen.getByLabelText(/Employee SS/i), '5')
    await userEvent.fill(screen.getByLabelText(/Employee MPF/i), '0')
    await userEvent.fill(screen.getByLabelText(/Effective Date/i), '2024-01-01')
    await userEvent.click(screen.getByRole('button', { name: /Create/i }))

    expect(onClose).not.toHaveBeenCalled()
  })
})
