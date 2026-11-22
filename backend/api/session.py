"""Sesión anónima del visitante para el modo público.

No hay cuentas: a cada navegador se le da una cookie aleatoria (`vm_session`). En modo
público (PUBLIC_MODE=true) sirve para que cada visitante vea y resuelva solo SUS propuestas
y para que lo que aprueba no se escriba en la bóveda compartida. No guarda ningún dato
personal: es un identificador opaco.
"""

import re
import secrets

from fastapi import Request, Response

from app.config import Settings

COOKIE = "vm_session"
VALID = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
MAX_AGE = 30 * 24 * 3600  # 30 días


async def session_middleware(request: Request, call_next) -> Response:
    """Asegura que cada petición tiene una sesión; si es nueva, la envía en una cookie."""
    current = request.cookies.get(COOKIE, "")
    is_new = not VALID.match(current)  # una cookie manipulada se trata como ausente
    request.state.session_id = secrets.token_urlsafe(24) if is_new else current
    response = await call_next(request)
    if is_new:
        https = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
        response.set_cookie(
            COOKIE,
            request.state.session_id,
            max_age=MAX_AGE,
            httponly=True,  # el JavaScript de la página no la necesita ni puede leerla
            samesite="lax",
            secure=https,
        )
    return response


def owner_of(request: Request, settings: Settings) -> str | None:
    """Dueño de lo que se cree o consulte: la sesión en modo público; nadie en local."""
    if not settings.public_mode:
        return None
    return getattr(request.state, "session_id", None)
