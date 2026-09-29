"""Tests unitarios del recuperador vectorial (`app.recuperador.recuperar`).

Cubre las garantías del RAG del chat en su capa de recuperación:
- aislamiento por portal (7.1)
- filtro de idioma en `articulo_chunks`; documentos sin filtro (7.2)
- umbral + top-k respetados (7.3)
- fallo del embedder → `error_proveedor` (7.4)

Se ejecuta sobre SQLite en memoria: la implementación cae al camino Python de
`_buscar_python` cuando el dialecto no es `postgresql`, así que no exige pgvector.
"""

from __future__ import annotations

from datetime import date

import pytest

from app import recuperador
from app.models import (
    Articulo,
    ArticuloChunk,
    ArticuloTraduccion,
    Documento,
    DocumentoChunk,
)
from app.servicios import PORTAL_DEFECTO_UUID
from app.servicios_ia import ErrorProveedor
from tests.conftest import SEGUNDO_PORTAL_UUID, sembrar_portal_secundario

# Portal del seed por defecto. El id ya no es un slug legible ("default"): es un
# UUID (migración `0012_portal_uuid`), así que hace falta la constante real.
PORTAL_A = PORTAL_DEFECTO_UUID


# --- Dobles del embedder -----------------------------------------------------


class _EmbedderFijo:
    """Embedder determinista: devuelve un vector concreto por texto."""

    def __init__(self, vector: list[float]) -> None:
        self._vector = list(vector)
        self.textos: list[str] = []

    def embeber(self, textos: list[str]) -> list[list[float]]:
        self.textos.extend(textos)
        return [list(self._vector) for _ in textos]


class _EmbedderQueFalla:
    def embeber(self, textos: list[str]) -> list[list[float]]:
        raise ErrorProveedor("proveedor caído")


@pytest.fixture
def con_embedder(monkeypatch):
    """Sustituye `crear_embedder` para devolver el embedder del test.

    Espeja el patrón de `test_admin_documentos.con_embedder_bueno` pero para el
    lado de la RECUPERACIÓN: aquí no hay ingesta, solo lectura vectorial.
    """
    def _instalar(embedder):
        monkeypatch.setattr(recuperador, "crear_embedder", lambda _db: embedder)
        return embedder

    return _instalar


# --- Helpers de siembra ------------------------------------------------------


def _crear_articulo_con_chunks(
    db,
    *,
    portal_id: str,
    articulo_id: str,
    slug_es: str,
    slug_pt: str,
    titulo_es: str,
    titulo_pt: str,
    vector_es: list[float],
    vector_pt: list[float],
    texto: str = "contenido de ayuda",
) -> None:
    """Alta bilingüe del artículo y un fragmento por idioma con el vector dado."""
    db.add(
        Articulo(
            id=articulo_id,
            portal_id=portal_id,
            categoria_id="cuenta",
            actualizado=date(2026, 1, 1),
            minutos_lectura=1,
            destacado=False,
        )
    )
    db.flush()
    for idioma, slug, titulo, vector in (
        ("es", slug_es, titulo_es, vector_es),
        ("pt", slug_pt, titulo_pt, vector_pt),
    ):
        db.add(
            ArticuloTraduccion(
                articulo_id=articulo_id,
                portal_id=portal_id,
                idioma=idioma,
                slug=slug,
                titulo=titulo,
                parrafos=[],
                how_to={"titulo": "", "pasos": []},
                nota=None,
                faq=[],
            )
        )
        db.add(
            ArticuloChunk(
                portal_id=portal_id,
                articulo_id=articulo_id,
                idioma=idioma,
                orden=0,
                contenido=f"[{idioma}] {texto}",
                embedding=list(vector),
            )
        )
    db.commit()


def _crear_documento_con_chunk(
    db,
    *,
    portal_id: str,
    nombre: str,
    vector: list[float],
    texto: str = "manual",
) -> int:
    doc = Documento(
        portal_id=portal_id,
        nombre=nombre,
        mime="text/plain",
        idioma="ambos",
        estado="listo",
        bytes=len(texto),
    )
    db.add(doc)
    db.flush()
    db.add(
        DocumentoChunk(
            portal_id=portal_id,
            documento_id=doc.id,
            orden=0,
            contenido=texto,
            embedding=list(vector),
        )
    )
    db.commit()
    return doc.id


# --- 7.1 Aislamiento por portal ---------------------------------------------


def test_recuperador_aisla_por_portal_aunque_el_otro_este_mas_cerca(
    db_session, con_embedder,
):
    """El portal B jamás debe aparecer en un resultado del portal A, incluso si
    su fragmento coincide EXACTAMENTE con la consulta y el del A no."""
    sembrar_portal_secundario(db_session)

    # Consulta apuntando a [1, 0, 0].
    con_embedder(_EmbedderFijo([1.0, 0.0, 0.0]))

    # Portal A: un chunk lejano (sim ≈ 0.3).
    _crear_articulo_con_chunks(
        db_session,
        portal_id=PORTAL_A,
        articulo_id="a-articulo",
        slug_es="a-es",
        slug_pt="a-pt",
        titulo_es="Ayuda A",
        titulo_pt="Ajuda A",
        vector_es=[0.3, 0.95, 0.0],
        vector_pt=[0.3, 0.95, 0.0],
        texto="ayuda del portal A",
    )
    # Portal B: un chunk que coincide EXACTAMENTE con la consulta.
    _crear_articulo_con_chunks(
        db_session,
        portal_id=SEGUNDO_PORTAL_UUID,
        articulo_id="b-articulo",
        slug_es="b-es",
        slug_pt="b-pt",
        titulo_es="Ayuda B",
        titulo_pt="Ajuda B",
        vector_es=[1.0, 0.0, 0.0],
        vector_pt=[1.0, 0.0, 0.0],
        texto="ayuda del portal B (nunca debe filtrar)",
    )

    resultado = recuperador.recuperar("cualquier cosa", "es", str(PORTAL_A), db_session)

    assert resultado.veredicto == "ok"
    # Solo fragmentos del portal A.
    # `FragmentoRecuperado.portal_id` es texto (`recuperador.py` lo serializa así);
    # `PORTAL_A` es el `uuid.UUID` real, así que se compara como texto.
    assert all(f.portal_id == str(PORTAL_A) for f in resultado.fragmentos)
    # Ninguna referencia al artículo B (defensa en profundidad).
    ids = {f.origen.get("articulo_id") for f in resultado.fragmentos}
    assert "b-articulo" not in ids


