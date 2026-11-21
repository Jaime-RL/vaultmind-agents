// Genera src/api/contract.gen.ts a partir de los esquemas JSON de contracts/.
//
// Por qué generar y no escribir los tipos a mano: contracts/ es la fuente de
// verdad. Si A cambia un esquema (en una PR acordada), basta con ejecutar
// `npm run gen:types` y TypeScript señala cada componente afectado.
//
// `npm run check:types` (lo usa la CI) falla si el fichero generado no coincide
// con los esquemas actuales: así nadie puede olvidarse de regenerarlo.
import { readFile, readdir, writeFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { compile } from 'json-schema-to-typescript'

const here = dirname(fileURLToPath(import.meta.url))
const contractsDir = join(here, '..', '..', 'contracts')
const outFile = join(here, '..', 'src', 'api', 'contract.gen.ts')
const checkOnly = process.argv.includes('--check')

const options = {
  bannerComment: '',
  additionalProperties: false,
  // Los esquemas con "format": "date-time" siguen siendo string en TypeScript.
  strictIndexSignatures: true,
  unreachableDefinitions: true, // exporta también los $defs (Proposal, Source...)
  format: true,
  style: { singleQuote: true, semi: false, printWidth: 100 },
}

const files = (await readdir(contractsDir)).filter((f) => f.endsWith('.schema.json')).sort()

// Cada esquema se compila por separado y los tipos con el mismo nombre
// (por ejemplo, Agent o Tier, que aparecen en varios) se escriben una sola vez.
const seen = new Set()
const chunks = []
for (const file of files) {
  const schema = JSON.parse(await readFile(join(contractsDir, file), 'utf8'))

  // Algunos esquemas (proposal, research) solo agrupan definiciones en $defs y su
  // raíz se llama igual que una de ellas («Proposal»). Si se compilan tal cual, el
  // generador renombra la definición real a «Proposal1». Para evitarlo, la raíz de
  // esos esquemas recibe un nombre interno (…Root) y se descarta del resultado.
  const isDefsContainer = !schema.type && !schema.oneOf && !schema.properties
  const rootName = isDefsContainer ? `${schema.title}Root` : schema.title
  const input = isDefsContainer ? { ...schema, title: rootName, description: undefined } : schema

  const ts = await compile(input, rootName ?? file, { ...options, cwd: contractsDir })
  for (const block of ts.split(/\n(?=export )/)) {
    const name = block.match(/^export (?:type|interface) (\w+)/)?.[1]
    if (isDefsContainer && name === rootName) continue
    if (name && seen.has(name)) continue
    if (name) seen.add(name)
    chunks.push(block.trim())
  }
}

const output = [
  '// FICHERO GENERADO por scripts/gen-contract-types.mjs desde contracts/*.schema.json.',
  '// No lo edites a mano: cambia el esquema (en una PR acordada) y ejecuta `npm run gen:types`.',
  '/* eslint-disable */',
  '',
  chunks.join('\n\n'),
  '',
].join('\n')

if (checkOnly) {
  const current = await readFile(outFile, 'utf8').catch(() => '')
  if (current !== output) {
    console.error('contract.gen.ts está desactualizado: ejecuta `npm run gen:types`.')
    process.exit(1)
  }
  console.log('contract.gen.ts está al día con contracts/.')
} else {
  await writeFile(outFile, output)
  console.log(`Tipos generados en ${outFile} (${seen.size} tipos).`)
}
