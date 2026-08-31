import { z } from 'zod'
import { createFileRoute } from '@tanstack/react-router'
import DepartmentsPage from '@/features/departments'

const searchSchema = z.object({
  page: z.number().optional().catch(1),
  pageSize: z.number().optional().catch(20),
})

export const Route = createFileRoute('/_authenticated/departments/')({
  component: DepartmentsPage,
  validateSearch: searchSchema,
})
