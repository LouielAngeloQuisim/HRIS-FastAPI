import { renderWithClient } from '@/test-utils/providers'
import { describe, expect, it, vi } from 'vitest'
import BlocksPage from './blocks/index'
import DepartmentsPage from './departments/index'
import DivisionPage from './divisions/index'

// Policy-based permissions mock that mirrors the real useCan semantics
// (is_superuser bypass; deny-by-default for missing module/action). A blanket
// boolean mock would ignore the action string and defeat the proof-by-reversion.
const { perms } = vi.hoisted(() => ({
  perms: {
    is_superuser: false,
    divisions: { view: true, add: false, edit: false, delete: false },
    blocks: { view: true, add: false, edit: false, delete: false },
    departments: { view: true, add: false, edit: false, delete: false },
  },
}))
vi.mock('@/context/permissions-provider', () => ({
  useCan: (module: string, action: string) =>
    perms.is_superuser ? true : perms[module]?.[action] === true,
}))
vi.mock('@/lib/api/divisions', () => ({
  useDivisions: () => ({
    data: {
      data: [
        {
          id: 'div-1',
          code: 'D-01',
          name: 'North',
          description: 'd',
          director_id: 'u1',
        },
      ],
      count: 1,
    },
    isPending: false,
    isError: false,
  }),
}))
vi.mock('@/lib/api/blocks', () => ({
  useBlocks: () => ({
    data: {
      data: [{ id: 'b1', block_name: 'Block A', phase_id: 'p1' }],
      count: 1,
    },
    isPending: false,
    isError: false,
  }),
}))
vi.mock('@/lib/api/departments', () => ({
  useDepartments: () => ({
    data: {
      data: [
        {
          id: 'd1',
          code: 'DPT-01',
          name: 'Dept A',
          description: 'd',
          division_id: 'div-1',
          manager_id: 'u1',
        },
      ],
      count: 1,
    },
    isPending: false,
    isError: false,
  }),
}))
vi.mock('@/lib/api/client', () => ({ api: { delete: vi.fn(), get: vi.fn() } }))
vi.mock('./divisions/components/resource-form', () => ({
  ResourceForm: () => null,
}))
vi.mock('./divisions/components/resource-delete-dialog', () => ({
  ResourceDeleteDialog: () => null,
}))
vi.mock('./blocks/components/resource-form', () => ({
  ResourceForm: () => null,
}))
vi.mock('./blocks/components/resource-delete-dialog', () => ({
  ResourceDeleteDialog: () => null,
}))
vi.mock('./departments/components/resource-form', () => ({
  ResourceForm: () => null,
}))
vi.mock('./departments/components/resource-delete-dialog', () => ({
  ResourceDeleteDialog: () => null,
}))

async function lowPriv() {
  perms.is_superuser = false
  for (const m of ['divisions', 'blocks', 'departments'] as const) {
    perms[m].view = true
    perms[m].add = false
    perms[m].edit = false
    perms[m].delete = false
  }
}
async function privileged() {
  perms.is_superuser = false
  for (const m of ['divisions', 'blocks', 'departments'] as const) {
    perms[m].view = true
    perms[m].add = true
    perms[m].edit = true
    perms[m].delete = true
  }
}
async function noView() {
  perms.is_superuser = false
  for (const m of ['divisions', 'blocks', 'departments'] as const) {
    perms[m].view = false
    perms[m].add = false
    perms[m].edit = false
    perms[m].delete = false
  }
}

describe('Permission-gate coverage (§8.6)', () => {
  describe('Division', () => {
    it('hides the Add button when the user lacks the add permission', async () => {
      await lowPriv()
      const { getByRole } = await renderWithClient(<DivisionPage />)
      await expect
        .element(getByRole('button', { name: /Add Division/i }))
        .not.toBeInTheDocument()
    })
    it('shows the Add button when the user has the add permission', async () => {
      await privileged()
      const { getByRole } = await renderWithClient(<DivisionPage />)
      await expect
        .element(getByRole('button', { name: /Add Division/i }))
        .toBeInTheDocument()
    })
    it('hides row Edit/Delete when the user lacks edit and delete permission', async () => {
      await lowPriv()
      const { getByText, getByRole } = await renderWithClient(<DivisionPage />)
      await expect.element(getByText('D-01')).toBeInTheDocument() // row is rendered
      await expect
        .element(getByRole('button', { name: /^Edit$/i }))
        .not.toBeInTheDocument()
      await expect
        .element(getByRole('button', { name: /^Delete$/i }))
        .not.toBeInTheDocument()
    })
    it('shows a permission-denied state when the user lacks view', async () => {
      await noView()
      const { getByText } = await renderWithClient(<DivisionPage />)
      await expect
        .element(getByText(/You do not have permission to view divisions/i))
        .toBeInTheDocument()
    })
  })

  describe('Blocks', () => {
    it('hides the Add button when the user lacks the add permission', async () => {
      await lowPriv()
      const { getByRole } = await renderWithClient(<BlocksPage />)
      await expect
        .element(getByRole('button', { name: /Add Blocks/i }))
        .not.toBeInTheDocument()
    })
    it('shows the Add button when the user has the add permission', async () => {
      await privileged()
      const { getByRole } = await renderWithClient(<BlocksPage />)
      await expect
        .element(getByRole('button', { name: /Add Blocks/i }))
        .toBeInTheDocument()
    })
    it('hides row Edit/Delete when the user lacks edit and delete permission', async () => {
      await lowPriv()
      const { getByText, getByRole } = await renderWithClient(<BlocksPage />)
      await expect.element(getByText('Block A')).toBeInTheDocument() // row is rendered
      await expect
        .element(getByRole('button', { name: /^Edit$/i }))
        .not.toBeInTheDocument()
      await expect
        .element(getByRole('button', { name: /^Delete$/i }))
        .not.toBeInTheDocument()
    })
    it('shows a permission-denied state when the user lacks view', async () => {
      await noView()
      const { getByText } = await renderWithClient(<BlocksPage />)
      await expect
        .element(getByText(/You do not have permission to view blocks/i))
        .toBeInTheDocument()
    })
  })

  describe('Departments', () => {
    it('hides the Add button when the user lacks the add permission', async () => {
      await lowPriv()
      const { getByRole } = await renderWithClient(<DepartmentsPage />)
      await expect
        .element(getByRole('button', { name: /Add Department/i }))
        .not.toBeInTheDocument()
    })
    it('shows the Add button when the user has the add permission', async () => {
      await privileged()
      const { getByRole } = await renderWithClient(<DepartmentsPage />)
      await expect
        .element(getByRole('button', { name: /Add Department/i }))
        .toBeInTheDocument()
    })
    it('hides row Edit/Delete when the user lacks edit and delete permission', async () => {
      await lowPriv()
      const { getByText, getByRole } = await renderWithClient(
        <DepartmentsPage />
      )
      await expect.element(getByText('DPT-01')).toBeInTheDocument() // row is rendered
      await expect
        .element(getByRole('button', { name: /^Edit$/i }))
        .not.toBeInTheDocument()
      await expect
        .element(getByRole('button', { name: /^Delete$/i }))
        .not.toBeInTheDocument()
    })
    it('shows a permission-denied state when the user lacks view', async () => {
      await noView()
      const { getByText } = await renderWithClient(<DepartmentsPage />)
      await expect
        .element(getByText(/You do not have permission to view departments/i))
        .toBeInTheDocument()
    })
  })
})
