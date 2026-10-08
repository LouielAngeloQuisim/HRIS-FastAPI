import { useState } from 'react'
import {
  useEmployeeTaxYearDeclaration,
  useSaveEmployeeTaxYearDeclaration,
  type EmployeeTaxYearDeclaration,
} from '@/lib/api/payroll'
import { useCan } from '@/context/permissions-provider'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'

type Props = { employeeId: string; taxYear: number }

export function TaxYearDeclaration({ employeeId, taxYear }: Props) {
  const query = useEmployeeTaxYearDeclaration(employeeId, taxYear)
  const save = useSaveEmployeeTaxYearDeclaration(employeeId, taxYear)

  if (query.isPending) {
    return (
      <Card>
        <CardContent className='py-5 text-sm text-muted-foreground'>
          Loading tax-year inputs…
        </CardContent>
      </Card>
    )
  }
  if (query.isError) {
    return (
      <p role='alert' className='text-sm text-destructive'>
        Tax-year inputs could not be loaded.
      </p>
    )
  }

  return (
    <TaxYearDeclarationEditor
      key={`${employeeId}-${taxYear}-${query.data?.updated_at ?? 'new'}`}
      initialData={query.data ?? null}
      taxYear={taxYear}
      save={save}
    />
  )
}

type EditorProps = {
  initialData: EmployeeTaxYearDeclaration | null
  taxYear: number
  save: ReturnType<typeof useSaveEmployeeTaxYearDeclaration>
}

