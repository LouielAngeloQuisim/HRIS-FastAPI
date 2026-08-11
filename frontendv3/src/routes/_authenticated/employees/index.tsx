import { z } from 'zod'
import { createFileRoute } from '@tanstack/react-router'
import { Employees } from '@/features/employees'

const employeesSearchSchema = z.object({
  page: z.number().optional().catch(1),
  pageSize: z.number().optional().catch(10),
  status: z.array(z.string()).optional(),
  q: z.string().optional(),
})

export const Route = createFileRoute('/_authenticated/employees/')({
  component: Employees,
  validateSearch: employeesSearchSchema,
})
