# Registro de desarrollo con IA

Materia prima para la sección «Cómo se construyó con IA» del README. Apunta aquí, con fecha y persona, los prompts que funcionaron, los que fallaron y lo que aprendiste.

## Plantilla

### AAAA-MM-DD · Persona A/B · Tema
- **Prompt:** (copia el prompt o su parte importante)
- **Qué funcionó:**
- **Qué costó o falló:**
- **Qué cambiaría:**

---

### 2026-11-21 · Persona A · Arranque del repo
- **Prompt:** prompt de arranque de la Persona A (rol, stack, arquitectura, reglas y tarea del día), pidiendo un plan antes de programar.
- **Qué funcionó:** pedir el plan primero permitió fijar decisiones antes de escribir código (esquemas JSON como fuente de verdad del contrato; `FakeLLMClient` que falla si se acaba el guion).
- **Qué costó o falló:**
- **Qué cambiaría:**

### 2026-11-21 · Persona B · Esqueleto del frontend e infraestructura
- **Prompt:** prompt de arranque de la Persona B con la tarea del sábado (esqueleto React + Vite, DevContainer, Dockerfile y docker-compose), pidiendo revisar `CLAUDE.md` y `contracts/` antes de proponer nada.
- **Qué funcionó:** pedir al agente que comprobara las dependencias entre paquetes antes de instalar: detectó que TypeScript 7 (la última) no es compatible con `typescript-eslint`, y se fijó `~6.0.3`. Generar los tipos TypeScript desde los esquemas JSON (`npm run gen:types`) en lugar de escribirlos a mano.
- **Qué costó o falló:** el entorno del agente no podía descargar imágenes de Docker, así que el Dockerfile se valida en la CI (build + arranque de la imagen + `/api/health`) y no en local.
- **Qué cambiaría:** decidir desde el día 1 que producción es un solo servicio (FastAPI sirve el frontend compilado): evita CORS y una URL distinta por entorno.
