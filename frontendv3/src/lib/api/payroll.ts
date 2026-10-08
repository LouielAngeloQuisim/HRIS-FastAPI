import { isAxiosError } from 'axios'
import {
  keepPreviousData,
  useQuery,
  useMutation,
  useQueryClient,
} from '@tanstack/react-query'
import { api } from './client'
import type {
  CutoffType,
  PayrollAdjustmentType,
  PayrollRunList,
  PayrollRunPublic,
  PayrollRunDetail,
  PayrollEntryPreview,
  EmployeeSalaryList,
  EmployeeSalaryPublic,
  EmployeeSalaryCreate,
  EmployeeSalaryUpdate,
  EmployeeLatestPayroll,
} from './types'

const API = ''

export interface EmployeeTaxYearDeclaration {
  id: string
  employee_id: string
  tax_year: number
  tax_classification: 'ordinary' | 'minimum_wage_earner'
  opening_as_of: string | null
  taxable_compensation_ytd: string
  tax_withheld_ytd: string
  opening_pay_period_count: number
  opening_pay_period_type:
    | 'daily'
    | 'weekly'
    | 'semi_monthly'
    | 'monthly'
    | null
  previous_employer_included: boolean
  source_reference: string | null
  is_verified: boolean
  verified_by: string | null
  verified_at: string | null
  created_at: string | null
  updated_at: string | null
}

export type EmployeeTaxYearDeclarationInput = Pick<
  EmployeeTaxYearDeclaration,
  | 'tax_classification'
  | 'opening_as_of'
  | 'taxable_compensation_ytd'
  | 'tax_withheld_ytd'
  | 'opening_pay_period_count'
  | 'opening_pay_period_type'
  | 'previous_employer_included'
  | 'source_reference'
> & { is_verified: boolean }

export function useEmployeeTaxYearDeclaration(
  employeeId: string,
  taxYear: number
) {
  return useQuery({
    queryKey: ['payroll-tax-year-declaration', employeeId, taxYear],
    queryFn: async () => {
      try {
        return (
          await api.get<EmployeeTaxYearDeclaration>(
            `/payroll/employees/${employeeId}/tax-year-declarations/${taxYear}`
          )
        ).data
      } catch (error) {
        if (isAxiosError(error) && error.response?.status === 404) return null
        throw error
      }
    },
    enabled: Boolean(employeeId && taxYear),
  })
}

export function useSaveEmployeeTaxYearDeclaration(
  employeeId: string,
  taxYear: number
) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: EmployeeTaxYearDeclarationInput) =>
      api
        .put<EmployeeTaxYearDeclaration>(
          `/payroll/employees/${employeeId}/tax-year-declarations/${taxYear}`,
          payload
        )
        .then((response) => response.data),
    onSuccess: () =>
      qc.invalidateQueries({
        queryKey: ['payroll-tax-year-declaration', employeeId, taxYear],
      }),
  })
}

// --- Review / generation payloads ------------------------------------------------
export interface PayrollReviewLoan {
  /** Existing loan id when adding an amortization against a known loan. */
  id?: string
  due_date?: string
  amount: string
}

/**
 * HR edits captured during Step 2 (Review/Edit). The payload is carried to the
 * backend on both recalc (`POST /payroll/runs/preview`) and generation
 * (`POST /payroll/runs/generate`) so generation uses exactly what was reviewed.
 */
export interface PayrollReviewOverride {
  employee_id: string
  overtime_pay?: string
  allowances?: string
  other_earnings?: string
  /** One-time, period-only non-taxable allowance. */
  non_taxable_income?: string
  attendance_deduction_override?: string
  attendance_deduction_reason?: string
  loan_amortizations?: PayrollReviewLoan[]
}

export interface PayrollPreviewPayload {
  cutoff_type: CutoffType
  date_from: string
  date_to: string
  adjustment_type?: PayrollAdjustmentType
  /** Reviewed per-employee overrides; backend must honour them for consistency. */
  entries?: PayrollReviewOverride[]
  employee_ids?: string[]
  department_id?: string
}

