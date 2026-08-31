// Backend contract types — mirror the verified FastAPI shapes in
// `backend/app/employee/schemas.py` (Phase 1). Kept in sync with
// `docs/roadmap/phase1-design.md`.

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

// Employee
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

// Division
export interface DivisionPublic {
  id: string
  code: string
  name: string
  description: string | null
  director_id: string | null
  is_deleted: boolean
  created_at: string | null
}

export interface DivisionList { data: DivisionPublic[]; count: number }
export interface DivisionCreate { code: string; name: string; description?: string | null; director_id?: string | null }
export interface DivisionUpdate { code?: string | null; name?: string | null; description?: string | null; director_id?: string | null }

// Department
export interface DepartmentPublic {
  id: string
  code: string
  name: string
  description: string | null
  division_id: string
  manager_id: string | null
  is_deleted: boolean
  created_at: string | null
}

export interface DepartmentList { data: DepartmentPublic[]; count: number }
export interface DepartmentCreate { code: string; name: string; description?: string | null; division_id: string; manager_id?: string | null }
export interface DepartmentUpdate { code?: string | null; name?: string | null; description?: string | null; division_id?: string | null; manager_id?: string | null }

// Subdivision
export interface SubdivisionPublic {
  id: string
  subdivision_code: string
  name: string
  description: string | null
  location: string
  is_deleted: boolean
  created_at: string | null
}

export interface SubdivisionList { data: SubdivisionPublic[]; count: number }
export interface SubdivisionCreate { subdivision_code: string; name: string; description?: string | null; location: string }
export interface SubdivisionUpdate { subdivision_code?: string | null; name?: string | null; description?: string | null; location?: string | null }

// Position
export interface PositionPublic {
  id: string
  code: string
  title: string
  description: string | null
  department_id: string | null
  is_deleted: boolean
  created_at: string | null
}

export interface PositionList { data: PositionPublic[]; count: number }
export interface PositionCreate { code: string; title: string; description?: string | null; department_id?: string | null }
export interface PositionUpdate { code?: string | null; title?: string | null; description?: string | null; department_id?: string | null }

// ProjectType
export interface ProjectTypePublic {
  id: string
  code: string
  name: string
  description: string | null
  is_deleted: boolean
  created_at: string | null
}

export interface ProjectTypeList { data: ProjectTypePublic[]; count: number }
export interface ProjectTypeCreate { code: string; name: string; description?: string | null }
export interface ProjectTypeUpdate { code?: string | null; name?: string | null; description?: string | null }

// Project
export interface ProjectPublic {
  id: string
  code: string
  name: string
  description: string | null
  subdivision_id: string
  project_type_id: string | null
  is_deleted: boolean
  created_at: string | null
}

export interface ProjectList { data: ProjectPublic[]; count: number }
export interface ProjectCreate { code: string; name: string; description?: string | null; subdivision_id: string; project_type_id?: string | null }
export interface ProjectUpdate { code?: string | null; name?: string | null; description?: string | null; subdivision_id?: string | null; project_type_id?: string | null }

// Phase
export interface PhasePublic {
  id: string
  code: string
  name: string
  subdivision_id: string
  is_deleted: boolean
  created_at: string | null
}

export interface PhaseList { data: PhasePublic[]; count: number }
export interface PhaseCreate { code: string; name: string; subdivision_id: string }
export interface PhaseUpdate { code?: string | null; name?: string | null; subdivision_id?: string | null }

// Blocks
export interface BlocksPublic {
  id: string
  block_name: string
  phase_id: string
  is_deleted: boolean
  created_at: string | null
}

export interface BlocksList { data: BlocksPublic[]; count: number }
export interface BlocksCreate { block_name: string; phase_id: string }
export interface BlocksUpdate { block_name?: string | null; phase_id?: string | null }

// Lots
export interface LotsPublic {
  id: string
  lot_num: number | null
  lot_name: string | null
  blocks_id: string
  category_id: string | null
  is_deleted: boolean
  created_at: string | null
}

export interface LotsList { data: LotsPublic[]; count: number }
export interface LotsCreate { lot_num?: number | null; lot_name?: string | null; blocks_id: string; category_id?: string | null }
export interface LotsUpdate { lot_num?: number | null; lot_name?: string | null; blocks_id?: string | null; category_id?: string | null }

// Category
export interface CategoryPublic {
  id: string
  code: string
  description: string | null
  location: string | null
  is_overhead: boolean | null
  project_id: string
  model_id: string | null
  phase_id: string
  blocks_id: string | null
  owner_id: string | null
  lot_id: string | null
  is_deleted: boolean
  created_at: string | null
}

