import { describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import { toast } from 'sonner'
import { ResourceForm } from './resource-form'

const { createMock, updateMock, deleteMock } = vi.hoisted(() => ({
  createMock: vi.fn(),
  updateMock: vi.fn(),
  deleteMock: vi.fn(),
}))

vi.mock('@/lib/api/employees', () => ({
  useCreateEmployee: () => ({ mutateAsync: createMock, isPending: false }),
  useUpdateEmployee: () => ({ mutateAsync: updateMock, isPending: false }),
  useDeleteEmployee: () => ({ mutateAsync: deleteMock, isPending: false }),
}))

describe('Employees ResourceForm (§8.5 create/edit/modal)', () => {
  it('renders nothing (no dialog) when closed', async () => {
    const screen = await render(<ResourceForm item={null} open={false} onClose={vi.fn()} />)
    await expect.element(screen.getByRole('dialog')).not.toBeInTheDocument()
  })

  it('opens as a modal dialog and shows core form fields', async () => {
    const screen = await render(<ResourceForm item={null} open={true} onClose={vi.fn()} />)

    const dialog = screen.getByRole('dialog')
    await expect.element(dialog).toBeInTheDocument()
    await expect.element(screen.getByRole('textbox', { name: /Employee Code/i })).toBeInTheDocument()
    await expect.element(screen.getByRole('textbox', { name: /First Name/i })).toBeInTheDocument()
    await expect.element(screen.getByRole('textbox', { name: /Last Name/i })).toBeInTheDocument()
    await expect.element(screen.getByRole('textbox', { name: /Email/i })).toBeInTheDocument()
  })

  it('calls onClose when the sheet is dismissed via Cancel', async () => {
    const onClose = vi.fn()
    const screen = await render(<ResourceForm item={null} open={true} onClose={onClose} />)
    await userEvent.click(screen.getByRole('button', { name: /Cancel/i }))
    await vi.waitFor(() => expect(onClose).toHaveBeenCalled())
  })

  it('pre-fills the form when editing an existing employee', async () => {
    const existing = {
      id: '550e8400-e29b-41d4-a716-446655440000',
      employee_code: 'EMP-001',
      first_name: 'Jane',
      middle_name: 'D',
      last_name: 'Doe',
      extension: 'Jr',
      birthdate: '1990-05-20',
      birth_place: 'Manila',
      gender: 'Female',
      civil_status: 'Single',
      email: 'jane.doe@example.com',
      date_hired: '2020-01-15',
      employee_status: 'Active',
      employment_type: 'Regular',
      position_id: '',
      division_id: '',
      department_id: '',
      telephone: '',
      cellphone: '',
      profile_photo_path: '',
      is_deleted: false,
    }
    const screen = await render(<ResourceForm item={existing} open={true} onClose={vi.fn()} />)

    await expect.element(screen.getByRole('textbox', { name: /Employee Code/i })).toHaveValue('EMP-001')
    await expect.element(screen.getByRole('textbox', { name: /First Name/i })).toHaveValue('Jane')
    await expect.element(screen.getByRole('textbox', { name: /Last Name/i })).toHaveValue('Doe')
    await expect.element(screen.getByRole('textbox', { name: /Email/i })).toHaveValue('jane.doe@example.com')
    await expect.element(screen.getByTestId('resource-form-archive-button')).toBeInTheDocument()
    // Confirm the status select opened and shows the current status as an option.
    await userEvent.click(screen.getByRole('combobox', { name: /Employee Status/i }))
    await expect.element(screen.getByRole('option', { name: /Active/i })).toBeInTheDocument()
  })

  it('creates a new employee on submit and calls onClose', async () => {
    const onClose = vi.fn()
    const screen = await render(<ResourceForm item={null} open={true} onClose={onClose} />)

    await userEvent.type(screen.getByRole('textbox', { name: /Employee Code/i }), 'EMP-999')
    await userEvent.type(screen.getByRole('textbox', { name: /First Name/i }), 'Test')
    await userEvent.type(screen.getByRole('textbox', { name: /Last Name/i }), 'User')
    await userEvent.type(screen.getByRole('textbox', { name: /Birthdate/i }), '1995-01-01')

    await userEvent.click(screen.getByRole('button', { name: /Create/i }))

    await vi.waitFor(() => {
      expect(createMock).toHaveBeenCalledWith(
        expect.objectContaining({
          employee_code: 'EMP-999',
          first_name: 'Test',
          last_name: 'User',
        })
      )
      expect(onClose).toHaveBeenCalled()
    })
  })

  it('updates an existing employee on submit with only changed fields', async () => {
    const onClose = vi.fn()
    const existing = {
      id: '550e8400-e29b-41d4-a716-446655440000',
      employee_code: 'EMP-001',
      first_name: 'Jane',
      last_name: 'Doe',
      birthdate: '1990-05-20',
      email: 'jane@example.com',
      date_hired: '2020-01-15',
      employee_status: 'Active',
      employment_type: 'Regular',
      position_id: '',
      division_id: '',
      department_id: '',
      is_deleted: false,
    }
    const screen = await render(<ResourceForm item={existing} open={true} onClose={onClose} />)

    await userEvent.type(screen.getByRole('textbox', { name: /First Name/i }), ' J.')
    await userEvent.click(screen.getByRole('button', { name: /Update/i }))

    await vi.waitFor(() => {
      expect(updateMock).toHaveBeenCalledWith(
        expect.objectContaining({
          id: '550e8400-e29b-41d4-a716-446655440000',
          data: expect.objectContaining({ first_name: expect.stringContaining('Jane J.') }),
        })
      )
      expect(onClose).toHaveBeenCalled()
    })
  })

  it('archives (soft-deletes) an employee when Archive is confirmed', async () => {
    const onClose = vi.fn()
    const existing = {
      id: '550e8400-e29b-41d4-a716-446655440000',
      employee_code: 'EMP-001',
      first_name: 'Jane',
      last_name: 'Doe',
      birthdate: '1990-05-20',
      email: 'jane@example.com',
      date_hired: '2020-01-15',
      employee_status: 'Active',
      employment_type: 'Regular',
      position_id: '',
      division_id: '',
      department_id: '',
      is_deleted: false,
    }
    const screen = await render(<ResourceForm item={existing} open={true} onClose={onClose} />)

    await userEvent.click(screen.getByTestId('resource-form-archive-button'))
    await vi.waitFor(() => expect(screen.getByRole('alertdialog')).toBeInTheDocument())

    await userEvent.click(screen.getByRole('button', { name: /Delete/i }))
    await vi.waitFor(() => {
      expect(deleteMock).toHaveBeenCalledWith('550e8400-e29b-41d4-a716-446655440000')
      expect(onClose).toHaveBeenCalled()
    })
  })

  it('shows a warning when no changes were made while editing', async () => {
    const onClose = vi.fn()
    const warningSpy = vi.spyOn(toast, 'warning').mockImplementation(() => {})
    const existing = {
      id: '550e8400-e29b-41d4-a716-446655440000',
      employee_code: 'EMP-001',
      first_name: 'Jane',
      last_name: 'Doe',
      birthdate: '1990-05-20',
      email: 'jane@example.com',
      date_hired: '2020-01-15',
      employee_status: 'Active',
      employment_type: 'Regular',
      position_id: '',
      division_id: '',
      department_id: '',
      is_deleted: false,
    }
    const screen = await render(<ResourceForm item={existing} open={true} onClose={onClose} />)

    await userEvent.click(screen.getByRole('button', { name: /Update/i }))

    await vi.waitFor(() => {
      expect(warningSpy).toHaveBeenCalledWith('No changes were made.')
      expect(onClose).toHaveBeenCalled()
    })
    warningSpy.mockRestore()
  })
})
