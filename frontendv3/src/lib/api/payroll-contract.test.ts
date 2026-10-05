import { beforeEach, describe, expect, it, vi } from 'vitest'
const { get, post, patch, del } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), patch: vi.fn(), del: vi.fn() }))
vi.mock('./client', () => ({ api: { get, post, patch, delete: del } }))
import { fetchPayrollRuns, previewPayroll, generatePayroll, fetchEmployeeSalaries, updateEmployeeSalary, deleteEmployeeSalary } from './payroll'
import { fetchSSSBrackets, fetchPhilHealthBrackets, fetchPagIBIGBrackets, fetchBIRBrackets } from './payroll-config'

describe('payroll current backend contracts', () => {
  beforeEach(() => vi.clearAllMocks())
  it('normalizes the salary endpoint raw array response', async () => {
    const rows = [{ id: 'salary-1', employee_id: 'employee-1', basic_rate: '18000.00' }]
    get.mockResolvedValueOnce({ data: rows })
    expect(await fetchEmployeeSalaries('employee-1')).toEqual({ data: rows, count: 1 })
    expect(get).toHaveBeenCalledWith('/payroll/employees/employee-1/salary')
  })
  it('sends salary sparse updates as one request variables object', async () => {
    patch.mockResolvedValueOnce({ data: { id: 'salary-1', employee_id: 'employee-1', basic_rate: '19000.00' } })
    const update = { salary_id: 'salary-1', salary: { basic_rate: '19000.00' } }
    expect(await updateEmployeeSalary(update)).toEqual({ id: 'salary-1', employee_id: 'employee-1', basic_rate: '19000.00' })
    expect(patch).toHaveBeenCalledWith('/payroll/salaries/salary-1', { basic_rate: '19000.00' })
  })
  it('archives only the selected salary and returns the message response', async () => {
    del.mockResolvedValueOnce({ data: { message: 'Employee salary archived' } })
    expect(await deleteEmployeeSalary('salary-1')).toEqual({ message: 'Employee salary archived' })
    expect(del).toHaveBeenCalledWith('/payroll/salaries/salary-1')
  })
  it.each([
    ['/payroll/sss-brackets/', fetchSSSBrackets],
    ['/payroll/philhealth-brackets/', fetchPhilHealthBrackets],
    ['/payroll/pagibig-brackets/', fetchPagIBIGBrackets],
    ['/payroll/bir-brackets/', fetchBIRBrackets],
  ] as const)('uses %s and preserves the backend array', async (path, fetch) => {
    const rows = [{ id: 'one' }, { id: 'two' }]
    get.mockResolvedValueOnce({ data: rows })
    expect(await fetch(0, 20)).toEqual({ data: rows, count: 2 })
    expect(get).toHaveBeenCalledWith(path, { params: { skip: 0, limit: 20, ...(path.includes('bir-brackets') ? { period_type: '' } : {}) } })
  })
  it('adapts the run list array without an extra API prefix', async () => {
    const rows = [{ id: 'draft-run', status: 'draft' }]
    get.mockResolvedValueOnce({ data: rows })
    expect(await fetchPayrollRuns(0, 20)).toEqual({ data: rows, count: 1 })
    expect(get).toHaveBeenCalledWith('/payroll/runs', { params: { skip: 0, limit: 20 } })
  })
  it('extracts preview entries from the transient backend response envelope', async () => {
    const entries = [{ employee_id: 'employee', gross_pay: '12500.00' }]
    post.mockResolvedValueOnce({ data: { payroll_run_id: 'preview-run', entries } })
    const request = { cutoff_type: 'monthly' as const, date_from: '2026-10-01', date_to: '2026-10-31' }
    expect(await previewPayroll(request)).toEqual(entries)
    expect(post).toHaveBeenCalledWith('/payroll/runs/preview', request)
  })
  it('generates through the add-authorized endpoint and carries reviewed overrides', async () => {
    const request = { cutoff_type: 'monthly' as const, date_from: '2026-10-01', date_to: '2026-10-31', entries: [{ employee_id: 'employee', overtime_pay: '500.25' }] }
    post.mockResolvedValueOnce({ data: { id: 'generated-run', status: 'draft' } })
    expect(await generatePayroll({ ...request, request_id: 'generation-request' })).toEqual({ id: 'generated-run', status: 'draft' })
    expect(post).toHaveBeenCalledWith('/payroll/runs/generate', { ...request, request_id: 'generation-request' })
  })
})
