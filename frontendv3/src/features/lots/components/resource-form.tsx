import { saveErrorMessage } from '@/lib/api/save-error'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'
import { Button } from '@/components/ui/button'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { SelectDropdown } from '@/components/select-dropdown'
import { useCreateLot, useUpdateLot } from '@/lib/api/lots'
import { useBlocks } from '@/lib/api/blocks'
import type { LotsPublic, LotsCreate, LotsUpdate } from '@/lib/api/types'

const formSchema = z.object({
  blocks_id: z.string().min(1, 'Select a parent record'),
  lot_number: z.string().optional(),
  lot_num: z.string().optional().refine(value => !value || Number.isInteger(Number(value)), 'Enter a whole lot number').transform(value => value ? Number(value) : null),
})
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type FormData = any

interface Props {
  item: LotsPublic | null
  onClose: () => void
  open: boolean
}

export function ResourceForm({ item, onClose, open }: Props) {
  const isEdit = Boolean(item?.id)
  const createMutation = useCreateLot()
  const updateMutation = useUpdateLot()
  const { data: blockData, isPending: blocksPending } = useBlocks(1, 100)

  const blockItems = blockData?.data.map((block) => ({
    label: block.block_name,
    value: block.id,
  }))

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      lot_number: item?.lot_name ?? '',
      lot_num: item?.lot_num == null ? '' : String(item.lot_num),
      blocks_id: item?.blocks_id ?? '',
    },
  })

  const onSubmit = async (data: FormData) => {
    const payload = { lot_name: data.lot_number || null, lot_num: data.lot_num, blocks_id: data.blocks_id }
    form.clearErrors('root.server')
    try {
      if (isEdit && item?.id) {
        await updateMutation.mutateAsync({ id: item.id, data: payload as unknown as LotsUpdate })
      } else {
        await createMutation.mutateAsync(payload as unknown as LotsCreate)
      }
      onClose()
    } catch (error) {
      form.setError('root.server', { message: saveErrorMessage(error) })
    }
  }

  const loading = createMutation.isPending || updateMutation.isPending

  return (
    <Sheet open={open} onOpenChange={(v) => { if (!v) onClose() }}>
      <SheetContent className="flex flex-col">
        <SheetHeader>
          <SheetTitle>{isEdit ? 'Update' : 'Create'} Lots</SheetTitle>
          <SheetDescription>
            {isEdit ? 'Update the lot by providing necessary info.' : 'Add a new lot by providing necessary info.'}
          </SheetDescription>
        </SheetHeader>
        <Form {...form}>
          <form id="lots-form" onSubmit={form.handleSubmit(onSubmit)} className="flex-1 space-y-6 overflow-y-auto px-4">
            {form.formState.errors.root?.server?.message && <p role="alert" className="text-destructive">{String(form.formState.errors.root.server.message)}</p>}
            <>
              <FormField control={form.control} name="lot_number" render={({ field }) => (
                <FormItem>
                  <FormLabel>Lot Name</FormLabel>
                  <FormControl><Input {...field} value={field.value ?? ''} data-testid="lots-lot-number-input" /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="lot_num" render={({ field }) => (
                <FormItem>
                  <FormLabel>Lot Number</FormLabel>
                  <FormControl><Input {...field} value={field.value ?? ''} data-testid="lots-numeric-number-input" /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="blocks_id" render={({ field }) => (
                <FormItem>
                  <FormLabel>Block</FormLabel>
                  <FormControl>
                     <SelectDropdown
                       defaultValue={field.value}
                       onValueChange={field.onChange}
                       placeholder="Select block"
                       items={blockItems ?? []}
                       isPending={blocksPending}
                       data-testid="lots-block-select"
                     />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )} />
            </>
          </form>
        </Form>
        <SheetFooter>
          <SheetClose asChild>
            <Button type="button" variant="outline">Cancel</Button>
          </SheetClose>
          <Button type="submit" form="lots-form" disabled={loading} data-testid="lots-submit-button">
            {loading ? 'Saving...' : isEdit ? 'Update' : 'Create'}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
