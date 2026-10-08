import { useState } from 'react'
import { toast } from 'sonner'
import {
  usePayrollAttendanceCalculationPreview,
  usePayrollRunPreflight,
  usePayrollSetup,
  usePrepareAttendancePayrollDraft,
  type PayrollAttendanceCalculationPreview,
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

export default function PayrollPage() {
  const canView = useCan('payroll', 'view')
  const canAdd = useCan('payroll', 'add')
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
                      {!entry.blockers.length && !entry.warnings.length && (
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
