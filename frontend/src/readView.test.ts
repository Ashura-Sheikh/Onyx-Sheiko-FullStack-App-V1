import { describe, expect, it } from 'vitest'
import cases from './readView.cases.json'
import { HIDDEN_SECTIONS, shownBody } from './readView'

// The same cases as backend/tests/test_read_view_cases.py, whose expected
// results come from the backend's own functions.
describe('read view body (matches the backend)', () => {
  it('hides the same sections', () => {
    expect(HIDDEN_SECTIONS).toEqual(cases.hidden_sections)
  })

  it.each(cases.cases.map((c) => [JSON.stringify(c.body).slice(0, 40), c]))('%s', (_, c) => {
    expect(shownBody(c.body, c.title)).toBe(c.shown)
  })
})
