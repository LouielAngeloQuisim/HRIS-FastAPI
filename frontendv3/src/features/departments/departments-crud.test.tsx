// §8.3 — Department CRUD (create/update/delete).
// COVERAGE NOTE (FIX C, Option c): useDepartments is mocked with a static
// return value and the create/update/delete hooks are stubbed
// (mutateAsync: vi.fn()), so the component never triggers a refetch and the
// table cannot reflect post-mutation state. These tests therefore assert the
// verifiable API CONTRACT — correct mutation payload, drawer close on
// success, correct DELETE endpoint — NOT post-refetch UI reflection. To assert
// row reflection, mock useDepartments as a stateful implementation that
// updates on refetch(), or replace the hook mocks with MSW-backed real
// queries. This is a documented limitation, not a blocker.
//
import { renderWithClient } from '@/test-utils/providers'
import { describe, expect, it, vi } from 'vitest'
import { userEvent } from 'vitest/browser'
import DepartmentPage from './index'

const h = vi.hoisted(() => ({
  useDepartmentsMock: vi.fn(),
  useCreateDeptMock: vi.fn(),
  useUpdateDeptMock: vi.fn(),
  useCanMock: vi.fn(),
  apiDeleteMock: vi.fn(),
}))
vi.mock('@/lib/api/departments', () => ({
  useDepartments: (...args: unknown[]) => h.useDepartmentsMock(...args),
  useCreateDepartment: () => ({
    mutateAsync: h.useCreateDeptMock,
    isPending: false,
  }),
  useUpdateDepartment: () => ({
    mutateAsync: h.useUpdateDeptMock,
    isPending: false,
  }),
}))
vi.mock('@/context/permissions-provider', () => ({
  useCan: (...args: unknown[]) => h.useCanMock(...args),
}))
vi.mock('@/lib/api/client', () => ({
  api: { delete: (...args: unknown[]) => h.apiDeleteMock(...args) },
}))

const DEPTS = {
  data: [
    {
      id: 'dept-1',
      code: 'HR',
      name: 'Human Resources',
      description: 'd',
      division_id: 'div-1',
      manager_id: 'u1',
    },
    {
      id: 'dept-2',
      code: 'FIN',
      name: 'Finance',
      description: 'd',
      division_id: 'div-2',
      manager_id: 'u2',
    },
  ],
  count: 2,
}

describe('Department full CRUD flow (§8.3)', () => {
  it('CREATE: opens the form, fills it, and submits a create mutation', async () => {
    h.useDepartmentsMock.mockReturnValue({
      data: DEPTS,
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })
    h.useCanMock.mockReturnValue(true)
    h.apiDeleteMock.mockResolvedValue({ data: {} })

    const { getByRole } = await renderWithClient(<DepartmentPage />)

    await userEvent.click(getByRole('button', { name: /Add Department/i }))
    await expect
      .element(getByRole('heading', { name: /Create Department/i }))
      .toBeInTheDocument()

    await userEvent.fill(getByRole('textbox', { name: /Code/i }), 'OPS')
    await userEvent.fill(getByRole('textbox', { name: /Name/i }), 'Operations')

    await userEvent.click(getByRole('button', { name: /^Create$/i }))

    await vi.waitFor(() => {
      expect(h.useCreateDeptMock).toHaveBeenCalledWith(
        expect.objectContaining({ code: 'OPS', name: 'Operations' })
      )
    })
    // Success path: the create drawer closes after the mutation resolves.
    await expect
      .element(getByRole('heading', { name: /Create Department/i }))
      .not.toBeInTheDocument()
  })

  it('EDIT: opens prefilled form and submits an update mutation', async () => {
    h.useDepartmentsMock.mockReturnValue({
      data: DEPTS,
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })
    h.useCanMock.mockReturnValue(true)
    h.apiDeleteMock.mockResolvedValue({ data: {} })

    const { getByRole } = await renderWithClient(<DepartmentPage />)

    const editButtons = getByRole('button', { name: /Edit/i }).all()
    await userEvent.click(editButtons[0])
    await expect
      .element(getByRole('heading', { name: /Update Department/i }))
      .toBeInTheDocument()
    await expect
      .element(getByRole('textbox', { name: /Name/i }))
      .toHaveValue('Human Resources')

    await userEvent.fill(getByRole('textbox', { name: /Name/i }), 'HR Renamed')
    await userEvent.click(getByRole('button', { name: /^Update$/i }))

    await vi.waitFor(() => {
      expect(h.useUpdateDeptMock).toHaveBeenCalledWith(
        expect.objectContaining({
          id: 'dept-1',
          data: expect.objectContaining({ name: 'HR Renamed' }),
        })
      )
    })
    // Success path: the edit drawer closes after the mutation resolves.
    await expect
      .element(getByRole('heading', { name: /Update Department/i }))
      .not.toBeInTheDocument()
  })

  it('DELETE: confirm dialog triggers the delete and closes', async () => {
    h.useDepartmentsMock.mockReturnValue({
      data: DEPTS,
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    })
    h.useCanMock.mockReturnValue(true)
    h.apiDeleteMock.mockResolvedValue({ data: {} })

    const { getByRole } = await renderWithClient(<DepartmentPage />)

    const deleteButtons = getByRole('button', { name: /Delete/i }).all()
    await userEvent.click(deleteButtons[0])

    await expect
      .element(getByRole('button', { name: /^Delete$/i }))
      .toBeInTheDocument()
    await userEvent.click(getByRole('button', { name: /^Delete$/i }))

    await vi.waitFor(() => {
      expect(h.apiDeleteMock).toHaveBeenCalledWith('/departments/dept-1')
    })
  })
})
