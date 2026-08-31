import { z } from 'zod'
import { createFileRoute } from '@tanstack/react-router'
import RolesPage from '@/features/roles'

const searchSchema = z.object({
  page: z.number().optional().catch(1),
  pageSize: z.number().optional().catch(20),
})

export const Route = createFileRoute('/_authenticated/roles/')({
  component: RolesPage,
  validateSearch: searchSchema,
})
