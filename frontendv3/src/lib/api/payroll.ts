import { keepPreviousData, useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type {
  CutoffType,
  PayrollAdjustmentType,
  PayrollRunList,
  PayrollRunPublic,
  PayrollRunDetail,
  PayrollEntryPreview,
} from './types'

const API = ''

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
export type PayrollPreviewEntry = PayrollEntryPreview & { warnings?: PayrollEntryWarning[] }

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
export const payrollRunsKey = (skip: number, limit: number) => ['payroll-runs', skip, limit]

export async function fetchPayrollRuns(skip: number, limit: number): Promise<PayrollRunList> {
  const { data } = await api.get<PayrollRunPublic[]>(`${API}/payroll/runs`, { params: { skip, limit } })
  return { data, count: data.length }
}

export function usePayrollRuns(skip: number, limit: number) {
  return useQuery({ queryKey: payrollRunsKey(skip, limit), queryFn: () => fetchPayrollRuns(skip, limit), placeholderData: keepPreviousData })
}

export function usePayrollRun(id: string | undefined) {
  return useQuery({ queryKey: ['payroll-runs', id], queryFn: () => api.get<PayrollRunDetail>(`${API}/payroll/runs/${id}`).then(r => r.data), enabled: Boolean(id) })
}

export async function previewPayroll(data: PayrollPreviewPayload): Promise<PayrollPreviewEntry[]> {
  const response = await api.post<{ entries: PayrollPreviewEntry[] }>('/payroll/runs/preview', data)
  return response.data.entries
}

export async function generatePayroll(data: PayrollPreviewPayload): Promise<PayrollRunPublic> {
  const response = await api.post<PayrollRunPublic>('/payroll/runs/generate', data)
  return response.data
}

export function usePreviewPayroll() {
  return useMutation({
    mutationFn: previewPayroll,
  })
}

export function useGeneratePayroll() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: generatePayroll,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['payroll-runs'] }),
  })
}

export function useApprovePayrollRun() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (id: string) => api.post<PayrollRunPublic>(`${API}/payroll/runs/${id}/approve`).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['payroll-runs'] }) })
}

export function useVoidPayrollRun() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (id: string) => api.post<PayrollRunPublic>(`${API}/payroll/runs/${id}/void`).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['payroll-runs'] }) })
}
