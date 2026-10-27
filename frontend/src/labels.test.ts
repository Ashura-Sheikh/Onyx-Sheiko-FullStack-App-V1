import { describe, expect, it } from 'vitest'
import { dateTime, greeting, isStage, longDate, shortDate } from './labels'
import { isPaletteShortcut } from './shortcuts'

describe('labels', () => {
  it('reads a due date as a calendar date', () => {
    expect(longDate('2031-04-16')).toBe('Wednesday 16 April')
    expect(shortDate('2031-04-01')).toBe('1 Apr')
    expect(shortDate('2031-12-31')).toBe('31 Dec')
  })

  it('shows times in the given time zone', () => {
    expect(dateTime('2031-04-14T20:00:00+00:00', 'UTC')).toBe('14 Apr, 20:00')
    expect(dateTime('2031-04-14T20:00:00+00:00', 'Asia/Tokyo')).toBe('15 Apr, 05:00')
  })

  it('greets by the time of day', () => {
    expect(greeting(0)).toBe('Good morning')
    expect(greeting(11)).toBe('Good morning')
    expect(greeting(12)).toBe('Good afternoon')
    expect(greeting(17)).toBe('Good afternoon')
    expect(greeting(18)).toBe('Good evening')
  })

  it('knows the four stages', () => {
    expect(isStage('in-review')).toBe(true)
    expect(isStage('created')).toBe(false)
  })

  it('⌘K and Ctrl+K open the palette, plain K does not', () => {
    expect(isPaletteShortcut({ key: 'k', metaKey: true, ctrlKey: false })).toBe(true)
    expect(isPaletteShortcut({ key: 'K', metaKey: false, ctrlKey: true })).toBe(true)
    expect(isPaletteShortcut({ key: 'k', metaKey: false, ctrlKey: false })).toBe(false)
    expect(isPaletteShortcut({ key: 'j', metaKey: true, ctrlKey: false })).toBe(false)
  })
})
