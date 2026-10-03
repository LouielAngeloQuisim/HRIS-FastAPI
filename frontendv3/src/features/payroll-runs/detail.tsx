import { useNavigate, useParams } from '@tanstack/react-router'
import { useCan } from '@/context/permissions-provider'
import { usePayrollRun, useApprovePayrollRun, useVoidPayrollRun } from '@/lib/api/payroll'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { toast } from 'sonner'

export function PayrollRunDetail() {
  const canView = useCan('payroll', 'view')
  const canApprove = useCan('payroll', 'edit')
  const { runId } = useParams({ from: '/_authenticated/payroll-runs/$runId' })
  const navigate = useNavigate()

  const { data, isPending, isError, refetch } = usePayrollRun(runId)
  const approveMutation = useApprovePayrollRun()
  const voidMutation = useVoidPayrollRun()

  if (!canView) {
    return (
      <div className='flex flex-1 flex-col items-center justify-center gap-4'>
        <p className='text-muted-foreground'>You do not have permission to view payroll run details.</p>
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
          <Button variant='outline' onClick={() => navigate({ to: '/payroll-runs' })}>Back to List</Button>
          {canApprove && data?.status === 'draft' && (
            <Button data-testid='approve-run-button' onClick={handleApprove} disabled={approveMutation.isPending}>
              {approveMutation.isPending ? 'Approving...' : 'Approve Run'}
            </Button>
          )}
          {canApprove && data?.status === 'draft' && (
            <Button data-testid='void-run-button' variant='destructive' onClick={handleVoid} disabled={voidMutation.isPending}>
              {voidMutation.isPending ? 'Voiding...' : 'Void Run'}
            </Button>
          )}
        </div>
      </div>

      {isPending && <p className='text-sm text-muted-foreground'>Loading...</p>}
      {isError && (
        <div className='flex flex-col items-center justify-center gap-2 rounded-md border border-dashed py-12 text-center'>
          <p className='text-sm text-muted-foreground'>Failed to load payroll run.</p>
          <button type='button' onClick={() => refetch()} className='text-sm font-medium text-primary underline underline-offset-4' data-testid='retry-button'>Try again</button>
        </div>
      )}
      {data && (
        <>
          <div className='grid gap-4 sm:grid-cols-4'>
            <div className='rounded-lg border p-3'>
              <p className='text-sm text-muted-foreground'>Status</p>
              <p className='text-lg font-semibold capitalize'>{data.status}</p>
            </div>
            <div className='rounded-lg border p-3'>
              <p className='text-sm text-muted-foreground'>Cutoff</p>
              <p className='text-lg font-semibold capitalize'>{data.cutoff_type.replace('_', ' ')}</p>
            </div>
            <div className='rounded-lg border p-3'>
              <p className='text-sm text-muted-foreground'>Date Range</p>
              <p className='text-lg font-semibold'>{data.date_from} → {data.date_to}</p>
            </div>
            <div className='rounded-lg border p-3'>
              <p className='text-sm text-muted-foreground'>Total Gross Pay</p>
              <p className='text-lg font-semibold'>{formatCurrency(totalGross)}</p>
            </div>
            <div className='rounded-lg border p-3'>
              <p className='text-sm text-muted-foreground'>Total Deductions</p>
              <p className='text-lg font-semibold'>{formatCurrency(totalDeductions)}</p>
            </div>
            <div className='rounded-lg border p-3'>
              <p className='text-sm text-muted-foreground'>Total Net Pay</p>
              <p className='text-lg font-semibold'>{formatCurrency(totalNet)}</p>
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
                    <TableCell className='text-right'>{formatCurrency(entry.basic_rate)}</TableCell>
                    <TableCell className='text-right'>{formatCurrency(entry.gross_pay)}</TableCell>
                    <TableCell className='text-right'>{formatCurrency(entry.total_deductions)}</TableCell>
                    <TableCell className='text-right font-medium'>{formatCurrency(entry.net_pay)}</TableCell>
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
