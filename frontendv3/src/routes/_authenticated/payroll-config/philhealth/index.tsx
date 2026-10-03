import { z } from 'zod'
import { createFileRoute } from '@tanstack/react-router'
import PhilHealthConfigPage from '@/features/payroll-config/philhealth'
import { assertSuperAdmin } from '@/features/payroll-config/super-admin-guard'

const searchSchema = z.object({
  page: z.number().optional().catch(1),
  pageSize: z.number().optional().catch(20),
})

export const Route = createFileRoute('/_authenticated/payroll-config/philhealth/')({
  beforeLoad: () => assertSuperAdmin(),
  component: PhilHealthConfigPage,
  validateSearch: searchSchema,
})