function TaxYearDeclarationEditor({ initialData, taxYear, save }: EditorProps) {
  const canVerify = useCan('payroll', 'approve')
  const [classification, setClassification] = useState<
    'ordinary' | 'minimum_wage_earner'
  >(initialData?.tax_classification ?? 'ordinary')
  const [openingAsOf, setOpeningAsOf] = useState(
    initialData?.opening_as_of ?? ''
  )
  const [taxableYtd, setTaxableYtd] = useState(
    initialData?.taxable_compensation_ytd ?? '0.00'
  )
  const [withheldYtd, setWithheldYtd] = useState(
    initialData?.tax_withheld_ytd ?? '0.00'
  )
  const [openingPayPeriodCount, setOpeningPayPeriodCount] = useState(
    String(initialData?.opening_pay_period_count ?? 0)
  )
  const [openingPayPeriodType, setOpeningPayPeriodType] = useState<
    'daily' | 'weekly' | 'semi_monthly' | 'monthly'
  >(initialData?.opening_pay_period_type ?? 'monthly')
  const [previousEmployer, setPreviousEmployer] = useState(
    initialData?.previous_employer_included ?? false
  )
  const [sourceReference, setSourceReference] = useState(
    initialData?.source_reference ?? ''
  )
  const [confirmReviewed, setConfirmReviewed] = useState(
    initialData?.is_verified ?? false
  )
  const openingHistoryIncluded =
    previousEmployer || Number(taxableYtd) > 0 || Number(withheldYtd) > 0

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    save.mutate({
      tax_classification: classification,
      opening_as_of: openingAsOf,
      taxable_compensation_ytd: taxableYtd,
      tax_withheld_ytd: withheldYtd,
      opening_pay_period_count: openingHistoryIncluded
        ? Number(openingPayPeriodCount)
        : 0,
      opening_pay_period_type: openingHistoryIncluded
        ? openingPayPeriodType
        : null,
      previous_employer_included: previousEmployer,
      source_reference: sourceReference.trim() || null,
      is_verified: confirmReviewed,
    })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className='text-base'>
          BIR tax-year inputs · {taxYear}
        </CardTitle>
      </CardHeader>
      <CardContent className='space-y-4'>
        {initialData?.is_verified ? (
          <p className='text-sm text-muted-foreground'>
            Reviewed by payroll approver on{' '}
            {new Date(initialData.verified_at ?? '').toLocaleDateString()}.
          </p>
        ) : (
          <p role='status' className='text-sm text-amber-700'>
            Tax inputs are unverified. Payroll remains blocked until reviewed.
          </p>
        )}
        {!canVerify ? (
          <p className='text-sm text-muted-foreground'>
            Payroll approval permission is required to edit or verify these
            figures.
          </p>
        ) : (
          <form onSubmit={handleSubmit} className='space-y-4'>
            <label className='flex flex-col gap-1 text-sm'>
              Tax classification
              <select
                className='h-9 rounded-md border bg-background px-3'
                value={classification}
                onChange={(event) =>
                  setClassification(event.target.value as typeof classification)
                }
              >
                <option value='ordinary'>Ordinary compensation earner</option>
                <option value='minimum_wage_earner'>
                  Minimum-wage earner (requires HR confirmation)
                </option>
              </select>
            </label>
            <label className='flex flex-col gap-1 text-sm'>
              Opening balances are complete through
              <Input
                type='date'
                required
                value={openingAsOf}
                onChange={(event) => setOpeningAsOf(event.target.value)}
              />
            </label>
            <div className='grid gap-3 sm:grid-cols-2'>
              <label className='flex flex-col gap-1 text-sm'>
                Taxable compensation already paid this year
                <Input
                  type='number'
                  min='0'
                  step='0.01'
                  required
                  value={taxableYtd}
                  onChange={(event) => setTaxableYtd(event.target.value)}
                />
              </label>
              <label className='flex flex-col gap-1 text-sm'>
                Withholding tax already withheld this year
                <Input
                  type='number'
                  min='0'
                  step='0.01'
                  required
                  value={withheldYtd}
                  onChange={(event) => setWithheldYtd(event.target.value)}
                />
              </label>
            </div>
            <label className='flex items-center gap-2 text-sm'>
              <input
                type='checkbox'
                checked={previousEmployer}
                onChange={(event) => setPreviousEmployer(event.target.checked)}
              />
              Figures include a previous employer
            </label>
            {openingHistoryIncluded ? (
              <label className='flex flex-col gap-1 text-sm'>
                Opening pay frequency
                <select
                  className='h-9 rounded-md border bg-background px-3'
                  value={openingPayPeriodType}
                  onChange={(event) =>
                    setOpeningPayPeriodType(
                      event.target.value as typeof openingPayPeriodType
                    )
                  }
                >
                  <option value='daily'>Daily</option>
                  <option value='weekly'>Weekly</option>
                  <option value='semi_monthly'>Semi-monthly</option>
                  <option value='monthly'>Monthly</option>
                </select>
              </label>
            ) : null}
            {openingHistoryIncluded ? (
              <label className='flex flex-col gap-1 text-sm'>
                Opening payroll periods covered by these totals
                <Input
                  type='number'
                  min='1'
                  max='366'
                  step='1'
                  required
                  value={openingPayPeriodCount}
                  onChange={(event) =>
                    setOpeningPayPeriodCount(event.target.value)
                  }
                />
                <span className='text-xs text-muted-foreground'>
                  Enter the actual pay periods included in the source figures.
                  Payroll uses this count and frequency for BIR
                  cumulative-average withholding.
                </span>
              </label>
            ) : null}
            <label className='flex flex-col gap-1 text-sm'>
              Source / review note (for example, Form 2316)
              <Input
                maxLength={512}
                required={openingHistoryIncluded}
                value={sourceReference}
                onChange={(event) => setSourceReference(event.target.value)}
              />
            </label>
            {openingHistoryIncluded && !sourceReference.trim() ? (
              <p role='alert' className='text-sm text-destructive'>
                Add a source note before verifying opening tax-year figures.
              </p>
            ) : null}
            <label className='flex items-start gap-2 text-sm'>
              <input
                type='checkbox'
                checked={confirmReviewed}
                onChange={(event) => setConfirmReviewed(event.target.checked)}
              />
              I reviewed these figures against payroll records and available tax
              documents.
            </label>
            {save.isError ? (
              <p role='alert' className='text-sm text-destructive'>
                Tax-year inputs could not be saved. Check for finalized payroll
                or permission conflicts.
              </p>
            ) : null}
            {save.isSuccess ? (
              <p role='status' className='text-sm text-green-700'>
                Tax-year inputs saved.
              </p>
            ) : null}
            <Button
              type='submit'
              disabled={
                save.isPending ||
                (openingHistoryIncluded &&
                  (!sourceReference.trim() || !Number(openingPayPeriodCount)))
              }
            >
              {save.isPending ? 'Saving…' : 'Save tax-year inputs'}
            </Button>
          </form>
        )}
      </CardContent>
    </Card>
  )
}
