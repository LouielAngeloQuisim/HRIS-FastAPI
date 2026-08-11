// Backend contract types — mirror the verified FastAPI shapes in
// `backend/app/` (Phase 0/1). Kept in sync with `docs/roadmap/phase1-design.md`.

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface UserPublic {
  id: string
  email: string
  is_active: boolean
  is_superuser: boolean
  full_name: string | null
  role_id: string | null
  created_at: string | null
}

export type PermissionAction = 'view' | 'add' | 'edit' | 'delete'

export type ModulePermissions = Record<PermissionAction, boolean>

export interface MyPermissions {
  role_code: string | null
  is_superuser: boolean
  permissions: Record<string, ModulePermissions>
}

export interface EmployeeRecordsPublic {
  id: string
  employee_code: string
  first_name: string
  middle_name: string | null
  last_name: string
  extension: string | null
  birthdate: string
  birth_place: string | null
  gender: string | null
  civil_status: string | null
  email: string | null
  zip_code: string | null
  area: string | null
  present_barangay: string | null
  present_city: string | null
  same_address: boolean | null
  permanent_barangay: string | null
  permanent_city: string | null
  date_hired: string | null
  employee_status: 'Active' | 'Resigned' | 'Terminated' | 'On Leave'
  employment_type: string | null
  contract_expiry_date: string | null
  date_separated: string | null
  probationary_date: string | null
  regularization_date: string | null
  telephone: string | null
  cellphone: string | null
  profile_photo_path: string | null
  position_id: string | null
  division_id: string | null
  department_id: string | null
  user_id: string | null
  is_deleted: boolean
  created_at: string | null
  updated_at: string | null
}

export interface EmployeeRecordsList {
  data: EmployeeRecordsPublic[]
  count: number
}

export interface DashboardStats {
  employee_records: number
  divisions: number
  departments: number
  projects: number
  subdivisions: number
  owners: number
  employee_projects: number
  model_count: number
  dtr_records_daily_count: number
}

// Standard error envelope returned by the backend (app/common/responses.py).
export interface ErrorBody {
  type: string
  message: string
  details: Array<{
    location?: string | null
    field?: string | null
    message: string
    type?: string | null
  }>
}

export interface ErrorResponse {
  success: boolean
  detail: string
  error: ErrorBody
  request_id: string | null
}
