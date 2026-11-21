# syntax=docker/dockerfile:1
#
# Un único Dockerfile multi-stage para todo VaultMind. Cada "target" es una imagen:
#
#   backend-dev   API con recarga en caliente   (docker compose, servicio backend)
#   frontend-dev  servidor de Vite              (docker compose, servicio frontend)
#   prod          UNA imagen: FastAPI sirve la API y el frontend compilado
#                 (la que se despliega en Render / Fly.io)
#
# Por qué uno solo y no backend/Dockerfile + frontend/Dockerfile: en producción
# queremos un único servicio (una URL, sin CORS) y eso exige compilar el frontend
# y copiarlo junto al backend en la misma imagen. Con stages compartidos, dev y
# prod usan exactamente las mismas versiones de Python, Node y dependencias.
#
# La estructura dentro de la imagen replica la del repo (/app/backend,
# /app/demo-vault...) porque backend/app/config.py resuelve la bóveda y la base de
# datos relativas a la raíz del repo.

ARG PYTHON_VERSION=3.12
ARG NODE_VERSION=24

# ---------------------------------------------------------------- backend ----
FROM python:${PYTHON_VERSION}-slim AS backend-base

# uv instala dependencias en segundos y respeta backend/uv.lock al pie de la letra.
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    # El entorno virtual vive FUERA de /app/backend: en desarrollo esa carpeta se
    # monta desde el host y taparía un .venv creado dentro durante el build.
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app/backend

# Primero solo los ficheros de dependencias: si cambia el código pero no las
# dependencias, Docker reutiliza esta capa y el build tarda segundos.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# --- backend-dev: dependencias de desarrollo y uvicorn --reload ---------------
FROM backend-base AS backend-dev
RUN uv sync --frozen --no-install-project
EXPOSE 8000
# El código no se copia: docker-compose.yml monta ./backend como volumen.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# --------------------------------------------------------------- frontend ----
FROM node:${NODE_VERSION}-alpine AS frontend-deps
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

# --- frontend-dev: servidor de Vite -------------------------------------------
FROM frontend-deps AS frontend-dev
EXPOSE 5173
# El código se monta como volumen; node_modules se queda en la imagen (ver compose).
CMD ["npm", "run", "dev"]

# --- frontend-build: compila a estáticos (dist/) ------------------------------
FROM frontend-deps AS frontend-build
COPY frontend/ ./
# VITE_API_URL vacío = el frontend llama a /api en su mismo origen.
ENV VITE_API_URL=""
RUN npm run build

# ------------------------------------------------------------------- prod ----
FROM backend-base AS prod

# Usuario sin privilegios: si alguien explotara la app, no sería root en el contenedor.
RUN useradd --create-home --uid 1000 app

COPY backend/ /app/backend/
COPY demo-vault/ /app/demo-vault/
# La grabación que reproduce el modo demo (fixtures/demo_run.json).
COPY fixtures/ /app/fixtures/
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist

# La base de datos SQLite y las notas aprobadas (_copilot/) se escriben en tiempo
# de ejecución: esas rutas deben pertenecer al usuario de la app.
RUN mkdir -p /app/data && chown -R app:app /app/data /app/demo-vault
USER app

# La imagen pública arranca en modo demo: sin clave de API y sin gasto. Para usarla
# con modelos reales: DEMO_MODE=false y LLM_API_KEY en el entorno del contenedor.
ENV FRONTEND_DIST=/app/frontend/dist \
    DEMO_MODE=true \
    PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/api/health', timeout=2)"

# Render y Fly.io inyectan el puerto en $PORT: por eso la forma shell (sh -c).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
