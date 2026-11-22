"""Lee una bóveda de Obsidian y la convierte en un grafo de notas.

Imita cómo Obsidian resuelve los enlaces, para que el grafo de VaultMind
coincida con lo que el usuario ve en su propia vista de grafo:

- `[[nota]]`, `[[nota|alias]]`, `[[nota#Encabezado]]`, `[[nota#^bloque]]` y `![[nota]]`
  enlazan todos a `nota`.
- `[[carpeta/nota]]` resuelve por ruta; `[[nota]]` por nombre de fichero, en cualquier carpeta.
- La resolución no distingue mayúsculas.
- Los enlaces dentro de bloques de código no cuentan.

Los enlaces que no apuntan a ninguna nota no entran en el grafo, pero se
guardan en `Note.unresolved`: son exactamente las «lagunas» (conceptos
mencionados sin nota propia) que buscará el agente Explorador.
"""

import re
from dataclasses import dataclass, field, replace
from pathlib import Path, PurePosixPath

from app.contracts import VaultGraph, VaultLink, VaultNode

# [[destino#sección|alias]] — el grupo 1 es el destino (puede estar vacío en [[#Encabezado]]).
WIKILINK_RE = re.compile(r"!?\[\[([^\[\]|#^]*)(?:[#^][^\[\]|]*)?(?:\|[^\[\]]*)?\]\]")

# #etiqueta: no puede ir pegada a una palabra, a '/' (URLs con anclas) ni a otra '#'.
# Un encabezado ("# Título") no casa porque exige un carácter justo después de '#'.
INLINE_TAG_RE = re.compile(r"(?<![\w/#])#([\w\-/]+)")

FENCED_CODE_RE = re.compile(r"^(```|~~~).*?^\1[^\n]*$", re.DOTALL | re.MULTILINE)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")

# Enlaces a adjuntos (imágenes, PDFs...): no son notas ni lagunas, se ignoran.
ATTACHMENT_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".pdf", ".mp3", ".mp4",
    ".webm", ".wav", ".csv", ".canvas", ".excalidraw",
}  # fmt: skip


class VaultNotFoundError(FileNotFoundError):
    """La ruta configurada no existe o no es una carpeta."""


@dataclass(frozen=True)
class Note:
    id: str  # ruta relativa sin .md, con '/' (ej.: 'ml/transformers')
    title: str  # nombre del fichero sin .md, como lo muestra Obsidian
    path: str  # ruta relativa con .md
    tags: tuple[str, ...]
    content: str  # texto completo, para que los agentes lo lean
    links: tuple[str, ...] = ()  # ids de las notas enlazadas que existen
    unresolved: tuple[str, ...] = ()  # destinos de enlaces que no existen (lagunas)


@dataclass
class Vault:
    root: Path
    notes: dict[str, Note] = field(default_factory=dict)

    def to_graph(self) -> VaultGraph:
        """Grafo con el formato de contracts/vault_graph.schema.json."""
        nodes = [
            VaultNode(id=n.id, title=n.title, path=n.path, tags=list(n.tags))
            for n in sorted(self.notes.values(), key=lambda n: n.id)
        ]
        links = [
            VaultLink(source=n.id, target=target)
            for n in sorted(self.notes.values(), key=lambda n: n.id)
            for target in n.links
        ]
        return VaultGraph(nodes=nodes, links=links)

    def unresolved_links(self) -> dict[str, list[str]]:
        """Concepto sin nota → ids de las notas que lo mencionan. Lo usa el Explorador."""
        gaps: dict[str, list[str]] = {}
        for note in sorted(self.notes.values(), key=lambda n: n.id):
            for target in note.unresolved:
                gaps.setdefault(target, []).append(note.id)
        return gaps

    def orphans(self) -> list[str]:
        """Notas sin enlaces de entrada ni de salida."""
        linked = {target for note in self.notes.values() for target in note.links}
        return sorted(n.id for n in self.notes.values() if not n.links and n.id not in linked)


