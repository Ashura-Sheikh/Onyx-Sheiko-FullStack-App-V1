/// <reference types="node" />
// Rules on the source code itself, checked in CI like any other test.
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

// Vitest runs from the frontend folder.
const SRC = join(process.cwd(), 'src') + '/'

function sourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry): string[] => {
    const path = join(dir, entry.name)
    if (entry.isDirectory()) return sourceFiles(path)
    return /\.(ts|tsx)$/.test(entry.name) && !entry.name.endsWith('.test.ts') && !entry.name.endsWith('.test.tsx') ? [path] : []
  })
}

// Tailwind reads files as plain text, so a class built from a variable
// (`bg-${color}-600`) produces no CSS. Use complete class names instead.
export const DYNAMIC_TAILWIND_CLASS = /[a-z0-9]-\$\{/

describe('source rules', () => {
  const files = sourceFiles(SRC)

  it('finds the source files', () => {
    expect(files.length).toBeGreaterThan(3)
  })

  it.each(files.map((f) => [f.slice(SRC.length)]))('%s builds no Tailwind class names from variables', (name) => {
    expect(readFileSync(join(SRC, name), 'utf8')).not.toMatch(DYNAMIC_TAILWIND_CLASS)
  })

  it('the rule catches a dynamic class name', () => {
    expect('className={`bg-${color}-600`}').toMatch(DYNAMIC_TAILWIND_CLASS)
    expect("className={isError ? 'text-red-600' : 'text-green-600'}").not.toMatch(DYNAMIC_TAILWIND_CLASS)
  })
})
