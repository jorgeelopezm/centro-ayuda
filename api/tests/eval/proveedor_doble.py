"""Dobles deterministas para el harness EDD del chat.

El modo `ci` (por defecto en `pytest -m eval`) NO llama a la red. En su lugar
sustituye dos piezas del pipeline por dobles deterministas:

- `ProveedorChatDoble`: implementa el `ProveedorChat.completar` con respuestas
  prefijadas por caso. Cada caso produce hasta dos llamadas al proveedor:
  clasificador de scope (`EN_SCOPE` / `FUERA_DE_SCOPE`) y, si aplica,
  generación (`{"respuesta": ..., "citas_usadas": [...], "encontrada": ...}`).
- `EmbedderDoble`: implementa el `ProveedorEmbeddings.embeber` devolviendo un
  vector por consulta. Cada `articulo_id` sembrado tiene un vector one-hot en
  la misma dimensión; el embedder del test devuelve el vector del artículo
  esperado del caso, de modo que el recuperador vectorial lo encuentre por
  encima del umbral. Los casos `sin_resultados` reciben un vector cero para
  caer por debajo del umbral.

Ambos dobles derivan su comportamiento de la lista de casos: no hay conocimiento
del pipeline salvo el contrato de `ProveedorChat` y `ProveedorEmbeddings`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


def cargar_casos(ruta: Path) -> list[dict]:
    """Lee un archivo JSONL de casos. Ignora líneas en blanco y comentarios `#`."""
    casos: list[dict] = []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        casos.append(json.loads(linea))
    return casos


def normalizar_consulta(texto: str) -> str:
    """Normalización barata pero estable: strip + lowercase + colapso de espacios.

    Los casos y los dobles la usan como clave; asegura que las diferencias de
    formato no rompan el mapeo entre consulta y respuesta prefijada.
    """
    return " ".join((texto or "").strip().lower().split())


@dataclass(frozen=True)
class RespuestasCaso:
    """Respuestas del doble para un caso concreto.

    `scope` es la etiqueta que devuelve el clasificador; `generacion` es el JSON
    (como texto) que devuelve la fase de generación (o vacío si el caso no llega
    a ella). `slug_esperado` sirve al embedder para devolver el vector del
    artículo correcto.
    """

    scope: str
    generacion: str
    slug_esperado: str | None
    articulo_id: str | None


def compilar_respuestas_por_caso(casos: list[dict]) -> dict[str, RespuestasCaso]:
    """Prepara el mapa `consulta_normalizada → RespuestasCaso` a partir de los casos.

    - `respondida`: scope=EN_SCOPE; generación cita el fragmento 1 (el primero
      que devuelve el recuperador para ese caso, que es el artículo sembrado
      con `slug=citas_esperadas_por_slug[0]`).
    - `sin_resultados`: scope=EN_SCOPE; sin generación (el recuperador no
      encuentra fragmentos por encima del umbral, así que el pipeline decide
      `sin_resultados` sin llamar al generador).
    - `fuera_de_scope`: scope=FUERA_DE_SCOPE; sin generación.
    - `escalar`: se dispara con `solicitar_soporte=True` en la llamada al
      pipeline; el doble no interviene (el pipeline corto-circuita antes).
    """
    mapa: dict[str, RespuestasCaso] = {}
    for caso in casos:
        clave = normalizar_consulta(caso["consulta"])
        veredicto = caso["veredicto_esperado"]
        slug = None
        articulo_id = None
        if veredicto == "respondida":
            slug = caso["citas_esperadas_por_slug"][0]
            articulo_id = _articulo_id(caso)
            texto = caso.get("respuesta_texto", "Aquí tienes la información solicitada.")
            generacion = json.dumps(
                {"respuesta": texto, "citas_usadas": [1], "encontrada": True},
                ensure_ascii=False,
            )
            scope = "EN_SCOPE"
        elif veredicto == "sin_resultados":
            scope = "EN_SCOPE"
            generacion = ""
        elif veredicto == "fuera_de_scope":
            scope = "FUERA_DE_SCOPE"
            generacion = ""
        elif veredicto == "escalar":
            scope = ""
            generacion = ""
        else:
            raise ValueError(f"veredicto desconocido en {caso['id']}: {veredicto}")
        mapa[clave] = RespuestasCaso(
            scope=scope,
            generacion=generacion,
            slug_esperado=slug,
            articulo_id=articulo_id,
        )
    return mapa


def _articulo_id(caso: dict) -> str:
    """Id de artículo sembrado por caso: coincide con `caso.id` para trazabilidad."""
    return caso["id"]


class ProveedorChatDoble:
    """Doble de `ProveedorChat` que responde por caso desde el mapa preparado.

    Mantiene un contador de llamadas por consulta para distinguir la fase
    (primera llamada = scope, segunda = generación).
    """

    def __init__(self, respuestas: dict[str, RespuestasCaso]) -> None:
        self._respuestas = respuestas
        self._llamadas_por_consulta: dict[str, int] = {}
        self.llamadas: list[dict] = []

    def _extraer_consulta(self, messages: list[dict]) -> str:
        """Recupera la consulta desde el último mensaje `user`. Los mensajes
        `user` viajan envueltos en `<contenido_no_confiable_*>`; el doble solo
        necesita el texto crudo, así que quita etiquetas HTML-like."""
        import re

        for m in reversed(messages):
            if m.get("role") == "user":
                contenido = m.get("content", "") or ""
                # Quita las etiquetas de delimitador y el prefijo "Consulta:" si viene.
                sin_tags = re.sub(r"</?contenido_no_confiable[a-zA-Z0-9_\-]*>", "", contenido)
                # Para el turno de generación, el user lleva "Consulta:\n...\n\nFragmentos...".
                m_consulta = re.search(r"Consulta:\s*(.+?)(?:\n\n|$)", sin_tags, re.DOTALL)
                if m_consulta:
                    return normalizar_consulta(m_consulta.group(1))
                return normalizar_consulta(sin_tags)
        return ""

    def completar(
        self,
        messages: list[dict],
        *,
        response_format_json: bool,
        temperature: float,
        max_tokens: int,
        timeout: float | None = None,
    ) -> str:
        consulta = self._extraer_consulta(messages)
        self.llamadas.append(
            {"consulta": consulta, "response_format_json": response_format_json}
        )
        respuestas = self._respuestas.get(consulta)
        if respuestas is None:
            # Consulta no mapeada: si piden JSON, devolvemos algo que el pipeline
            # descartará (encontrada=false, sin citas). Si no piden JSON, `EN_SCOPE`
            # conservador. Esto no debería pasar con un dataset bien construido.
            if response_format_json:
                return json.dumps({"respuesta": "sin datos", "citas_usadas": [], "encontrada": False})
            return "EN_SCOPE"
        n = self._llamadas_por_consulta.get(consulta, 0)
        self._llamadas_por_consulta[consulta] = n + 1
        if n == 0:
            return respuestas.scope or "EN_SCOPE"
        return respuestas.generacion or json.dumps(
            {"respuesta": "sin datos", "citas_usadas": [], "encontrada": False}
        )


class EmbedderDoble:
    """Doble de `ProveedorEmbeddings.embeber`.

    Devuelve un vector one-hot por consulta según el artículo esperado del caso.
    Para `sin_resultados` y `fuera_de_scope` devuelve un vector cero, que da
    similitud 0 con cualquier fragmento (por debajo del umbral). El pipeline
    corto-circuita `fuera_de_scope` antes del embedder, así que el vector cero
    solo se usa efectivamente para `sin_resultados`.
    """

    def __init__(
        self,
        respuestas: dict[str, RespuestasCaso],
        articulo_a_vector: dict[str, list[float]],
        dimension: int,
    ) -> None:
        self._respuestas = respuestas
        self._articulo_a_vector = articulo_a_vector
        self._dimension = dimension

    def embeber(self, textos: list[str]) -> list[list[float]]:
        vectores: list[list[float]] = []
        for texto in textos:
            clave = normalizar_consulta(texto)
            r = self._respuestas.get(clave)
            if r is None or r.articulo_id is None:
                vectores.append([0.0] * self._dimension)
                continue
            vector = self._articulo_a_vector.get(r.articulo_id)
            if vector is None:
                vectores.append([0.0] * self._dimension)
                continue
            vectores.append(list(vector))
        return vectores


def construir_corpus_vectores(casos: list[dict]) -> tuple[dict[str, list[float]], int]:
    """Asigna un vector one-hot único a cada `articulo_id` de los casos `respondida`.

    Devuelve el mapa `articulo_id → vector` y la dimensión. Un vector one-hot da
    similitud coseno 1 con sí mismo y 0 con el resto, por lo que el recuperador
    encuentra siempre y solo el artículo del caso.
    """
    articulos = [_articulo_id(c) for c in casos if c["veredicto_esperado"] == "respondida"]
    dimension = max(len(articulos), 1)
    mapa: dict[str, list[float]] = {}
    for i, articulo_id in enumerate(articulos):
        vector = [0.0] * dimension
        vector[i] = 1.0
        mapa[articulo_id] = vector
    return mapa, dimension
