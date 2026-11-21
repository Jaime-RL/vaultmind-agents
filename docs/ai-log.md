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

### 2026-11-21 · Persona A · HU1: parser de la bóveda
- **Prompt:** «Parser de la bóveda (Markdown + wikilinks) → /api/vault, con tests. Crear la bóveda de demostración».
- **Qué funcionó:** escribir primero una bóveda mínima con todos los casos límite de Obsidian (alias, secciones, embebidos, nombres repetidos, código). Los tests encontraron un bug real: el `#` de `[[#Encabezado]]` se leía como etiqueta.
- **Qué costó o falló:** al arrancar el servidor a mano, la ruta por defecto `demo-vault` era relativa al directorio actual y fallaba desde `backend/`; los tests no lo detectaron porque pasaban la ruta explícita. Además, la regla `vault/` del `.gitignore` ignoraba en silencio `backend/vault/` y el código no se subía. Lección: probar la app real y revisar `git status` antes de dar algo por subido.
- **Qué cambiaría:** —

### 2026-11-21 · Persona A · SmartRoute y fixture de eventos
- **Prompt:** «SmartRoute: reglas por tipo de tarea, escalada si el SLM falla o devuelve un JSON inválido; registro de coste y latencia. Grabar fixtures/run_example.jsonl».
- **Qué funcionó:** tratar «respuesta rechazada por un validador» igual que «fallo del proveedor» (ambos son `LLMError`) simplificó la escalada a un solo `try/except`. Generar el fixture con los propios modelos del contrato en lugar de escribir JSON a mano: es válido por construcción y un test vigila que sus enlaces existan en la bóveda de demo.
- **Qué costó o falló:** decidir cómo contar el coste de una escalada; se cobra también el intento fallido del SLM, para que el ahorro mostrado no sea optimista.
- **Qué cambiaría:** los precios por defecto son orientativos; hay que fijarlos a los modelos reales antes de publicar cifras de ahorro.
