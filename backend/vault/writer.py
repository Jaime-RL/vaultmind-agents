"""Escritura segura de notas aprobadas en la bóveda.

Reglas (CLAUDE.md, regla 3):
- Solo se escribe dentro de `<bóveda>/_copilot/`.
- Nunca se sobrescribe una nota existente: si el nombre está ocupado se añade " (2)", " (3)"...
- El título viene de un LLM, así que se trata como entrada no confiable: se limpian
  los caracteres que no valen en un nombre de fichero y se impide salir de la carpeta
  con '..', rutas absolutas o enlaces simbólicos.
"""

import re
from pathlib import Path

COPILOT_DIR = "_copilot"
MAX_NAME_LENGTH = 100
# Prohibidos en nombres de fichero (Windows) o con significado especial en Obsidian.
FORBIDDEN_CHARS = re.compile(r'[\\/:*?"<>|#^\[\]\x00-\x1f]')
WINDOWS_RESERVED = (
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)


class UnsafeWriteError(Exception):
    """El destino calculado quedaría fuera de la carpeta permitida."""


def safe_note_name(title: str) -> str:
    name = FORBIDDEN_CHARS.sub(" ", title)
    name = re.sub(r"\s+", " ", name).strip(" .")  # sin espacios ni puntos en los extremos
    name = name[:MAX_NAME_LENGTH].rstrip(" .")
    if not name or set(name) == {"."}:
        name = "Nota"
    if name.upper() in WINDOWS_RESERVED:
        name += "_"
    return name


def write_copilot_note(vault_root: Path, title: str, markdown: str) -> str:
    """Crea la nota y devuelve su ruta relativa a la bóveda (con '/')."""
    root = Path(vault_root).resolve()
    target_dir = root / COPILOT_DIR
    target_dir.mkdir(exist_ok=True)
    # Si _copilot fuera un enlace simbólico a otra parte, resolve() lo delataría.
    if not target_dir.resolve().is_relative_to(root):
        raise UnsafeWriteError("La carpeta _copilot apunta fuera de la bóveda")

    base = safe_note_name(title)
    for attempt in range(1, 1000):
        name = base if attempt == 1 else f"{base} ({attempt})"
        path = target_dir / f"{name}.md"
        if not path.resolve().parent == target_dir.resolve():
            raise UnsafeWriteError(f"Ruta no permitida: {name}")
        try:
            # Modo 'x': crea el fichero y falla si ya existe. Es atómico, así que
            # ni dos aprobaciones simultáneas pueden pisarse.
            with path.open("x", encoding="utf-8") as file:
                file.write(markdown if markdown.endswith("\n") else markdown + "\n")
        except FileExistsError:
            continue
        return f"{COPILOT_DIR}/{path.name}"
    raise UnsafeWriteError("Demasiadas notas con el mismo nombre")
