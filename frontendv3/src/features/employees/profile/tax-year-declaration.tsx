import { useEffect, useState } from 'react'
import { useCan } from '@/context/permissions-provider'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  useEmployeeTaxYearDeclaration,
  useSaveEmployeeTaxYearDeclaration,
} from '@/lib/api/payroll'

type Props = { employeeId: string; taxYear: number }

export function TaxYearDeclaration({ employeeId, taxYear }: Props) {
  const canVerify = useCan('payroll', 'approve')
  const query = useEmployeeTaxYearDeclaration(employeeId, taxYear)
  const save = useSaveEmployeeTaxYearDeclaration(employeeId, taxYear)
  const [classification, setClassification] = useState<'ordinary' | 'minimum_wage_earner'>('ordinary')
  const [taxableYtd, setTaxableYtd] = useState('0.00')
  const [withheldYtd, setWithheldYtd] = useState('0.00')
  const [previousEmployer, setPreviousEmployer] = useState(false)
  const [sourceReference, setSourceReference] = useState('')
  const [confirmReviewed, setConfirmReviewed] = useState(false)

  useEffect(() => {
    const row = query.data
    if (!row) return
    setClassification(row.tax_classification)
    setTaxableYtd(row.taxable_compensation_ytd)
    setWithheldYtd(row.tax_withheld_ytd)
    setPreviousEmployer(row.previous_employer_included)
    setSourceReference(row.source_reference ?? '')
    setConfirmReviewed(row.is_verified)
  }, [query.data])

  if (query.isPending) return <Card><CardContent className='py-5 text-sm text-muted-foreground'>Loading tax-year inputs…</CardContent></Card>
  if (query.isError) return <p role='alert' className='text-sm text-destructive'>Tax-year inputs could not be loaded.</p>

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    save.mutate({
      tax_classification: classification,
      taxable_compensation_ytd: taxableYtd,
      tax_withheld_ytd: withheldYtd,
      previous_employer_included: previousEmployer,
      source_reference: sourceReference.trim() || null,
      is_verified: confirmReviewed,
    })
  }

  return (
    <Card>
      <CardHeader><CardTitle className='text-base'>BIR tax-year inputs · {taxYear}</CardTitle></CardHeader>
      <CardContent className='space-y-4'>
        {query.data?.is_verified ? (
          <p className='text-sm text-muted-foreground'>Reviewed by payroll approver on {new Date(query.data.verified_at ?? '').toLocaleDateString()}.</p>
        ) : (
          <p role='status' className='text-sm text-amber-700'>Tax inputs are unverified. Payroll remains blocked until reviewed.</p>
        )}
        {!canVerify ? <p className='text-sm text-muted-foreground'>Payroll approval permission is required to edit or verify these figures.</p> : (
          <form onSubmit={handleSubmit} className='space-y-4'>
            <label className='flex flex-col gap-1 text-sm'>Tax classification
              <select className='h-9 rounded-md border bg-background px-3' value={classification} onChange={(event) => setClassification(event.target.value as typeof classification)}>
                <option value='ordinary'>Ordinary compensation earner</option>
                <option value='minimum_wage_earner'>Minimum-wage earner (requires HR confirmation)</option>
              </select>
            </label>
            <div className='grid gap-3 sm:grid-cols-2'>
              <label className='flex flex-col gap-1 text-sm'>Taxable compensation already paid this year
                <Input type='number' min='0' step='0.01' required value={taxableYtd} onChange={(event) => setTaxableYtd(event.target.value)} />
              </label>
              <label className='flex flex-col gap-1 text-sm'>Withholding tax already withheld this year
                <Input type='number' min='0' step='0.01' required value={withheldYtd} onChange={(event) => setWithheldYtd(event.target.value)} />
              </label>
            </div>
            <label className='flex items-center gap-2 text-sm'>
              <input type='checkbox' checked={previousEmployer} onChange={(event) => setPreviousEmployer(event.target.checked)} />
              Figures include a previous employer
            </label>
            <label className='flex flex-col gap-1 text-sm'>Source / review note (for example, Form 2316)
              <Input maxLength={512} value={sourceReference} onChange={(event) => setSourceReference(event.target.value)} />
            </label>
            {previousEmployer && !sourceReference.trim() ? <p role='alert' className='text-sm text-destructive'>Add a source note before verifying previous-employer figures.</p> : null}
            <label className='flex items-start gap-2 text-sm'>
              <input type='checkbox' checked={confirmReviewed} onChange={(event) => setConfirmReviewed(event.target.checked)} />
              I reviewed these figures against payroll records and available tax documents.
            </label>
            {save.isError ? <p role='alert' className='text-sm text-destructive'>Tax-year inputs could not be saved. Check for finalized payroll or permission conflicts.</p> : null}
            {save.isSuccess ? <p role='status' className='text-sm text-green-700'>Tax-year inputs saved.</p> : null}
            <Button type='submit' disabled={save.isPending || (previousEmployer && !sourceReference.trim())}>
              {save.isPending ? 'Saving…' : 'Save tax-year inputs'}
            </Button>
          </form>
        )}
      </CardContent>
    </Card>
  )
}
