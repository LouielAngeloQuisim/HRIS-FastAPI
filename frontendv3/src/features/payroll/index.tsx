import { useState } from 'react'
import { toast } from 'sonner'
import {
  useCreatePayrollContributionCorrection,
  usePayrollAttendanceCalculationPreview,
  usePayrollContributionCorrectionTargets,
  usePayrollContributionLedger,
  usePayrollRunPreflight,
  usePayrollSetup,
  usePrepareAttendancePayrollDraft,
  type PayrollAttendanceCalculationPreview,
  type PayrollContributionLedgerRow,
  type PayrollRunPreflight,
} from '@/lib/api/payroll'
import { saveErrorMessage } from '@/lib/api/save-error'
import { useCan } from '@/context/permissions-provider'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

const PAGE_SIZE = 100

function ContributionCorrectionForm({
  row,
}: {
  row: PayrollContributionLedgerRow
}) {
  const [open, setOpen] = useState(false)
  const [targetEntryId, setTargetEntryId] = useState('')
  const [employeeAmount, setEmployeeAmount] = useState('0.00')
  const [employerAmount, setEmployerAmount] = useState('0.00')
  const [birWithholdingDelta, setBirWithholdingDelta] = useState('0.00')
  const [taxReviewReference, setTaxReviewReference] = useState('')
  const [reason, setReason] = useState('')
  const [sourceReference, setSourceReference] = useState('')
  const targets = usePayrollContributionCorrectionTargets(row.id, open)
  const correction = useCreatePayrollContributionCorrection()

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!targetEntryId) {
      toast.error('Choose a later draft payroll for this employee.')
      return
    }
    try {
      await correction.mutateAsync({
        source_ledger_id: row.id,
        target_entry_id: targetEntryId,
        employee_amount: employeeAmount,
        employer_amount: employerAmount,
        bir_withholding_delta: birWithholdingDelta,
        tax_review_reference: taxReviewReference,
        reason,
        source_reference: sourceReference,
      })
      toast.success(
        'Contribution correction added to the draft; review it again.'
      )
      setOpen(false)
      setTargetEntryId('')
      setEmployeeAmount('0.00')
      setEmployerAmount('0.00')
      setBirWithholdingDelta('0.00')
      setTaxReviewReference('')
      setReason('')
      setSourceReference('')
    } catch (error) {
      toast.error(saveErrorMessage(error))
    }
  }

  return (
    <div className='mt-2'>
      <Button
        type='button'
        size='sm'
        variant='outline'
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        {open ? 'Close correction' : 'Correct in later draft'}
      </Button>
      {open && (
        <form className='mt-2 grid min-w-64 gap-2' onSubmit={submit}>
          <label className='grid gap-1 text-xs'>
            Later payroll draft
            <select
              className='h-9 rounded-md border bg-background px-2 text-sm'
              value={targetEntryId}
              onChange={(event) => setTargetEntryId(event.target.value)}
              required
            >
              <option value=''>Select a draft</option>
              {(targets.data ?? []).map((target) => (
                <option key={target.entry_id} value={target.entry_id}>
                  {target.date_from} to {target.date_to} · {target.review_state}
                </option>
              ))}
            </select>
          </label>
          {targets.isPending && (
            <p role='status' className='text-xs'>
              Loading eligible drafts…
            </p>
          )}
          {targets.isError && (
            <p role='alert' className='text-xs text-destructive'>
              {saveErrorMessage(targets.error)}
            </p>
          )}
          {targets.data?.length === 0 && (
            <p className='text-xs text-muted-foreground'>
              No later unreviewed payroll draft is available for this employee.
            </p>
          )}
          <label className='grid gap-1 text-xs'>
            Employee contribution change
            <Input
              type='number'
              step='0.01'
              value={employeeAmount}
              onChange={(event) => setEmployeeAmount(event.target.value)}
            />
          </label>
          <label className='grid gap-1 text-xs'>
            Employer contribution change
            <Input
              type='number'
              step='0.01'
              value={employerAmount}
              onChange={(event) => setEmployerAmount(event.target.value)}
            />
          </label>
          <label className='grid gap-1 text-xs'>
            Reviewed BIR withholding change
            <Input
              type='number'
              step='0.01'
              value={birWithholdingDelta}
              onChange={(event) => setBirWithholdingDelta(event.target.value)}
            />
          </label>
          <label className='grid gap-1 text-xs'>
            BIR tax review reference (required for employee correction)
            <Input
              value={taxReviewReference}
              minLength={3}
              required={Number(employeeAmount) !== 0}
              onChange={(event) => setTaxReviewReference(event.target.value)}
            />
          </label>
          <label className='grid gap-1 text-xs'>
            Reason
            <Input
              value={reason}
              minLength={5}
              onChange={(event) => setReason(event.target.value)}
              required
            />
          </label>
          <label className='grid gap-1 text-xs'>
            Reconciliation reference
            <Input
              value={sourceReference}
              minLength={3}
              onChange={(event) => setSourceReference(event.target.value)}
              required
            />
          </label>
          <Button
            type='submit'
            size='sm'
            disabled={
              !targets.data?.length ||
              !targetEntryId ||
              correction.isPending ||
              (Number(employeeAmount) !== 0 && !taxReviewReference.trim())
            }
          >
            {correction.isPending ? 'Saving correction…' : 'Apply to draft'}
          </Button>
          <p className='text-xs text-muted-foreground'>
            Enter a signed delta. Negative employee amounts return an
            over-collection through the next payslip; positive amounts add a
            deduction. Employee contribution changes also adjust taxable
            compensation and require the separately reviewed BIR withholding
            change. Finalized payroll is never changed.
          </p>
        </form>
      )}
    </div>
  )
}