export interface PayrollEntryWarning {
  code: string
  message: string
}

/** Preview entry plus backend-provided compliance warnings when available. */
export type PayrollPreviewEntry = PayrollEntryPreview & {
  warnings?: PayrollEntryWarning[]
}

// --- Payslips --------------------------------------------------------------------
export interface PayrollPayslip {
  employee_id: string
  employee_code: string
  full_name: string
  gross_pay: number
  total_deductions: number
  net_pay: number
  overtime_pay: number
  thirteenth_month: number
  non_taxable_income: number
  taxable_income: number
}

export interface EmployeePayslip extends PayrollPayslip {
  run_id: string
}

// --- Payroll Runs ---------------------------------------------------------------
export const payrollRunsKey = (skip: number, limit: number) => [
  'payroll-runs',
  skip,
  limit,
]

export async function fetchPayrollRuns(
  skip: number,
  limit: number
): Promise<PayrollRunList> {
  const { data } = await api.get<PayrollRunPublic[]>(`${API}/payroll/runs`, {
    params: { skip, limit },
  })
  return { data, count: data.length }
}

export function usePayrollRuns(skip: number, limit: number) {
  return useQuery({
    queryKey: payrollRunsKey(skip, limit),
    queryFn: () => fetchPayrollRuns(skip, limit),
    placeholderData: keepPreviousData,
  })
}

export function usePayrollRun(id: string | undefined) {
  return useQuery({
    queryKey: ['payroll-runs', id],
    queryFn: () =>
      api
        .get<PayrollRunDetail>(`${API}/payroll/runs/${id}`)
        .then((r) => r.data),
    enabled: Boolean(id),
  })
}

export interface PayrollReviewActionResult {
  run_id: string
  entry_id: string | null
  workflow_status: string
  reviewed_count: number
  excluded_count: number
  unresolved_count: number
}

function usePayrollReviewMutation<TPayload>(
  mutationFn: (payload: TPayload) => Promise<PayrollReviewActionResult>,
  runId: string
) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ['payroll-runs', runId] }),
        qc.invalidateQueries({ queryKey: ['payroll-runs'] }),
      ])
    },
  })
}

export function useStartPayrollReview(runId: string) {
  return usePayrollReviewMutation(
    () =>
      api
        .post<PayrollReviewActionResult>(`/payroll/runs/${runId}/start-review`)
        .then((r) => r.data),
    runId
  )
}

export function useRebuildAttendancePayrollDraft(runId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: {
      expected_run_fingerprint: string
      reason: string
    }) =>
      api
        .post<PayrollRunPublic>(
          `/payroll/runs/${runId}/rebuild-attendance-draft`,
          payload
        )
        .then((r) => r.data),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ['payroll-runs', runId] }),
        qc.invalidateQueries({ queryKey: ['payroll-runs'] }),
      ])
    },
  })
}

export function useReviewPayrollEntry(runId: string) {
  return usePayrollReviewMutation(
    (payload: {
      entryId: string
      action: 'reviewed' | 'excluded'
      expected_input_fingerprint: string
      reason?: string
    }) =>
      api
        .post<PayrollReviewActionResult>(
          `/payroll/runs/${runId}/entries/${payload.entryId}/review`,
          {
            action: payload.action,
            expected_input_fingerprint: payload.expected_input_fingerprint,
            reason: payload.reason,
          }
        )
        .then((r) => r.data),
    runId
  )
}

export function useFinalizePayrollRun(runId: string) {
  return usePayrollReviewMutation(
    () =>
      api
        .post<PayrollReviewActionResult>(`/payroll/runs/${runId}/finalize`)
        .then((r) => r.data),
    runId
  )
}

export interface PayrollDeliveryStatus {
  id: string
  payroll_entry_id: string
  document_version: number
  recipient_snapshot: string | null
  status: 'scheduled' | 'sent' | 'failed' | 'uncertain' | 'blocked_email'
  attempts: number
  next_attempt_at: string | null
  sent_at: string | null
  last_error_code: string | null
  last_action_reason: string | null
}

