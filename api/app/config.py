"""Configuración leída del entorno. Los secretos nunca viven en el repo."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Ruta absoluta al .env: una ruta relativa dependería del directorio desde el que
# se arranque el proceso, y un .env no encontrado degradaría la configuración en
# silencio en lugar de fallar.
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    # 127.0.0.1 y no localhost: el contenedor publica solo en IPv4 (ver
    # docker-compose.yml) y en Windows `localhost` resuelve antes a ::1, lo que
    # añade más de dos minutos de espera por cada conexión antes de reintentar.
    database_url: str = "postgresql+psycopg://helpcenter:helpcenter@127.0.0.1:5432/helpcenter"

    # Sin valor por defecto a propósito. Un secreto de firma embebido en el código
    # permitiría a cualquiera que lea el repositorio forjar un token de
    # administrador válido: si falta la variable, la aplicación no debe arrancar.
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    # Vida del refresh token opaco (cookie httpOnly) con el que el BFF renueva el
    # access token en silencio. Rota en cada uso; se revoca en logout y ante
    # reutilización. Ver `app.sesiones`.
    refresh_expire_days: int = 14

    # Administrador inicial que crea el seed. La contraseña, por el mismo motivo
    # que el secreto, es obligatoria y no tiene valor por defecto. El seed lo crea
    # como Administrador (nivel 3): es el primer usuario y quien gestiona a los demás.
    admin_email: str = "admin@centro-ayuda.local"
    admin_password: str

    # SuperAdmin inicial (nivel 4, transversal a los portales). Opcional a propósito:
    # sin `superadmin_password` el seed no lo crea (ni crea el portal de plataforma), y
    # el entorno de desarrollo single-portal sigue funcionando igual. Cuando se define,
    # el seed provisiona el/los SuperAdmin. Es un secreto: no tiene valor por defecto.
    superadmin_email: str = "superadmin@centro-ayuda.local"
    superadmin_password: str | None = None

    # Valor inicial del campo [Empresa] (nombre de marca global). Editable después
    # desde el panel por un usuario Administrador; el seed solo lo usa para la primera fila.
    empresa_inicial: str = "[Empresa]"

    # Dominio base de los subdominios de portal (`<slug>.tuapp.com`). Solo se usa para
    # extraer el slug cuando el host ES un subdominio suyo; los dominios propios y el
    # desarrollo (`localhost`) se resuelven por coincidencia exacta en la tabla
    # `dominios`. Configurable por entorno para no fijar el dominio de producción aquí.
    base_domain: str = "tuapp.com"

    # Clave simétrica (Fernet) con la que se cifran en reposo las claves de API de
    # los proveedores de IA que introduce el Administrador. Opcional a propósito: sin ella la
    # API arranca igual y todo funciona salvo guardar/usar claves de IA (traducción),
    # que avisa de que falta configurarla. Generar una propia:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    clave_cifrado_ia: str | None = None

    # --- Chat con RAG por portal ---------------------------------------------
    # Los valores por defecto se calibraron con `voyage-3` (1024 dims) y `deepseek-chat`:
    # umbral y top-k son la mínima ceremonia para distinguir «sin resultados» de un
    # hit real; los límites de entrada, historial y tasa cortan payloads y abuso antes
    # de tocar al proveedor (ver spec `chat-generativo-rag`).

    # Similitud mínima (coseno) que un fragmento debe superar para considerarse
    # relevante. Por debajo se descarta y el pipeline devuelve `sin_resultados`
    # en lugar de improvisar.
    rag_umbral_similitud: float = 0.28
    # Cota superior de fragmentos que el recuperador devuelve al pipeline.
    rag_top_k: int = 6

    # Máximo de caracteres aceptado en la consulta del usuario antes de invocar al
    # proveedor. Corta consultas desmesuradas (defensa contra abuso e inyección).
    chat_max_consulta_chars: int = 500
    # Últimos turnos de historial que el pipeline conserva al componer el prompt.
    chat_max_historial_turnos: int = 10
    # Nº de `sin_resultados` consecutivos por sesión tras el que se escala a soporte.
    chat_umbral_turnos_sin_resultados: int = 2
    # Vida útil de una sesión de chat en memoria del proceso (segundos). Al vencer,
    # el contador de turnos sin resultados se pierde y se emite un `session_id` nuevo.
    chat_ttl_sesion_seg: int = 1800
    # Techo de peticiones por IP y minuto al endpoint público del chat.
    chat_limite_tasa_min: int = 30
    # Interruptor de mantenimiento: `false` responde 503 sin invocar al proveedor.
    chat_habilitado: bool = True
    # Escritura de cada interacción del chat en `chat_interaccion` (spec
    # `supervision-chats`). Bandera de emergencia: si `False`, la respuesta al
    # usuario funciona igual pero no queda traza para el panel de supervisión.
    chat_persistencia_habilitada: bool = True
    # Tope duro por caracteres para la respuesta final del asistente. El pipeline
    # aplica un recorte suave (al último `.` o ` > ` dentro de la ventana) SOLO
    # cuando el veredicto es `respondida`; el recorte no cambia el veredicto ni
    # invalida las citas (la spec `chat-generativo-rag` lo detalla). 1400 chars
    # ≈ 3 frases + un procedimiento de 4 pasos, en línea con `MAX_TOKENS_CHAT`.
    chat_longitud_max_chars: int = 1400

    # Caché de respuesta a nivel de aplicación (spec `chat-generativo-rag` ›
    # «Caché de respuesta por portal con revalidación de citas»). Solo se cachea
    # el veredicto `respondida`; antes de servir un hit se revalida que cada
    # recurso citado sigue existiendo en el portal. La clave lleva `portal_id`,
    # `idioma`, `consulta_normalizada`, `config_ia_version` y
    # `schema_recuperacion`: cambiar el proveedor o el modelo invalida el hit
    # implícitamente. Apagable con `CHAT_CACHE_HABILITADA=0`.
    chat_cache_habilitada: bool = True
    chat_cache_ttl_seg: int = 600
    chat_cache_max_entradas: int = 1000

    # --- Proxies de confianza (X-Forwarded-*) --------------------------------
    # Lista separada por comas de IPs del salto inmediato ante el backend cuyo
    # `X-Forwarded-For` y `X-Forwarded-Host` se aceptan como fuente del cliente
    # y del portal. Cualquier otra IP peer se ignora: se cae al socket para la
    # IP y al `Host` para el portal, previniendo suplantación por un cliente
    # que fabrique esas cabeceras y llegue directo al puerto del backend.
    # Default: loopback (dev con Next → uvicorn en la misma máquina). En
    # producción, la IP del reverse proxy (nginx/traefik/etc.) debe estar aquí.
    proxies_confiables: str = "127.0.0.1,::1"

    @property
    def proxies_confiables_set(self) -> frozenset[str]:
        return frozenset(p.strip() for p in self.proxies_confiables.split(",") if p.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
