import { z } from 'zod'
import { createFileRoute } from '@tanstack/react-router'
import ModelTypesPage from '@/features/model-types'

const searchSchema = z.object({
  page: z.number().optional().catch(1),
  pageSize: z.number().optional().catch(20),
})

export const Route = createFileRoute('/_authenticated/model-types/')({
  component: ModelTypesPage,
  validateSearch: searchSchema,
})
