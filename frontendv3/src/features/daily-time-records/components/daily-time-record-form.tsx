import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Button } from '@/components/ui/button'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Sheet, SheetClose, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { useUpdateDailyTimeRecord } from '@/lib/api/daily-time-records'
import { saveErrorMessage } from '@/lib/api/save-error'
import type { DailyTimeRecordPublic } from '@/lib/api/types'

const schema = z.object({
  login_date: z.string().min(1, 'Login time is required'),
  logout_date: z.string().min(1, 'Logout time is required'),
}).refine(data => data.login_date < data.logout_date, { path: ['logout_date'], message: 'Logout must be after login' })
type Values = z.infer<typeof schema>
interface Props { item: DailyTimeRecordPublic; open: boolean; onClose: () => void }
export function DailyTimeRecordForm({ item, open, onClose }: Props) {
  const update = useUpdateDailyTimeRecord()
  const toUtcInput = (value: string | null) => value ? new Date(value).toISOString().slice(0, 16) : ''
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { login_date: toUtcInput(item.login_date), logout_date: toUtcInput(item.logout_date) } })
  const submit = async (values: Values) => {
    form.clearErrors('root.server')
    try {
      await update.mutateAsync({ id: item.id, data: { login_date: new Date(values.login_date + 'Z').toISOString(), logout_date: new Date(values.logout_date + 'Z').toISOString() } })
      onClose()
    } catch (error) { form.setError('root.server', { message: saveErrorMessage(error) }) }
  }
  return <Sheet open={open} onOpenChange={value => { if (!value) onClose() }}><SheetContent className="flex flex-col">
    <SheetHeader><SheetTitle>Update Daily Time Record</SheetTitle><SheetDescription>Enter punch times in UTC. The list displays your local time.</SheetDescription></SheetHeader>
    <Form {...form}><form id="dtr-edit-form" onSubmit={form.handleSubmit(submit)} className="flex-1 space-y-4 px-4">
      {form.formState.errors.root?.server?.message && <p role="alert">{form.formState.errors.root.server.message}</p>}
      {(['login_date', 'logout_date'] as const).map(name => <FormField key={name} control={form.control} name={name} render={({ field }) => <FormItem><FormLabel>{name === 'login_date' ? 'Login Time (UTC)' : 'Logout Time (UTC)'}</FormLabel><FormControl><Input type="datetime-local" {...field} data-testid={'dtr-' + (name === 'login_date' ? 'login' : 'logout') + '-input'} /></FormControl><FormMessage /></FormItem>} />)}
    </form></Form>
    <SheetFooter><SheetClose asChild><Button variant="outline">Cancel</Button></SheetClose><Button type="submit" form="dtr-edit-form" disabled={update.isPending} data-testid="dtr-update-button">Update</Button></SheetFooter>
  </SheetContent></Sheet>
}