export async function downloadPayrollPayslip(
  runId: string,
  entryId: string
): Promise<void> {
  const response = await api.get<Blob>(
    `/payroll/runs/${runId}/entries/${entryId}/payslip.pdf`,
    { responseType: 'blob' }
  )
  const objectUrl = URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = `payslip-${entryId}.pdf`
  link.click()
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
}

export function usePayrollDeliveryStatus(runId: string, enabled = true) {
  return useQuery({
    queryKey: ['payroll-delivery-status', runId],
    queryFn: () =>
      api
        .get<PayrollDeliveryStatus[]>(
          `/payroll/runs/${runId}/delivery-status`,
          {
            params: { skip: 0, limit: 200 },
          }
        )
        .then((response) => response.data),
    enabled: Boolean(runId && enabled),
  })
}

function usePayrollDeliveryAction<TPayload>(
  runId: string,
  action: (jobId: string, payload: TPayload) => Promise<PayrollDeliveryStatus>
) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ jobId, payload }: { jobId: string; payload: TPayload }) =>
      action(jobId, payload),
    onSuccess: async () => {
      await qc.invalidateQueries({
        queryKey: ['payroll-delivery-status', runId],
      })
    },
  })
}

export function useCorrectPayrollDeliveryAddress(runId: string) {
  return usePayrollDeliveryAction(
    runId,
    (jobId, payload: { email: string; reason: string }) =>
      api
        .post<PayrollDeliveryStatus>(
          `/payroll/runs/${runId}/delivery/${jobId}/address`,
          payload
        )
        .then((response) => response.data)
  )
}

export function useResendPayrollDelivery(runId: string) {
  return usePayrollDeliveryAction(
    runId,
    (jobId, payload: { reason: string; confirm_duplicate_risk: boolean }) =>
      api
        .post<PayrollDeliveryStatus>(
          `/payroll/runs/${runId}/delivery/${jobId}/resend`,
          payload
        )
        .then((response) => response.data)
  )
}

export async function previewPayroll(
  data: PayrollPreviewPayload
): Promise<PayrollPreviewEntry[]> {
  const response = await api.post<{ entries: PayrollPreviewEntry[] }>(
    '/payroll/runs/preview',
    data
  )
  return response.data.entries
}

export async function generatePayroll(
  data: PayrollPreviewPayload & { request_id: string }
): Promise<PayrollRunPublic> {
  const response = await api.post<PayrollRunPublic>(
    '/payroll/runs/generate',
    data
  )
  return response.data
}

export function usePreviewPayroll() {
  return useMutation({
    mutationFn: previewPayroll,
    onError: () => {}, // The payroll page displays the actionable error once.
  })
}

export function useGeneratePayroll() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: generatePayroll,
    onError: () => {}, // The page owns generation and unknown-outcome errors.
    onSuccess: () => qc.invalidateQueries({ queryKey: ['payroll-runs'] }),
  })
}

export function useApprovePayrollRun() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      api
        .post<PayrollRunPublic>(`${API}/payroll/runs/${id}/approve`)
        .then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['payroll-runs'] }),
  })
}

export function useVoidPayrollRun() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      api
        .post<PayrollRunPublic>(`${API}/payroll/runs/${id}/void`)
        .then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['payroll-runs'] }),
  })
}

export interface PayrollPayGroup {
  id: string
  code: string
  name: string
  cadence: CutoffType
  first_period_end_day: number | null
  second_period_end_day: number | null
  payment_offset_days: number
  weekend_rule: string
  is_active: boolean
}

export interface PayrollPayPeriod {
  pay_group_id: string
  date_from: string
  date_to: string
  payment_date: string
  cadence: CutoffType
}

