import { z } from 'zod'
import { createFileRoute } from '@tanstack/react-router'
import EmpTasksPage from '@/features/emp-tasks'

const searchSchema = z.object({
  page: z.number().optional().catch(1),
  pageSize: z.number().optional().catch(20),
})

export const Route = createFileRoute('/_authenticated/emp-tasks/')({
  component: EmpTasksPage,
  validateSearch: searchSchema,
})
