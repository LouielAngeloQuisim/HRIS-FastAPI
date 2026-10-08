import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import { ResourceForm } from './resource-form'

const { createMock, updateMock } = vi.hoisted(() => ({
  createMock: { mutateAsync: vi.fn() },
  updateMock: { mutateAsync: vi.fn() },
}))
vi.mock('@/lib/api/holidays', () => ({
  useCreateHolidayConfig: () => createMock,
  useUpdateHolidayConfig: () => updateMock,
}))

vi.mock('@/context/permissions-provider', () => ({
  useCan: () => true,
}))

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

describe('Holidays ResourceForm', () => {
  it('renders create form with empty fields', async () => {
    const screen = await render(
      <ResourceForm item={null} open={true} onClose={() => {}} />
    )

    await expect
      .element(screen.getByTestId('holiday-code-input'))
      .toBeVisible()
    await expect
      .element(screen.getByTestId('holiday-name-input'))
      .toBeVisible()
    await expect
      .element(screen.getByTestId('holiday-month-day-input'))
      .toBeVisible()
    await expect
      .element(screen.getByTestId('holiday-submit-button'))
      .toBeVisible()
    await expect.element(screen.getByTestId('holiday-type-select')).toBeVisible()
    await expect
      .element(screen.getByText('Create Holiday'))
      .toBeVisible()
  })

  it('renders edit form with existing data', async () => {
    const existing = {
      id: 'h1',
      code: 'NEWYEAR',
      name: "New Year's Day",
      month_day: '01-01',
      type: 'special_non_working',
      region_code: null,
      observe_weekend_as: null,
      multiplier_regular: null,
      multiplier_overtime: null,
      multiplier_regular_rest_day: null,
      multiplier_overtime_rest_day: null,
      is_recurring: true,
      is_active: true,
      is_deleted: false,
      created_at: null,
      updated_at: null,
    }

    const screen = await render(
      <ResourceForm item={existing} open={true} onClose={() => {}} />
    )

    await expect
      .element(screen.getByText('Update Holiday'))
      .toBeVisible()
    const codeInput = screen.getByTestId('holiday-code-input')
    await expect.element(codeInput).toHaveValue('NEWYEAR')
  })

  it('calls create mutation with correct payload on submit', async () => {
    createMock.mutateAsync.mockResolvedValue({})

    const onClose = vi.fn()
    const screen = await render(
      <ResourceForm item={null} open={true} onClose={onClose} />
    )

    await userEvent.type(
      screen.getByTestId('holiday-code-input'),
      'XMAS'
    )
    await userEvent.type(
      screen.getByTestId('holiday-name-input'),
      'Christmas Day'
    )
    await userEvent.type(
      screen.getByTestId('holiday-month-day-input'),
      '12-25'
    )
    await userEvent.type(
      screen.getByTestId('holiday-regular-factor-input'),
      '2'
    )
    await userEvent.type(
      screen.getByTestId('holiday-overtime-factor-input'),
      '2.6'
    )
    await userEvent.type(
      screen.getByTestId('holiday-rest-day-factor-input'),
      '2.6'
    )
    await userEvent.type(
      screen.getByTestId('holiday-rest-day-overtime-factor-input'),
      '3.38'
    )

    await userEvent.click(screen.getByTestId('holiday-submit-button'))

    expect(createMock.mutateAsync).toHaveBeenCalled()
    const payload = createMock.mutateAsync.mock.calls[0][0]
    expect(payload.code).toBe('XMAS')
    expect(payload.name).toBe('Christmas Day')
    expect(payload.month_day).toBe('12-25')
    expect(payload.multiplier_regular).toBe(2)
    expect(payload.multiplier_overtime).toBe(2.6)
    expect(payload.multiplier_regular_rest_day).toBe(2.6)
    expect(payload.multiplier_overtime_rest_day).toBe(3.38)
    expect(onClose).toHaveBeenCalled()
  })

  it('calls update mutation with correct payload on submit', async () => {
    updateMock.mutateAsync.mockResolvedValue({})

    const onClose = vi.fn()
    const existing = {
      id: 'h1',
      code: 'NEWYEAR',
      name: "New Year's Day",
      month_day: '01-01',
      type: 'special_non_working',
      region_code: null,
      observe_weekend_as: null,
      multiplier_regular: null,
      multiplier_overtime: null,
      multiplier_regular_rest_day: null,
      multiplier_overtime_rest_day: null,
      is_recurring: true,
      is_active: true,
      is_deleted: false,
      created_at: null,
      updated_at: null,
    }

    const screen = await render(
      <ResourceForm item={existing} open={true} onClose={onClose} />
    )

    await userEvent.click(screen.getByTestId('holiday-submit-button'))

    expect(updateMock.mutateAsync).toHaveBeenCalled()
    const call = updateMock.mutateAsync.mock.calls[0][0]
    expect(call.id).toBe('h1')
    expect(call.data.type).toBe('special_non_working')
    expect(onClose).toHaveBeenCalled()
  })
})
