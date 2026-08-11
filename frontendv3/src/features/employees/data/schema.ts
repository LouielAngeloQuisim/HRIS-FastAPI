import { z } from 'zod'

const employeeStatusSchema = z.union([
  z.literal('Active'),
  z.literal('Resigned'),
  z.literal('Terminated'),
  z.literal('On Leave'),
])
export type EmployeeStatus = z.infer<typeof employeeStatusSchema>

export const employeeSchema = z.object({
  id: z.string(),
  employee_code: z.string(),
  first_name: z.string(),
  middle_name: z.string().nullable(),
  last_name: z.string(),
  extension: z.string().nullable(),
  birthdate: z.string(),
  birth_place: z.string().nullable(),
  gender: z.string().nullable(),
  civil_status: z.string().nullable(),
  email: z.string().nullable(),
  zip_code: z.string().nullable(),
  area: z.string().nullable(),
  present_barangay: z.string().nullable(),
  present_city: z.string().nullable(),
  same_address: z.boolean().nullable(),
  permanent_barangay: z.string().nullable(),
  permanent_city: z.string().nullable(),
  date_hired: z.string().nullable(),
  employee_status: employeeStatusSchema,
  employment_type: z.string().nullable(),
  contract_expiry_date: z.string().nullable(),
  date_separated: z.string().nullable(),
  probationary_date: z.string().nullable(),
  regularization_date: z.string().nullable(),
  telephone: z.string().nullable(),
  cellphone: z.string().nullable(),
  profile_photo_path: z.string().nullable(),
  position_id: z.string().nullable(),
  division_id: z.string().nullable(),
  department_id: z.string().nullable(),
  user_id: z.string().nullable(),
  is_deleted: z.boolean(),
  created_at: z.string().nullable(),
  updated_at: z.string().nullable(),
})
export type Employee = z.infer<typeof employeeSchema>

export function fullName(e: Pick<Employee, 'last_name' | 'first_name' | 'middle_name'>): string {
  const parts = [e.last_name, e.first_name, e.middle_name].filter(Boolean)
  return parts.join(', ')
}