def parse_vault(root: Path, extra: dict[str, str] | None = None) -> Vault:
    """Lee la bóveda. `extra` añade notas en memoria ({ruta relativa .md: texto}) como si
    existieran en disco: en la URL pública son las notas que ha aprobado cada visitante."""
    root = Path(root)
    if not root.is_dir():
        raise VaultNotFoundError(f"La bóveda no existe o no es una carpeta: {root}")
    real_root = root.resolve()

    # 1.ª pasada: leer todas las notas. Hace falta conocerlas todas antes de
    # resolver enlaces, porque [[x]] puede apuntar a una nota que aún no hemos leído.
    files: list[tuple[PurePosixPath, str]] = []
    for file in sorted(root.rglob("*.md")):
        relative = file.relative_to(root)
        # Carpetas ocultas (.obsidian, .trash, .git): configuración, no notas.
        if any(part.startswith(".") for part in relative.parts):
            continue
        # Un enlace simbólico podría apuntar fuera de la bóveda: no lo seguimos.
        if not file.resolve().is_relative_to(real_root):
            continue
        files.append(
            (PurePosixPath(relative.as_posix()), file.read_text(encoding="utf-8", errors="replace"))
        )
    on_disk = {str(rel) for rel, _ in files}
    for rel, text in (extra or {}).items():
        if rel not in on_disk:  # lo que ya está en disco manda
            files.append((PurePosixPath(rel), text))

    raw: dict[str, tuple[Note, list[str]]] = {}
    for rel_posix, text in files:
        frontmatter, body = split_frontmatter(text)
        visible = strip_code(body)

        note = Note(
            id=str(rel_posix.with_suffix("")),
            title=rel_posix.stem,
            path=str(rel_posix),
            # Se quitan los wikilinks antes de buscar etiquetas: si no, el '#'
            # de [[nota#Sección]] o [[#Encabezado]] se leería como una etiqueta.
            tags=tuple(
                dedupe(frontmatter_tags(frontmatter) + inline_tags(WIKILINK_RE.sub("", visible)))
            ),
            content=text,
        )
        targets = [m.group(1).strip() for m in WIKILINK_RE.finditer(visible)]
        raw[note.id] = (note, targets)

    # 2.ª pasada: resolver cada destino contra el índice de notas.
    resolver = LinkResolver(list(raw))
    vault = Vault(root=root)
    for note_id, (note, targets) in raw.items():
        links, unresolved = [], []
        for target in targets:
            if not target or is_attachment(target):
                continue  # [[#Encabezado]] de la propia nota, o un adjunto
            resolved = resolver.resolve(target)
            if resolved is None:
                unresolved.append(target)
            elif resolved != note_id:  # un enlace a sí misma no aporta al grafo
                links.append(resolved)
        vault.notes[note_id] = replace(
            note, links=tuple(dedupe(links)), unresolved=tuple(dedupe(unresolved))
        )
    return vault


class LinkResolver:
    """Resuelve el texto de un [[enlace]] al id de una nota, como Obsidian."""

    def __init__(self, ids: list[str]):
        self._by_id = {i.lower(): i for i in ids}
        # Varias notas pueden llamarse igual en carpetas distintas: Obsidian
        # elige la de ruta más corta; desempatamos alfabéticamente para ser deterministas.
        self._by_stem: dict[str, list[str]] = {}
        for i in sorted(ids, key=lambda i: (i.count("/"), i)):
            self._by_stem.setdefault(PurePosixPath(i).name.lower(), []).append(i)

    def resolve(self, target: str) -> str | None:
        key = target.replace("\\", "/").strip("/").lower().removesuffix(".md")
        if "/" in key:
            if key in self._by_id:
                return self._by_id[key]
            # [[sub/nota]] también vale para 'carpeta/sub/nota'
            matches = sorted(
                (i for k, i in self._by_id.items() if k.endswith("/" + key)),
                key=lambda i: (i.count("/"), i),
            )
            return matches[0] if matches else None
        candidates = self._by_stem.get(key)
        return candidates[0] if candidates else None


def split_frontmatter(text: str) -> tuple[str, str]:
    """Separa la cabecera YAML (entre '---') del cuerpo de la nota."""
    if not text.startswith("---"):
        return "", text
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "".join(lines[1:i]), "".join(lines[i + 1 :])
    return "", text  # cabecera sin cerrar: se trata como texto normal


def frontmatter_tags(frontmatter: str) -> list[str]:
    """Lee `tags` del YAML sin depender de una librería de YAML.

    Soporta las tres formas habituales en Obsidian:
    `tags: [a, b]`, `tags: a, b` y la lista con guiones en líneas siguientes.
    """
    lines = frontmatter.splitlines()
    for i, line in enumerate(lines):
        match = re.match(r"^(tags|tag)\s*:\s*(.*)$", line.strip())
        if not match:
            continue
        value = match.group(2).strip()
        if value:
            items = value.strip("[]").split(",")
        else:
            items = []
            for following in lines[i + 1 :]:
                item = re.match(r"^\s*-\s*(.+)$", following)
                if not item:
                    break
                items.append(item.group(1))
        return [normalize_tag(t) for t in items if normalize_tag(t)]
    return []


def inline_tags(text: str) -> list[str]:
    # Obsidian exige al menos un carácter no numérico: '#2024' no es una etiqueta.
    return [normalize_tag(t) for t in INLINE_TAG_RE.findall(text) if not t.isdigit()]


def normalize_tag(tag: str) -> str:
    # Las etiquetas no distinguen mayúsculas en Obsidian: se guardan en minúscula.
    return tag.strip().strip("'\"").lstrip("#").lower()


def strip_code(text: str) -> str:
    """Quita bloques de código y código en línea: lo que hay dentro no son enlaces ni etiquetas."""
    return INLINE_CODE_RE.sub("", FENCED_CODE_RE.sub("", text))


def is_attachment(target: str) -> bool:
    return PurePosixPath(target.lower()).suffix in ATTACHMENT_EXTENSIONS


def dedupe(items: list[str]) -> list[str]:
    """Quita duplicados conservando el orden de aparición."""
    return list(dict.fromkeys(items))
