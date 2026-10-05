import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import { LeavePolicyDeleteDialog } from './policy-delete-dialog'

const onConfirm = vi.fn()

vi.mock('@/components/resource-delete-dialog', () => ({
  ResourceDeleteDialog: ({
    onConfirm: realOnConfirm,
    open,
    onOpenChange,
    entityLabel,
  }: {
    onConfirm: () => void
    open: boolean
    onOpenChange?: (open: boolean) => void
    entityLabel?: string
  }) => {
    if (!open) return null
    return (
      <div role='alertdialog' data-testid='resource-form-archive-dialog'>
        <p>{entityLabel ? `Delete ${entityLabel}?` : 'Delete Leave Policy?'}</p>
        <button type='button' data-testid='cancel-delete-button' onClick={() => onOpenChange?.(false)}>
          Cancel
        </button>
        <button type='button' data-testid='confirm-delete-button' onClick={realOnConfirm}>
          Delete
        </button>
      </div>
    )
  },
}))

describe('LeavePolicyDeleteDialog (§QA-04 archive)', () => {
  it('renders nothing (no dialog) when policy is null', async () => {
    const screen = await render(<LeavePolicyDeleteDialog open={true} onOpenChange={vi.fn()} policy={null} onConfirm={onConfirm} />)
    await expect(screen.getByRole('alertdialog')).not.toBeInTheDocument()
  })

  it('renders the delete dialog with policy name when policy is provided', async () => {
    const policy = {
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
    }
    const screen = await render(<LeavePolicyDeleteDialog open={true} onOpenChange={vi.fn()} policy={policy} onConfirm={onConfirm} />)
    await expect.element(screen.getByRole('alertdialog')).toBeInTheDocument()
    await expect.element(screen.getByText('Sick Leave')).toBeInTheDocument()
  })

  it('calls onConfirm when Delete is clicked', async () => {
    const policy = {
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
    }
    const screen = await render(<LeavePolicyDeleteDialog open={true} onOpenChange={vi.fn()} policy={policy} onConfirm={onConfirm} />)
    await userEvent.click(screen.getByRole('button', { name: /Delete/i }))
    await vi.waitFor(() => expect(onConfirm).toHaveBeenCalled())
  })

  it('calls onOpenChange(false) when Cancel is clicked', async () => {
    const onOpenChange = vi.fn()
    const policy = {
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
    }
    const screen = await render(<LeavePolicyDeleteDialog open={true} onOpenChange={onOpenChange} policy={policy} onConfirm={onConfirm} />)
    await userEvent.click(screen.getByRole('button', { name: /Cancel/i }))
    await vi.waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false))
  })
})
