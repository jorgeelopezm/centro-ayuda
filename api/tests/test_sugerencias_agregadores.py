"""Tests de los agregadores de candidatos (`app.sugerencias`, spec
`sugerencia-articulos-ia`).

Cubre la tarea 7.1: las tres fuentes agregadas con datos sembrados por
portal, incluido el aislamiento cruzado, y el marcado `ya_generada`.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.models import (
    Articulo,
    ArticuloChunk,
    ChatInteraccion,
    Documento,
    DocumentoChunk,
    PreguntaSinResolver,
    SugerenciaArticulo,
)
from app.servicios import PORTAL_DEFECTO_UUID
from app.sugerencias import (
    UMBRAL_SIMILITUD_COBERTURA,
    listar_candidatos,
    resolver_candidato,
)
from tests.conftest import SEGUNDO_PORTAL_UUID, sembrar_portal_secundario

PORTAL_A = PORTAL_DEFECTO_UUID


# --- Helpers de siembra -------------------------------------------------------


def _interaccion(
    db,
    *,
    portal_id,
    veredicto: str,
    consulta: str,
    idioma: str = "es",
    chat_id: str = "c1",
    turno: int = 1,
) -> None:
    db.add(
        ChatInteraccion(
            id=str(uuid.uuid4()),
            portal_id=portal_id,
            chat_id=chat_id,
            turno=turno,
            idioma=idioma,
            consulta=consulta,
            veredicto=veredicto,
            mensaje="",
            citas=[],
            latencia_ms=100,
            proveedor="deepseek",
            modelo="deepseek-chat",
            creado_en=datetime.now(timezone.utc),
        )
    )
    db.commit()


def _articulo_con_chunk(db, *, portal_id, articulo_id: str, embedding: list[float]) -> None:
    db.add(
        Articulo(
            id=articulo_id,
            portal_id=portal_id,
            categoria_id="cuenta",
            actualizado=datetime.now(timezone.utc).date(),
            minutos_lectura=1,
            destacado=False,
        )
    )
    db.flush()
    db.add(
        ArticuloChunk(
            portal_id=portal_id,
            articulo_id=articulo_id,
            idioma="es",
            orden=0,
            contenido="contenido cubierto",
            embedding=embedding,
        )
    )
    db.commit()


def _documento_con_chunks(
    db, *, portal_id, nombre: str, embeddings: list[list[float]], estado: str = "listo"
) -> Documento:
    doc = Documento(
        portal_id=portal_id, nombre=nombre, mime="text/plain",
        idioma="ambos", estado=estado, bytes=10,
    )
    db.add(doc)
    db.flush()
    for i, emb in enumerate(embeddings):
        db.add(
            DocumentoChunk(
                portal_id=portal_id, documento_id=doc.id, orden=i,
                contenido=f"fragmento {i}", embedding=emb,
            )
        )
    db.commit()
    db.refresh(doc)
    return doc


# --- chat_escalado ------------------------------------------------------------


def test_chat_escalado_agrupa_por_consulta_normalizada_y_cuenta_prioridad(db_session):
    _interaccion(db_session, portal_id=PORTAL_A, veredicto="escalar", consulta="  Cómo Cancelo Mi Cuenta  ")
    _interaccion(db_session, portal_id=PORTAL_A, veredicto="escalar", consulta="cómo cancelo mi cuenta")
    _interaccion(db_session, portal_id=PORTAL_A, veredicto="escalar", consulta="otra consulta distinta")
    # Un veredicto distinto de "escalar" no debe contar para esta fuente.
    _interaccion(db_session, portal_id=PORTAL_A, veredicto="respondida", consulta="cómo cancelo mi cuenta")

    candidatos = listar_candidatos(db_session, PORTAL_A, "chat_escalado")

    agrupado = next(c for c in candidatos if c.titulo_sugerido == "cómo cancelo mi cuenta")
    assert agrupado.prioridad == 2
    assert agrupado.fuente == "chat_escalado"
    otro = next(c for c in candidatos if c.titulo_sugerido == "otra consulta distinta")
    assert otro.prioridad == 1


def test_chat_escalado_aisla_por_portal(db_session):
    sembrar_portal_secundario(db_session)
    _interaccion(db_session, portal_id=PORTAL_A, veredicto="escalar", consulta="consulta del portal A")
    _interaccion(db_session, portal_id=SEGUNDO_PORTAL_UUID, veredicto="escalar", consulta="consulta del portal B")

    candidatos_a = listar_candidatos(db_session, PORTAL_A, "chat_escalado")
    titulos_a = {c.titulo_sugerido for c in candidatos_a}
    assert "consulta del portal A" in titulos_a
    assert "consulta del portal B" not in titulos_a


# --- pregunta_sin_resolver ------------------------------------------------


def test_pregunta_sin_resolver_incluye_nueva_y_excluye_cubierta(db_session):
    db_session.add(
        PreguntaSinResolver(
            portal_id=PORTAL_A, idioma="es", pregunta="¿Cómo recupero mi factura?",
            veces=3, similitud=0.4, fecha=datetime.now(timezone.utc).date(),
            estado="nueva", orden=1,
        )
    )
    db_session.add(
        PreguntaSinResolver(
            portal_id=PORTAL_A, idioma="es", pregunta="¿Ya tiene artículo?",
            veces=5, similitud=0.4, fecha=datetime.now(timezone.utc).date(),
            estado="cubierta", orden=2,
        )
    )
    db_session.commit()

    candidatos = listar_candidatos(db_session, PORTAL_A, "pregunta_sin_resolver")
    titulos = {c.titulo_sugerido for c in candidatos}
    assert "¿Cómo recupero mi factura?" in titulos
    assert "¿Ya tiene artículo?" not in titulos


def test_pregunta_sin_resolver_agrupa_interacciones_sin_resultados(db_session):
    _interaccion(db_session, portal_id=PORTAL_A, veredicto="sin_resultados", consulta="cómo exporto mis datos")
    _interaccion(db_session, portal_id=PORTAL_A, veredicto="sin_resultados", consulta="Cómo exporto mis datos")

    candidatos = listar_candidatos(db_session, PORTAL_A, "pregunta_sin_resolver")
    agrupado = next(c for c in candidatos if c.titulo_sugerido == "Cómo exporto mis datos")
    assert agrupado.prioridad == 2
    assert agrupado.referencia.startswith("consulta:")


def test_pregunta_sin_resolver_aisla_por_portal(db_session):
    sembrar_portal_secundario(db_session)
    db_session.add(
        PreguntaSinResolver(
            portal_id=SEGUNDO_PORTAL_UUID, idioma="es", pregunta="pregunta del portal B",
            veces=1, similitud=0.4, fecha=datetime.now(timezone.utc).date(),
            estado="nueva", orden=1,
        )
    )
    db_session.commit()

    candidatos_a = listar_candidatos(db_session, PORTAL_A, "pregunta_sin_resolver")
    titulos_a = {c.titulo_sugerido for c in candidatos_a}
    assert "pregunta del portal B" not in titulos_a


# --- documentacion_rag ------------------------------------------------------


def test_documentacion_rag_detecta_documento_sin_cobertura(db_session):
    # Sin ningún artículo indexado en el portal: cualquier documento cuenta
    # como hueco (similitud 0.0 < UMBRAL_SIMILITUD_COBERTURA).
    doc = _documento_con_chunks(
        db_session, portal_id=PORTAL_A, nombre="manual.pdf",
        embeddings=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
    )

    candidatos = listar_candidatos(db_session, PORTAL_A, "documentacion_rag")
    referencias = {c.referencia: c for c in candidatos}
    assert f"documento:{doc.id}" in referencias
    assert referencias[f"documento:{doc.id}"].prioridad == 2


def test_documentacion_rag_excluye_documento_bien_cubierto(db_session):
    vector = [1.0, 0.0, 0.0]
    _articulo_con_chunk(db_session, portal_id=PORTAL_A, articulo_id="ya-existe", embedding=vector)
    # El fragmento del documento es idéntico al del artículo: similitud 1.0 >= umbral.
    assert UMBRAL_SIMILITUD_COBERTURA < 1.0
    doc = _documento_con_chunks(
        db_session, portal_id=PORTAL_A, nombre="cubierto.pdf", embeddings=[vector],
    )

    candidatos = listar_candidatos(db_session, PORTAL_A, "documentacion_rag")
    referencias = {c.referencia for c in candidatos}
    assert f"documento:{doc.id}" not in referencias


def test_documentacion_rag_ignora_documentos_no_listos(db_session):
    doc = _documento_con_chunks(
        db_session, portal_id=PORTAL_A, nombre="pendiente.pdf",
        embeddings=[[1.0, 0.0, 0.0]], estado="procesando",
    )

    candidatos = listar_candidatos(db_session, PORTAL_A, "documentacion_rag")
    referencias = {c.referencia for c in candidatos}
    assert f"documento:{doc.id}" not in referencias


def test_documentacion_rag_aisla_por_portal(db_session):
    sembrar_portal_secundario(db_session)
    doc_b = _documento_con_chunks(
        db_session, portal_id=SEGUNDO_PORTAL_UUID, nombre="del-portal-b.pdf",
        embeddings=[[1.0, 0.0, 0.0]],
    )

    candidatos_a = listar_candidatos(db_session, PORTAL_A, "documentacion_rag")
    referencias_a = {c.referencia for c in candidatos_a}
    assert f"documento:{doc_b.id}" not in referencias_a


# --- ya_generada y resolución ------------------------------------------------


def test_listar_candidatos_marca_ya_generada_con_sugerencia_pendiente(db_session):
    _interaccion(db_session, portal_id=PORTAL_A, veredicto="escalar", consulta="consulta ya generada")
    candidatos_previos = listar_candidatos(db_session, PORTAL_A, "chat_escalado")
    candidato = next(c for c in candidatos_previos if c.titulo_sugerido == "consulta ya generada")
    assert candidato.ya_generada is False

    db_session.add(
        SugerenciaArticulo(
            id=uuid.uuid4(), portal_id=PORTAL_A, fuente="chat_escalado",
            referencia=candidato.referencia, estado="pendiente",
            contenido={"es": {}, "pt": {}}, citas=[],
            proveedor_chat="deepseek", proveedor_traduccion="anthropic",
            modelo="deepseek-chat", creado_por="admin@test.local",
        )
    )
    db_session.commit()

    candidatos = listar_candidatos(db_session, PORTAL_A, "chat_escalado")
    marcado = next(c for c in candidatos if c.titulo_sugerido == "consulta ya generada")
    assert marcado.ya_generada is True


def test_listar_candidatos_ordena_por_prioridad_descendente(db_session):
    _interaccion(db_session, portal_id=PORTAL_A, veredicto="escalar", consulta="baja")
    for _ in range(3):
        _interaccion(db_session, portal_id=PORTAL_A, veredicto="escalar", consulta="alta")

    candidatos = listar_candidatos(db_session, PORTAL_A, "chat_escalado")
    prioridades = [c.prioridad for c in candidatos]
    assert prioridades == sorted(prioridades, reverse=True)


def test_resolver_candidato_no_encuentra_referencia_inexistente(db_session):
    assert resolver_candidato(db_session, PORTAL_A, "chat_escalado", "consulta:no-existe") is None


def test_resolver_candidato_reconstruye_desde_la_fuente_no_del_cliente(db_session):
    """`resolver_candidato` vuelve a agregar la fuente: si el candidato ya no
    existe (p. ej. la pregunta se borró), no se puede resolver aunque el
    cliente mande una referencia con forma válida."""
    db_session.add(
        PreguntaSinResolver(
            portal_id=PORTAL_A, idioma="es", pregunta="pregunta efímera",
            veces=1, similitud=0.4, fecha=datetime.now(timezone.utc).date(),
            estado="nueva", orden=9,
        )
    )
    db_session.commit()
    candidato = next(
        c for c in listar_candidatos(db_session, PORTAL_A, "pregunta_sin_resolver")
        if c.titulo_sugerido == "pregunta efímera"
    )

    resuelto = resolver_candidato(db_session, PORTAL_A, "pregunta_sin_resolver", candidato.referencia)
    assert resuelto is not None
    assert resuelto.titulo_sugerido == "pregunta efímera"

    # Se borra la pregunta: ya no debe poder resolverse ese candidato.
    pregunta_id = int(candidato.referencia.split(":", 1)[1])
    db_session.query(PreguntaSinResolver).filter(PreguntaSinResolver.id == pregunta_id).delete()
    db_session.commit()

    assert resolver_candidato(db_session, PORTAL_A, "pregunta_sin_resolver", candidato.referencia) is None
