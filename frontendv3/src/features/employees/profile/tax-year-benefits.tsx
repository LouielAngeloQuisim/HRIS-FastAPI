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
import { useLeavePolicies } from '@/lib/api/leave-policies'

type Props = { employeeId: string; taxYear: number }

export function TaxYearBenefits({ employeeId, taxYear }: Props) {
  const canApprove = useCan('payroll', 'approve')
  const query = useEmployeeTaxYearBenefits(employeeId, taxYear)
  const leavePolicies = useLeavePolicies(1, 200)
  const record = useRecordEmployeeTaxYearBenefit(employeeId, taxYear)
  const [paidOn, setPaidOn] = useState('')
  const [benefitType, setBenefitType] = useState<EmployeeTaxBenefit['benefit_type']>('thirteenth_month')
  const [deMinimisCategory, setDeMinimisCategory] = useState('rice_subsidy')
  const [eligibilityEvidence, setEligibilityEvidence] = useState<string[]>([])
  const [qualifyingDays, setQualifyingDays] = useState('')
  const [vacationLeavePolicyId, setVacationLeavePolicyId] = useState('')
  const [qualifyingWorkDates, setQualifyingWorkDates] = useState('')
  const [dailyMinimumWage, setDailyMinimumWage] = useState('')
  const [regionCode, setRegionCode] = useState('')
  const [wageOrderReference, setWageOrderReference] = useState('')
  const [wageOrderEffectiveFrom, setWageOrderEffectiveFrom] = useState('')
  const [wageOrderEffectiveTo, setWageOrderEffectiveTo] = useState('')
  const [amount, setAmount] = useState('')
  const [source, setSource] = useState('')
  const [reason, setReason] = useState('')
  const [reversal, setReversal] = useState<EmployeeTaxBenefit | null>(null)

  const reversedIds = useMemo(
    () => new Set((query.data ?? []).map(row => row.correction_of_id).filter(Boolean)),
    [query.data]
  )
  const parsedWorkDates = qualifyingWorkDates
    .split(/[\s,]+/)
    .map(value => value.trim())
    .filter(Boolean)

  const submit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    record.mutate({
      paid_on: paidOn,
      benefit_type: reversal?.benefit_type ?? benefitType,
      de_minimis_category: reversal?.de_minimis_category ?? (benefitType === 'de_minimis' ? deMinimisCategory : null),
      eligibility_evidence: reversal?.eligibility_evidence ?? eligibilityEvidence,
      qualifying_days: reversal?.qualifying_days ?? (benefitType === 'de_minimis' && deMinimisCategory === 'daily_meal_ot_night' ? parsedWorkDates.length : benefitType === 'de_minimis' && deMinimisCategory === 'monetized_unused_vacation_leave' && qualifyingDays ? Number(qualifyingDays) : null),
      vacation_leave_policy_id: reversal?.vacation_leave_policy_id ?? (benefitType === 'de_minimis' && deMinimisCategory === 'monetized_unused_vacation_leave' ? vacationLeavePolicyId : null),
      qualifying_work_dates: reversal?.qualifying_work_dates ?? (benefitType === 'de_minimis' && deMinimisCategory === 'daily_meal_ot_night' ? parsedWorkDates : null),
      regional_daily_minimum_wage: reversal?.regional_daily_minimum_wage ?? (benefitType === 'de_minimis' && deMinimisCategory === 'daily_meal_ot_night' ? dailyMinimumWage || null : null),
      region_code: reversal?.region_code ?? (benefitType === 'de_minimis' && deMinimisCategory === 'daily_meal_ot_night' ? regionCode.trim() || null : null),
      wage_order_reference: reversal?.wage_order_reference ?? (benefitType === 'de_minimis' && deMinimisCategory === 'daily_meal_ot_night' ? wageOrderReference.trim() || null : null),
      wage_order_effective_from: reversal?.wage_order_effective_from ?? (benefitType === 'de_minimis' && deMinimisCategory === 'daily_meal_ot_night' ? wageOrderEffectiveFrom || null : null),
      wage_order_effective_to: reversal?.wage_order_effective_to ?? (benefitType === 'de_minimis' && deMinimisCategory === 'daily_meal_ot_night' ? wageOrderEffectiveTo || null : null),
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
        setQualifyingDays('')
        setVacationLeavePolicyId('')
        setQualifyingWorkDates('')
        setDailyMinimumWage('')
        setRegionCode('')
        setWageOrderReference('')
        setWageOrderEffectiveFrom('')
        setWageOrderEffectiveTo('')
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
                  {item.qualifying_days != null ? (
                    <p className='text-muted-foreground'>
                      {item.qualifying_days} qualifying day(s)
                      {item.region_code ? ` · ${item.region_code} wage order ${item.wage_order_reference} · ₱${item.regional_daily_minimum_wage}/day` : ''}
                      {typeof item.eligibility_snapshot?.policy_name === 'string' ? ` · ${item.eligibility_snapshot.policy_name}` : ''}
                    </p>
                  ) : null}
                  {item.qualifying_work_dates?.length ? (
                    <p className='text-muted-foreground'>Attendance dates: {item.qualifying_work_dates.join(', ')}</p>
                  ) : null}
                  {item.wage_order_effective_from ? (
                    <p className='text-muted-foreground'>Wage order effective: {item.wage_order_effective_from} to {item.wage_order_effective_to ?? 'open-ended'}</p>
                  ) : null}
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
                    setQualifyingDays(item.qualifying_days == null ? '' : String(item.qualifying_days))
                    setVacationLeavePolicyId(item.vacation_leave_policy_id ?? '')
                    setQualifyingWorkDates((item.qualifying_work_dates ?? []).join(', '))
                    setDailyMinimumWage(item.regional_daily_minimum_wage ?? '')
                    setRegionCode(item.region_code ?? '')
                    setWageOrderReference(item.wage_order_reference ?? '')
                    setWageOrderEffectiveFrom(item.wage_order_effective_from ?? '')
                    setWageOrderEffectiveTo(item.wage_order_effective_to ?? '')
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
                if (nextType !== 'de_minimis') {
                  setEligibilityEvidence([])
                  setQualifyingDays('')
                  setQualifyingWorkDates('')
                  setDailyMinimumWage('')
                  setRegionCode('')
                  setWageOrderReference('')
                  setWageOrderEffectiveFrom('')
                  setWageOrderEffectiveTo('')
                }
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
                  setQualifyingDays('')
                  setQualifyingWorkDates('')
                  setDailyMinimumWage('')
                  setRegionCode('')
                  setWageOrderReference('')
                  setWageOrderEffectiveFrom('')
                  setWageOrderEffectiveTo('')
                }}>
                  <option value='medical_cash_dependents'>Medical cash allowance to dependents</option>
                  <option value='rice_subsidy'>Rice subsidy</option>
                  <option value='uniform_clothing'>Uniform and clothing</option>
                  <option value='actual_medical_assistance'>Actual medical assistance</option>
                  <option value='laundry_allowance'>Laundry allowance</option>
                  <option value='achievement_award'>Achievement award</option>
                  <option value='christmas_anniversary_gift'>Christmas or anniversary gift</option>
                  <option value='cba_productivity_incentive'>CBA or productivity incentive</option>
                  <option value='daily_meal_ot_night'>Meal allowance for overtime/night shift</option>
                  <option value='monetized_unused_vacation_leave'>Monetized unused vacation leave</option>
                </select>
              </label>
            ) : null}
            {benefitType === 'de_minimis' && ['daily_meal_ot_night', 'monetized_unused_vacation_leave'].includes(deMinimisCategory) ? (
              <>
                {deMinimisCategory === 'daily_meal_ot_night' ? (
                  <>
                    <label className='flex flex-col gap-1 text-sm sm:col-span-2'>Qualifying attendance dates (YYYY-MM-DD, comma or space separated)
                      <Input required disabled={Boolean(reversal)} value={reversal?.qualifying_work_dates?.join(', ') ?? qualifyingWorkDates} onChange={event => setQualifyingWorkDates(event.target.value)} placeholder='2026-07-01, 2026-07-02' />
                    </label>
                    <p className='text-xs text-muted-foreground sm:col-span-2'>Each date must have a matching attendance record proving approved overtime or night work. The server checks the records before saving.</p>
                    <p className='text-xs text-muted-foreground sm:col-span-2'>
                      Use one record per region and wage order. If qualifying days span different regional rates, split the paid amount and days into separate sourced records.
                    </p>
                    <label className='flex flex-col gap-1 text-sm'>Regional daily minimum wage
                      <Input type='number' min='0.01' step='0.01' required disabled={Boolean(reversal)} value={reversal?.regional_daily_minimum_wage ?? dailyMinimumWage} onChange={event => setDailyMinimumWage(event.target.value)} />
                    </label>
                    <label className='flex flex-col gap-1 text-sm'>Region code
                      <Input required minLength={2} disabled={Boolean(reversal)} value={reversal?.region_code ?? regionCode} onChange={event => setRegionCode(event.target.value)} />
                    </label>
                    <label className='flex flex-col gap-1 text-sm'>Wage order source reference
                      <Input required minLength={3} disabled={Boolean(reversal)} value={reversal?.wage_order_reference ?? wageOrderReference} onChange={event => setWageOrderReference(event.target.value)} />
                    </label>
                    <label className='flex flex-col gap-1 text-sm'>Wage order effective from
                      <Input aria-label='Wage order effective from' type='date' required disabled={Boolean(reversal)} value={reversal?.wage_order_effective_from ?? wageOrderEffectiveFrom} onChange={event => setWageOrderEffectiveFrom(event.target.value)} />
                    </label>
                    <label className='flex flex-col gap-1 text-sm'>Wage order effective to (optional)
                      <Input aria-label='Wage order effective to' type='date' disabled={Boolean(reversal)} value={reversal?.wage_order_effective_to ?? wageOrderEffectiveTo} onChange={event => setWageOrderEffectiveTo(event.target.value)} />
                    </label>
                    <label className='flex items-center gap-2 text-sm sm:col-span-2'>
                      <input type='checkbox' disabled={Boolean(reversal)} checked={eligibilityEvidence.includes('approved_overtime_or_night_shift_records')} onChange={event => setEligibilityEvidence(current => event.target.checked ? [...current, 'approved_overtime_or_night_shift_records'] : current.filter(item => item !== 'approved_overtime_or_night_shift_records'))} />
                      Approved overtime or night-shift records verified for these days
                    </label>
                  </>
                ) : (
                  <>
                    <label className='flex flex-col gap-1 text-sm'>Eligible paid vacation leave policy
                      <select className='h-9 rounded-md border bg-background px-3' required disabled={Boolean(reversal) || leavePolicies.isPending || leavePolicies.isError} value={reversal?.vacation_leave_policy_id ?? vacationLeavePolicyId} onChange={event => setVacationLeavePolicyId(event.target.value)}>
                        <option value=''>Select policy</option>
                {(leavePolicies.data?.data ?? []).filter(policy => policy.is_active && !policy.is_deleted && policy.is_paid && policy.tax_exempt_unused_vacation_leave).map(policy => <option key={policy.id} value={policy.id}>{policy.name} ({policy.code})</option>)}
                      </select>
                    </label>
                    {leavePolicies.isError ? <p role='alert' className='text-sm text-destructive'>Vacation policies could not be loaded; retry before recording monetized leave.</p> : null}
                    {leavePolicies.isSuccess && !(leavePolicies.data?.data ?? []).some(policy => policy.is_active && !policy.is_deleted && policy.is_paid && policy.tax_exempt_unused_vacation_leave) ? <p className='text-xs text-muted-foreground'>No eligible policy is configured. An authorized user must mark the paid vacation policy as eligible in Leave Policies first.</p> : null}
                    <label className='flex flex-col gap-1 text-sm'>Qualifying eligible days
                      <Input type='number' min='1' max='366' step='1' required disabled={Boolean(reversal)} value={reversal?.qualifying_days ?? qualifyingDays} onChange={event => setQualifyingDays(event.target.value)} />
                    </label>
                    <p className='text-xs text-muted-foreground sm:col-span-2'>The server checks the employee’s active enrollment and leave-ledger balance, then records the balance debit with this benefit. A checkbox cannot establish eligibility.</p>
                  </>
                )}
              </>
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
              <Button type='submit' disabled={record.isPending || !paidOn || !source.trim() || (reversal ? !reason.trim() : !amount || Number(amount) <= 0) || (benefitType === 'de_minimis' && deMinimisCategory === 'actual_medical_assistance' && !eligibilityEvidence.includes('actual_medical_documentation')) || (benefitType === 'de_minimis' && deMinimisCategory === 'achievement_award' && !eligibilityEvidence.includes('written_non_discriminatory_award_plan')) || (benefitType === 'de_minimis' && deMinimisCategory === 'cba_productivity_incentive' && !eligibilityEvidence.includes('cba_or_productivity_incentive_evidence')) || (benefitType === 'de_minimis' && deMinimisCategory === 'daily_meal_ot_night' && (parsedWorkDates.length < 1 || new Set(parsedWorkDates).size !== parsedWorkDates.length)) || (benefitType === 'de_minimis' && deMinimisCategory === 'monetized_unused_vacation_leave' && (!qualifyingDays || Number(qualifyingDays) < 1 || !vacationLeavePolicyId)) || (benefitType === 'de_minimis' && deMinimisCategory === 'daily_meal_ot_night' && (!dailyMinimumWage || !regionCode.trim() || !wageOrderReference.trim() || !wageOrderEffectiveFrom || !eligibilityEvidence.includes('approved_overtime_or_night_shift_records') || (Boolean(wageOrderEffectiveTo) && wageOrderEffectiveTo < wageOrderEffectiveFrom)))}>
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