export function usePayGroupPeriods(groupId: string, month: string) {
  return useQuery({
    queryKey: ['payroll-pay-groups', groupId, 'periods', month],
    queryFn: () =>
      api
        .get<
          PayrollPayPeriod[]
        >(`/payroll/pay-groups/${groupId}/periods`, { params: { month } })
        .then((r) => r.data),
    enabled: Boolean(groupId && month),
  })
}

export interface EmployeePayGroupAssignment {
  id: string
  employee_id: string
  pay_group_id: string
  effective_from: string
  effective_to: string | null
}

export interface EmployeePayGroupAssignmentCreate {
  employee_id: string
  pay_group_id: string
  effective_from: string
  effective_to: string | null
}

export interface EmployeePayGroupBulkRequest {
  batch_id: string
  pay_group_id: string
  effective_from: string
  employee_ids: string[]
}

export interface EmployeePayGroupBulkIssue {
  row_index: number
  employee_id: string
  code: string
  message: string
}

export interface EmployeePayGroupBulkPreflight {
  batch_id: string
  valid: boolean
  requested: number
  replayed: boolean
  issues: EmployeePayGroupBulkIssue[]
}

export interface EmployeePayGroupBulkCommit {
  batch_id: string
  replayed: boolean
  assignments: EmployeePayGroupAssignment[]
}

export interface PayrollPolicyVersion {
  id: string
  version: number
  effective_from: string
  effective_to: string | null
  policy: Record<string, unknown>
  confirmed: boolean
}

export interface PayrollSalaryRosterItem {
  employee_id: string
  employee_code: string
  first_name: string
  last_name: string
  employee_status: string
  has_effective_salary: boolean
}

export interface SalaryBulkRow {
  employee_id: string
  basic_rate: string
  pay_type: 'hourly' | 'daily' | 'monthly'
  overtime_rate: string
  non_taxable_allowance: string
}

export interface SalaryBulkRequest {
  batch_id: string
  effective_date: string
  rows: SalaryBulkRow[]
}

export interface SalaryBulkIssue {
  row_index: number
  employee_id: string
  code: string
  message: string
}

export interface SalaryBulkPreflight {
  batch_id: string
  valid: boolean
  requested: number
  issues: SalaryBulkIssue[]
}

export interface SalaryBulkCommit {
  batch_id: string
  replayed: boolean
  salaries: EmployeeSalaryPublic[]
}

export interface PayrollRunPreflightEmployee {
  employee_id: string
  employee_code: string
  employee_name: string
  email: string | null
  blockers: { code: string; message: string; work_date: string | null }[]
  warnings: string[]
  attendance_records: number
  eligible_overtime_minutes: number
  approved_overtime_minutes: number
}

export interface PayrollRunPreflight {
  pay_group_id: string
  date_from: string
  date_to: string
  policy_versions: number[]
  entries: PayrollRunPreflightEmployee[]
  count: number
  blocked_count: number
  ready_count: number
  has_more: boolean
}

export interface PayrollAttendanceCalculationPreview {
  pay_group_id: string
  date_from: string
  date_to: string
  calculation_status: 'provisional_earnings_only'
  entries: {
    employee_id: string
    employee_code: string
    employee_name: string
    regular_earnings: string | null
    approved_overtime: string | null
    attendance_deduction: string | null
    gross_before_statutory: string | null
    blockers: { code: string; message: string; work_date: string | null }[]
    formula: string[]
    source_references: string[]
  }[]
  count: number
  has_more: boolean
}

export function usePayrollRunPreflight() {
  return useMutation({
    mutationFn: (params: {
      pay_group_id: string
      date_from: string
      date_to: string
      skip?: number
      limit?: number
    }) =>
      api
        .get<PayrollRunPreflight>('/payroll/runs/preflight', { params })
        .then((response) => response.data),
  })
}

export function usePayrollAttendanceCalculationPreview() {
  return useMutation({
    mutationFn: (params: {
      pay_group_id: string
      date_from: string
      date_to: string
      skip?: number
      limit?: number
    }) =>
      api
        .get<PayrollAttendanceCalculationPreview>(
          '/payroll/runs/attendance-calculation-preview',
          { params }
        )
        .then((response) => response.data),
  })
}

