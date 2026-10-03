import { z } from 'zod'
import { createFileRoute } from '@tanstack/react-router'
import SSSConfigPage from '@/features/payroll-config/sss'
import { assertSuperAdmin } from '@/features/payroll-config/super-admin-guard'

const searchSchema = z.object({
  page: z.number().optional().catch(1),
  pageSize: z.number().optional().catch(20),
})

export const Route = createFileRoute('/_authenticated/payroll-config/sss/')({
  beforeLoad: () => assertSuperAdmin(),
  component: SSSConfigPage,
  validateSearch: searchSchema,
})
