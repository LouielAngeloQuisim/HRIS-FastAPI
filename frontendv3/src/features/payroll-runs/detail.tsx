import { useState } from 'react'
import { useNavigate, useParams } from '@tanstack/react-router'
import { toast } from 'sonner'
import {
  usePayrollRun,
  useApprovePayrollRun,
  useVoidPayrollRun,
  useFinalizePayrollRun,
  useReviewPayrollEntry,
  useStartPayrollReview,
} from '@/lib/api/payroll'
import { useCan } from '@/context/permissions-provider'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

export function PayrollRunDetail() {
  const canView = useCan('payroll', 'view')
  const canEdit = useCan('payroll', 'edit')
  const canFinalize = useCan('payroll', 'approve')
  const canApprove = useCan('payroll', 'edit')
  const { runId } = useParams({ from: '/_authenticated/payroll-runs/$runId' })
  const navigate = useNavigate()

  const { data, isPending, isError, refetch } = usePayrollRun(runId)
  const approveMutation = useApprovePayrollRun()
  const voidMutation = useVoidPayrollRun()
  const startReviewMutation = useStartPayrollReview(runId)
  const reviewEntryMutation = useReviewPayrollEntry(runId)
  const finalizeMutation = useFinalizePayrollRun(runId)
  const [exclusionReasons, setExclusionReasons] = useState<
    Record<string, string>
  >({})

  if (!canView) {
    return (
      <div className='flex flex-1 flex-col items-center justify-center gap-4'>
        <p className='text-muted-foreground'>
          You do not have permission to view payroll run details.
        </p>
      </div>
    )
  }

  const handleApprove = async () => {
    if (!runId) return
    try {
      await approveMutation.mutateAsync(runId)
      toast.success('Payroll run approved')
      refetch()
    } catch {
      toast.error('Failed to approve payroll run')
    }
  }

  const handleVoid = async () => {
    if (!runId) return
    try {
      await voidMutation.mutateAsync(runId)
      toast.success('Payroll run voided')
      refetch()
    } catch {
      toast.error('Failed to void payroll run')
    }
  }

  const handleStartReview = async () => {
    if (!runId) return
    try {
      await startReviewMutation.mutateAsync(undefined)
      toast.success('Payroll run opened for employee review')
      refetch()
    } catch {
      toast.error('Resolve all payroll blockers before opening review.')
    }
  }

  const handleReviewEntry = async (
    entryId: string,
    action: 'reviewed' | 'excluded'
  ) => {
    const entry = data?.entries.find((candidate) => candidate.id === entryId)
    if (!entry?.input_fingerprint) {
      toast.error(
        'This entry has no current calculation fingerprint and cannot be reviewed.'
      )
      return
    }
    const reason = exclusionReasons[entryId]?.trim()
    if (action === 'excluded' && !reason) {
      toast.error('Enter a reason before excluding an employee.')
      return
    }
    try {
      await reviewEntryMutation.mutateAsync({
        entryId,
        action,
        expected_input_fingerprint: entry.input_fingerprint,
        reason: action === 'excluded' ? reason : undefined,
      })
      toast.success(
        action === 'reviewed'
          ? 'Employee payroll reviewed'
          : 'Employee excluded with reason'
      )
      refetch()
    } catch {
      toast.error(
        'The entry could not be reviewed. Reload and resolve any changed inputs or blockers.'
      )
    }
  }

  const handleFinalize = async () => {
    if (
      !runId ||
      !window.confirm(
        'Finalize this reviewed payroll run and schedule its payslip delivery?'
      )
    )
      return
    try {
      await finalizeMutation.mutateAsync(undefined)
      toast.success(
        'Payroll finalized; payslip delivery is scheduled separately.'
      )
      refetch()
    } catch {
      toast.error(
        'Finalization was rejected. Check approver separation, current inputs, contribution snapshots and blockers.'
      )
    }
  }

  const formatCurrency = (value: string | number) => {
    const num = typeof value === 'string' ? Number(value) : value
    return Number.isFinite(num) ? `₱${num.toLocaleString()}` : '₱0.00'
  }

  const totalNet = data?.total_net_pay ?? 0
  const totalGross = data?.total_gross_pay ?? 0
  const totalDeductions = data?.total_deductions ?? 0

  return (
    <div className='space-y-4'>
      <div className='flex items-center justify-between'>
        <div>
          <h1 className='text-2xl font-bold'>Payroll Run Detail</h1>
          <p className='text-muted-foreground'>Run ID: {data?.id ?? runId}</p>
        </div>
        <div className='flex gap-2'>
          <Button
            variant='outline'
            onClick={() => navigate({ to: '/payroll-runs' })}
          >
            Back to List
          </Button>
          {canApprove && !data?.workflow_status && data?.status === 'draft' && (
            <Button
              data-testid='approve-run-button'
              onClick={handleApprove}
              disabled={approveMutation.isPending}
            >
              {approveMutation.isPending ? 'Approving...' : 'Approve Run'}
            </Button>
          )}
          {canApprove && !data?.workflow_status && data?.status === 'draft' && (
            <Button
              data-testid='void-run-button'
              variant='destructive'
              onClick={handleVoid}
              disabled={voidMutation.isPending}
            >
              {voidMutation.isPending ? 'Voiding...' : 'Void Run'}
            </Button>
          )}
        </div>
      </div>

      {isPending && <p className='text-sm text-muted-foreground'>Loading...</p>}
      {isError && (
        <div className='flex flex-col items-center justify-center gap-2 rounded-md border border-dashed py-12 text-center'>
          <p className='text-sm text-muted-foreground'>
            Failed to load payroll run.
          </p>
          <button
            type='button'
            onClick={() => refetch()}
            className='text-sm font-medium text-primary underline underline-offset-4'
            data-testid='retry-button'
          >
            Try again
          </button>
        </div>
      )}
      {data && (
        <>
          {data.workflow_status && (
            <section
              className='space-y-3 rounded-lg border p-4'
              aria-label='Payroll review workflow'
            >
              <div className='flex flex-wrap items-center justify-between gap-3'>
                <div>
                  <h2 className='font-semibold'>Payroll review</h2>
                  <p className='text-sm text-muted-foreground'>
                    Workflow: {data.workflow_status.replace(/_/g, ' ')}
                  </p>
                </div>
                {canEdit && data.workflow_status === 'draft' && (
                  <Button
                    onClick={handleStartReview}
                    disabled={startReviewMutation.isPending}
                  >
                    {startReviewMutation.isPending
                      ? 'Checking entries…'
                      : 'Start employee review'}
                  </Button>
                )}
                {canFinalize &&
                  data.workflow_status === 'ready_for_finalization' && (
                    <Button
                      onClick={handleFinalize}
                      disabled={finalizeMutation.isPending}
                    >
                      {finalizeMutation.isPending
                        ? 'Finalizing…'
                        : 'Finalize and schedule payslips'}
                    </Button>
                  )}
              </div>
              {data.workflow_status === 'draft' && (
                <p role='status' className='text-sm text-amber-700'>
                  Drafts with unresolved attendance, salary, shift, policy or
                  statutory blockers cannot enter review.
                </p>
              )}
              {data.workflow_status === 'ready_for_finalization' &&
                canFinalize && (
                  <p className='text-sm text-muted-foreground'>
                    Final approval must be performed by a user different from
                    the preparer and every employee reviewer. Finalization
                    freezes the reviewed amounts and schedules delivery; it does
                    not confirm a bank payout.
                  </p>
                )}
              <div className='space-y-3'>
                {data.entries.map((entry) => (
                  <article
                    key={entry.id}
                    className='space-y-2 rounded-md border p-3'
                    data-testid={`payroll-entry-${entry.id}`}
                  >
                    <div className='flex flex-wrap items-center justify-between gap-2'>
                      <div>
                        <p className='font-medium'>
                          Employee {entry.employee_id}
                        </p>
                        <p className='text-xs text-muted-foreground'>
                          Review state: {entry.review_state}
                        </p>
                      </div>
                      <p className='text-sm'>
                        Net {formatCurrency(entry.net_pay)}
                      </p>
                    </div>
                    {!!entry.blockers.length && (
                      <ul
                        className='list-disc pl-5 text-sm text-destructive'
                        aria-label='Entry blockers'
                      >
                        {entry.blockers.map((blocker, index) => (
                          <li key={`${blocker.code}-${index}`}>
                            {blocker.work_date ? `${blocker.work_date}: ` : ''}
                            {blocker.message}
                          </li>
                        ))}
                      </ul>
                    )}
                    <details className='text-xs'>
                      <summary>Calculation inputs and lines</summary>
                      <pre className='mt-2 max-h-64 overflow-auto rounded bg-muted p-2 whitespace-pre-wrap'>
                        {JSON.stringify(
                          {
                            earnings: entry.earnings,
                            deductions: entry.deductions,
                          },
                          null,
                          2
                        )}
                      </pre>
                    </details>
                    {canEdit &&
                      data.workflow_status === 'in_review' &&
                      entry.review_state === 'ready' &&
                      !entry.blockers.length && (
                        <div className='flex flex-wrap items-end gap-2'>
                          <Button
                            onClick={() =>
                              handleReviewEntry(entry.id, 'reviewed')
                            }
                            disabled={reviewEntryMutation.isPending}
                          >
                            Mark reviewed
                          </Button>
                          <label className='grid min-w-56 flex-1 gap-1 text-xs'>
                            Exclusion reason
                            <input
                              value={exclusionReasons[entry.id] ?? ''}
                              onChange={(event) =>
                                setExclusionReasons((current) => ({
                                  ...current,
                                  [entry.id]: event.target.value,
                                }))
                              }
                              maxLength={1024}
                              className='h-9 rounded border bg-background px-3 text-sm'
                            />
                          </label>
                          <Button
                            variant='outline'
                            onClick={() =>
                              handleReviewEntry(entry.id, 'excluded')
                            }
                            disabled={
                              reviewEntryMutation.isPending ||
                              !(exclusionReasons[entry.id] ?? '').trim()
                            }
                          >
                            Exclude with reason
                          </Button>
                        </div>
                      )}
                  </article>
                ))}
              </div>
            </section>
          )}
          <div className='grid gap-4 sm:grid-cols-4'>
            <div className='rounded-lg border p-3'>
              <p className='text-sm text-muted-foreground'>Status</p>
              <p className='text-lg font-semibold capitalize'>{data.status}</p>
            </div>
            <div className='rounded-lg border p-3'>
              <p className='text-sm text-muted-foreground'>Cutoff</p>
              <p className='text-lg font-semibold capitalize'>
                {data.cutoff_type.replace('_', ' ')}
              </p>
            </div>
            <div className='rounded-lg border p-3'>
              <p className='text-sm text-muted-foreground'>Date Range</p>
              <p className='text-lg font-semibold'>
                {data.date_from} → {data.date_to}
              </p>
            </div>
            <div className='rounded-lg border p-3'>
              <p className='text-sm text-muted-foreground'>Total Gross Pay</p>
              <p className='text-lg font-semibold'>
                {formatCurrency(totalGross)}
              </p>
            </div>
            <div className='rounded-lg border p-3'>
              <p className='text-sm text-muted-foreground'>Total Deductions</p>
              <p className='text-lg font-semibold'>
                {formatCurrency(totalDeductions)}
              </p>
            </div>
            <div className='rounded-lg border p-3'>
              <p className='text-sm text-muted-foreground'>Total Net Pay</p>
              <p className='text-lg font-semibold'>
                {formatCurrency(totalNet)}
              </p>
            </div>
          </div>

          <div className='overflow-x-auto rounded-lg border'>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Employee ID</TableHead>
                  <TableHead className='text-right'>Basic Rate</TableHead>
                  <TableHead className='text-right'>Gross Pay</TableHead>
                  <TableHead className='text-right'>Deductions</TableHead>
                  <TableHead className='text-right'>Net Pay</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.entries.map((entry) => (
                  <TableRow key={entry.id} className='hover:bg-muted/50'>
                    <TableCell>{entry.employee_id}</TableCell>
                    <TableCell className='text-right'>
                      {formatCurrency(entry.basic_rate)}
                    </TableCell>
                    <TableCell className='text-right'>
                      {formatCurrency(entry.gross_pay)}
                    </TableCell>
                    <TableCell className='text-right'>
                      {formatCurrency(entry.total_deductions)}
                    </TableCell>
                    <TableCell className='text-right font-medium'>
                      {formatCurrency(entry.net_pay)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </>
      )}
    </div>
  )
}
