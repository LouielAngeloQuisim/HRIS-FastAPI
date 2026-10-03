import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { useCan } from '@/context/permissions-provider'
import { usePayrollRuns } from '@/lib/api/payroll'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

export default function PayrollRunsPage() {
  const canView = useCan('payroll', 'view')
  const navigate = useNavigate()
  const [page] = useState(1)
  const pageSize = 20

  const { data, isPending, isError, refetch } = usePayrollRuns((page - 1) * pageSize, pageSize)

  if (!canView) {
    return (
      <div className='flex flex-1 flex-col items-center justify-center gap-4'>
        <p className='text-muted-foreground'>You do not have permission to view payroll runs.</p>
      </div>
    )
  }

  return (
    <div className='space-y-4'>
      <div>
        <h1 className='text-2xl font-bold'>Payroll Runs</h1>
        <p className='text-muted-foreground'>{data?.count ?? 0} runs</p>
      </div>
      {isPending && <p className='text-sm text-muted-foreground'>Loading...</p>}
      {isError && (
        <div className='flex flex-col items-center justify-center gap-2 rounded-md border border-dashed py-12 text-center'>
          <p className='text-sm text-muted-foreground'>Failed to load payroll runs.</p>
          <button type='button' onClick={() => refetch()} className='text-sm font-medium text-primary underline underline-offset-4' data-testid='retry-button'>Try again</button>
        </div>
      )}
      {data && (
        <div className='overflow-x-auto rounded-lg border'>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Run ID</TableHead>
                <TableHead>Cutoff</TableHead>
                <TableHead>Date Range</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Adjustment</TableHead>
                <TableHead className='text-right'>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.data.map((item) => (
                <TableRow key={item.id} className='hover:bg-muted/50'>
                  <TableCell className='font-mono text-xs'>{item.id}</TableCell>
                  <TableCell className='capitalize'>{item.cutoff_type.replace('_', ' ')}</TableCell>
                  <TableCell>{item.date_from} → {item.date_to}</TableCell>
                  <TableCell>
                    <span className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${
                      item.status === 'draft' ? 'bg-yellow-100 text-yellow-800' :
                      item.status === 'approved' ? 'bg-green-100 text-green-800' :
                      item.status === 'void' ? 'bg-red-100 text-red-800' :
                      'bg-blue-100 text-blue-800'
                    }`}>
                      {item.status}
                    </span>
                  </TableCell>
                  <TableCell className='capitalize'>{item.adjustment_type.replace('_', ' ')}</TableCell>
                  <TableCell className='text-right'>
                    <Button
                      data-testid={`view-run-button-${item.id}`}
                      variant='ghost'
                      size='sm'
                      onClick={() => navigate({ to: '/payroll-runs/$runId', params: { runId: item.id } })}
                    >
                      View
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}
