import { beforeEach, describe, expect, it, vi } from 'vitest'
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
  beforeEach(() => vi.clearAllMocks())
  it('renders form fields when open', async () => {
    const screen = await render(
      <SSSResourceForm item={null} open={true} onClose={() => {}} />
    )
    await expect.element(screen.getByRole('dialog')).toBeInTheDocument()
    await expect.element(screen.getByLabelText(/MSC Min/i)).toBeInTheDocument()
    await expect.element(screen.getByLabelText(/MSC Max/i)).toBeInTheDocument()
    await expect
      .element(screen.getByLabelText(/Monthly Compensation From/i))
      .toBeInTheDocument()
    await expect
      .element(screen.getByLabelText(/Monthly Salary Credit/i))
      .toBeInTheDocument()
    await expect
      .element(screen.getByLabelText('Employer SS (₱)', { exact: true }))
      .toBeInTheDocument()
  })

  it('blocks submission when required fields are empty', async () => {
    const screen = await render(
      <SSSResourceForm item={null} open={true} onClose={() => {}} />
    )

    await userEvent.click(screen.getByRole('button', { name: /Create/i }))
    expect(createMock).not.toHaveBeenCalled()
    await expect
      .element(screen.getByText('Select an effective date.'))
      .toBeVisible()
  })

  it('submits create mutation when form is valid', async () => {
    createMock.mockResolvedValue({})
    const screen = await render(
      <SSSResourceForm item={null} open={true} onClose={() => {}} />
    )

    await userEvent.fill(screen.getByLabelText(/MSC Min/i), '1000')
    await userEvent.fill(screen.getByLabelText(/MSC Max/i), '2000')
    await userEvent.fill(
      screen.getByLabelText(/Monthly Compensation From/i),
      '1000'
    )
    await userEvent.fill(
      screen.getByLabelText(/Monthly Compensation Through/i),
      '2000'
    )
    await userEvent.fill(
      screen.getByLabelText(/Monthly Salary Credit/i),
      '2000'
    )
    await userEvent.fill(screen.getByLabelText(/Employer SS/i), '1234.56')
    await userEvent.fill(screen.getByLabelText(/Employer EC/i), '30')
    await userEvent.fill(screen.getByLabelText(/Employer MPF/i), '0')
    await userEvent.fill(screen.getByLabelText(/Employee SS/i), '567.89')
    await userEvent.fill(screen.getByLabelText(/Employee MPF/i), '0')
    await userEvent.fill(screen.getByLabelText(/Effective Date/i), '2024-01-01')
    await userEvent.click(screen.getByRole('button', { name: /Create/i }))

    expect(createMock).toHaveBeenCalledWith(
      expect.objectContaining({
        employer_ss: 1234.56,
        employee_ss: 567.89,
        monthly_salary_credit: 2000,
      })
    )
  })

  it('submits update mutation when editing an existing item', async () => {
    updateMock.mockResolvedValue({})
    const screen = await render(
      <SSSResourceForm
        item={{
          id: '1',
          msc_min: '1000',
          msc_max: '2000',
          compensation_min: '1000',
          compensation_max: '2000',
          monthly_salary_credit: '2000',
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
    const screen = await render(
      <SSSResourceForm item={null} open={true} onClose={onClose} />
    )

    await userEvent.fill(screen.getByLabelText(/MSC Min/i), '1000')
    await userEvent.fill(screen.getByLabelText(/MSC Max/i), '2000')
    await userEvent.fill(
      screen.getByLabelText(/Monthly Compensation From/i),
      '1000'
    )
    await userEvent.fill(
      screen.getByLabelText(/Monthly Compensation Through/i),
      '2000'
    )
    await userEvent.fill(
      screen.getByLabelText(/Monthly Salary Credit/i),
      '2000'
    )
    await userEvent.fill(screen.getByLabelText(/Employer SS/i), '1234.56')
    await userEvent.fill(screen.getByLabelText(/Employer EC/i), '30')
    await userEvent.fill(screen.getByLabelText(/Employer MPF/i), '0')
    await userEvent.fill(screen.getByLabelText(/Employee SS/i), '567.89')
    await userEvent.fill(screen.getByLabelText(/Employee MPF/i), '0')
    await userEvent.fill(screen.getByLabelText(/Effective Date/i), '2024-01-01')
    await userEvent.click(screen.getByRole('button', { name: /Create/i }))

    expect(onClose).not.toHaveBeenCalled()
    await expect.element(screen.getByRole('alert')).toBeInTheDocument()
    await expect
      .element(screen.getByLabelText(/Effective Date/i))
      .toHaveValue('2024-01-01')
  })
})

it('shows a clear numeric error, preserves the value and prevents a rejected submission', async () => {
  createMock.mockClear()
  const screen = await render(
    <SSSResourceForm item={null} open={true} onClose={() => {}} />
  )
  await userEvent.fill(screen.getByTestId('sss-msc_min-input'), '-1')
  await userEvent.fill(
    screen.getByTestId('sss-effective-date-input'),
    '2028-01-01'
  )
  await userEvent.click(screen.getByRole('button', { name: /Create/i }))
  await expect
    .element(screen.getByText('Enter 0 or a positive value.'))
    .toBeVisible()
  await expect.element(screen.getByTestId('sss-msc_min-input')).toHaveValue(-1)
  expect(createMock).not.toHaveBeenCalled()
})
