import { z } from 'zod'
import { createFileRoute } from '@tanstack/react-router'
import EmployeeProjectsPage from '@/features/employee-projects'

const searchSchema = z.object({
  page: z.number().optional().catch(1),
  pageSize: z.number().optional().catch(20),
})

export const Route = createFileRoute('/_authenticated/employee-projects/')({
  component: EmployeeProjectsPage,
  validateSearch: searchSchema,
})