# --- 7.2 Filtro de idioma ---------------------------------------------------


def test_recuperador_filtra_articulos_por_idioma_documentos_no(
    db_session, con_embedder,
):
    """`articulo_chunks` se filtra por idioma; `documento_chunks` no lleva idioma."""
    con_embedder(_EmbedderFijo([1.0, 0.0, 0.0]))

    _crear_articulo_con_chunks(
        db_session,
        portal_id=PORTAL_A,
        articulo_id="bilingue",
        slug_es="bilingue-es",
        slug_pt="bilingue-pt",
        titulo_es="Título ES",
        titulo_pt="Título PT",
        vector_es=[1.0, 0.0, 0.0],
        vector_pt=[1.0, 0.0, 0.0],
    )
    _crear_documento_con_chunk(
        db_session, portal_id=PORTAL_A, nombre="manual.pdf", vector=[1.0, 0.0, 0.0],
    )

    # Consulta en portugués: solo debe traer el chunk `pt` del artículo + el documento.
    resultado = recuperador.recuperar("qualquer coisa", "pt", str(PORTAL_A), db_session)
    assert resultado.veredicto == "ok"

    idiomas_articulo = {
        f.origen.get("idioma") for f in resultado.fragmentos if f.tipo == "articulo"
    }
    assert idiomas_articulo == {"pt"}  # ningún es

    tipos = {f.tipo for f in resultado.fragmentos}
    assert "documento" in tipos  # el documento sí aparece (sin filtro de idioma)


# --- 7.3 Umbral y top-k -----------------------------------------------------


def test_recuperador_respeta_top_k_y_umbral(db_session, con_embedder):
    """Ningún resultado por debajo del umbral; a lo sumo `RAG_TOP_K` fragmentos."""
    from app.config import get_settings

    settings = get_settings()
    con_embedder(_EmbedderFijo([1.0, 0.0, 0.0]))

    # 8 documentos que superan el umbral (todos apuntando a [1, 0, 0] con
    # pequeñas variaciones que dan similitud ~1).
    for i in range(8):
        _crear_documento_con_chunk(
            db_session,
            portal_id=PORTAL_A,
            nombre=f"doc-alto-{i}.txt",
            vector=[1.0, i * 0.001, 0.0],
        )
    # 2 documentos claramente por debajo del umbral (~0.02).
    for i in range(2):
        _crear_documento_con_chunk(
            db_session,
            portal_id=PORTAL_A,
            nombre=f"doc-bajo-{i}.txt",
            vector=[0.02, 1.0, 0.0],
        )

    resultado = recuperador.recuperar("consulta", "es", str(PORTAL_A), db_session)

    assert resultado.veredicto == "ok"
    assert len(resultado.fragmentos) <= settings.rag_top_k
    assert all(f.similitud >= settings.rag_umbral_similitud for f in resultado.fragmentos)


def test_recuperador_sin_resultados_si_nada_supera_umbral(db_session, con_embedder):
    con_embedder(_EmbedderFijo([1.0, 0.0, 0.0]))
    # Todos los vectores ortogonales o casi ortogonales a la consulta → similitud baja.
    for i in range(3):
        _crear_documento_con_chunk(
            db_session,
            portal_id=PORTAL_A,
            nombre=f"doc-{i}.txt",
            vector=[0.05, 1.0, 0.0],
        )

    resultado = recuperador.recuperar("consulta", "es", str(PORTAL_A), db_session)

    assert resultado.veredicto == "sin_resultados"
    assert resultado.fragmentos == []


# --- 7.4 Fallo del embedder --------------------------------------------------


def test_recuperador_error_proveedor_si_falla_embedder(db_session, con_embedder):
    con_embedder(_EmbedderQueFalla())
    _crear_documento_con_chunk(
        db_session, portal_id=PORTAL_A, nombre="x.txt", vector=[1.0, 0.0, 0.0],
    )

    resultado = recuperador.recuperar("consulta", "es", str(PORTAL_A), db_session)

    assert resultado.veredicto == "error_proveedor"
    assert resultado.fragmentos == []
    # `detalle` es un identificador interno (no un texto del proveedor).
    assert resultado.detalle == "embedder"


def test_recuperador_error_proveedor_si_embedder_devuelve_vector_vacio(
    db_session, con_embedder,
):
    con_embedder(_EmbedderFijo([]))
    _crear_documento_con_chunk(
        db_session, portal_id=PORTAL_A, nombre="x.txt", vector=[1.0, 0.0, 0.0],
    )

    resultado = recuperador.recuperar("consulta", "es", str(PORTAL_A), db_session)

    assert resultado.veredicto == "error_proveedor"
    assert resultado.fragmentos == []
