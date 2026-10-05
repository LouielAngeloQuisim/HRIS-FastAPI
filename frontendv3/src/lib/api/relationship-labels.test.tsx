import { QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { renderWithClient } from '@/test-utils/providers'
import { api } from './client'
import { relationshipLabel, relationshipOwner, useRelationshipLabels } from './relationship-labels'

const { owner } = vi.hoisted(() => ({ owner: { id: 'qa-owner' as string | undefined } }))
vi.mock('@/stores/auth-store', () => ({ useAuthStore: () => owner.id }))

function Labels({ ids }: { ids: string[] }) {
  const result = useRelationshipLabels('projects', ids)
  return <div>{result.isSuccess ? Object.values(result.data).join(',') : 'Loading'}</div>
}

describe('bounded relationship labels', () => {
  beforeEach(() => { vi.restoreAllMocks(); owner.id = 'qa-owner' })

  it('deduplicates and chunks requests at 200 IDs, then renders returned labels', async () => {
    const counts: number[] = []
    vi.spyOn(api, 'get').mockImplementation(async (url) => {
      const ids = new URL(url, 'http://qa.invalid').searchParams.getAll('ids')
      counts.push(ids.length)
      return { data: Object.fromEntries(ids.map(id => [id, `Project ${id}`])) }
    })
    const ids = Array.from({ length: 401 }, (_, index) => `id-${index}`)
    const screen = await renderWithClient(<Labels ids={[...ids, ids[0]]} />)
    await expect.element(screen.getByText(/Project id-0/)).toBeInTheDocument()
    expect(counts).toEqual([200, 200, 1])
  })

  it('does not expose another account cached relationship labels', async () => {
    const get = vi.spyOn(api, 'get').mockResolvedValueOnce({ data: { parent: 'First account parent' } }).mockResolvedValueOnce({ data: {} })
    const screen = await renderWithClient(<Labels ids={['parent']} />)
    await expect.element(screen.getByText('First account parent')).toBeInTheDocument()
    owner.id = 'other-owner'
    await screen.rerender(<QueryClientProvider client={screen.client}><Labels ids={['parent']} /></QueryClientProvider>)
    await vi.waitFor(() => expect(get).toHaveBeenCalledTimes(2))
    await expect.element(screen.getByText('First account parent')).not.toBeInTheDocument()
    owner.id = undefined
    await screen.rerender(<QueryClientProvider client={screen.client}><Labels ids={['parent']} /></QueryClientProvider>)
    expect(get).toHaveBeenCalledTimes(2)
  })

  it('partitions a reloaded session by token subject without treating decoding as authorization', () => {
    const token = `placeholder.${btoa(JSON.stringify({ sub: 'reloaded-owner' }))}.placeholder`
    expect(relationshipOwner(undefined, token)).toBe('reloaded-owner')
    expect(relationshipOwner('hydrated-owner', token)).toBe('hydrated-owner')
    expect(relationshipOwner(undefined, 'malformed')).toBeUndefined()
    expect(relationshipOwner(undefined, '')).toBeUndefined()
  })

  it('uses explicit missing/deleted fallbacks and preserves IDs for callers', () => {
    const identity = 'original-id'
    expect(relationshipLabel({ [identity]: 'P01 — Named project' }, identity)).toBe('P01 — Named project')
    expect(relationshipLabel({}, identity)).toBe('Unavailable record')
    expect(relationshipLabel(undefined, null)).toBe('—')
    expect(identity).toBe('original-id')
  })
})
