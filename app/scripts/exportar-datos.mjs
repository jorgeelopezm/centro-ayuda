// Vuelca el contenido de `src/data/{es,pt}` a `../api/seed_data/{es,pt}.json`,
// fuente única del seed del backend (no se duplica ni se transcribe a mano).
//
// Requiere Node con borrado de tipos de TypeScript (por defecto en Node >= 23.6;
// la máquina de desarrollo tiene Node 24). Los módulos de datos solo usan
// `import type`, así que sus imports de tipos se borran y no hay que resolver alias.
//
// Uso desde `app/`:  node scripts/exportar-datos.mjs

import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { categorias as categoriasEs } from '../src/data/es/categorias.ts'
import { articulos as articulosEs } from '../src/data/es/articulos.ts'
import { conversacion as conversacionEs } from '../src/data/es/conversacion.ts'
import { metricas as metricasEs, preguntasSinResolver as preguntasEs } from '../src/data/es/preguntas-sin-resolver.ts'

import { categorias as categoriasPt } from '../src/data/pt/categorias.ts'
import { articulos as articulosPt } from '../src/data/pt/articulos.ts'
import { conversacion as conversacionPt } from '../src/data/pt/conversacion.ts'
import { metricas as metricasPt, preguntasSinResolver as preguntasPt } from '../src/data/pt/preguntas-sin-resolver.ts'

const aqui = dirname(fileURLToPath(import.meta.url))
const salida = resolve(aqui, '../../api/seed_data')
mkdirSync(salida, { recursive: true })

const contenido = {
  es: {
    categorias: categoriasEs,
    articulos: articulosEs,
    conversacion: conversacionEs,
    preguntasSinResolver: preguntasEs,
    metricas: metricasEs,
  },
  pt: {
    categorias: categoriasPt,
    articulos: articulosPt,
    conversacion: conversacionPt,
    preguntasSinResolver: preguntasPt,
    metricas: metricasPt,
  },
}

for (const [idioma, datos] of Object.entries(contenido)) {
  const ruta = resolve(salida, `${idioma}.json`)
  writeFileSync(ruta, JSON.stringify(datos, null, 2) + '\n', 'utf8')
  console.log(`Exportado ${ruta} (${datos.articulos.length} artículos)`)
}