export interface CategoryList { data: CategoryPublic[]; count: number }
export interface CategoryCreate {
  code: string
  description?: string | null
  location?: string | null
  is_overhead?: boolean | null
  project_id: string
  model_id?: string | null
  phase_id: string
  blocks_id?: string | null
  owner_id?: string | null
  lot_id?: string | null
}

export interface CategoryUpdate {
  code?: string | null
  description?: string | null
  location?: string | null
  is_overhead?: boolean | null
  project_id?: string | null
  model_id?: string | null
  phase_id?: string | null
  blocks_id?: string | null
  owner_id?: string | null
  lot_id?: string | null
}

// Model
export interface ModelPublic {
  id: string
  name: string
  model_type_id: string | null
  is_deleted: boolean
  created_at: string | null
}

export interface ModelList { data: ModelPublic[]; count: number }
export interface ModelCreate { name: string; model_type_id?: string | null }
export interface ModelUpdate { name?: string | null; model_type_id?: string | null }

// ModelTypes
export interface ModelTypesPublic {
  id: string
  name: string | null
  code: string
  additional_options: boolean | null
  is_deleted: boolean
  created_at: string | null
}

export interface ModelTypesList { data: ModelTypesPublic[]; count: number }
export interface ModelTypesCreate { name?: string | null; code: string; additional_options?: boolean | null }
export interface ModelTypesUpdate { name?: string | null; code?: string | null; additional_options?: boolean | null }

// Owner
export interface OwnerPublic {
  id: string
  first_name: string | null
  last_name: string | null
  lot_no: string | null
  block: string | null
  email: string | null
  contact_no: string | null
  is_deleted: boolean
  created_at: string | null
}

export interface OwnerList { data: OwnerPublic[]; count: number }
export interface OwnerCreate { first_name?: string | null; last_name?: string | null; lot_no?: string | null; block?: string | null; email?: string | null; contact_no?: string | null }
export interface OwnerUpdate { first_name?: string | null; last_name?: string | null; lot_no?: string | null; block?: string | null; email?: string | null; contact_no?: string | null }

// EmployeeProjects
export interface EmployeeProjectsPublic {
  id: string
  employee_id: string
  project_id: string
  date: string | null
  rendered_hours: number | null
  task: string | null
  is_assigned: boolean | null
  is_deleted: boolean
  created_at: string | null
}

export interface EmployeeProjectsList { data: EmployeeProjectsPublic[]; count: number }
export interface EmployeeProjectsCreate { employee_id: string; project_id: string; date?: string | null; rendered_hours?: number | null; task?: string | null; is_assigned?: boolean | null }
export interface EmployeeProjectsUpdate { date?: string | null; rendered_hours?: number | null; task?: string | null; is_assigned?: boolean | null }

// EmpTask
export interface EmpTaskPublic {
  id: string
  emp_project_id: string
  task_desc: string | null
  rendered_hours: number | null
  assigned_hours: string | null
  date: string | null
  approved: boolean | null
  is_adjusted: boolean | null
  is_deleted: boolean
  created_at: string | null
}

export interface EmpTaskList { data: EmpTaskPublic[]; count: number }
export interface EmpTaskCreate { emp_project_id: string; task_desc?: string | null; rendered_hours?: number | null; assigned_hours?: string | number | null; date?: string | null; approved?: boolean | null; is_adjusted?: boolean | null }
export interface EmpTaskUpdate { task_desc?: string | null; rendered_hours?: number | null; assigned_hours?: string | number | null; date?: string | null; approved?: boolean | null; is_adjusted?: boolean | null }

// RBAC Role
export interface RolePublic {
  id: string
  code: string
  name: string
  is_system: boolean
  is_active: boolean
  created_at: string | null
}

export interface RoleList { data: RolePublic[]; count: number }
export interface RoleCreate { code: string; name: string; is_active?: boolean }
export interface RoleUpdate { code?: string | null; name?: string | null; is_active?: boolean | null }

export interface PermissionModule {
  view: boolean
  add: boolean
  edit: boolean
  delete: boolean
}

// Dashboard
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

// Shifts
export interface ShiftsPublic {
  id: string
  code: string
  name: string
  start_time: string
  end_time: string
  lunch_break_duration: number
  total_hours_minus_lunch: number
  days_of_week: string[]
  description: string | null
  is_deleted: boolean
  created_at: string | null
  updated_at: string | null
}

export interface ShiftsList { data: ShiftsPublic[]; count: number }
export interface ShiftsCreate { code: string; name: string; start_time?: string; end_time?: string; lunch_break_duration?: number; total_hours_minus_lunch?: number; days_of_week?: string[]; description?: string | null }
export interface ShiftsUpdate { code?: string; name?: string; start_time?: string; end_time?: string; lunch_break_duration?: number; total_hours_minus_lunch?: number; days_of_week?: string[]; description?: string | null }


// Error envelope
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
