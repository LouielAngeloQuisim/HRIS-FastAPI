import { renderWithClient } from '@/test-utils/providers'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { userEvent } from 'vitest/browser'
import PayrollSettingsPage from './index'

const { can, setup, createPolicy, employees, periods } = vi.hoisted(() => ({
  can: vi.fn(() => true),
  setup: vi.fn(),
  createPolicy: vi.fn(),
  employees: vi.fn(),
  periods: vi.fn(),
}))

vi.mock('@/context/permissions-provider', () => ({
  useCan: (..._args: unknown[]) => can(),
}))
vi.mock('@/lib/api/payroll', () => ({
  usePayrollSetup: () => setup(),
  usePayGroupPeriods: (...args: unknown[]) => periods(...args),
}))
vi.mock('@/lib/api/employees', () => ({
  useEmployees: (...args: unknown[]) => employees(...args),
}))

describe('Payroll settings monthly salary policy', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    can.mockReturnValue(true)
    setup.mockReturnValue({
      groups: { data: [], isPending: false, isError: false },
      policies: { data: [], isError: false },
      assignments: { data: [], isError: false },
      createGroup: { mutateAsync: vi.fn(), isPending: false },
      assignGroup: { mutateAsync: vi.fn(), isPending: false },
      createPolicy: { mutateAsync: createPolicy, isPending: false },
      confirmPolicy: { mutateAsync: vi.fn(), isPending: false },
    })
    employees.mockReturnValue({ data: { data: [] } })
    periods.mockReturnValue({ data: [], isError: false })
    createPolicy.mockResolvedValue({ id: 'policy-1' })
  })

  it('submits the explicit monthly salary proration rule in a new policy draft', async () => {
    const screen = await renderWithClient(<PayrollSettingsPage />)
    const defaultPolicy = screen.getByTestId('payroll-policy-json').element() as HTMLTextAreaElement
    expect(JSON.parse(defaultPolicy.value).allowance_tax_treatment).toEqual({
      fixed_recurring: 'taxable',
      proration: 'calendar_days',
      absence: 'not_deducted',
    })
    await userEvent.fill(
      screen.getByTestId('payroll-policy-effective-date'),
      '2026-11-01'
    )
    await userEvent.fill(
      screen.getByTestId('payroll-policy-json'),
      JSON.stringify({
        timezone: 'Asia/Manila',
        monthly_salary_proration: 'scheduled_workday_fraction',
        monthly_holiday_pay_divisor: null,
        premium_rules: {
          night_differential_rate: '0.10',
          rest_day_regular_multiplier: '1.30',
          rest_day_overtime_multiplier: '1.69',
        },
      })
    )
    expect(
      screen.getByText(/night_differential_rate.*at least.*0.10/i)
    ).toBeInTheDocument()
    expect(
      screen.getByText(/rest_day_regular_multiplier.*at least.*1.30/i)
    ).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Save policy draft' }))

    expect(createPolicy).toHaveBeenCalledWith(
      expect.objectContaining({
        effective_from: '2026-11-01',
        policy: expect.objectContaining({
          monthly_salary_proration: 'scheduled_workday_fraction',
          monthly_holiday_pay_divisor: null,
          premium_rules: {
            night_differential_rate: '0.10',
            rest_day_regular_multiplier: '1.30',
            rest_day_overtime_multiplier: '1.69',
          },
        }),
      })
    )
  })

  it('shows payroll policy settings without certificate identity setup', async () => {
    const screen = await renderWithClient(<PayrollSettingsPage />)
    await expect.element(screen.getByTestId('payroll-policy-json')).toBeVisible()
  })
})