export default function PayrollPage() {
  const canView = useCan('payroll', 'view')
  const canAdd = useCan('payroll', 'add')
  const canEdit = useCan('payroll', 'edit')
  const setup = usePayrollSetup()
  const preflightMutation = usePayrollRunPreflight()
  const calculationMutation = usePayrollAttendanceCalculationPreview()
  const prepareMutation = usePrepareAttendancePayrollDraft()
  const [payGroupId, setPayGroupId] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [page, setPage] = useState(0)
  const [preflight, setPreflight] = useState<PayrollRunPreflight | null>(null)
  const [calculation, setCalculation] =
    useState<PayrollAttendanceCalculationPreview | null>(null)
  const [preparedRunId, setPreparedRunId] = useState<string | null>(null)
  const [ledgerMonth, setLedgerMonth] = useState('')
  const [ledgerScheme, setLedgerScheme] = useState('')
  const [ledgerEmployeeCode, setLedgerEmployeeCode] = useState('')
  const [ledgerPage, setLedgerPage] = useState(0)
  const ledger = usePayrollContributionLedger({
    month: ledgerMonth,
    scheme: ledgerScheme,
    employeeCode: ledgerEmployeeCode,
    skip: ledgerPage * PAGE_SIZE,
  })

  const clearResults = () => {
    setPreflight(null)
    setCalculation(null)
    setPreparedRunId(null)
    setPage(0)
  }

  const checkReadiness = async (targetPage = page) => {
    if (!payGroupId || !dateFrom || !dateTo) {
      toast.error('Select a pay group and earning period.')
      return
    }
    try {
      const result = await preflightMutation.mutateAsync({
        pay_group_id: payGroupId,
        date_from: dateFrom,
        date_to: dateTo,
        skip: targetPage * PAGE_SIZE,
        limit: PAGE_SIZE,
      })
      setPreflight(result)
      setPage(targetPage)
      toast.success(
        `Readiness checked: ${result.ready_count} ready, ${result.blocked_count} blocked on this page.`
      )
    } catch (error) {
      setPreflight(null)
      toast.error(saveErrorMessage(error))
    }
  }

  const previewAttendanceEarnings = async () => {
    if (!payGroupId || !dateFrom || !dateTo) {
      toast.error('Select a pay group and earning period.')
      return
    }
    try {
      const result = await calculationMutation.mutateAsync({
        pay_group_id: payGroupId,
        date_from: dateFrom,
        date_to: dateTo,
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      })
      setCalculation(result)
      toast.success(
        `Provisional earnings previewed for ${result.entries.length} employees.`
      )
    } catch (error) {
      setCalculation(null)
      toast.error(saveErrorMessage(error))
    }
  }

  const prepareDraft = async () => {
    if (!payGroupId || !dateFrom || !dateTo) return
    try {
      const run = await prepareMutation.mutateAsync({
        pay_group_id: payGroupId,
        date_from: dateFrom,
        date_to: dateTo,
      })
      setPreparedRunId(run.id)
      toast.success(
        `Blocked draft ${run.id.slice(0, 8)} is saved for traceability.`
      )
    } catch (error) {
      toast.error(saveErrorMessage(error))
    }
  }

  if (!canView) {
    return (
      <div className='p-6 text-muted-foreground'>
        You do not have permission to view payroll.
      </div>
    )
  }

  return (
    <main className='space-y-5 p-6'>
      <header>
        <h1 className='text-2xl font-bold'>Payroll readiness</h1>
        <p className='text-muted-foreground'>
          Check the expected employee roster, attendance, compensation setup and
          blockers for one configured earning period.
        </p>
      </header>

      <section
        className='space-y-3 rounded-lg border p-4'
        aria-label='Monthly statutory contribution ledger'
      >
        <div>
          <h2 className='text-lg font-semibold'>Contribution reconciliation</h2>
          <p className='text-sm text-muted-foreground'>
            Read-only finalized monthly collections and linked correction
            records. Corrections never rewrite a finalized payslip.
          </p>
        </div>
        <div className='flex flex-wrap items-end gap-3'>
          <label className='grid gap-1 text-sm'>
            Contribution month
            <Input
              data-testid='payroll-ledger-month'
              type='month'
              value={ledgerMonth}
              onChange={(event) => {
                setLedgerMonth(event.target.value)
                setLedgerPage(0)
              }}
            />
          </label>
          <label className='grid gap-1 text-sm'>
            Employee code
            <Input
              data-testid='payroll-ledger-employee-code'
              value={ledgerEmployeeCode}
              onChange={(event) => {
                setLedgerEmployeeCode(event.target.value)
                setLedgerPage(0)
              }}
            />
          </label>
          <label className='grid gap-1 text-sm'>
            Scheme
            <Select
              value={ledgerScheme || 'all'}
              onValueChange={(value) => {
                setLedgerScheme(value === 'all' ? '' : value)
                setLedgerPage(0)
              }}
            >
              <SelectTrigger data-testid='payroll-ledger-scheme'>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value='all'>All schemes</SelectItem>
                <SelectItem value='sss'>SSS</SelectItem>
                <SelectItem value='philhealth'>PhilHealth</SelectItem>
                <SelectItem value='pagibig'>Pag-IBIG</SelectItem>
              </SelectContent>
            </Select>
          </label>
        </div>
        {!ledgerMonth && (
          <p className='text-sm text-muted-foreground'>
            Choose a month to view finalized contribution records.
          </p>
        )}
        {ledger.isError && (
          <p role='alert' className='text-sm text-destructive'>
            Contribution records could not be loaded.
          </p>
        )}
        {ledgerMonth && ledger.isPending && (
          <p role='status' className='text-sm'>
            Loading contribution records…
          </p>
        )}
        {ledgerMonth && ledger.data && (
          <>
            <div className='max-h-[28rem] overflow-auto rounded-md border'>
              <table className='w-full text-sm'>
                <thead className='sticky top-0 bg-muted'>
                  <tr>
                    <th className='p-2 text-left'>Employee</th>
                    <th className='p-2 text-left'>Scheme / type</th>
                    <th className='p-2 text-right'>Basis</th>
                    <th className='p-2 text-right'>Employee</th>
                    <th className='p-2 text-right'>Employer</th>
                    <th className='p-2 text-left'>Source / correction</th>
                  </tr>
                </thead>
                <tbody>
                  {ledger.data.data.map((row) => (
                    <tr key={row.id} className='border-t align-top'>
                      <td className='p-2'>
                        {row.employee_code} · {row.employee_name}
                      </td>
                      <td className='p-2'>
                        {row.scheme.toUpperCase()}
                        {row.sequence > 0 && (
                          <span className='block text-amber-700'>
                            Correction
                          </span>
                        )}
                      </td>
                      <td className='p-2 text-right'>₱{row.monthly_basis}</td>
                      <td className='p-2 text-right'>₱{row.employee_amount}</td>
                      <td className='p-2 text-right'>₱{row.employer_amount}</td>
                      <td className='space-y-1 p-2'>
                        {row.adjustment_reason && (
                          <p>{row.adjustment_reason}</p>
                        )}
                        {row.reverses_id && (
                          <p className='text-xs text-muted-foreground'>
                            Reverses {row.reverses_id}
                          </p>
                        )}
                        {row.source_references.map((source) =>
                          /^https?:\/\//i.test(source) ? (
                            <a
                              key={source}
                              href={source}
                              target='_blank'
                              rel='noreferrer'
                              className='block text-xs break-all underline'
                            >
                              Source
                            </a>
                          ) : (
                            <p key={source} className='text-xs break-all'>
                              Reference: {source}
                            </p>
                          )
                        )}
                        {canEdit && row.sequence === 0 && (
                          <ContributionCorrectionForm key={row.id} row={row} />
                        )}
                      </td>
                    </tr>
                  ))}
                  {!ledger.data.data.length && (
                    <tr>
                      <td
                        colSpan={6}
                        className='p-4 text-center text-muted-foreground'
                      >
                        No finalized contribution records match this month.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            <div className='flex items-center justify-between text-sm'>
              <span>{ledger.data.count} finalized records</span>
              <div className='flex gap-2'>
                <Button
                  type='button'
                  variant='outline'
                  disabled={ledgerPage === 0 || ledger.isFetching}
                  onClick={() => setLedgerPage((current) => current - 1)}
                >
                  Previous
                </Button>
                <Button
                  type='button'
                  variant='outline'
                  disabled={
                    ledger.isFetching ||
                    (ledgerPage + 1) * PAGE_SIZE >= ledger.data.count
                  }
                  onClick={() => setLedgerPage((current) => current + 1)}
                >
                  Next
                </Button>
              </div>
            </div>
          </>
        )}
      </section>

      <section
        className='space-y-4 rounded-lg border p-4'
        aria-label='Payroll readiness preflight'
      >
        <div className='grid gap-3 md:grid-cols-3'>
          <label className='grid gap-1 text-sm'>
            Pay group
            <Select
              value={payGroupId}
              onValueChange={(value) => {
                setPayGroupId(value)
                clearResults()
              }}
            >
              <SelectTrigger data-testid='payroll-pay-group-select'>
                <SelectValue placeholder='Select pay group' />
              </SelectTrigger>
              <SelectContent>
                {setup.groups.data?.map((group) => (
                  <SelectItem key={group.id} value={group.id}>
                    {group.name} · {group.cadence.replace('_', ' ')}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </label>
          <label className='grid gap-1 text-sm'>
            Period from
            <Input
              data-testid='payroll-period-from'
              type='date'
              value={dateFrom}
              onChange={(event) => {
                setDateFrom(event.target.value)
                clearResults()
              }}
            />
          </label>
          <label className='grid gap-1 text-sm'>
            Period through
            <Input
              data-testid='payroll-period-to'
              type='date'
              value={dateTo}
              onChange={(event) => {
                setDateTo(event.target.value)
                clearResults()
              }}
            />
          </label>
        </div>
        {setup.groups.isError && (
          <p role='alert' className='text-sm text-destructive'>
            Pay groups could not be loaded.
          </p>
        )}
        {!setup.groups.isPending && !setup.groups.data?.length && (
          <p className='text-sm text-muted-foreground'>
            Create a pay group in Payroll setup before checking a period.
          </p>
        )}
        <Button
          type='button'
          data-testid='payroll-preflight-button'
          disabled={
            !payGroupId || !dateFrom || !dateTo || preflightMutation.isPending
          }
          onClick={() => checkReadiness(0)}
        >
          {preflightMutation.isPending
            ? 'Checking readiness…'
            : 'Check payroll readiness'}
        </Button>
        <Button
          type='button'
          variant='outline'
          data-testid='payroll-attendance-preview-button'
          disabled={
            !payGroupId || !dateFrom || !dateTo || calculationMutation.isPending
          }
          onClick={previewAttendanceEarnings}
        >
          {calculationMutation.isPending
            ? 'Calculating provisional earnings…'
            : 'Preview attendance earnings'}
        </Button>
        {canAdd && (
          <Button
            type='button'
            variant='outline'
            data-testid='payroll-prepare-draft-button'
            disabled={
              !payGroupId || !dateFrom || !dateTo || prepareMutation.isPending
            }
            onClick={prepareDraft}
          >
            {prepareMutation.isPending
              ? 'Saving draft…'
              : 'Prepare payroll draft'}
          </Button>
        )}
      </section>

      <div
        role='status'
        className='rounded-md border border-amber-500/40 p-3 text-sm text-muted-foreground'
      >
        Drafts include versioned attendance calculations and named blockers for
        unsupported or missing inputs. Final approval also requires the
        employer's confirmed payroll rules, HR's parallel calculation review,
        and the system approval gate.
      </div>
      {preparedRunId && (
        <p role='status' className='text-sm'>
          Draft saved: {preparedRunId}. It cannot be reviewed or finalized while
          blockers remain.
        </p>
      )}

      {preflight && (
        <section className='space-y-3' aria-label='Payroll preflight results'>
          <div className='flex flex-wrap items-center justify-between gap-2'>
            <p className='text-sm'>
              {preflight.ready_count} ready · {preflight.blocked_count} blocked
              on this page · {preflight.count} expected employees total
            </p>
            <div className='flex gap-2'>
              <Button
                variant='outline'
                type='button'
                disabled={page === 0 || preflightMutation.isPending}
                onClick={() => checkReadiness(page - 1)}
              >
                Previous
              </Button>
              <Button
                variant='outline'
                type='button'
                disabled={!preflight.has_more || preflightMutation.isPending}
                onClick={() => checkReadiness(page + 1)}
              >
                Next
              </Button>
            </div>
          </div>
          <div className='max-h-[36rem] overflow-auto rounded-lg border'>
            <table className='w-full text-sm'>
              <thead className='sticky top-0 bg-muted'>
                <tr>
                  <th className='p-2 text-left'>Employee</th>
                  <th className='p-2 text-left'>Blockers and warnings</th>
                  <th className='p-2 text-right'>DTRs</th>
                  <th className='p-2 text-right'>Approved OT</th>
                </tr>
              </thead>
              <tbody>
                {preflight.entries.map((entry) => (
                  <tr key={entry.employee_id} className='border-t align-top'>
                    <td className='p-2'>
                      {entry.employee_code} · {entry.employee_name}
                    </td>
                    <td className='space-y-1 p-2'>
                      {entry.blockers.map((blocker, index) => (
                        <p
                          key={`${blocker.code}-${blocker.work_date ?? index}`}
                          className='text-destructive'
                        >
                          {blocker.work_date ? `${blocker.work_date}: ` : ''}
                          {blocker.message}
                        </p>
                      ))}
                      {entry.warnings.map((warning) => (
                        <p key={warning} className='text-amber-700'>
                          {warning}
                        </p>
                      ))}
                      {!entry.blockers.length && (
                        <span className='text-green-700'>
                          Ready for calculation review
                        </span>
                      )}
                    </td>
                    <td className='p-2 text-right'>
                      {entry.attendance_records}
                    </td>
                    <td className='p-2 text-right'>
                      {entry.approved_overtime_minutes} /{' '}
                      {entry.eligible_overtime_minutes} min
                    </td>
                  </tr>
                ))}
                {!preflight.entries.length && (
                  <tr>
                    <td
                      colSpan={4}
                      className='p-4 text-center text-muted-foreground'
                    >
                      No expected employees in this pay group and period.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {calculation && (
        <section className='space-y-3' aria-label='Attendance earnings preview'>
          <div
            role='status'
            className='rounded-md border border-amber-500/40 p-3 text-sm'
          >
            Provisional earnings only. Statutory contributions, tax, loans,
            final approval, payslip generation and email delivery are not
            included or enabled.
          </div>
          <div className='max-h-[36rem] overflow-auto rounded-lg border'>
            <table className='w-full text-sm'>
              <thead className='sticky top-0 bg-muted'>
                <tr>
                  <th className='p-2 text-left'>Employee</th>
                  <th className='p-2 text-left'>Blockers</th>
                  <th className='p-2 text-right'>Regular</th>
                  <th className='p-2 text-right'>Approved OT</th>
                  <th className='p-2 text-right'>Holiday premium</th>
                  <th className='p-2 text-right'>Rest-day premium</th>
                  <th className='p-2 text-right'>Night differential</th>
                  <th className='p-2 text-right'>Fixed allowance</th>
                  <th className='p-2 text-right'>Attendance deduction</th>
                  <th className='p-2 text-right'>Gross before statutory</th>
                </tr>
              </thead>
              <tbody>
                {calculation.entries.map((entry) => (
                  <tr key={entry.employee_id} className='border-t align-top'>
                    <td className='p-2'>
                      {entry.employee_code} · {entry.employee_name}
                      <details className='mt-1 text-xs'>
                        <summary>Formula and sources</summary>
                        {entry.formula.map((line) => (
                          <p key={line}>{line}</p>
                        ))}
                        {entry.source_references.map((source) => (
                          <p key={source} className='text-muted-foreground'>
                            {source}
                          </p>
                        ))}
                      </details>
                    </td>
                    <td className='p-2 text-destructive'>
                      {entry.blockers.map((blocker) => (
                        <p key={`${blocker.code}-${blocker.work_date}`}>
                          {blocker.work_date ? `${blocker.work_date}: ` : ''}
                          {blocker.message}
                        </p>
                      ))}
                    </td>
                    <td className='p-2 text-right'>
                      {entry.regular_earnings ?? '—'}
                    </td>
                    <td className='p-2 text-right'>
                      {entry.approved_overtime ?? '—'}
                    </td>
                    <td className='p-2 text-right'>
                      {entry.holiday_premium ?? '—'}
                    </td>
                    <td className='p-2 text-right'>
                      {entry.rest_day_premium ?? '—'}
                    </td>
                    <td className='p-2 text-right'>
                      {entry.night_differential ?? '—'}
                    </td>
                    <td className='p-2 text-right'>
                      {entry.fixed_recurring_allowance ?? '—'}
                    </td>
                    <td className='p-2 text-right'>
                      {entry.attendance_deduction ?? '—'}
                    </td>
                    <td className='p-2 text-right'>
                      {entry.gross_before_statutory ?? '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {calculation.has_more && (
            <p className='text-sm text-muted-foreground'>
              This is one bounded page of the expected roster. Change the
              readiness page before previewing the next page.
            </p>
          )}
        </section>
      )}
    </main>
  )
}
