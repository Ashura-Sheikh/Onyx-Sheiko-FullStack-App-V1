import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { generateTypes, getRoutes, SCHEMA_FILE, TYPES_FILE } from './gen-api-types.ts'

const api = JSON.parse(readFileSync(SCHEMA_FILE, 'utf8'))

describe('generated API types', () => {
  it('src/api-types.ts is up to date with openapi.json (run `npm run gen:api`)', async () => {
    expect(readFileSync(TYPES_FILE, 'utf8')).toBe(await generateTypes(api))
  })

  it('maps every GET endpoint to its response type', () => {
    expect(getRoutes(api)).toEqual([
      ['/api/health', 'Health'],
      ['/api/home', 'HomeData'],
      ['/api/items', 'ItemList'],
      ['/api/note', 'NoteDetail'],
      ['/api/notes', 'NoteList'],
      ['/api/session', 'SessionStatus'],
    ])
  })

  it('names only the models, not each field', async () => {
    const types = await generateTypes(api)
    expect(types).not.toMatch(/export type \w+1 =/)
    expect(types).toContain('export interface NoteDetail {')
  })

  it('keeps JSON names that are not valid identifiers', async () => {
    const types = await generateTypes(api)
    expect(types).toContain("'in-progress': number")
    expect(types).toMatch(/^\s+from: string$/m)
  })

  it('gives ItemList exactly one field', async () => {
    const types = await generateTypes(api)
    const block = types.slice(types.indexOf('export interface ItemList {'))
    expect(block.slice(0, block.indexOf('}') + 1)).toBe('export interface ItemList {\n  items: Item[]\n}')
  })
})
