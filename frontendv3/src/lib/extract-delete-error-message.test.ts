import { describe, expect, it } from 'vitest'
import { extractDeleteErrorMessage } from './extract-delete-error-message'

describe('extractDeleteErrorMessage', () => {
  it('prefers the ErrorBody error.message from an axios-like response', () => {
    const err = {
      response: { data: { error: { message: 'still has active blocks' } } },
    }

    expect(extractDeleteErrorMessage(err, 'Lot')).toBe(
      'still has active blocks'
    )
  })

  it('falls back to a string detail when no error envelope is present (409 FastAPI shape)', () => {
    const err = { response: { data: { detail: 'cannot delete' } } }

    expect(extractDeleteErrorMessage(err, 'Block')).toBe('cannot delete')
  })

  it('uses the first element when detail is an array', () => {
    const err = { response: { data: { detail: ['first', 'second'] } } }

    expect(extractDeleteErrorMessage(err, 'Division')).toBe('first')
  })

  it('returns the generic message when error.message is an empty string', () => {
    const err = { response: { data: { error: { message: '' } } } }

    expect(extractDeleteErrorMessage(err, 'Project')).toBe(
      'Failed to delete Project'
    )
  })

  it('returns the generic message when the error has no response', () => {
    expect(extractDeleteErrorMessage(new Error('network'), 'Shift')).toBe(
      'Failed to delete Shift'
    )
  })

  it('returns the generic message for non-object errors', () => {
    expect(extractDeleteErrorMessage('boom', 'Phase')).toBe(
      'Failed to delete Phase'
    )
    expect(extractDeleteErrorMessage(null, 'Phase')).toBe(
      'Failed to delete Phase'
    )
  })

  it('returns the generic message when response data is empty', () => {
    const err = { response: { data: {} } }

    expect(extractDeleteErrorMessage(err, 'Owner')).toBe(
      'Failed to delete Owner'
    )
  })
})
