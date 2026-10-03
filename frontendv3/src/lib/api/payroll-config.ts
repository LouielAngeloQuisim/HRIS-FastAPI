import { keepPreviousData, useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type {
  SSSBracketPublic,
  SSSBracketCreate,
  SSSBracketUpdate,
  SSSBracketList,
  PhilHealthBracketPublic,
  PhilHealthBracketCreate,
  PhilHealthBracketUpdate,
  PhilHealthBracketList,
  PagIBIGBracketPublic,
  PagIBIGBracketCreate,
  PagIBIGBracketUpdate,
  PagIBIGBracketList,
  BIRBracketPublic,
  BIRBracketCreate,
  BIRBracketUpdate,
  BIRBracketList,
} from './types'

const API = ''

// --- SSS -----------------------------------------------------------------------
export const sssBracketsKey = (skip: number, limit: number) => ['payroll-config', 'sss', skip, limit]

export async function fetchSSSBrackets(skip: number, limit: number): Promise<SSSBracketList> {
  const { data } = await api.get<SSSBracketPublic[]>(`${API}/payroll/sss-brackets/`, { params: { skip, limit } })
  return { data, count: data.length }
}

export function useSSSBrackets(skip: number, limit: number) {
  return useQuery({ queryKey: sssBracketsKey(skip, limit), queryFn: () => fetchSSSBrackets(skip, limit), placeholderData: keepPreviousData })
}

export function useSSSBracket(id: string | undefined) {
  return useQuery({ queryKey: ['payroll-config', 'sss', id], queryFn: () => api.get<SSSBracketPublic>(`${API}/payroll/sss-brackets/${id}`).then(r => r.data), enabled: Boolean(id) })
}

export function useCreateSSSBracket() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (data: SSSBracketCreate) => api.post(`${API}/payroll/sss-brackets/`, data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['payroll-config'] }) })
}

export function useUpdateSSSBracket() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: ({ id, data }: { id: string; data: SSSBracketUpdate }) => api.patch(`${API}/payroll/sss-brackets/${id}`, data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['payroll-config'] }) })
}

export function useDeleteSSSBracket() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (id: string) => api.delete(`${API}/payroll/sss-brackets/${id}`).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['payroll-config'] }) })
}

// --- PhilHealth -----------------------------------------------------------------
export const philHealthBracketsKey = (skip: number, limit: number) => ['payroll-config', 'philhealth', skip, limit]

export async function fetchPhilHealthBrackets(skip: number, limit: number): Promise<PhilHealthBracketList> {
  const { data } = await api.get<PhilHealthBracketPublic[]>(`${API}/payroll/philhealth-brackets/`, { params: { skip, limit } })
  return { data, count: data.length }
}

export function usePhilHealthBrackets(skip: number, limit: number) {
  return useQuery({ queryKey: philHealthBracketsKey(skip, limit), queryFn: () => fetchPhilHealthBrackets(skip, limit), placeholderData: keepPreviousData })
}

export function usePhilHealthBracket(id: string | undefined) {
  return useQuery({ queryKey: ['payroll-config', 'philhealth', id], queryFn: () => api.get<PhilHealthBracketPublic>(`${API}/payroll/philhealth-brackets/${id}`).then(r => r.data), enabled: Boolean(id) })
}

export function useCreatePhilHealthBracket() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (data: PhilHealthBracketCreate) => api.post(`${API}/payroll/philhealth-brackets/`, data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['payroll-config'] }) })
}

export function useUpdatePhilHealthBracket() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: ({ id, data }: { id: string; data: PhilHealthBracketUpdate }) => api.patch(`${API}/payroll/philhealth-brackets/${id}`, data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['payroll-config'] }) })
}

export function useDeletePhilHealthBracket() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (id: string) => api.delete(`${API}/payroll/philhealth-brackets/${id}`).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['payroll-config'] }) })
}

// --- Pag-IBIG -------------------------------------------------------------------
export const pagibigBracketsKey = (skip: number, limit: number) => ['payroll-config', 'pagibig', skip, limit]

export async function fetchPagIBIGBrackets(skip: number, limit: number): Promise<PagIBIGBracketList> {
  const { data } = await api.get<PagIBIGBracketPublic[]>(`${API}/payroll/pagibig-brackets/`, { params: { skip, limit } })
  return { data, count: data.length }
}

export function usePagIBIGBrackets(skip: number, limit: number) {
  return useQuery({ queryKey: pagibigBracketsKey(skip, limit), queryFn: () => fetchPagIBIGBrackets(skip, limit), placeholderData: keepPreviousData })
}

export function usePagIBIGBracket(id: string | undefined) {
  return useQuery({ queryKey: ['payroll-config', 'pagibig', id], queryFn: () => api.get<PagIBIGBracketPublic>(`${API}/payroll/pagibig-brackets/${id}`).then(r => r.data), enabled: Boolean(id) })
}

export function useCreatePagIBIGBracket() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (data: PagIBIGBracketCreate) => api.post(`${API}/payroll/pagibig-brackets/`, data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['payroll-config'] }) })
}

export function useUpdatePagIBIGBracket() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: ({ id, data }: { id: string; data: PagIBIGBracketUpdate }) => api.patch(`${API}/payroll/pagibig-brackets/${id}`, data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['payroll-config'] }) })
}

export function useDeletePagIBIGBracket() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (id: string) => api.delete(`${API}/payroll/pagibig-brackets/${id}`).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['payroll-config'] }) })
}

// --- BIR -----------------------------------------------------------------------
export const birBracketsKey = (skip: number, limit: number) => ['payroll-config', 'bir', skip, limit]

export async function fetchBIRBrackets(skip: number, limit: number): Promise<BIRBracketList> {
  const { data } = await api.get<BIRBracketPublic[]>(`${API}/payroll/bir-brackets/`, { params: { skip, limit, period_type: '' } })
  return { data, count: data.length }
}

export function useBIRBrackets(skip: number, limit: number) {
  return useQuery({ queryKey: birBracketsKey(skip, limit), queryFn: () => fetchBIRBrackets(skip, limit), placeholderData: keepPreviousData })
}

export function useBIRBracket(id: string | undefined) {
  return useQuery({ queryKey: ['payroll-config', 'bir', id], queryFn: () => api.get<BIRBracketPublic>(`${API}/payroll/bir-brackets/${id}`).then(r => r.data), enabled: Boolean(id) })
}

export function useCreateBIRBracket() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (data: BIRBracketCreate) => api.post(`${API}/payroll/bir-brackets/`, data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['payroll-config'] }) })
}

export function useUpdateBIRBracket() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: ({ id, data }: { id: string; data: BIRBracketUpdate }) => api.patch(`${API}/payroll/bir-brackets/${id}`, data).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['payroll-config'] }) })
}

export function useDeleteBIRBracket() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (id: string) => api.delete(`${API}/payroll/bir-brackets/${id}`).then(r => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['payroll-config'] }) })
}
