import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import type { LeavePolicyPublic } from '@/lib/api/types'
import { toast } from 'sonner'
import { LeavePolicyForm } from './policy-form'

const { createMock, updateMock } = vi.hoisted(() => ({
  createMock: vi.fn(),
  updateMock: vi.fn(),
}))

vi.mock('@/lib/api/leave-policies', () => ({
  useCreateLeavePolicy: () => ({ mutateAsync: createMock, isPending: false }),
  useUpdateLeavePolicy: () => ({ mutateAsync: updateMock, isPending: false }),
}))

describe('LeavePolicyForm (§QA-04 add/edit modal)', () => {
  it('renders nothing (no sheet) when closed', async () => {
    const screen = await render(<LeavePolicyForm open={false} onClose={vi.fn()} />)
    await expect.element(screen.getByRole('dialog')).not.toBeInTheDocument()
  })

  it('opens as a modal sheet and shows core form fields', async () => {
    const screen = await render(<LeavePolicyForm open={true} onClose={vi.fn()} />)

    const dialog = screen.getByRole('dialog')
    await expect.element(dialog).toBeInTheDocument()
    await expect.element(screen.getByRole('textbox', { name: /Policy Code/i })).toBeInTheDocument()
    await expect.element(screen.getByRole('textbox', { name: /Policy Name/i })).toBeInTheDocument()
    await expect.element(screen.getByRole('combobox', { name: /Cadence/i })).toBeInTheDocument()
    await expect.element(screen.getByTestId('policy-form-entitlement-input')).toBeInTheDocument()
  })

  it('pre-fills the form when editing an existing policy', async () => {
    const existing = {
      id: '550e8400-e29b-41d4-a716-446655440000',
      code: 'SL',
      name: 'Sick Leave',
      description: 'Sick leave policy',
      calendar_color: '#FF0000',
      cadence: 'annual',
      annual_entitlement_days: '15.00',
      prorate_on_hire: true,
      carry_over_enabled: true,
      carry_over_max_days: '5.00',
      carry_over_expires_on: '2026-12-31',
      is_paid: true,
      eligible_departments: [],
      gender_scope: 'all',
      marital_status_scope: 'all',
      is_active: true,
      is_system: false,
      is_deleted: false,
      created_at: null,
      updated_at: null,
    } as LeavePolicyPublic
    const screen = await render(<LeavePolicyForm open={true} onClose={vi.fn()} initialData={existing} />)

    await expect.element(screen.getByRole('textbox', { name: /Policy Code/i })).toHaveValue('SL')
    await expect.element(screen.getByRole('textbox', { name: /Policy Name/i })).toHaveValue('Sick Leave')
    await expect.element(screen.getByTestId('policy-form-entitlement-input')).toHaveValue(15)
    await expect.element(screen.getByRole('checkbox', { name: /Paid Leave/i })).toBeChecked()
  })

  it('creates a new leave policy on submit and calls onClose', async () => {
    const onClose = vi.fn()
    const screen = await render(<LeavePolicyForm open={true} onClose={onClose} />)

    await userEvent.type(screen.getByRole('textbox', { name: /Policy Code/i }), 'CL')
    await userEvent.type(screen.getByRole('textbox', { name: /Policy Name/i }), 'Casual Leave')

    await userEvent.click(screen.getByRole('button', { name: /Create/i }))

    await vi.waitFor(() => {
      expect(createMock).toHaveBeenCalledWith(
        expect.objectContaining({
          code: 'CL',
          name: 'Casual Leave',
        })
      )
      expect(onClose).toHaveBeenCalled()
    })
  })

  it('updates an existing leave policy on submit with only changed fields', async () => {
    const onClose = vi.fn()
    const existing = {
      id: '550e8400-e29b-41d4-a716-446655440000',
      code: 'SL',
      name: 'Sick Leave',
      description: 'Sick leave',
      calendar_color: '#FF0000',
      cadence: 'annual',
      annual_entitlement_days: '15.00',
      prorate_on_hire: true,
      carry_over_enabled: false,
      carry_over_max_days: '5.00',
      carry_over_expires_on: '2026-12-31',
      is_paid: true,
      eligible_departments: [],
      gender_scope: 'all',
      marital_status_scope: 'all',
      is_active: true,
      is_system: false,
      is_deleted: false,
      created_at: null,
      updated_at: null,
    } as LeavePolicyPublic
    const screen = await render(<LeavePolicyForm open={true} onClose={onClose} initialData={existing} />)

    const entitlementInput = screen.getByTestId('policy-form-entitlement-input')
    await userEvent.clear(entitlementInput)
    await userEvent.type(entitlementInput, '20.00')

    await userEvent.click(screen.getByRole('button', { name: /Update/i }))

    await vi.waitFor(() => {
      expect(updateMock).toHaveBeenCalledWith({
        id: '550e8400-e29b-41d4-a716-446655440000',
        data: expect.objectContaining({
          annual_entitlement_days: '20.00',
        }),
      })
      expect(onClose).toHaveBeenCalled()
    })
  })

  it('shows a warning when no changes were made while editing', async () => {
    const onClose = vi.fn()
    const warningSpy = vi.spyOn(toast, 'warning').mockImplementation(() => 'mock-message')
    const existing = {
      id: '550e8400-e29b-41d4-a716-446655440000',
      code: 'SL',
      name: 'Sick Leave',
      description: 'Sick leave',
      calendar_color: '#FF0000',
      cadence: 'annual',
      annual_entitlement_days: '15.00',
      prorate_on_hire: true,
      carry_over_enabled: false,
      carry_over_max_days: '5.00',
      carry_over_expires_on: '2026-12-31',
      is_paid: true,
      eligible_departments: [],
      gender_scope: 'all',
      marital_status_scope: 'all',
      is_active: true,
      is_system: false,
      is_deleted: false,
      created_at: null,
      updated_at: null,
    } as LeavePolicyPublic
    const screen = await render(<LeavePolicyForm open={true} onClose={onClose} initialData={existing} />)

    await userEvent.click(screen.getByRole('button', { name: /Update/i }))

    await vi.waitFor(() => {
      expect(warningSpy).toHaveBeenCalledWith('No changes were made.')
      expect(onClose).toHaveBeenCalled()
    })
    warningSpy.mockRestore()
  })

  it('validates required fields on submit', async () => {
    const screen = await render(<LeavePolicyForm open={true} onClose={vi.fn()} />)

    await userEvent.click(screen.getByRole('button', { name: /Create/i }))

    await vi.waitFor(() => {
      expect(screen.getByText('Policy code is required')).toBeInTheDocument()
      expect(screen.getByText('Policy name is required')).toBeInTheDocument()
    })
  })
})
