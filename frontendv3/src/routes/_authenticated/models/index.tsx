import { z } from 'zod'
import { createFileRoute } from '@tanstack/react-router'
import ModelsPage from '@/features/models'

const searchSchema = z.object({
  page: z.number().optional().catch(1),
  pageSize: z.number().optional().catch(20),
})

export const Route = createFileRoute('/_authenticated/models/')({
  component: ModelsPage,
  validateSearch: searchSchema,
})
