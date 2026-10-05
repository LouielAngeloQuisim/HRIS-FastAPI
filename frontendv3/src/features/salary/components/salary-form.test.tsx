import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import type { EmployeeSalaryPublic } from '@/lib/api/types'
import { toast } from 'sonner'
import { SalaryForm } from './salary-form'

const { createMock, updateMock, deleteMock } = vi.hoisted(() => ({
  createMock: vi.fn(),
  updateMock: vi.fn(),
  deleteMock: vi.fn(),
}))

vi.mock('@/lib/api/payroll', () => ({
  useCreateSalary: () => ({ mutateAsync: createMock, isPending: false }),
  useUpdateSalary: () => ({ mutateAsync: updateMock, isPending: false }),
  useDeleteSalary: () => ({ mutateAsync: deleteMock, isPending: false }),
}))
vi.mock('@/lib/api/employees', () => ({
  useEmployees: () => ({ data: { data: [] }, isPending: false, isError: false }),
  useDeleteEmployee: () => ({ mutateAsync: deleteMock, isPending: false }),
}))

describe('SalaryForm (§PAY-03 add/edit modal)', () => {
  it('renders nothing (no sheet) when closed', async () => {
    const screen = await render(<SalaryForm open={false} onClose={vi.fn()} employeeId='1' />)
    await expect.element(screen.getByRole('dialog')).not.toBeInTheDocument()
  })

  it('opens as a modal sheet and shows core form fields', async () => {
    const screen = await render(<SalaryForm open={true} onClose={vi.fn()} employeeId='1' />)

    const dialog = screen.getByRole('dialog')
    await expect.element(dialog).toBeInTheDocument()
    await expect.element(screen.getByTestId('salary-form-basic-rate-input')).toBeInTheDocument()
    await expect.element(screen.getByTestId('salary-form-effective-date-input')).toBeInTheDocument()
    await expect.element(screen.getByRole('combobox', { name: /Pay Type/i })).toBeInTheDocument()
  })

  it('shows a disabled employee field pre-filled from employeeId', async () => {
    const screen = await render(<SalaryForm open={true} onClose={vi.fn()} employeeId='abc-123' />)
    const employeeField = screen.getByRole('textbox', { name: /Employee/i })
    await expect.element(employeeField).toBeDisabled()
    await expect.element(employeeField).toHaveValue('abc-123')
  })

  it('creates a new salary on submit and calls onClose', async () => {
    const onClose = vi.fn()
    const screen = await render(
      <SalaryForm
        open={true}
        onClose={onClose}
        employeeId='emp-1'
        initialData={{
          employee_id: 'emp-1',
          basic_rate: '',
          currency: 'PHP',
          effective_date: '2026-06-01',
          pay_type: 'monthly',
          overtime_rate: '0.000',
          absent_penalty_rate: '0.000',
          non_taxable_allowance: '0.00',
          thirteenth_month_exempt_portion: '90000.00',
          is_active: true,
          is_deleted: false,
          created_at: null,
          updated_at: null,
        } as EmployeeSalaryPublic}
      />
    )

    await userEvent.type(screen.getByTestId('salary-form-basic-rate-input'), '20000.00')

    await userEvent.click(screen.getByRole('button', { name: /Create/i }))

    await vi.waitFor(() => {
      expect(createMock).toHaveBeenCalledWith({
        employee_id: 'emp-1',
        basic_rate: '20000.00',
        effective_date: '2026-06-01',
        currency: 'PHP',
        pay_type: 'monthly',
        overtime_rate: '0.000',
        absent_penalty_rate: '0.000',
        non_taxable_allowance: '0.00',
        thirteenth_month_exempt_portion: '90000.00',
        is_active: true,
      })
      expect(onClose).toHaveBeenCalled()
    })
  })

  it('pre-fills the form when editing an existing salary', async () => {
    const existing = {
      id: '550e8400-e29b-41d4-a716-446655440000',
      employee_id: 'emp-1',
      basic_rate: '18000.00',
      currency: 'PHP',
      effective_date: '2025-01-01',
      pay_type: 'monthly',
      overtime_rate: '0.000',
      absent_penalty_rate: '0.000',
      non_taxable_allowance: '500.00',
      thirteenth_month_exempt_portion: '90000.00',
      is_active: true,
      is_deleted: false,
      created_at: null,
      updated_at: null,
    } as EmployeeSalaryPublic
    const screen = await render(<SalaryForm open={true} onClose={vi.fn()} employeeId='emp-1' initialData={existing} />)

    await expect.element(screen.getByTestId('salary-form-basic-rate-input')).toHaveValue(18000)
    await expect.element(screen.getByTestId('salary-form-effective-date-input')).toHaveValue('2025-01-01')
    await expect.element(screen.getByTestId('salary-form-non-taxable-input')).toHaveValue(500)
    await expect.element(screen.getByRole('checkbox', { name: /Active/i })).toBeChecked()
  })

  it('updates an existing salary on submit with only changed fields', async () => {
    const onClose = vi.fn()
    const existing = {
      id: '550e8400-e29b-41d4-a716-446655440000',
      employee_id: 'emp-1',
      basic_rate: '18000.00',
      currency: 'PHP',
      effective_date: '2025-01-01',
      pay_type: 'monthly',
      overtime_rate: '0.000',
      absent_penalty_rate: '0.000',
      non_taxable_allowance: '500.00',
      thirteenth_month_exempt_portion: '90000.00',
      is_active: true,
      is_deleted: false,
      created_at: null,
      updated_at: null,
    } as EmployeeSalaryPublic
    const screen = await render(<SalaryForm open={true} onClose={onClose} employeeId='emp-1' initialData={existing} />)

    await userEvent.type(screen.getByTestId('salary-form-basic-rate-input'), '19000.00')

    await userEvent.click(screen.getByRole('button', { name: /Update/i }))

    await vi.waitFor(() => {
      expect(updateMock).toHaveBeenCalledWith({
        salary_id: '550e8400-e29b-41d4-a716-446655440000',
        salary: expect.objectContaining({ basic_rate: '19000.00' }),
      })
      expect(onClose).toHaveBeenCalled()
    })
  })

  it('shows a warning when no changes were made while editing', async () => {
    const onClose = vi.fn()
    const warningSpy = vi.spyOn(toast, 'warning').mockImplementation(() => 'mock-message')
    const existing = {
      id: '550e8400-e29b-41d4-a716-446655440000',
      employee_id: 'emp-1',
      basic_rate: '18000.00',
      currency: 'PHP',
      effective_date: '2025-01-01',
      pay_type: 'monthly',
      overtime_rate: '0.000',
      absent_penalty_rate: '0.000',
      non_taxable_allowance: '500.00',
      thirteenth_month_exempt_portion: '90000.00',
      is_active: true,
      is_deleted: false,
      created_at: null,
      updated_at: null,
    } as EmployeeSalaryPublic
    const screen = await render(<SalaryForm open={true} onClose={onClose} employeeId='emp-1' initialData={existing} />)

    await userEvent.click(screen.getByRole('button', { name: /Update/i }))

    await vi.waitFor(() => {
      expect(warningSpy).toHaveBeenCalledWith('No changes were made.')
      expect(onClose).toHaveBeenCalled()
    })
    warningSpy.mockRestore()
  })

  it('validates required fields on submit', async () => {
    const screen = await render(<SalaryForm open={true} onClose={vi.fn()} employeeId='emp-1' />)

    await userEvent.click(screen.getByRole('button', { name: /Create/i }))

    await vi.waitFor(() => {
      expect(screen.getByText('Basic rate is required')).toBeInTheDocument()
      expect(screen.getByText('Effective date is required')).toBeInTheDocument()
    })
  })
})
