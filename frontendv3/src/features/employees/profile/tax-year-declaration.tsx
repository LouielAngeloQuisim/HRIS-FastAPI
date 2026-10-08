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
import { TaxYearBenefits } from './tax-year-benefits'

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
    <div className='space-y-4'>
      <TaxYearDeclarationEditor
        key={`${employeeId}-${taxYear}-${query.data?.updated_at ?? 'new'}`}
        initialData={query.data ?? null}
        taxYear={taxYear}
        save={save}
      />
      <TaxYearBenefits employeeId={employeeId} taxYear={taxYear} />
    </div>
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
  const [openingBenefitsExemptYtd, setOpeningBenefitsExemptYtd] = useState(
    initialData?.opening_benefits_exempt_ytd ?? '0.00'
  )
  const [openingBenefitsReconciled, setOpeningBenefitsReconciled] = useState(
    initialData?.opening_benefits_reconciled ?? false
  )
  const [annualDeMinimis, setAnnualDeMinimis] = useState<Record<string, string>>({
    uniform_clothing: '0.00',
    actual_medical_assistance: '0.00',
    achievement_award: '0.00',
    christmas_anniversary_gift: '0.00',
    cba_productivity_incentive: '0.00',
    ...initialData?.opening_de_minimis_annual_ytd,
  })
  const [monthlyDeMinimis, setMonthlyDeMinimis] = useState<Record<string, string>>({
    medical_cash_dependents: '0.00',
    rice_subsidy: '0.00',
    laundry_allowance: '0.00',
    ...initialData?.opening_de_minimis_monthly_ytd,
  })
  const [sourceReference, setSourceReference] = useState(
    initialData?.source_reference ?? ''
  )
  const [confirmReviewed, setConfirmReviewed] = useState(
    initialData?.is_verified ?? false
  )
  const openingHistoryIncluded =
    previousEmployer || Number(taxableYtd) > 0 || Number(withheldYtd) > 0 || Number(openingBenefitsExemptYtd) > 0

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
      opening_benefits_exempt_ytd: openingBenefitsExemptYtd,
      opening_benefits_reconciled: openingBenefitsReconciled,
      opening_de_minimis_annual_ytd: openingBenefitsReconciled ? annualDeMinimis : {},
      opening_de_minimis_monthly_ytd: openingBenefitsReconciled ? monthlyDeMinimis : {},
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
            <label className='flex flex-col gap-1 text-sm'>
              Opening benefits already counted toward the ₱90,000 exemption
              <Input
                type='number'
                min='0'
                max='90000'
                step='0.01'
                required
                value={openingBenefitsExemptYtd}
                onChange={(event) => setOpeningBenefitsExemptYtd(event.target.value)}
              />
              <span className='text-xs text-muted-foreground'>
                Enter the exempt portion through the opening date, not the taxable excess. Use source payroll/tax records; later payments must be recorded below.
              </span>
            </label>
            <label className='flex items-start gap-2 text-sm'>
              <input
                type='checkbox'
                checked={openingBenefitsReconciled}
                onChange={(event) => setOpeningBenefitsReconciled(event.target.checked)}
              />
              I reconciled 13th-month and other benefit payments through the opening date against source records.
            </label>
            {openingBenefitsReconciled ? (
              <fieldset className='space-y-3 rounded-md border p-3 sm:col-span-2'>
                <legend className='px-1 text-sm font-medium'>De minimis amounts already paid through the opening date</legend>
                <p className='text-xs text-muted-foreground'>Enter prior totals by category, including zero where none were paid. Monthly amounts apply to the month containing the opening date. These keep statutory category ceilings continuous across employers and payroll history.</p>
                <div className='grid gap-3 sm:grid-cols-2'>
                  {Object.entries({
                    uniform_clothing: 'Uniform/clothing · annual',
                    actual_medical_assistance: 'Actual medical assistance · annual',
                    achievement_award: 'Achievement award · annual',
                    christmas_anniversary_gift: 'Christmas/anniversary gift · annual',
                    cba_productivity_incentive: 'CBA/productivity incentive · annual',
                  }).map(([key, label]) => (
                    <label key={key} className='flex flex-col gap-1 text-sm'>{label}
                      <Input type='number' min='0' step='0.01' required value={annualDeMinimis[key] ?? '0.00'} onChange={event => setAnnualDeMinimis(current => ({ ...current, [key]: event.target.value }))} />
                    </label>
                  ))}
                  {Object.entries({
                    medical_cash_dependents: 'Medical cash to dependents · monthly',
                    rice_subsidy: 'Rice subsidy · monthly',
                    laundry_allowance: 'Laundry allowance · monthly',
                  }).map(([key, label]) => (
                    <label key={key} className='flex flex-col gap-1 text-sm'>{label}
                      <Input type='number' min='0' step='0.01' required value={monthlyDeMinimis[key] ?? '0.00'} onChange={event => setMonthlyDeMinimis(current => ({ ...current, [key]: event.target.value }))} />
                    </label>
                  ))}
                </div>
              </fieldset>
            ) : null}
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
            {classification === 'minimum_wage_earner' ? (
              <p className='text-xs text-muted-foreground'>
                BIR exemption is applied only to the statutory minimum wage and
                approved overtime captured here. Before verifying, confirm the
                employee is paid the applicable rate for their assigned work
                location and cite the DOLE regional wage order below. Payroll
                remains blocked for unsupported taxable allowances or benefits.
              </p>
            ) : null}
            <label className='flex flex-col gap-1 text-sm'>
              Source / review note
              <Input
                maxLength={512}
                required={
                  openingHistoryIncluded ||
                  classification === 'minimum_wage_earner' ||
                  Number(openingBenefitsExemptYtd) > 0 ||
                  openingBenefitsReconciled
                }
                value={sourceReference}
                onChange={(event) => setSourceReference(event.target.value)}
              />
            </label>
            {(openingHistoryIncluded ||
              classification === 'minimum_wage_earner' ||
              Number(openingBenefitsExemptYtd) > 0 ||
              openingBenefitsReconciled) &&
            !sourceReference.trim() ? (
              <p role='alert' className='text-sm text-destructive'>
                Add the required supporting source before verifying these tax inputs.
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
                ((previousEmployer || Number(openingBenefitsExemptYtd) > 0) && !openingBenefitsReconciled) ||
                ((openingHistoryIncluded ||
                  classification === 'minimum_wage_earner' ||
                  Number(openingBenefitsExemptYtd) > 0 ||
                  openingBenefitsReconciled) &&
                  !sourceReference.trim()) ||
                (openingHistoryIncluded && !Number(openingPayPeriodCount))
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
