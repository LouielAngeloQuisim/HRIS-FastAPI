import { useState } from 'react'
import { useCan } from '@/context/permissions-provider'
import { useLeaveCalendar } from '@/lib/api/leave-ledger'
import { Button } from '@/components/ui/button'

export default function LeaveCalendarPage() {
  const today = new Date()
  const [fromDate, setFromDate] = useState(today.toISOString().split('T')[0])
  const [toDate, setToDate] = useState(today.toISOString().split('T')[0])
  const [employeeId] = useState('00000000-0000-0000-0000-000000000000')
  const canView = useCan('emp_leaves', 'view')

  const { data, isPending, isError, refetch } = useLeaveCalendar(employeeId, fromDate, toDate)

  if (!canView) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4">
        <p className="text-muted-foreground">You do not have permission to view leave calendar.</p>
      </div>
    )
  }

  const grouped = data?.reduce<Record<string, typeof data>>((acc, event) => {
    const day = event.observed_date
    if (!acc[day]) acc[day] = []
    acc[day].push(event)
    return acc
  }, {}) ?? {}

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Leave Calendar</h1>
          <p className="text-muted-foreground">{data?.length ?? 0} events</p>
        </div>
        <div className="flex gap-2">
          <input
            type="date"
            className="border rounded px-2 py-1 text-sm"
            value={fromDate}
            onChange={(e) => setFromDate(e.target.value)}
            data-testid="leave-calendar-from-date"
          />
          <input
            type="date"
            className="border rounded px-2 py-1 text-sm"
            value={toDate}
            onChange={(e) => setToDate(e.target.value)}
            data-testid="leave-calendar-to-date"
          />
          <Button onClick={() => refetch()} data-testid="leave-calendar-apply-button">Apply</Button>
        </div>
      </div>
      {isPending && <p className="text-sm text-muted-foreground">Loading...</p>}
      {isError && (
        <div className="flex flex-col items-center justify-center gap-2 rounded-md border border-dashed py-12 text-center">
          <p className="text-sm text-muted-foreground">Failed to load leave calendar.</p>
          <button type="button" onClick={() => refetch()} className="text-sm font-medium text-primary underline underline-offset-4">Try again</button>
        </div>
      )}
      {data && data.length === 0 && (
        <div className="flex flex-col items-center justify-center gap-2 rounded-md border border-dashed py-12 text-center">
          <p className="text-sm text-muted-foreground">No leave events found for the selected range.</p>
        </div>
      )}
      {data && data.length > 0 && (
        <div className="border rounded-lg overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="p-2 text-left">Date</th>
                <th className="p-2 text-left">Title</th>
                <th className="p-2 text-left">Type</th>
                <th className="p-2 text-left">Status</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(grouped).sort(([a], [b]) => a.localeCompare(b)).map(([day, events]) =>
                events.map((event, idx) => (
                  <tr key={event.id} className="border-b last:border-0 hover:bg-muted/50">
                    {idx === 0 && (
                      <td className="p-2 align-top" rowSpan={events.length}>
                        {day}
                      </td>
                    )}
                    <td className="p-2">
                      <span className="inline-block w-3 h-3 rounded-full mr-2" style={{ backgroundColor: event.color }} />
                      {event.title}
                    </td>
                    <td className="p-2 capitalize">{event.type}</td>
                    <td className="p-2">{event.status ?? '—'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
