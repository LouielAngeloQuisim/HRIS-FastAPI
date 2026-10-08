import { renderWithClient } from '@/test-utils/providers'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { userEvent } from 'vitest/browser'
import PayrollSettingsPage from './index'

const { can, setup, createPolicy, employees, periods, profile, saveProfile, verifyProfile } = vi.hoisted(() => ({
  can: vi.fn(() => true),
  setup: vi.fn(),
  createPolicy: vi.fn(),
  employees: vi.fn(),
  periods: vi.fn(),
  profile: vi.fn(),
  saveProfile: vi.fn(),
  verifyProfile: vi.fn(),
}))

vi.mock('@/context/permissions-provider', () => ({
  useCan: (..._args: unknown[]) => can(),
}))
vi.mock('@/lib/api/payroll', () => ({
  usePayrollSetup: () => setup(),
  usePayGroupPeriods: (...args: unknown[]) => periods(...args),
  usePayrollEmployerProfile: () => profile(),
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
    profile.mockReturnValue({
      profile: { data: null, isError: false },
      save: { mutateAsync: saveProfile, isPending: false },
      verify: { mutateAsync: verifyProfile, isPending: false },
    })
    createPolicy.mockResolvedValue({ id: 'policy-1' })
    saveProfile.mockResolvedValue({ id: 'default' })
    verifyProfile.mockResolvedValue({ id: 'default', is_verified: true })
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

  it('saves the employer identity required by payroll certificates', async () => {
    const screen = await renderWithClient(<PayrollSettingsPage />)
    await userEvent.fill(screen.getByRole('textbox', { name: 'Employer TIN' }), '123-456-789-000')
    await userEvent.fill(screen.getByRole('textbox', { name: 'Registered employer name' }), 'Example Company Inc.')
    await userEvent.fill(screen.getByRole('textbox', { name: 'Registered address' }), '1 Sample Street, Manila')
    await userEvent.fill(screen.getByRole('textbox', { name: 'Postal code' }), '1000')
    await userEvent.fill(screen.getByRole('textbox', { name: 'RDO code' }), '039')
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Employer type' }), 'main')
    await userEvent.fill(screen.getByRole('textbox', { name: 'Authorized signatory name' }), 'Payroll Officer')
    await userEvent.fill(screen.getByRole('textbox', { name: 'Authorized signatory title' }), 'HR Manager')
    await userEvent.fill(screen.getByRole('textbox', { name: 'Source note for employer details' }), 'Company registration certificate reviewed')
    await userEvent.click(screen.getByRole('button', { name: 'Save employer details' }))

    expect(saveProfile).toHaveBeenCalledWith({
      tin_number: '123-456-789-000',
      registered_name: 'Example Company Inc.',
      registered_address: '1 Sample Street, Manila',
      postal_code: '1000',
      rdo_code: '039',
      employer_type: 'main',
      signatory_name: 'Payroll Officer',
      signatory_title: 'HR Manager',
      source_reference: 'Company registration certificate reviewed',
    })
  })

  it('requires an authorized approver action to verify saved employer details', async () => {
    profile.mockReturnValue({
      profile: {
        data: {
          id: 'default',
          tin_number: '123-456-789-000',
          registered_name: 'Example Company Inc.',
          registered_address: '1 Sample Street, Manila',
          postal_code: '1000',
          rdo_code: '039',
          employer_type: 'main',
          signatory_name: 'Payroll Officer',
          signatory_title: 'HR Manager',
          source_reference: 'Company registration certificate reviewed',
          is_verified: false,
          verified_by: null,
          verified_at: null,
          updated_by: null,
          updated_at: null,
        },
        isError: false,
      },
      save: { mutateAsync: saveProfile, isPending: false },
      verify: { mutateAsync: verifyProfile, isPending: false },
    })
    const screen = await renderWithClient(<PayrollSettingsPage />)
    await userEvent.click(screen.getByRole('button', { name: 'Verify employer details' }))
    expect(verifyProfile).toHaveBeenCalledOnce()
  })
})
