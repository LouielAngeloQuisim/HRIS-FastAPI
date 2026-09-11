import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import { ResourceForm } from './resource-form'

const { createMock, updateMock } = vi.hoisted(() => ({
  createMock: { mutateAsync: vi.fn() },
  updateMock: { mutateAsync: vi.fn() },
}))
vi.mock('@/lib/api/owners', () => ({
  useCreateOwner: () => createMock,
  useUpdateOwner: () => updateMock,
}))

vi.mock('@/context/permissions-provider', () => ({
  useCan: () => true,
}))

describe('Owners ResourceForm', () => {
  it('renders create form with Name, Email, and Phone fields', async () => {
    const screen = await render(
      <ResourceForm item={null} open={true} onClose={() => {}} />
    )

    await expect.element(screen.getByText('Create Owner')).toBeVisible()
    await expect.element(screen.getByLabelText('Name')).toBeVisible()
    await expect.element(screen.getByLabelText('Email')).toBeVisible()
    await expect.element(screen.getByLabelText('Phone')).toBeVisible()
  })

  it('remaps form fields to backend schema on create (name→first_name, phone→contact_no)', async () => {
    createMock.mutateAsync.mockResolvedValue({})

    const onClose = vi.fn()
    const screen = await render(
      <ResourceForm item={null} open={true} onClose={onClose} />
    )

    await userEvent.type(screen.getByLabelText('Name'), 'John')
    await userEvent.type(screen.getByLabelText('Email'), 'john@example.com')
    await userEvent.type(screen.getByLabelText('Phone'), '555-1234')

    await userEvent.click(screen.getByRole('button', { name: /Create/i }))

    expect(createMock.mutateAsync).toHaveBeenCalled()
    const payload = createMock.mutateAsync.mock.calls[0][0]
    expect(payload.first_name).toBe('John')
    expect(payload.email).toBe('john@example.com')
    expect(payload.contact_no).toBe('555-1234')
    expect(payload.name).toBeUndefined()
    expect(payload.phone).toBeUndefined()
  })

  it('remaps form fields to backend schema on update', async () => {
    updateMock.mutateAsync.mockResolvedValue({})

    const onClose = vi.fn()
    const existing = {
      id: 'o1',
      first_name: 'Jane',
      last_name: 'Doe',
      lot_no: 'L1',
      block: 'B1',
      email: 'jane@example.com',
      contact_no: '555-9999',
      is_deleted: false,
      created_at: null,
    }

    const screen = await render(
      <ResourceForm item={existing} open={true} onClose={onClose} />
    )

    const nameInput = screen.getByLabelText('Name')
    await userEvent.clear(nameInput)
    await userEvent.type(nameInput, 'Janet')

    await userEvent.click(screen.getByRole('button', { name: /Update/i }))

    expect(updateMock.mutateAsync).toHaveBeenCalled()
    const call = updateMock.mutateAsync.mock.calls[0][0]
    expect(call.id).toBe('o1')
    expect(call.data.first_name).toBe('Janet')
    expect(call.data.contact_no).toBe('555-9999')
    expect(call.data.name).toBeUndefined()
    expect(onClose).toHaveBeenCalled()
  })
})
