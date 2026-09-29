"""Harness de evaluación del chat con RAG (EDD).

Ejecuta cada caso del dataset (`casos_{es,pt}.jsonl`) contra `chat.responder`
en dos modos:

- **`ci`** (por defecto, `pytest -m eval`): usa dobles deterministas para el
  proveedor de chat y el embedder. No hace llamadas de red. Comprueba el
  pipeline completo (scope, recuperación, validación de citas, formato) contra
  el veredicto esperado, la precisión/recall de citas por slug y las cotas de
  brevedad.
- **`real`** (`pytest -m eval --real`, requiere `CHAT_EVAL_HABILITADO_REAL=1`):
  apunta al proveedor real de `ConfigIA` y mide además latencia y coste
  estimado por caso. Se salta con `pytest.skip` sin la combinación bandera+flag.

Ambos modos escriben `reports/last.json` con métricas agregadas por idioma y
por corrida, y por caso. El gate contra `baseline.json` falla el test si alguna
métrica cae bajo su umbral (configurable por métrica en el baseline).
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import cache_chat as cache_mod
from app import chat as chat_mod
from app import recuperador as recuperador_mod
from app import sesiones_chat
from app.chat import responder
from app.database import Base
from app.models import (
    AdminUser,
    Ajustes,
    Articulo,
    ArticuloChunk,
    ArticuloTraduccion,
    Categoria,
    CategoriaTraduccion,
    Dominio,
    NivelAcceso,
    Portal,
)
from app.security import hash_password
from app.servicios import PORTAL_DEFECTO_UUID
from tests.eval.proveedor_doble import (
    EmbedderDoble,
    ProveedorChatDoble,
    cargar_casos,
    compilar_respuestas_por_caso,
    construir_corpus_vectores,
)

pytestmark = pytest.mark.eval

DIR_EVAL = Path(__file__).resolve().parent
DIR_REPORTS = DIR_EVAL / "reports"
FILE_BASELINE = DIR_EVAL / "baseline.json"

PORTAL_HOST = "localhost"
# El id ya no es el slug legible ("default"): es un UUID (migración
# `0012_portal_uuid`); se reutiliza la constante fija del portal `default` para
# que el fixture no dependa de un UUID inventado.
PORTAL_EVAL_SLUG = "default"
PORTAL_EVAL_UUID = PORTAL_DEFECTO_UUID
# El campo `portal` de cada caso del dataset (`casos_{es,pt}.jsonl`) es una
# etiqueta legible, no el id real: se traduce al UUID que sembró el fixture.
_PORTAL_UUID_POR_ETIQUETA = {PORTAL_EVAL_SLUG: str(PORTAL_EVAL_UUID)}

# Regex barato para detectar el formato de pasos en línea (`paso 1 > paso 2 > ...`).
# Se acepta cualquier separador con un ` > ` entre segmentos: contamos 1 acierto si
# la respuesta contiene AL MENOS un ` > `. La cota de 4 pasos la aplica el prompt.
_PATRON_PASOS = " > "


@dataclass
class ResultadoCaso:
    id: str
    idioma: str
    veredicto_esperado: str
    veredicto_obtenido: str
    citas_obtenidas: list[str]
    citas_esperadas: list[str]
    longitud: int
    latencia_ms: int
    tokens_entrada: int | None = None
    tokens_salida: int | None = None
    coste_estimado_usd: float = 0.0
    debe_contener_pasos: bool = False
    pasos_correctos: bool = False
    longitud_max: int | None = None
    dentro_de_longitud: bool = True
    error: str | None = None


@dataclass
class Metricas:
    total: int = 0
    exactitud_veredicto: float = 0.0
    precision_citas: float = 0.0
    recall_citas: float = 0.0
    longitud_media: float = 0.0
    pasos_en_formato_correcto: float = 0.0
    latencia_media_ms: float = 0.0
    coste_total_usd_estimado: float = 0.0
    por_veredicto: dict[str, dict[str, int]] = field(default_factory=dict)


# --- Fixtures ---------------------------------------------------------------


@pytest.fixture(scope="module")
def casos() -> list[dict]:
    todos: list[dict] = []
    for idioma in ("es", "pt"):
        todos.extend(cargar_casos(DIR_EVAL / f"casos_{idioma}.jsonl"))
    return todos


@pytest.fixture
def corpus_vectores(casos) -> tuple[dict[str, list[float]], int]:
    """Mapa `articulo_id → vector one-hot` y dimensión, compartido por el
    sembrador de la base y el embedder doble para que ambos usen el mismo
    espacio vectorial."""
    return construir_corpus_vectores(casos)


@pytest.fixture
def db_eval(casos, corpus_vectores):
    """Base SQLite en memoria con el corpus del harness sembrado.

    Reutiliza el patrón del `conftest` general (StaticPool + `create_all`) pero
    siembra artículos concretos derivados de los casos `respondida` para que el
    recuperador vectorial encuentre exactamente el artículo esperado por caso.
    """
    articulo_a_vector, _dimension = corpus_vectores
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _activar_fk(dbapi_conn, _record):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()

    # Portal + host + categoría + admin mínimos (misma forma que `_sembrar_minimo`).
    db.add(
        Portal(
            id=PORTAL_EVAL_UUID,
            slug=PORTAL_EVAL_SLUG,
            nombre_empresa="Eval",
            estado="activo",
        )
    )
    db.add(Dominio(host=PORTAL_HOST, portal_id=PORTAL_EVAL_UUID, principal=True))
    db.flush()
    db.add(Categoria(id="cuenta", portal_id=PORTAL_EVAL_UUID, icono="usuario", orden=0))
    for idioma, slug, nombre in (("es", "cuenta", "Cuenta"), ("pt", "conta", "Conta")):
        db.add(CategoriaTraduccion(
            categoria_id="cuenta", portal_id=PORTAL_EVAL_UUID,
            idioma=idioma, slug=slug, nombre=nombre,
        ))
    db.add(AdminUser(
        portal_id=PORTAL_EVAL_UUID, email="eval@test.local",
        password_hash=hash_password("secreto-de-eval"),
        nivel=NivelAcceso.ADMINISTRADOR.value, activo=True,
    ))
    db.add(Ajustes(id=1, portal_id=PORTAL_EVAL_UUID))
    # Flush explícito antes del bucle de artículos: SQLAlchemy no siempre ordena
    # correctamente el insert de `Articulo` (FK compuesta `(portal_id,
    # categoria_id) → categorias(portal_id, id)`) respecto al de `Categoria` en
    # el mismo flush; sin este flush la FK falla en SQLite (donde el chequeo es
    # inmediato al hacer el INSERT en el orden que el ORM elige).
    db.flush()

    # Un artículo por caso `respondida`, con un chunk cuyo vector coincide con el
    # asignado en `articulo_a_vector` (one-hot). El embedder doble devuelve el
    # mismo vector para la consulta del caso, así que el recuperador lo encuentra.
    for caso in casos:
        if caso["veredicto_esperado"] != "respondida":
            continue
        articulo_id = caso["id"]
        slug = caso["citas_esperadas_por_slug"][0]
        idioma = caso["idioma"]
        vector = articulo_a_vector[articulo_id]
        db.add(Articulo(
            id=articulo_id, portal_id=PORTAL_EVAL_UUID, categoria_id="cuenta",
            actualizado=date(2026, 1, 1), minutos_lectura=1, destacado=False,
        ))
        db.flush()
        db.add(ArticuloTraduccion(
            articulo_id=articulo_id, portal_id=PORTAL_EVAL_UUID, idioma=idioma,
            slug=slug, titulo=f"Artículo {articulo_id}",
            parrafos=[], how_to={"titulo": "", "pasos": []}, nota=None, faq=[],
        ))
        db.add(ArticuloChunk(
            portal_id=PORTAL_EVAL_UUID, articulo_id=articulo_id, idioma=idioma,
            orden=0, contenido=f"Fragmento del caso {articulo_id}",
            embedding=list(vector),
        ))
    db.commit()

    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def dobles(casos, corpus_vectores, monkeypatch):
    """Instala los dobles del proveedor de chat y del embedder.

    En modo `ci` los dobles son deterministas; en modo `real` esta fixture no
    los instala (los tests correspondientes usan `crear_chat` y `crear_embedder`
    reales, que resuelven a partir de `ConfigIA`).
    """
    respuestas = compilar_respuestas_por_caso(casos)
    articulo_a_vector, dimension = corpus_vectores

    chat_mod.inyectar_chat_factory(
        lambda _db: ProveedorChatDoble(respuestas)
    )
    embedder_doble = EmbedderDoble(respuestas, articulo_a_vector, dimension)
    monkeypatch.setattr(recuperador_mod, "crear_embedder", lambda _db: embedder_doble)
    yield
    chat_mod.restaurar_chat_factory()


@pytest.fixture(autouse=True)
def _reset_estado_por_test():
    """Cada corrida del harness arranca con las sesiones y la caché vacías."""
    sesiones_chat.reset_para_tests()
    sesiones_chat.restaurar_reloj()
    cache_mod.reset_para_tests()
    yield
    sesiones_chat.reset_para_tests()
    sesiones_chat.restaurar_reloj()
    cache_mod.reset_para_tests()


# --- Ejecución de un caso ---------------------------------------------------


def _ejecutar_caso(caso: dict, db) -> ResultadoCaso:
    """Ejecuta un caso end-to-end y devuelve el resultado observado.

    No propaga excepciones: si el pipeline levanta (por ejemplo, `ConsultaInvalida`),
    se anota `error` y se registran valores neutros para no romper el harness.
    """
    inicio = time.monotonic()
    try:
        respuesta = responder(
            consulta=caso["consulta"],
            idioma=caso["idioma"],
            historial=[],
            portal_id=_PORTAL_UUID_POR_ETIQUETA[caso["portal"]],
            chat_id=None,
            solicitar_soporte=bool(caso.get("solicitar_soporte", False)),
            db=db,
        )
    except Exception as exc:  # noqa: BLE001
        return ResultadoCaso(
            id=caso["id"], idioma=caso["idioma"],
            veredicto_esperado=caso["veredicto_esperado"],
            veredicto_obtenido="error",
            citas_obtenidas=[], citas_esperadas=list(caso.get("citas_esperadas_por_slug", [])),
            longitud=0, latencia_ms=int((time.monotonic() - inicio) * 1000),
            debe_contener_pasos=bool(caso.get("debe_contener_pasos", False)),
            longitud_max=caso.get("longitud_max"),
            error=f"{type(exc).__name__}: {exc}",
        )

    latencia_ms = int((time.monotonic() - inicio) * 1000)
    citas_obtenidas = [
        f.slug if f.tipo == "articulo" else f.titulo for f in respuesta.fuentes
    ]
    citas_esperadas = list(caso.get("citas_esperadas_por_slug", []))
    debe_contener_pasos = bool(caso.get("debe_contener_pasos", False))
    pasos_correctos = _PATRON_PASOS in respuesta.mensaje if debe_contener_pasos else True
    longitud_max = caso.get("longitud_max")
    dentro_de_longitud = (
        len(respuesta.mensaje) <= longitud_max if longitud_max is not None else True
    )
    return ResultadoCaso(
        id=caso["id"], idioma=caso["idioma"],
        veredicto_esperado=caso["veredicto_esperado"],
        veredicto_obtenido=respuesta.veredicto,
        citas_obtenidas=citas_obtenidas, citas_esperadas=citas_esperadas,
        longitud=len(respuesta.mensaje), latencia_ms=latencia_ms,
        debe_contener_pasos=debe_contener_pasos,
        pasos_correctos=pasos_correctos,
        longitud_max=longitud_max,
        dentro_de_longitud=dentro_de_longitud,
    )


# --- Métricas ---------------------------------------------------------------


def _promedio(valores: list[float]) -> float:
    return sum(valores) / len(valores) if valores else 0.0


def _precision_recall_citas(resultados: list[ResultadoCaso]) -> tuple[float, float]:
    """Precisión y recall macro sobre los casos `respondida`.

    Precisión por caso: |obtenidas ∩ esperadas| / |obtenidas|.
    Recall por caso: |obtenidas ∩ esperadas| / |esperadas|.
    Sin obtenidas o sin esperadas, ese caso aporta 0 al promedio para no
    inflar por vacío.
    """
    precisiones: list[float] = []
    recalls: list[float] = []
    for r in resultados:
        if r.veredicto_esperado != "respondida":
            continue
        obtenidas = set(r.citas_obtenidas)
        esperadas = set(r.citas_esperadas)
        inter = obtenidas & esperadas
        precisiones.append(len(inter) / len(obtenidas) if obtenidas else 0.0)
        recalls.append(len(inter) / len(esperadas) if esperadas else 0.0)
    return _promedio(precisiones), _promedio(recalls)


def _calcular_metricas(resultados: list[ResultadoCaso]) -> Metricas:
    total = len(resultados)
    if not total:
        return Metricas()
    aciertos = sum(1 for r in resultados if r.veredicto_obtenido == r.veredicto_esperado)
    precision_citas, recall_citas = _precision_recall_citas(resultados)
    longitudes = [r.longitud for r in resultados if r.veredicto_obtenido == "respondida"]
    con_pasos = [r for r in resultados if r.debe_contener_pasos]
    pasos_ok = sum(1 for r in con_pasos if r.pasos_correctos) / len(con_pasos) if con_pasos else 0.0
    latencias = [r.latencia_ms for r in resultados]
    por_veredicto: dict[str, dict[str, int]] = {}
    for r in resultados:
        entrada = por_veredicto.setdefault(
            r.veredicto_esperado, {"esperados": 0, "aciertos": 0}
        )
        entrada["esperados"] += 1
        if r.veredicto_obtenido == r.veredicto_esperado:
            entrada["aciertos"] += 1
    return Metricas(
        total=total,
        exactitud_veredicto=aciertos / total,
        precision_citas=precision_citas,
        recall_citas=recall_citas,
        longitud_media=_promedio(longitudes),
        pasos_en_formato_correcto=pasos_ok,
        latencia_media_ms=_promedio(latencias),
        coste_total_usd_estimado=sum(r.coste_estimado_usd for r in resultados),
        por_veredicto=por_veredicto,
    )


def _metricas_a_dict(m: Metricas) -> dict:
    return {
        "total": m.total,
        "exactitud_veredicto": round(m.exactitud_veredicto, 4),
        "precision_citas": round(m.precision_citas, 4),
        "recall_citas": round(m.recall_citas, 4),
        "longitud_media": round(m.longitud_media, 2),
        "pasos_en_formato_correcto": round(m.pasos_en_formato_correcto, 4),
        "latencia_media_ms": round(m.latencia_media_ms, 2),
        "coste_total_usd_estimado": round(m.coste_total_usd_estimado, 4),
        "por_veredicto": m.por_veredicto,
    }


def _resultado_a_dict(r: ResultadoCaso) -> dict:
    return {
        "id": r.id,
        "idioma": r.idioma,
        "veredicto_esperado": r.veredicto_esperado,
        "veredicto_obtenido": r.veredicto_obtenido,
        "citas_esperadas": r.citas_esperadas,
        "citas_obtenidas": r.citas_obtenidas,
        "longitud": r.longitud,
        "latencia_ms": r.latencia_ms,
        "tokens_entrada": r.tokens_entrada,
        "tokens_salida": r.tokens_salida,
        "coste_estimado_usd": r.coste_estimado_usd,
        "debe_contener_pasos": r.debe_contener_pasos,
        "pasos_correctos": r.pasos_correctos,
        "longitud_max": r.longitud_max,
        "dentro_de_longitud": r.dentro_de_longitud,
        "error": r.error,
    }


# --- Gate contra baseline ---------------------------------------------------


def _cargar_baseline() -> dict:
    if not FILE_BASELINE.exists():
        return {}
    return json.loads(FILE_BASELINE.read_text(encoding="utf-8"))


def _fallos_de_gate(actual: dict, baseline: dict) -> list[str]:
    """Compara métricas del run contra el baseline. Devuelve una lista de
    mensajes de fallo (vacía si todo pasa)."""
    if not baseline:
        return []
    fallos: list[str] = []
    metricas = baseline.get("metricas", {})
    for nombre, config in metricas.items():
        umbral = config.get("umbral")
        modo = config.get("modo", "min")  # min = actual >= umbral - margen; max = actual <= umbral * factor
        margen = config.get("margen", 0.0)
        factor = config.get("factor", 1.0)
        actual_valor = actual.get(nombre)
        if actual_valor is None:
            continue
        if modo == "min":
            limite = umbral - margen
            if actual_valor < limite:
                fallos.append(
                    f"{nombre}: {actual_valor:.4f} < baseline {umbral:.4f} - margen {margen:.4f}"
                )
        elif modo == "max":
            limite = umbral * factor
            if actual_valor > limite:
                fallos.append(
                    f"{nombre}: {actual_valor:.4f} > baseline {umbral:.4f} * factor {factor:.4f}"
                )
    return fallos


# --- Tests ------------------------------------------------------------------


def _modo_real_activo(request) -> bool:
    """`--real` en CLI y `CHAT_EVAL_HABILITADO_REAL=1` en entorno.

    Si `--real` viene sin la variable, se salta el test (no falla).
    """
    return bool(request.config.getoption("--real", default=False))


def _modo_real_permitido() -> bool:
    return os.environ.get("CHAT_EVAL_HABILITADO_REAL") == "1"


def test_dataset_cubre_los_cuatro_veredictos_por_idioma(casos):
    """Requisito del spec `evaluacion-chat-rag`: cada idioma con los cuatro veredictos."""
    esperados = {"respondida", "sin_resultados", "fuera_de_scope", "escalar"}
    for idioma in ("es", "pt"):
        veredictos = {c["veredicto_esperado"] for c in casos if c["idioma"] == idioma}
        assert esperados.issubset(veredictos), (
            f"El dataset {idioma} no cubre todos los veredictos: falta {esperados - veredictos}"
        )


def test_dataset_incluye_adversario_por_idioma(casos):
    for idioma in ("es", "pt"):
        adversarios = [c for c in casos if c["idioma"] == idioma and c.get("adversario")]
        assert adversarios, f"El dataset {idioma} no incluye ningún caso adversario"


def test_harness_eval_chat_ci(request, casos, db_eval, dobles):
    """Ejecuta el harness en modo `ci` (dobles deterministas) y aplica el gate."""
    if _modo_real_activo(request):
        if not _modo_real_permitido():
            pytest.skip("Modo `--real` requiere CHAT_EVAL_HABILITADO_REAL=1; se salta")
        # En modo real, el test dedicado más abajo se encarga; se salta este.
        pytest.skip("Modo real activo: se ejecuta `test_harness_eval_chat_real`")

    resultados = [_ejecutar_caso(c, db_eval) for c in casos]
    metricas_global = _calcular_metricas(resultados)
    por_idioma = {
        idioma: _calcular_metricas([r for r in resultados if r.idioma == idioma])
        for idioma in ("es", "pt")
    }

    informe = {
        "modo": "ci",
        "generado_en": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "proveedor": "doble-determinista",
        "modelo": "n/a",
        "metricas": _metricas_a_dict(metricas_global),
        "por_idioma": {i: _metricas_a_dict(m) for i, m in por_idioma.items()},
        "casos": [_resultado_a_dict(r) for r in resultados],
    }
    DIR_REPORTS.mkdir(parents=True, exist_ok=True)
    (DIR_REPORTS / "last.json").write_text(
        json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    baseline = _cargar_baseline()
    fallos = _fallos_de_gate(informe["metricas"], baseline)
    if fallos:
        detalle = "\n".join(f"  - {f}" for f in fallos)
        pytest.fail(f"Gate contra baseline falla:\n{detalle}")


def test_harness_eval_chat_real(request, casos, db_eval):
    """Ejecuta el harness contra el proveedor real de `ConfigIA`.

    Se salta si no se pasó `--real` o si `CHAT_EVAL_HABILITADO_REAL` no es 1
    (protección contra ejecuciones accidentales con coste).
    """
    if not _modo_real_activo(request):
        pytest.skip("Modo `real` requiere el flag `--real`")
    if not _modo_real_permitido():
        pytest.skip("Modo `real` requiere CHAT_EVAL_HABILITADO_REAL=1")

    # En modo real no se instalan dobles: el chat resuelve con `crear_chat` y el
    # embedder con `crear_embedder`, ambos leyendo la clave real de `ConfigIA`.
    resultados = [_ejecutar_caso(c, db_eval) for c in casos]
    metricas_global = _calcular_metricas(resultados)
    informe = {
        "modo": "real",
        "generado_en": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "proveedor": os.environ.get("CHAT_EVAL_PROVEEDOR", "config_ia"),
        "modelo": os.environ.get("CHAT_EVAL_MODELO", "config_ia"),
        "metricas": _metricas_a_dict(metricas_global),
        "casos": [_resultado_a_dict(r) for r in resultados],
    }
    DIR_REPORTS.mkdir(parents=True, exist_ok=True)
    (DIR_REPORTS / "last.json").write_text(
        json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    baseline = _cargar_baseline()
    fallos = _fallos_de_gate(informe["metricas"], baseline)
    if fallos:
        detalle = "\n".join(f"  - {f}" for f in fallos)
        pytest.fail(f"Gate contra baseline falla (modo real):\n{detalle}")
