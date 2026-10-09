import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import { TaxYearBenefits } from './tax-year-benefits'

const { saveBenefit } = vi.hoisted(() => ({ saveBenefit: vi.fn() }))

vi.mock('@/context/permissions-provider', () => ({ useCan: () => true }))
vi.mock('@/lib/api/payroll', () => ({
  useEmployeeTaxYearBenefits: () => ({
    data: [],
    isPending: false,
    isError: false,
    isSuccess: true,
  }),
  useRecordEmployeeTaxYearBenefit: () => ({
    mutate: saveBenefit,
    isPending: false,
    isError: false,
  }),
}))
vi.mock('@/lib/api/leave-policies', () => ({
  useLeavePolicies: () => ({
    data: {
      data: [
        {
          id: 'vacation-policy-1',
          code: 'VL',
          name: 'Annual Vacation Leave',
          is_active: true,
          is_deleted: false,
          is_paid: true,
          tax_exempt_unused_vacation_leave: true,
        },
        {
          id: 'unpaid-policy',
          code: 'UL',
          name: 'Unpaid Leave',
          is_active: true,
          is_deleted: false,
          is_paid: false,
          tax_exempt_unused_vacation_leave: true,
        },
      ],
    },
    isPending: false,
    isError: false,
    isSuccess: true,
  }),
}))

describe('TaxYearBenefits vacation-leave evidence', () => {
  beforeEach(() => saveBenefit.mockReset())

  it('submits the selected eligible policy without client-asserted balance evidence', async () => {
    const screen = await render(
      <TaxYearBenefits employeeId='employee-1' taxYear={2026} />
    )

    await userEvent.fill(screen.getByLabelText('Paid date'), '2026-07-01')
    await userEvent.selectOptions(screen.getByLabelText('Benefit type'), 'de_minimis')
    await userEvent.selectOptions(
      screen.getByLabelText('De minimis category'),
      'monetized_unused_vacation_leave'
    )
    await userEvent.selectOptions(
      screen.getByLabelText('Eligible paid vacation leave policy'),
      'vacation-policy-1'
    )
    await userEvent.type(screen.getByLabelText('Qualifying eligible days'), '4')
    await userEvent.type(screen.getByLabelText('Gross amount paid'), '4000')
    await userEvent.type(screen.getByLabelText('Payment source reference'), 'Voucher VL-001')
    await userEvent.click(screen.getByRole('button', { name: 'Record paid benefit' }))

    await vi.waitFor(() => {
      expect(saveBenefit).toHaveBeenCalledWith(
        expect.objectContaining({
          benefit_type: 'de_minimis',
          de_minimis_category: 'monetized_unused_vacation_leave',
          vacation_leave_policy_id: 'vacation-policy-1',
          qualifying_days: 4,
          gross_amount: '4000',
          source_reference: 'Voucher VL-001',
          eligibility_evidence: [],
        }),
        expect.any(Object)
      )
    })
    const [submittedBenefit] = saveBenefit.mock.calls[0] as [Record<string, unknown>]
    expect(submittedBenefit).not.toHaveProperty(
      'unused_vacation_leave_balance_verified'
    )
  })
})
