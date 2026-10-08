import { useMemo, useState } from 'react'
import { useCan } from '@/context/permissions-provider'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  useEmployeeTaxYearBenefits,
  useRecordEmployeeTaxYearBenefit,
  type EmployeeTaxBenefit,
} from '@/lib/api/payroll'

type Props = { employeeId: string; taxYear: number }

export function TaxYearBenefits({ employeeId, taxYear }: Props) {
  const canApprove = useCan('payroll', 'approve')
  const query = useEmployeeTaxYearBenefits(employeeId, taxYear)
  const record = useRecordEmployeeTaxYearBenefit(employeeId, taxYear)
  const [paidOn, setPaidOn] = useState('')
  const [benefitType, setBenefitType] = useState<EmployeeTaxBenefit['benefit_type']>('thirteenth_month')
  const [deMinimisCategory, setDeMinimisCategory] = useState('rice_subsidy')
  const [eligibilityEvidence, setEligibilityEvidence] = useState<string[]>([])
  const [amount, setAmount] = useState('')
  const [source, setSource] = useState('')
  const [reason, setReason] = useState('')
  const [reversal, setReversal] = useState<EmployeeTaxBenefit | null>(null)

  const reversedIds = useMemo(
    () => new Set((query.data ?? []).map(row => row.correction_of_id).filter(Boolean)),
    [query.data]
  )

  const submit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    record.mutate({
      paid_on: paidOn,
      benefit_type: reversal?.benefit_type ?? benefitType,
      de_minimis_category: reversal?.de_minimis_category ?? (benefitType === 'de_minimis' ? deMinimisCategory : null),
      eligibility_evidence: reversal?.eligibility_evidence ?? eligibilityEvidence,
      gross_amount: reversal ? `-${reversal.gross_amount}` : amount,
      source_reference: source.trim(),
      correction_of_id: reversal?.id ?? null,
      correction_reason: reversal ? reason.trim() : null,
    }, {
      onSuccess: () => {
        setAmount('')
        setSource('')
        setReason('')
        setEligibilityEvidence([])
        setReversal(null)
      },
    })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className='text-base'>13th-month and other benefits · {taxYear}</CardTitle>
      </CardHeader>
      <CardContent className='space-y-4'>
        <p className='text-sm text-muted-foreground'>
          Record benefits actually paid that use BIR’s shared ₱90,000 annual exemption. The annual payroll adjustment taxes the excess. Keep the payment voucher or other source reference with each entry.
        </p>
        {query.isPending ? <p role='status'>Loading benefit payments…</p> : null}
        {query.isError ? <p role='alert' className='text-sm text-destructive'>Benefit payments could not be loaded.</p> : null}
        {(query.data ?? []).length ? (
          <ul className='divide-y rounded-md border'>
            {(query.data ?? []).map(item => (
              <li key={item.id} className='flex flex-wrap items-center justify-between gap-3 p-3 text-sm'>
                <div>
                  <p className='font-medium'>
                    {item.paid_on} · {item.benefit_type === 'thirteenth_month' ? '13th-month pay' : item.benefit_type === 'de_minimis' ? `De minimis · ${item.de_minimis_category?.replace(/_/g, ' ')}` : 'Other benefit'} · ₱{item.gross_amount}
                  </p>
                  <p className='text-muted-foreground'>
                    {item.correction_of_id ? `Reversal: ${item.correction_reason}` : item.source_reference}
                  </p>
                </div>
                {canApprove && !item.correction_of_id && !reversedIds.has(item.id) ? (
                  <Button type='button' variant='outline' size='sm' onClick={() => {
                    setReversal(item)
                    setBenefitType(item.benefit_type)
                    setDeMinimisCategory(item.de_minimis_category ?? 'rice_subsidy')
                    setEligibilityEvidence(item.eligibility_evidence)
                  }}>
                    Reverse record
                  </Button>
                ) : null}
              </li>
            ))}
          </ul>
        ) : query.isSuccess ? <p className='text-sm text-muted-foreground'>No paid benefit records for this tax year.</p> : null}
        {canApprove ? (
          <form onSubmit={submit} className='grid gap-3 rounded-md border p-3 sm:grid-cols-2'>
            <label className='flex flex-col gap-1 text-sm'>Paid date
              <Input type='date' required value={paidOn} onChange={event => setPaidOn(event.target.value)} />
            </label>
            <label className='flex flex-col gap-1 text-sm'>Benefit type
              <select className='h-9 rounded-md border bg-background px-3' value={reversal?.benefit_type ?? benefitType} disabled={Boolean(reversal)} onChange={event => {
                const nextType = event.target.value as typeof benefitType
                setBenefitType(nextType)
                if (nextType !== 'de_minimis') setEligibilityEvidence([])
              }}>
                <option value='thirteenth_month'>13th-month pay</option>
                <option value='other_benefit'>Other benefit subject to the shared ceiling</option>
                <option value='de_minimis'>De minimis benefit</option>
              </select>
            </label>
            {benefitType === 'de_minimis' ? (
              <label className='flex flex-col gap-1 text-sm'>De minimis category
                <select className='h-9 rounded-md border bg-background px-3' value={reversal?.de_minimis_category ?? deMinimisCategory} disabled={Boolean(reversal)} onChange={event => {
                  setDeMinimisCategory(event.target.value)
                  setEligibilityEvidence([])
                }}>
                  <option value='medical_cash_dependents'>Medical cash allowance to dependents</option>
                  <option value='rice_subsidy'>Rice subsidy</option>
                  <option value='uniform_clothing'>Uniform and clothing</option>
                  <option value='actual_medical_assistance'>Actual medical assistance</option>
                  <option value='laundry_allowance'>Laundry allowance</option>
                  <option value='achievement_award'>Achievement award</option>
                  <option value='christmas_anniversary_gift'>Christmas or anniversary gift</option>
                  <option value='cba_productivity_incentive'>CBA or productivity incentive</option>
                </select>
              </label>
            ) : null}
            {benefitType === 'de_minimis' && deMinimisCategory === 'actual_medical_assistance' ? (
              <label className='flex items-center gap-2 text-sm'>
                <input type='checkbox' disabled={Boolean(reversal)} checked={eligibilityEvidence.includes('actual_medical_documentation')} onChange={event => setEligibilityEvidence(current => event.target.checked ? [...current, 'actual_medical_documentation'] : current.filter(item => item !== 'actual_medical_documentation'))} />
                Actual medical expense documentation verified
              </label>
            ) : null}
            {benefitType === 'de_minimis' && deMinimisCategory === 'achievement_award' ? (
              <label className='flex items-center gap-2 text-sm'>
                <input type='checkbox' disabled={Boolean(reversal)} checked={eligibilityEvidence.includes('written_non_discriminatory_award_plan')} onChange={event => setEligibilityEvidence(current => event.target.checked ? [...current, 'written_non_discriminatory_award_plan'] : current.filter(item => item !== 'written_non_discriminatory_award_plan'))} />
                Written non-discriminatory award plan verified
              </label>
            ) : null}
            {benefitType === 'de_minimis' && deMinimisCategory === 'cba_productivity_incentive' ? (
              <label className='flex items-center gap-2 text-sm'>
                <input type='checkbox' disabled={Boolean(reversal)} checked={eligibilityEvidence.includes('cba_or_productivity_incentive_evidence')} onChange={event => setEligibilityEvidence(current => event.target.checked ? [...current, 'cba_or_productivity_incentive_evidence'] : current.filter(item => item !== 'cba_or_productivity_incentive_evidence'))} />
                CBA or productivity-incentive evidence verified
              </label>
            ) : null}
            <label className='flex flex-col gap-1 text-sm'>
              {reversal ? `Full reversal amount (₱${reversal.gross_amount})` : 'Gross amount paid'}
              <Input type='number' min='0.01' step='0.01' required disabled={Boolean(reversal)} value={reversal ? reversal.gross_amount : amount} onChange={event => setAmount(event.target.value)} />
            </label>
            <label className='flex flex-col gap-1 text-sm'>Payment source reference
              <Input required minLength={3} maxLength={512} value={source} onChange={event => setSource(event.target.value)} />
            </label>
            {reversal ? (
              <label className='flex flex-col gap-1 text-sm sm:col-span-2'>Reason for full reversal
                <Input required minLength={3} maxLength={512} value={reason} onChange={event => setReason(event.target.value)} />
              </label>
            ) : null}
            <div className='flex gap-2 sm:col-span-2'>
              {reversal ? <Button type='button' variant='outline' onClick={() => setReversal(null)}>Cancel reversal</Button> : null}
              <Button type='submit' disabled={record.isPending || !paidOn || !source.trim() || (reversal ? !reason.trim() : !amount || Number(amount) <= 0) || (benefitType === 'de_minimis' && deMinimisCategory === 'actual_medical_assistance' && !eligibilityEvidence.includes('actual_medical_documentation')) || (benefitType === 'de_minimis' && deMinimisCategory === 'achievement_award' && !eligibilityEvidence.includes('written_non_discriminatory_award_plan')) || (benefitType === 'de_minimis' && deMinimisCategory === 'cba_productivity_incentive' && !eligibilityEvidence.includes('cba_or_productivity_incentive_evidence'))}>
                {record.isPending ? 'Saving…' : reversal ? 'Record full reversal' : 'Record paid benefit'}
              </Button>
            </div>
            {record.isError ? <p role='alert' className='text-sm text-destructive sm:col-span-2'>Benefit record could not be saved. Finalized tax years are locked.</p> : null}
          </form>
        ) : <p className='text-sm text-muted-foreground'>Payroll approval permission is required to record or reverse benefit payments.</p>}
      </CardContent>
    </Card>
  )
}
