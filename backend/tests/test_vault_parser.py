"""Tests del parser de la bóveda con una bóveda mínima llena de casos límite.

La bóveda se crea en tmp_path para que cada caso límite quede escrito junto
a la aserción que lo comprueba.
"""

import os
from pathlib import Path

import pytest

from vault import VaultNotFoundError, parse_vault

INDEX = """---
tags:
  - Proyecto
  - "indice"
---
# Índice

Enlaces normales: [[Alpha]] y repetido con alias y otra capitalización [[alpha|la primera]].
Con sección [[beta#Una sección]], con bloque [[beta#^abc123]] y embebido ![[gamma]].
Por ruta [[sub/delta]] y por ruta parcial [[x/epsilon]].
Roto: [[Nota que no existe]]. Adjunto: [[diagrama.png]].
Propio encabezado: [[#Índice]]. A sí misma: [[index]].

Etiquetas en línea #Tag-Uno y #area/clima, pero no #2024 ni https://example.com/#ancla.

```python
# esto no es un encabezado ni una etiqueta: #codigo
enlace_en_codigo = "[[Dentro de código]]"
```

Código en línea `[[En línea]]` tampoco cuenta.
"""

FILES = {
    "index.md": INDEX,
    "Alpha.md": "---\ntags: [a, b]\n---\nEnlaza a [[Beta]] y a [[delta]].\n",
    "beta.md": "---\ntags: solo\n---\nSin enlaces.\n",
    "folder/gamma.md": "Nota en carpeta.\n",
    "sub/delta.md": "Delta corta.\n",
    "other/sub/delta.md": "Delta con el mismo nombre pero ruta más larga.\n",
    "deep/x/epsilon.md": "Épsilon.\n",
    "lonely.md": "Nota huérfana, sin enlaces de entrada ni de salida.\n",
    ".obsidian/workspace.md": "Configuración de Obsidian: [[Alpha]]\n",
    "notas.txt": "No es Markdown: [[Alpha]]\n",
}


@pytest.fixture
def vault_dir(tmp_path: Path) -> Path:
    for rel, text in FILES.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


@pytest.fixture
def vault(vault_dir):
    return parse_vault(vault_dir)


def test_reads_only_visible_markdown_notes(vault):
    assert set(vault.notes) == {
        "index",
        "Alpha",
        "beta",
        "folder/gamma",
        "sub/delta",
        "other/sub/delta",
        "deep/x/epsilon",
        "lonely",
    }


def test_note_metadata(vault):
    note = vault.notes["folder/gamma"]
    assert (note.title, note.path) == ("gamma", "folder/gamma.md")


def test_resolves_all_wikilink_forms_without_duplicates(vault):
    # alias, sección, bloque y embebido apuntan a la misma nota; se cuenta una vez.
    assert vault.notes["index"].links == (
        "Alpha",
        "beta",
        "folder/gamma",
        "sub/delta",
        "deep/x/epsilon",
    )


def test_ambiguous_name_resolves_to_shortest_path(vault):
    assert "sub/delta" in vault.notes["Alpha"].links
    assert "other/sub/delta" not in vault.notes["Alpha"].links


def test_resolution_is_case_insensitive(vault):
    assert vault.notes["Alpha"].links[0] == "beta"  # [[Beta]] → beta.md


def test_broken_links_are_kept_as_gaps(vault):
    assert vault.notes["index"].unresolved == ("Nota que no existe",)
    assert vault.unresolved_links() == {"Nota que no existe": ["index"]}


def test_ignores_links_in_code_attachments_and_self(vault):
    index = vault.notes["index"]
    everything = index.links + index.unresolved
    for ignored in ("Dentro de código", "En línea", "diagrama.png", "index"):
        assert ignored not in everything


def test_tags_from_frontmatter_and_body(vault):
    assert vault.notes["index"].tags == ("proyecto", "indice", "tag-uno", "area/clima")
    assert vault.notes["Alpha"].tags == ("a", "b")
    assert vault.notes["beta"].tags == ("solo",)


def test_orphans(vault):
    # other/sub/delta también queda huérfana: [[delta]] resuelve a sub/delta.
    assert vault.orphans() == ["lonely", "other/sub/delta"]


def test_section_links_are_not_tags(vault):
    assert "índice" not in vault.notes["index"].tags
    assert "una" not in vault.notes["index"].tags


def test_graph_matches_contract_shape(vault):
    graph = vault.to_graph()
    ids = {node.id for node in graph.nodes}

    assert len(graph.nodes) == 8
    # Todo enlace del grafo une dos nodos que existen.
    assert all(link.source in ids and link.target in ids for link in graph.links)
    assert {"source": "Alpha", "target": "beta"} in [link.model_dump() for link in graph.links]


def test_missing_vault_raises(tmp_path):
    with pytest.raises(VaultNotFoundError):
        parse_vault(tmp_path / "no-existe")


@pytest.mark.skipif(os.name == "nt", reason="los enlaces simbólicos requieren permisos en Windows")
def test_does_not_follow_symlinks_outside_the_vault(tmp_path):
    outside = tmp_path / "fuera"
    outside.mkdir()
    (outside / "secreto.md").write_text("No debería leerse.\n", encoding="utf-8")
    inside = tmp_path / "boveda"
    inside.mkdir()
    (inside / "nota.md").write_text("Hola\n", encoding="utf-8")
    (inside / "enlace.md").symlink_to(outside / "secreto.md")

    assert set(parse_vault(inside).notes) == {"nota"}
