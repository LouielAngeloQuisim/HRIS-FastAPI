import { z } from 'zod'
import { createFileRoute } from '@tanstack/react-router'
import PagIBIGConfigPage from '@/features/payroll-config/pagibig'
import { assertSuperAdmin } from '@/features/payroll-config/super-admin-guard'

const searchSchema = z.object({
  page: z.number().optional().catch(1),
  pageSize: z.number().optional().catch(20),
})

export const Route = createFileRoute('/_authenticated/payroll-config/pagibig/')({
  beforeLoad: () => assertSuperAdmin(),
  component: PagIBIGConfigPage,
  validateSearch: searchSchema,
})