export function usePrepareAttendancePayrollDraft() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: {
      pay_group_id: string
      date_from: string
      date_to: string
    }) =>
      api
        .post<PayrollRunPublic>('/payroll/runs/prepare-attendance-draft', data)
        .then((response) => response.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['payroll-runs'] }),
    onError: () => {}, // The payroll page presents the actionable API message.
  })
}

export function useBulkSalary() {
  const qc = useQueryClient()
  const preflight = useMutation({
    mutationFn: (request: SalaryBulkRequest) =>
      api
        .post<SalaryBulkPreflight>('/payroll/salaries/bulk/preflight', request)
        .then((r) => r.data),
  })
  const commit = useMutation({
    mutationFn: (request: SalaryBulkRequest) =>
      api
        .post<SalaryBulkCommit>('/payroll/salaries/bulk/commit', request)
        .then((r) => r.data),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['payroll-salary-roster'] })
      await qc.invalidateQueries({ queryKey: ['salary'] })
    },
  })
  return { preflight, commit }
}

export function useSalaryRoster(missingSalary: boolean) {
  return useQuery({
    queryKey: ['payroll-salary-roster', missingSalary],
    queryFn: () =>
      api
        .get<{
          data: PayrollSalaryRosterItem[]
          count: number
        }>('/payroll/salary-roster', {
          params: { missing_salary: missingSalary, limit: 500 },
        })
        .then((r) => r.data),
  })
}

export function useEmployeePayGroupAssignments(employeeId: string) {
  return useQuery({
    queryKey: ['payroll-pay-group-assignments', employeeId],
    queryFn: () =>
      api
        .get<
          EmployeePayGroupAssignment[]
        >('/payroll/pay-group-assignments', { params: { employee_id: employeeId, limit: 100 } })
        .then((r) => r.data),
    enabled: Boolean(employeeId),
  })
}

export function usePayrollSetup() {
  const qc = useQueryClient()
  const groups = useQuery({
    queryKey: ['payroll-pay-groups'],
    queryFn: () =>
      api.get<PayrollPayGroup[]>('/payroll/pay-groups').then((r) => r.data),
  })
  const policies = useQuery({
    queryKey: ['payroll-policies'],
    queryFn: () =>
      api.get<PayrollPolicyVersion[]>('/payroll/policies').then((r) => r.data),
  })
  const assignments = useQuery({
    queryKey: ['payroll-pay-group-assignments'],
    queryFn: () =>
      api
        .get<EmployeePayGroupAssignment[]>('/payroll/pay-group-assignments')
        .then((r) => r.data),
  })
  const createGroup = useMutation({
    mutationFn: (payload: Omit<PayrollPayGroup, 'id' | 'is_active'>) =>
      api.post('/payroll/pay-groups', payload).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['payroll-pay-groups'] }),
  })
  const assignGroup = useMutation({
    mutationFn: (payload: EmployeePayGroupAssignmentCreate) =>
      api.post('/payroll/pay-group-assignments', payload).then((r) => r.data),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ['payroll-pay-group-assignments'] }),
  })
  const createPolicy = useMutation({
    mutationFn: (payload: {
      effective_from: string
      policy: Record<string, unknown>
    }) =>
      api
        .post<PayrollPolicyVersion>('/payroll/policies', payload)
        .then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['payroll-policies'] }),
  })
  const confirmPolicy = useMutation({
    mutationFn: (id: string) =>
      api
        .post<PayrollPolicyVersion>(`/payroll/policies/${id}/confirm`)
        .then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['payroll-policies'] }),
  })
  return {
    groups,
    policies,
    assignments,
    createGroup,
    assignGroup,
    createPolicy,
    confirmPolicy,
  }
}

export function usePayGroupList() {
  return useQuery({
    queryKey: ['payroll-pay-groups'],
    queryFn: () =>
      api.get<PayrollPayGroup[]>('/payroll/pay-groups').then((r) => r.data),
  })
}

