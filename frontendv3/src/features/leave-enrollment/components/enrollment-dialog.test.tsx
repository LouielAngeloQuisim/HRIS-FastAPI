import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import { EnrollmentDialog } from './enrollment-dialog'

const onConfirm = vi.fn()

vi.mock('@/lib/api/leave-policies', () => ({
  useEnrollEmployee: () => ({ mutateAsync: onConfirm, isPending: false }),
  useLeavePolicies: () => ({ data: { data: [] } }),
}))
vi.mock('@/lib/api/employees', () => ({
  useEmployees: () => ({
    data: {
      data: [
        {
          id: 'emp-1',
          employee_code: 'EMP-001',
          first_name: 'Jane',
          middle_name: 'D',
          last_name: 'Doe',
          extension: null,
          birthdate: '1990-01-01',
          birth_place: null,
          gender: null,
          civil_status: null,
          email: null,
          zip_code: null,
          area: null,
          present_barangay: null,
          present_city: null,
          same_address: null,
          permanent_barangay: null,
          permanent_city: null,
          date_hired: null,
          employee_status: 'Active',
          employment_type: null,
          contract_expiry_date: null,
          date_separated: null,
          probationary_date: null,
          regularization_date: null,
          telephone: null,
          cellphone: null,
          profile_photo_path: null,
          position_id: null,
          division_id: null,
          department_id: null,
          user_id: null,
          is_deleted: false,
          created_at: null,
          updated_at: null,
        },
      ],
    },
  }),
}))

describe('EnrollmentDialog (§QA-04 enroll modal)', () => {
  it('renders employee, policy, and leave year selects', async () => {
    const policies = [
      {
        id: '550e8400-e29b-41d4-a716-446655440000',
        code: 'SL',
        name: 'Sick Leave',
        description: null,
        calendar_color: null,
        cadence: null,
        annual_entitlement_days: null,
        prorate_on_hire: null,
        carry_over_enabled: null,
        carry_over_max_days: null,
        carry_over_expires_on: null,
        is_paid: null,
        eligible_departments: null,
        gender_scope: null,
        marital_status_scope: null,
        is_active: true,
        is_system: false,
        is_deleted: false,
        created_at: null,
        updated_at: null,
      },
    ]
    const screen = await render(
      <EnrollmentDialog
        open={true}
        onOpenChange={vi.fn()}
        employeeId='emp-1'
        leaveYear={2026}
        availablePolicies={policies}
        onClose={vi.fn()}
      />
    )
    await expect.element(screen.getByRole('dialog')).toBeInTheDocument()
    await expect.element(screen.getByRole('combobox', { name: /Employee/i })).toBeInTheDocument()
    await expect.element(screen.getByRole('combobox', { name: /Leave Policy/i })).toBeInTheDocument()
    await expect.element(screen.getByRole('combobox', { name: /Leave Year/i })).toBeInTheDocument()
  })

  it('enrolls the selected employee in the selected policy on submit', async () => {
    const policies = [
      {
        id: '550e8400-e29b-41d4-a716-446655440000',
        code: 'SL',
        name: 'Sick Leave',
        description: null,
        calendar_color: null,
        cadence: null,
        annual_entitlement_days: null,
        prorate_on_hire: null,
        carry_over_enabled: null,
        carry_over_max_days: null,
        carry_over_expires_on: null,
        is_paid: null,
        eligible_departments: null,
        gender_scope: null,
        marital_status_scope: null,
        is_active: true,
        is_system: false,
        is_deleted: false,
        created_at: null,
        updated_at: null,
      },
    ]
    const screen = await render(
      <EnrollmentDialog
        open={true}
        onOpenChange={vi.fn()}
        employeeId='emp-1'
        leaveYear={2026}
        availablePolicies={policies}
        onClose={vi.fn()}
      />
    )
    // Employee (Jane Doe) is pre-selected via employeeId; open the policy dropdown
    await userEvent.click(screen.getByRole('combobox', { name: /Leave Policy/i }))
    await expect.element(screen.getByRole('option', { name: /Sick Leave/i })).toBeInTheDocument()
    // Select the policy item
    await userEvent.click(screen.getByRole('option', { name: /Sick Leave/i }))
    await userEvent.click(screen.getByRole('button', { name: /Enroll/i }))
    await vi.waitFor(() => {
      expect(onConfirm).toHaveBeenCalledWith({
        employee_id: 'emp-1',
        data: {
          policy_id: '550e8400-e29b-41d4-a716-446655440000',
          leave_year: 2026,
        },
      })
    })
  })

  it('submits with the selected leave year, not the initial year', async () => {
    const policies = [
      {
        id: '550e8400-e29b-41d4-a716-446655440000',
        code: 'SL',
        name: 'Sick Leave',
        description: null,
        calendar_color: null,
        cadence: null,
        annual_entitlement_days: null,
        prorate_on_hire: null,
        carry_over_enabled: null,
        carry_over_max_days: null,
        carry_over_expires_on: null,
        is_paid: null,
        eligible_departments: null,
        gender_scope: null,
        marital_status_scope: null,
        is_active: true,
        is_system: false,
        is_deleted: false,
        created_at: null,
        updated_at: null,
      },
    ]
    const screen = await render(
      <EnrollmentDialog
        open={true}
        onOpenChange={vi.fn()}
        employeeId='emp-1'
        leaveYear={2024}
        availablePolicies={policies}
        onClose={vi.fn()}
      />
    )
    // Open the policy dropdown and select the policy
    await userEvent.click(screen.getByRole('combobox', { name: /Leave Policy/i }))
    await expect.element(screen.getByRole('option', { name: /Sick Leave/i })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('option', { name: /Sick Leave/i }))
    // Open the year dropdown and select 2026 (not the initial 2024)
    await userEvent.click(screen.getByRole('combobox', { name: /Leave Year/i }))
    await expect.element(screen.getByRole('option', { name: /2026/i })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('option', { name: /2026/i }))
    await userEvent.click(screen.getByRole('button', { name: /Enroll/i }))
    await vi.waitFor(() => {
      expect(onConfirm).toHaveBeenCalledWith(
        expect.objectContaining({
          data: expect.objectContaining({ leave_year: 2026 }),
        })
      )
    })
  })
})
