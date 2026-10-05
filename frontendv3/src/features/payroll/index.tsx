import { isAxiosError } from 'axios'
import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { useCan } from '@/context/permissions-provider'
import { usePreviewPayroll, useGeneratePayroll, useApprovePayrollRun, useVoidPayrollRun } from '@/lib/api/payroll'
import { useEmployees } from '@/lib/api/employees'
import { useDepartments } from '@/lib/api/departments'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { toast } from 'sonner'
import { saveErrorMessage } from '@/lib/api/save-error'
import type { CutoffType, PayrollEntryPreview, PayrollRunPublic } from '@/lib/api/types'

type Step = 'preview' | 'review' | 'result'

export default function PayrollPage() {
  const canView = useCan('payroll', 'view')
  const canEdit = useCan('payroll', 'edit')
  const canCreate = useCan('payroll', 'add')
  const canApprove = useCan('payroll', 'edit')

  const [generationUncertain, setGenerationUncertain] = useState(false)
  const [generationId, setGenerationId] = useState(() => crypto.randomUUID())
  const [reviewDirty, setReviewDirty] = useState(false)
  const [step, setStep] = useState<Step>('preview')
  const [cutoffType, setCutoffType] = useState<CutoffType>('monthly')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<string>('__all__')
  const [selectedDepartmentId, setSelectedDepartmentId] = useState<string>('__all__')
  const [previewEntries, setPreviewEntries] = useState<PayrollEntryPreview[]>([])
  const [run, setRun] = useState<PayrollRunPublic | null>(null)
  const [missingSalary, setMissingSalary] = useState(false)
  const navigate = useNavigate()

  const { data: employeesData } = useEmployees(1, 100)
  const { data: departmentsData } = useDepartments(1, 100)
  const previewMutation = usePreviewPayroll()
  const generateMutation = useGeneratePayroll()
  const approveMutation = useApprovePayrollRun()
  const voidMutation = useVoidPayrollRun()

  if (!canView) {
    return (
      <div className='flex flex-1 flex-col items-center justify-center gap-4'>
        <p className='text-muted-foreground'>You do not have permission to view payroll.</p>
      </div>
    )
  }

  const handlePreview = async () => {
    if (!dateFrom || !dateTo || dateFrom > dateTo) {
      toast.error('Select a valid date range with the end on or after the start.')
      return
    }
    setMissingSalary(false)
    try {
      const entries = await previewMutation.mutateAsync({
        cutoff_type: cutoffType,
        date_from: dateFrom,
        date_to: dateTo,
        employee_ids: selectedEmployeeId && selectedEmployeeId !== '__all__' ? [selectedEmployeeId] : undefined,
        department_id: selectedDepartmentId === '__all__' ? undefined : selectedDepartmentId,
      })
      setReviewDirty(false)
      setPreviewEntries(entries)
      setGenerationId(crypto.randomUUID())
      setStep('review')
      toast.success(`Preview generated: ${entries.length} entries`)
    } catch (error) {
      const message = saveErrorMessage(error)
      setMissingSalary(/no active salary record|no employees with active salary records/i.test(message))
      toast.error(message)
    }
  }

  const handleGenerate = async () => {
    if (!dateFrom || !dateTo) return
    try {
      const result = await generateMutation.mutateAsync({
        request_id: generationId,
        cutoff_type: cutoffType,
        date_from: dateFrom,
        date_to: dateTo,
        employee_ids: selectedEmployeeId && selectedEmployeeId !== '__all__' ? [selectedEmployeeId] : undefined,
        department_id: selectedDepartmentId === '__all__' ? undefined : selectedDepartmentId,
        entries: previewEntries.map(entry => ({ employee_id: entry.employee_id, overtime_pay: entry.overtime_pay })),
      })
      setRun(result)
      setGenerationUncertain(false)
      setStep('result')
      toast.success('Payroll run generated')
    } catch (error) {
      const status = isAxiosError(error) ? error.response?.status : undefined
      setGenerationUncertain(status === undefined || status >= 500)
      toast.error(saveErrorMessage(error))
    }
  }

  const handleApprove = async () => {
    if (!run) return
    try {
      await approveMutation.mutateAsync(run.id)
      setRun({ ...run, status: 'approved' })
      toast.success('Payroll run approved')
    } catch {
      toast.error('Failed to approve payroll run')
    }
  }

  const handleVoid = async () => {
    if (!run) return
    try {
      await voidMutation.mutateAsync(run.id)
      setRun({ ...run, status: 'void' })
      toast.success('Payroll run voided')
    } catch {
      toast.error('Failed to void payroll run')
    }
  }

  const updateEntry = (index: number, field: keyof PayrollEntryPreview, value: unknown) => {
    setReviewDirty(true)
    setPreviewEntries(prev => prev.map((e, i) => i === index ? { ...e, [field]: value } : e))
  }

  const recalculateReview = async () => {
    try {
      const entries = await previewMutation.mutateAsync({ cutoff_type: cutoffType, date_from: dateFrom, date_to: dateTo,
        employee_ids: selectedEmployeeId === '__all__' ? undefined : [selectedEmployeeId],
        department_id: selectedDepartmentId === '__all__' ? undefined : selectedDepartmentId,
        entries: previewEntries.map(entry => ({ employee_id: entry.employee_id, overtime_pay: entry.overtime_pay })),
      })
      setPreviewEntries(entries)
      setReviewDirty(false)
    } catch { toast.error('Failed to recalculate payroll review') }
  }

  const formatCurrency = (value: string | number) => {
    const num = typeof value === 'string' ? Number(value) : value
    return Number.isFinite(num) ? `₱${num.toLocaleString()}` : '₱0.00'
  }

  return (
    <div className='space-y-4'>
      <div>
        <h1 className='text-2xl font-bold'>Payroll Execution</h1>
        <p className='text-muted-foreground'>Generate and approve payroll runs</p>
        <p className='text-sm text-muted-foreground'>Preview and recalculation currently save draft runs. Review Payroll Runs before generating again.</p>
      </div>

      {step === 'preview' && (
        <div className='space-y-4 rounded-lg border p-4'>
          <div className='grid gap-4 sm:grid-cols-3'>
            <div className='space-y-2'>
              <Label htmlFor='cutoff-type'>Cutoff Type</Label>
              <Select value={cutoffType} onValueChange={(v) => setCutoffType(v as CutoffType)}>
                <SelectTrigger id='cutoff-type' data-testid='cutoff-type-select'>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value='daily'>Daily</SelectItem>
                  <SelectItem value='weekly'>Weekly</SelectItem>
                  <SelectItem value='semi_monthly'>Semi-Monthly</SelectItem>
                  <SelectItem value='monthly'>Monthly</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className='space-y-2'>
              <Label htmlFor='date-from'>Date From</Label>
              <Input id='date-from' type='date' data-testid='date-from-input' value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
            </div>
            <div className='space-y-2'>
              <Label htmlFor='date-to'>Date To</Label>
              <Input id='date-to' type='date' data-testid='date-to-input' value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
            </div>
          </div>
          <div className='grid gap-4 sm:grid-cols-2'>
            <div className='space-y-2'>
              <Label htmlFor='department-filter'>Department</Label>
              <Select value={selectedDepartmentId} onValueChange={setSelectedDepartmentId}>
                <SelectTrigger id='department-filter' data-testid='department-filter-select'>
                  <SelectValue placeholder='All departments' />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value='__all__'>All departments</SelectItem>
                  {(departmentsData?.data ?? []).map((dept) => (
                    <SelectItem key={dept.id} value={dept.id}>{dept.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className='space-y-2'>
              <Label htmlFor='employee-filter'>Employee</Label>
              <Select value={selectedEmployeeId} onValueChange={setSelectedEmployeeId}>
                <SelectTrigger id='employee-filter' data-testid='employee-filter-select'>
                  <SelectValue placeholder='All employees' />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value='__all__'>All employees</SelectItem>
                  {(employeesData?.data ?? []).map((emp) => (
                    <SelectItem key={emp.id} value={emp.id}>{emp.employee_code} — {emp.first_name} {emp.last_name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <Button data-testid='preview-payroll-button' onClick={handlePreview} disabled={previewMutation.isPending}>
            {previewMutation.isPending ? 'Previewing...' : 'Preview Payroll'}
          </Button>
          {missingSalary && (
            <div role='alert' data-testid='missing-salary-recovery' className='flex flex-wrap items-center justify-between gap-3 rounded-md border border-amber-500/40 bg-amber-50 p-4 text-sm dark:bg-amber-950'>
              <span>No active salary is configured for one or more selected employees. Add an effective-dated salary, then return to preview.</span>
              <Button type='button' variant='outline' data-testid='open-salary-setup-button' onClick={() => navigate({ to: '/payroll/salary' })}>
                Open Salary Setup
              </Button>
            </div>
          )}
        </div>
      )}

      {generationUncertain && <p role='alert' data-testid='generation-outcome-unknown'>Generation outcome is unknown. Retry the same reviewed payroll to recover its result safely.</p>}
      {step === 'review' && (
        <div className='space-y-4'>
          <div className='flex items-center justify-between'>
            <h2 className='text-xl font-semibold'>Review Payroll Entries</h2>
            <div className='flex gap-2'>
              <Button variant='outline' disabled={generationUncertain} onClick={() => setStep('preview')}>Back</Button>
              <Button data-testid='recalculate-payroll-button' onClick={recalculateReview} disabled={previewMutation.isPending || generationUncertain}>Recalculate Review</Button>
              <Button data-testid='proceed-to-review-button' onClick={handleGenerate} disabled={generateMutation.isPending || previewMutation.isPending || reviewDirty || !canCreate || previewEntries.length === 0}>
                {generateMutation.isPending ? 'Generating...' : 'Generate Payroll'}
              </Button>
            </div>
          </div>
          {previewEntries.some((e) => e.warnings && e.warnings.length > 0) && (
            <div data-testid='compliance-warnings' className='space-y-2 rounded-lg border border-yellow-200 bg-yellow-50 p-4 dark:border-yellow-900 dark:bg-yellow-950'>
              <h3 className='text-sm font-semibold text-yellow-800 dark:text-yellow-200'>Compliance Warnings</h3>
              <ul className='list-inside list-disc space-y-1 text-sm text-yellow-700 dark:text-yellow-300'>
                {previewEntries.flatMap((entry) =>
                  (entry.warnings ?? []).map((w, i) => (
                    <li key={`${entry.employee_id}-${i}`}>
                      <span className='font-mono'>{entry.employee_id}</span>: <span className='font-mono'>{w.code}</span> — {w.message}
                    </li>
                  )),
                )}
              </ul>
            </div>
          )}
          <div className='overflow-x-auto rounded-lg border'>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Employee ID</TableHead>
                  <TableHead className='text-right'>Basic Rate</TableHead>
                  <TableHead className='text-right'>Overtime Pay</TableHead>
                  <TableHead className='text-right'>Non-Taxable</TableHead>
                  <TableHead className='text-right'>Gross Pay</TableHead>
                  <TableHead className='text-right'>Total Deductions</TableHead>
                  <TableHead className='text-right'>Net Pay</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {previewEntries.map((entry, idx) => (
                  <TableRow key={entry.employee_id}>
                    <TableCell>{entry.employee_id}</TableCell>
                    <TableCell className='text-right'>{formatCurrency(entry.basic_rate)}</TableCell>
                    <TableCell className='text-right'>
                      {canEdit && (
                        <Input
                          type='number'
                          disabled={generationUncertain}
                          className='w-24 text-right'
                          value={Number(entry.overtime_pay)}
                          onChange={(e) => updateEntry(idx, 'overtime_pay', e.target.value)}
                          data-testid={`edit-overtime-${entry.employee_id}`}
                        />
                      )}
                      {!canEdit && formatCurrency(entry.overtime_pay)}
                    </TableCell>
                    <TableCell className='text-right'>{formatCurrency(entry.non_taxable_income)}</TableCell>
                    <TableCell className='text-right'>{formatCurrency(entry.gross_pay)}</TableCell>
                    <TableCell className='text-right'>{formatCurrency(entry.total_deductions)}</TableCell>
                    <TableCell className='text-right font-medium'>{formatCurrency(entry.net_pay)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      )}

      {step === 'result' && run && (
        <div className='space-y-4'>
          <div className='rounded-lg border p-4'>
            <h2 className='text-xl font-semibold'>Payroll Run Generated</h2>
            <p className='text-muted-foreground'>Run ID: {run.id}</p>
            <p className='text-muted-foreground'>Status: {run.status}</p>
            <p className='text-muted-foreground'>Cutoff: {run.cutoff_type} ({run.date_from} → {run.date_to})</p>
            <p className='text-muted-foreground'>Entries: {previewEntries.length}</p>
          </div>
          <div className='flex gap-2'>
            <Button data-testid='view-payslips-button' onClick={() => { window.open(`#/payroll-runs/${run.id}`, '_blank') }}>
              View Payslips
            </Button>
            {canApprove && run.status === 'draft' && (
              <Button data-testid='approve-payroll-run-button' onClick={handleApprove} disabled={approveMutation.isPending}>
                {approveMutation.isPending ? 'Approving...' : 'Approve Run'}
              </Button>
            )}
            {canApprove && run.status === 'draft' && (
              <Button data-testid='void-payroll-run-button' variant='destructive' onClick={handleVoid} disabled={voidMutation.isPending}>
                {voidMutation.isPending ? 'Voiding...' : 'Void Run'}
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
