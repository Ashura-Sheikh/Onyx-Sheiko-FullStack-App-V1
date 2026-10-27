// Generate src/api-types.ts from openapi.json (written by the backend:
// `uv run python -m onyx.schema`). Run with `npm run gen:api`.
//
// json-schema-to-typescript writes the types as text; it doesn't need the
// TypeScript compiler API, which TypeScript 7 no longer has (so
// openapi-typescript can't be used here).
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { compile, type JSONSchema } from 'json-schema-to-typescript'

const HERE = dirname(fileURLToPath(import.meta.url))
export const SCHEMA_FILE = join(HERE, '..', 'openapi.json')
export const TYPES_FILE = join(HERE, '..', 'src', 'api-types.ts')

const BANNER = `// Generated from openapi.json by scripts/gen-api-types.ts. Don't edit by hand:
// change backend/onyx/models.py, then run \`uv run python -m onyx.schema\` in
// backend/ and \`npm run gen:api\` here. A test fails if this file is out of date.
`

type OpenApi = {
  paths: Record<string, Record<string, { responses: Record<string, { content?: Record<string, { schema: { $ref?: string } }> }> }>>
  components: { schemas: Record<string, JSONSchema> }
}

const REF = '#/components/schemas/'

/** Every GET endpoint with a JSON body, mapped to the name of its response type. */
export function getRoutes(api: OpenApi): [string, string][] {
  const routes: [string, string][] = []
  for (const [path, operations] of Object.entries(api.paths)) {
    const ref = operations.get?.responses['200']?.content?.['application/json']?.schema.$ref
    if (ref?.startsWith(REF)) routes.push([path, ref.slice(REF.length)])
  }
  return routes.sort(([a], [b]) => a.localeCompare(b))
}

/**
 * Pydantic gives every field a title, which would make each field its own
 * named type (Path1, Title3, …). Keep titles on the models only.
 */
function withoutFieldTitles(value: unknown, isModel: boolean): unknown {
  if (Array.isArray(value)) return value.map((v) => withoutFieldTitles(v, false))
  if (value === null || typeof value !== 'object') return value
  const out: Record<string, unknown> = {}
  for (const [key, child] of Object.entries(value)) {
    if (key === 'title' && !isModel) continue
    // The keys of "properties" are field names, not schemas.
    out[key] =
      key === 'properties' && child && typeof child === 'object'
        ? Object.fromEntries(Object.entries(child).map(([name, field]) => [name, withoutFieldTitles(field, false)]))
        : withoutFieldTitles(child, false)
  }
  return out
}

export async function generateTypes(api: OpenApi): Promise<string> {
  const names = Object.keys(api.components.schemas).sort()
  const schemas = Object.fromEntries(names.map((name) => [name, withoutFieldTitles(api.components.schemas[name], true)]))
  // One root object that points at every schema, so each becomes an exported type.
  const root = {
    title: 'ApiSchemas',
    type: 'object',
    additionalProperties: false,
    required: names,
    properties: Object.fromEntries(names.map((name) => [name, { $ref: `${REF}${name}` }])),
    components: { schemas },
  } as JSONSchema
  const types = await compile(root, 'ApiSchemas', {
    bannerComment: '',
    additionalProperties: false,
    declareExternallyReferenced: true,
    // Its min/max-items handling adds a stray `minItems?: 0` field to a model
    // that has a field named "items" (ItemList). The API has no such limits.
    ignoreMinAndMaxItems: true,
    unreachableDefinitions: false,
    style: { singleQuote: true, semi: false, printWidth: 120 },
  })
  const routes = getRoutes(api)
    .map(([path, name]) => `  '${path}': ${name}`)
    .join('\n')
  return `${BANNER}\n${types}\n/** The response type of each GET endpoint. */\nexport interface GetResponses {\n${routes}\n}\n`
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const api = JSON.parse(readFileSync(SCHEMA_FILE, 'utf8')) as OpenApi
  writeFileSync(TYPES_FILE, await generateTypes(api))
  console.error(`Wrote ${TYPES_FILE}`)
}
