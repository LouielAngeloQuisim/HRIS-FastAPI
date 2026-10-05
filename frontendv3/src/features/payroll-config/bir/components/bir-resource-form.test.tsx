import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import { BIRResourceForm } from './bir-resource-form'

const { createMock, updateMock } = vi.hoisted(() => ({
  createMock: vi.fn(),
  updateMock: vi.fn(),
}))

vi.mock('@/lib/api/payroll-config', () => ({
  useCreateBIRBracket: () => ({ mutateAsync: createMock, isPending: false }),
  useUpdateBIRBracket: () => ({ mutateAsync: updateMock, isPending: false }),
}))

describe('BIRResourceForm validation', () => {
  beforeEach(() => vi.clearAllMocks())
  it('renders form fields when open', async () => {
    const screen = await render(<BIRResourceForm item={null} open={true} onClose={() => {}} />)
    await expect.element(screen.getByRole('dialog')).toBeInTheDocument()
    await expect.element(screen.getByLabelText(/Period/i)).toBeInTheDocument()
    await expect.element(screen.getByLabelText(/Bracket Min/i)).toBeInTheDocument()
  })

  it('blocks submission when required fields are empty', async () => {
    const screen = await render(<BIRResourceForm item={null} open={true} onClose={() => {}} />)

    await userEvent.click(screen.getByRole('button', { name: /Create/i }))
    expect(createMock).not.toHaveBeenCalled()
  })

  it('submits create mutation when form is valid', async () => {
    createMock.mockResolvedValue({})
    const screen = await render(<BIRResourceForm item={null} open={true} onClose={() => {}} />)

    await userEvent.selectOptions(screen.getByLabelText(/Period/i), 'monthly')
    await userEvent.fill(screen.getByLabelText(/Bracket Min/i), '0')
    await userEvent.fill(screen.getByLabelText(/Bracket Max/i), '20833')
    await userEvent.fill(screen.getByLabelText(/Base Tax/i), '0')
    await userEvent.fill(screen.getByLabelText(/Excess Rate/i), '0')
    await userEvent.fill(screen.getByLabelText(/Effective Date/i), '2025-01-01')
    await userEvent.click(screen.getByRole('button', { name: /Create/i }))

    expect(createMock).toHaveBeenCalled()
  })

  it('submits an open-ended bracket with a supported period and preserves decimal amounts', async () => {
    createMock.mockResolvedValue({})
    const screen = await render(<BIRResourceForm item={null} open={true} onClose={() => {}} />)
    await userEvent.selectOptions(screen.getByLabelText(/Period/i), 'semi_monthly')
    await userEvent.fill(screen.getByLabelText(/Bracket Min/i), '100000.25')
    await userEvent.fill(screen.getByLabelText(/Base Tax/i), '1234.56')
    await userEvent.fill(screen.getByLabelText(/Excess Rate/i), '20')
    await userEvent.fill(screen.getByLabelText(/Effective Date/i), '2026-01-01')
    await userEvent.click(screen.getByRole('button', { name: /Create/i }))
    expect(createMock).toHaveBeenCalledWith(expect.objectContaining({ period: 'semi_monthly', bracket_max: null, bracket_min: 100000.25, base_tax: 1234.56 }))
  })

  it('submits update mutation when editing an existing item', async () => {
    updateMock.mockResolvedValue({})
    const screen = await render(
      <BIRResourceForm
        item={{
          id: '1',
          period: 'monthly',
          bracket_min: '0',
          bracket_max: '20833',
          base_tax: '0',
          excess_rate: '0',
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

    await userEvent.fill(screen.getByLabelText(/Bracket Min/i), '1000')
    await userEvent.click(screen.getByRole('button', { name: /Update/i }))

    expect(updateMock).toHaveBeenCalled()
  })

  it('does not call onClose when mutation throws', async () => {
    createMock.mockRejectedValue(new Error('fail'))
    const onClose = vi.fn()
    const screen = await render(<BIRResourceForm item={null} open={true} onClose={onClose} />)

    await userEvent.selectOptions(screen.getByLabelText(/Period/i), 'monthly')
    await userEvent.fill(screen.getByLabelText(/Bracket Min/i), '0')
    await userEvent.fill(screen.getByLabelText(/Bracket Max/i), '20833')
    await userEvent.fill(screen.getByLabelText(/Base Tax/i), '0')
    await userEvent.fill(screen.getByLabelText(/Excess Rate/i), '0')
    await userEvent.fill(screen.getByLabelText(/Effective Date/i), '2025-01-01')
    await userEvent.click(screen.getByRole('button', { name: /Create/i }))

    expect(onClose).not.toHaveBeenCalled()
    await expect.element(screen.getByRole('alert')).toBeInTheDocument()
    await expect.element(screen.getByLabelText(/Effective Date/i)).toHaveValue('2025-01-01')
  })
})
