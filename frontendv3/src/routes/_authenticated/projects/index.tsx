import { z } from 'zod'
import { createFileRoute } from '@tanstack/react-router'
import ProjectsPage from '@/features/projects'

const searchSchema = z.object({
  page: z.number().optional().catch(1),
  pageSize: z.number().optional().catch(20),
})

export const Route = createFileRoute('/_authenticated/projects/')({
  component: ProjectsPage,
  validateSearch: searchSchema,
})
