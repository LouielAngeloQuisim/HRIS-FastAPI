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
  useRebuildAttendancePayrollDraft,
  usePayrollDeliveryStatus,
  useCorrectPayrollDeliveryAddress,
  useResendPayrollDelivery,
  downloadPayrollPayslip,
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

function calculationLines(
  value: Record<string, unknown> | null,
  prefix = ''
): Array<{ label: string; value: string }> {
  if (!value) return []
  return Object.entries(value).flatMap(([key, item]) => {
    const label = [prefix, key.replace(/_/g, ' ')].filter(Boolean).join(' · ')
    if (item && typeof item === 'object' && !Array.isArray(item)) {
      return calculationLines(item as Record<string, unknown>, label)
    }
    if (
      typeof item === 'number' ||
      (typeof item === 'string' && /^-?\d+(\.\d+)?$/.test(item))
    ) {
      return [{ label, value: `₱${Number(item).toLocaleString()}` }]
    }
    if (typeof item === 'string' && item.trim()) {
      return [{ label, value: item }]
    }
    return []
  })
}

export function PayrollRunDetail() {
  const canView = useCan('payroll', 'view')
  const canEdit = useCan('payroll', 'edit')
  const canFinalize = useCan('payroll', 'approve')
  const canApprove = useCan('payroll', 'edit')
  const { runId } = useParams({ from: '/_authenticated/payroll-runs/$runId' })
  const navigate = useNavigate()

  const { data, isPending, isError, refetch } = usePayrollRun(runId)
  const hasProvisionalReviewedEntries =
    data?.entries.some(
      (entry) =>
        entry.review_state === 'reviewed' &&
        (entry.calculation_version?.endsWith('-provisional') === true ||
          entry.earnings?.provisional === true)
    ) ?? false
  const approveMutation = useApprovePayrollRun()
  const voidMutation = useVoidPayrollRun()
  const startReviewMutation = useStartPayrollReview(runId)
  const rebuildDraftMutation = useRebuildAttendancePayrollDraft(runId)
  const reviewEntryMutation = useReviewPayrollEntry(runId)
  const finalizeMutation = useFinalizePayrollRun(runId)
  const deliveryQuery = usePayrollDeliveryStatus(
    runId,
    data?.workflow_status === 'finalized'
  )
  const addressMutation = useCorrectPayrollDeliveryAddress(runId)
  const resendMutation = useResendPayrollDelivery(runId)
  const [exclusionReasons, setExclusionReasons] = useState<
    Record<string, string>
  >({})
  const [deliveryInputs, setDeliveryInputs] = useState<
    Record<string, { email: string; reason: string }>
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

  const handleRebuildDraft = async () => {
    if (!runId || !data?.input_fingerprint) {
      toast.error(
        'This draft has no current fingerprint and cannot be rebuilt.'
      )
      return
    }
    const reason = window
      .prompt('Why are you rebuilding this blocked or outdated draft?')
      ?.trim()
    if (!reason) return
    if (reason.length < 5) {
      toast.error('Enter a reason with at least 5 characters.')
      return
    }
    try {
      const replacement = await rebuildDraftMutation.mutateAsync({
        expected_run_fingerprint: data.input_fingerprint,
        reason,
      })
      toast.success('A replacement draft was prepared from current inputs.')
      await navigate({
        to: '/payroll-runs/$runId',
        params: { runId: replacement.id },
      })
    } catch {
      toast.error(
        'Draft rebuild failed. Reload, resolve the blockers, and retry.'
      )
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

  const handleDeliveryAddress = async (jobId: string) => {
    const input = deliveryInputs[jobId]
    if (!input?.email.trim() || input.reason.trim().length < 5) {
      toast.error(
        'Enter a recipient email and a reason of at least 5 characters.'
      )
      return
    }
    try {
      await addressMutation.mutateAsync({
        jobId,
        payload: { email: input.email.trim(), reason: input.reason.trim() },
      })
      toast.success('Payslip recipient updated; delivery is scheduled.')
    } catch {
      toast.error('Recipient update failed. Reload and verify delivery status.')
    }
  }

  const handleDeliveryResend = async (jobId: string, uncertain: boolean) => {
    const input = deliveryInputs[jobId]
    if (!input || input.reason.trim().length < 5) {
      toast.error('Enter a reason of at least 5 characters before retrying.')
      return
    }
    if (
      uncertain &&
      !window.confirm(
        'The prior email may already have been delivered. Resending can send a duplicate payslip. Continue?'
      )
    ) {
      return
    }
    try {
      await resendMutation.mutateAsync({
        jobId,
        payload: {
          reason: input?.reason.trim() ?? '',
          confirm_duplicate_risk: uncertain,
        },
      })
      toast.success('Payslip delivery retry scheduled.')
    } catch {
      toast.error('Retry request failed. Reload and verify delivery status.')
    }
  }

  const handleDownloadPayslip = async (entryId: string) => {
    try {
      await downloadPayrollPayslip(runId, entryId)
    } catch {
      toast.error(
        'Payslip download failed. Verify the run is finalized and retry.'
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
                {canEdit &&
                  (data.workflow_status === 'draft' ||
                    data.workflow_status === 'in_review') && (
                    <div className='flex flex-wrap gap-2'>
                      {data.workflow_status === 'draft' && (
                        <Button
                          onClick={handleStartReview}
                          disabled={startReviewMutation.isPending}
                        >
                          {startReviewMutation.isPending
                            ? 'Checking entries…'
                            : 'Start employee review'}
                        </Button>
                      )}
                      {data.status === 'draft' &&
                        data.input_fingerprint &&
                        data.entries.every((entry) =>
                          ['blocked', 'ready'].includes(entry.review_state)
                        ) && (
                          <Button
                            variant='outline'
                            onClick={handleRebuildDraft}
                            disabled={rebuildDraftMutation.isPending}
                          >
                            {rebuildDraftMutation.isPending
                              ? 'Rebuilding…'
                              : 'Rebuild blocked draft'}
                          </Button>
                        )}
                    </div>
                  )}
                {canFinalize &&
                  data.workflow_status === 'ready_for_finalization' && (
                    <Button
                      onClick={handleFinalize}
                      disabled={
                        finalizeMutation.isPending ||
                        hasProvisionalReviewedEntries ||
                        !data.payroll_finalization_enabled
                      }
                    >
                      {finalizeMutation.isPending
                        ? 'Finalizing…'
                        : hasProvisionalReviewedEntries
                          ? 'Calculation not approved'
                          : data.payroll_finalization_enabled
                            ? 'Finalize and schedule payslips'
                            : 'Finalization disabled'}
                    </Button>
                  )}
              </div>
              {(data.workflow_status === 'draft' ||
                data.workflow_status === 'in_review') && (
                <p role='status' className='text-sm text-amber-700'>
                  Resolve blockers and rebuild before review, or explicitly
                  exclude a blocked employee with a reason. Any review or
                  exclusion decision locks the draft against rebuilding.
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
              {data.workflow_status === 'ready_for_finalization' &&
                canFinalize &&
                hasProvisionalReviewedEntries && (
                  <p role='status' className='text-sm text-amber-700'>
                    Finalization is blocked because one or more reviewed entries
                    still use provisional earnings. Complete and approve the
                    payroll calculation first.
                  </p>
                )}
              {data.workflow_status === 'ready_for_finalization' &&
                canFinalize &&
                !data.payroll_finalization_enabled && (
                  <p role='status' className='text-sm text-amber-700'>
                    Finalization is disabled until statutory configuration and
                    HR-approved parallel payroll comparisons are accepted.
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
                          {entry.employee_name ??
                            `Employee ${entry.employee_id}`}
                          {entry.employee_code && (
                            <span className='ml-2 text-xs text-muted-foreground'>
                              {entry.employee_code}
                            </span>
                          )}
                        </p>
                        <p className='text-xs text-muted-foreground'>
                          Review state: {entry.review_state}
                        </p>
                        {entry.review_reason && (
                          <p className='text-xs text-muted-foreground'>
                            Review reason: {entry.review_reason}
                          </p>
                        )}
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
                    <details className='text-sm'>
                      <summary>
                        Calculation breakdown and source history
                      </summary>
                      <div className='mt-2 grid gap-3 rounded bg-muted p-3'>
                        <p className='text-xs text-muted-foreground'>
                          Formula: gross earnings − employee deductions = net
                          pay · Version:{' '}
                          {entry.calculation_version ?? 'unavailable'}
                        </p>
                        <p className='text-xs text-muted-foreground'>
                          Gross {formatCurrency(entry.gross_pay)} − deductions{' '}
                          {formatCurrency(entry.total_deductions)} = net{' '}
                          {formatCurrency(entry.net_pay)}
                        </p>
                        <div className='grid gap-3 md:grid-cols-2'>
                          {(
                            [
                              ['Earnings', entry.earnings],
                              [
                                'Deductions and employer contributions',
                                entry.deductions,
                              ],
                            ] as Array<[string, Record<string, unknown> | null]>
                          ).map(([heading, lines]) => {
                            const items = calculationLines(lines)
                            return (
                              <div key={heading as string}>
                                <h3 className='font-medium'>{heading}</h3>
                                {items.length ? (
                                  <dl className='mt-1 space-y-1'>
                                    {items.map((item) => (
                                      <div
                                        key={`${item.label}-${item.value}`}
                                        className='flex justify-between gap-3 text-xs'
                                      >
                                        <dt className='capitalize'>
                                          {item.label}
                                        </dt>
                                        <dd className='text-right'>
                                          {item.value}
                                        </dd>
                                      </div>
                                    ))}
                                  </dl>
                                ) : (
                                  <p className='text-xs text-muted-foreground'>
                                    None
                                  </p>
                                )}
                              </div>
                            )
                          })}
                        </div>
                        <div>
                          <h3 className='font-medium'>Source revisions</h3>
                          <dl className='mt-1 grid grid-cols-2 gap-x-4 gap-y-1 text-xs md:grid-cols-4'>
                            {[
                              ['Attendance', 'attendance_revisions'],
                              ['Salary', 'salary_versions'],
                              ['Shifts', 'shift_assignments'],
                              ['Pay group', 'pay_group_assignments'],
                              ['Leave', 'leave_revisions'],
                              ['Holidays', 'holiday_revisions'],
                              ['Policy', 'policy_versions'],
                            ].map(([label, key]) => (
                              <div
                                key={key}
                                className='flex justify-between gap-2'
                              >
                                <dt>{label}</dt>
                                <dd>
                                  {Array.isArray(entry.input_snapshot[key])
                                    ? entry.input_snapshot[key].length
                                    : 0}
                                </dd>
                              </div>
                            ))}
                          </dl>
                        </div>
                      </div>
                    </details>
                    {canEdit &&
                      data.workflow_status === 'in_review' &&
                      ['ready', 'blocked'].includes(entry.review_state) && (
                        <div className='flex flex-wrap items-end gap-2'>
                          {entry.review_state === 'ready' &&
                            !entry.blockers.length && (
                              <Button
                                onClick={() =>
                                  handleReviewEntry(entry.id, 'reviewed')
                                }
                                disabled={reviewEntryMutation.isPending}
                              >
                                Mark reviewed
                              </Button>
                            )}
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
          {data.workflow_status === 'finalized' && (
            <section
              className='space-y-3 rounded-lg border p-4'
              aria-label='Payslip delivery'
            >
              <div>
                <h2 className='font-semibold'>Payslip delivery</h2>
                <p className='text-sm text-muted-foreground'>
                  Email status is separate from payroll approval and does not
                  confirm payment.
                </p>
              </div>
              {!data.payslip_delivery_enabled && (
                <p role='status' className='text-sm text-amber-700'>
                  Email delivery is disabled by system configuration. Delivery
                  jobs remain queued until an operator enables the worker after
                  acceptance.
                </p>
              )}
              {deliveryQuery.isPending && (
                <p className='text-sm'>Loading delivery status…</p>
              )}
              {deliveryQuery.isError && (
                <div className='flex items-center gap-2 text-sm'>
                  <span>Could not load delivery status.</span>
                  <Button
                    variant='outline'
                    onClick={() => deliveryQuery.refetch()}
                  >
                    Retry
                  </Button>
                </div>
              )}
              {deliveryQuery.data?.length === 0 && (
                <p className='text-sm text-muted-foreground'>
                  No payslip delivery jobs are recorded for this run.
                </p>
              )}
              <div className='space-y-3'>
                {deliveryQuery.data?.map((job) => {
                  const input = deliveryInputs[job.id] ?? {
                    email: job.recipient_snapshot ?? '',
                    reason: '',
                  }
                  const employee = data.entries.find(
                    (entry) => entry.id === job.payroll_entry_id
                  )
                  return (
                    <article
                      key={job.id}
                      className='space-y-2 rounded-md border p-3'
                      data-testid={`delivery-${job.id}`}
                    >
                      <p className='font-medium'>
                        {employee?.employee_name ??
                          `Employee ${employee?.employee_id ?? job.payroll_entry_id}`}
                        {employee?.employee_code
                          ? ` (${employee.employee_code})`
                          : ''}
                      </p>
                      <p className='text-sm'>
                        Status:{' '}
                        <span className='font-medium'>
                          {job.status.replace(/_/g, ' ')}
                        </span>{' '}
                        · Attempts: {job.attempts}
                      </p>
                      {data.workflow_status === 'finalized' && (
                        <Button
                          variant='outline'
                          onClick={() =>
                            handleDownloadPayslip(job.payroll_entry_id)
                          }
                        >
                          Download PDF
                        </Button>
                      )}
                      {job.sent_at && (
                        <p className='text-sm'>
                          Sent: {new Date(job.sent_at).toLocaleString()}
                        </p>
                      )}
                      {job.next_attempt_at && job.status === 'scheduled' && (
                        <p className='text-sm'>
                          Scheduled:{' '}
                          {new Date(job.next_attempt_at).toLocaleString()}
                        </p>
                      )}
                      {job.last_error_code && (
                        <p className='text-sm text-destructive'>
                          Last delivery error: {job.last_error_code}
                        </p>
                      )}
                      {(job.status === 'blocked_email' ||
                        job.status === 'failed') &&
                        canEdit && (
                          <label className='grid gap-1 text-sm'>
                            Correct recipient email
                            <input
                              type='email'
                              value={input.email}
                              onChange={(event) =>
                                setDeliveryInputs((current) => ({
                                  ...current,
                                  [job.id]: {
                                    ...input,
                                    email: event.target.value,
                                  },
                                }))
                              }
                              className='h-9 rounded border bg-background px-3'
                            />
                          </label>
                        )}
                      {(job.status === 'failed' ||
                        job.status === 'uncertain' ||
                        job.status === 'blocked_email') &&
                        canEdit && (
                          <>
                            <label className='grid gap-1 text-sm'>
                              Action reason
                              <input
                                value={input.reason}
                                maxLength={1024}
                                onChange={(event) =>
                                  setDeliveryInputs((current) => ({
                                    ...current,
                                    [job.id]: {
                                      ...input,
                                      reason: event.target.value,
                                    },
                                  }))
                                }
                                className='h-9 rounded border bg-background px-3'
                              />
                            </label>
                            <div className='flex flex-wrap gap-2'>
                              {(job.status === 'blocked_email' ||
                                job.status === 'failed') && (
                                <Button
                                  variant='outline'
                                  onClick={() => handleDeliveryAddress(job.id)}
                                  disabled={
                                    addressMutation.isPending ||
                                    input.reason.trim().length < 5 ||
                                    !input.email.trim()
                                  }
                                >
                                  Correct email and schedule
                                </Button>
                              )}
                              {(job.status === 'failed' ||
                                job.status === 'uncertain') && (
                                <Button
                                  variant='outline'
                                  onClick={() =>
                                    handleDeliveryResend(
                                      job.id,
                                      job.status === 'uncertain'
                                    )
                                  }
                                  disabled={
                                    resendMutation.isPending ||
                                    input.reason.trim().length < 5 ||
                                    !job.recipient_snapshot
                                  }
                                >
                                  {job.status === 'uncertain'
                                    ? 'Confirm duplicate risk and resend'
                                    : 'Retry delivery'}
                                </Button>
                              )}
                            </div>
                          </>
                        )}
                      {job.last_action_reason && (
                        <p className='text-xs text-muted-foreground'>
                          Last action: {job.last_action_reason}
                        </p>
                      )}
                    </article>
                  )
                })}
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
                  <TableHead>Employee</TableHead>
                  <TableHead className='text-right'>Basic Rate</TableHead>
                  <TableHead className='text-right'>Gross Pay</TableHead>
                  <TableHead className='text-right'>Deductions</TableHead>
                  <TableHead className='text-right'>Net Pay</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.entries.map((entry) => (
                  <TableRow key={entry.id} className='hover:bg-muted/50'>
                    <TableCell>
                      <div>
                        {entry.employee_name ?? `Employee ${entry.employee_id}`}
                      </div>
                      {entry.employee_code && (
                        <div className='text-xs text-muted-foreground'>
                          {entry.employee_code}
                        </div>
                      )}
                    </TableCell>
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
