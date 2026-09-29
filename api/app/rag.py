"""Constantes compartidas del pipeline RAG (ingesta).

Este módulo aloja los parámetros comunes a modelos, migración de esquema y
servicio de embeddings, para no dispersarlos por el código. Cambiar el modelo
implica cambiar `EMBEDDING_DIM` y re-embeber todo el contenido existente:
operación de mantenimiento, no soportada como migración de datos automática.

La decisión del proveedor se tomó en la primera tarea del cambio OpenSpec
`rag-ingesta`. Verificaciones contra la API real:

- **DeepSeek**: NO expone `/embeddings` (HTTP 404 confirmado contra su API).
- **Anthropic**: NO expone `/embeddings` propio; su propia documentación
  recomienda **Voyage AI** (adquirida por Anthropic en 2025) como el proveedor
  canónico de embeddings para RAG con Claude.

Se eligió **Voyage AI** (`voyage-3`) por ser la vía oficial recomendada por
Anthropic, con buen rendimiento multilingüe (es/pt) y vectores de 1024
dimensiones (menor huella en pgvector que los 1536 de OpenAI). Voyage expone
un endpoint compatible con el patrón OpenAI (`POST /v1/embeddings` con el
mismo shape de request/response), así que la abstracción de `servicios_ia.py`
sigue siendo un único cliente OpenAI-compatible: solo cambia `base_url`, el
nombre de modelo y la clave (que SuperAdmin configura en `ConfigIA`).

**Nota:** Voyage AI tiene infraestructura y facturación separadas de
Anthropic pese a pertenecer al mismo grupo: se necesita una cuenta y una
clave nuevas (`dash.voyageai.com`), la clave de Anthropic (`sk-ant-…`) NO
autentica contra Voyage.
"""

from __future__ import annotations

# Modelo de embeddings y su dimensión. Un cambio aquí exige re-embeber el
# contenido existente y modificar la migración `0008_rag_chunks` (no hay
# migración automática de vectores entre modelos).
#
# `voyage-3` es el modelo estable de la serie 3 con 1024 dims. Alternativas si
# se quiere cambiar en el futuro (solo hace falta actualizar estas constantes,
# regenerar el esquema y re-embeber):
#   - `voyage-3-large` (1024, mejor calidad, algo más caro)
#   - `voyage-3-lite`  (512,  más económico y menor huella)
#   - `voyage-4`       (1024, generación 2026 con MoE, mayor calidad)
EMBEDDING_MODELO = "voyage-3"
EMBEDDING_DIM = 1024

# Base URL del proveedor OpenAI-compatible para embeddings. Voyage AI (default)
# expone su endpoint aquí. Cambiar a otro proveedor OpenAI-compatible (OpenAI,
# Together, etc.) requiere ajustar también `EMBEDDING_MODELO`, `EMBEDDING_DIM`
# y seleccionarlo desde el panel (rol `proveedorEmbeddings` de la config de IA).
URL_BASE_EMBEDDINGS = "https://api.voyageai.com/v1"
