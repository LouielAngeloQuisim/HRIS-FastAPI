import { z } from 'zod'
import { createFileRoute } from '@tanstack/react-router'
import { EmployeeProfile } from '@/features/employees/profile'

const profileSearchSchema = z.object({})

export const Route = createFileRoute('/_authenticated/employees/$employeeId')({
  component: EmployeeProfile,
  validateSearch: profileSearchSchema,
})