export function useBulkPayGroupAssignments() {
  const qc = useQueryClient()
  const preflight = useMutation({
    mutationFn: (request: EmployeePayGroupBulkRequest) =>
      api
        .post<EmployeePayGroupBulkPreflight>(
          '/payroll/pay-group-assignments/bulk/preflight',
          request
        )
        .then((r) => r.data),
  })
  const commit = useMutation({
    mutationFn: (request: EmployeePayGroupBulkRequest) =>
      api
        .post<EmployeePayGroupBulkCommit>(
          '/payroll/pay-group-assignments/bulk/commit',
          request
        )
        .then((r) => r.data),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['payroll-pay-group-assignments'] })
      await qc.invalidateQueries({ queryKey: ['payroll-runs'] })
    },
  })
  return { preflight, commit }
}

// -----------------------------------------------------------------------------
// Employee Salary Management (PAY-03)
// -----------------------------------------------------------------------------

export const salaryKey = (employeeId: string) => ['salary', employeeId]

export async function fetchEmployeeSalaries(
  employeeId: string
): Promise<EmployeeSalaryList> {
  const { data } = await api.get<EmployeeSalaryPublic[]>(
    `/payroll/employees/${employeeId}/salary`
  )
  // Backend returns a raw array, not an envelope; normalize to the UI contract.
  return { data, count: data.length }
}

export function useEmployeeSalaries(employeeId: string | undefined) {
  return useQuery({
    queryKey: salaryKey(employeeId ?? 'none'),
    queryFn: () => fetchEmployeeSalaries(employeeId as string),
    enabled: Boolean(employeeId),
    placeholderData: keepPreviousData,
  })
}

export function useEmployeeLatestPayroll(employeeId: string | undefined) {
  return useQuery({
    queryKey: ['employee-latest-payroll', employeeId ?? 'none'],
    queryFn: async () => {
      try {
        return (
          await api.get<EmployeeLatestPayroll | null>(
            `/payroll/employees/${employeeId}/payslip`
          )
        ).data
      } catch (error) {
        if (isAxiosError(error) && error.response?.status === 404) return null
        throw error
      }
    },
    enabled: Boolean(employeeId),
  })
}

export async function createEmployeeSalary(
  salary: EmployeeSalaryCreate
): Promise<EmployeeSalaryPublic> {
  const response = await api.post<EmployeeSalaryPublic>(
    `/payroll/employees/${salary.employee_id}/salary`,
    salary
  )
  return response.data
}

export async function updateEmployeeSalary({
  salary_id,
  salary,
}: {
  salary_id: string
  salary: EmployeeSalaryUpdate
}): Promise<EmployeeSalaryPublic> {
  const response = await api.patch<EmployeeSalaryPublic>(
    `/payroll/salaries/${salary_id}`,
    salary
  )
  return response.data
}

export async function deleteEmployeeSalary(
  salary_id: string
): Promise<{ message: string }> {
  const response = await api.delete<{ message: string }>(
    `/payroll/salaries/${salary_id}`
  )
  return response.data
}

export function useCreateSalary() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createEmployeeSalary,
    onSuccess: async (_, { employee_id }) => {
      await qc.invalidateQueries({ queryKey: salaryKey(employee_id) })
      await qc.invalidateQueries({ queryKey: ['payroll-salary-roster'] })
    },
  })
}

export function useUpdateSalary() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: updateEmployeeSalary,
    onSuccess: async (updated) => {
      await qc.invalidateQueries({
        queryKey: salaryKey(updated.employee_id ?? ''),
      })
      await qc.invalidateQueries({ queryKey: ['payroll-salary-roster'] })
    },
  })
}

export function useDeleteSalary() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ salary_id }: { salary_id: string; employee_id: string }) =>
      deleteEmployeeSalary(salary_id),
    onSuccess: (_, { employee_id }) =>
      qc.invalidateQueries({ queryKey: salaryKey(employee_id) }),
  })
}
