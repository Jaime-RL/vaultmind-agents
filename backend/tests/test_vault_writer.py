import os

import pytest

from vault import parse_vault
from vault.writer import UnsafeWriteError, safe_note_name, write_copilot_note


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("LoRA", "LoRA"),
        ("Routing de modelos", "Routing de modelos"),
        ("../../etc/passwd", "etc passwd"),
        ("/absoluta/ruta", "absoluta ruta"),
        ('a:b*c?d"e<f>g|h', "a b c d e f g h"),
        ("[[Enlace]] #tag ^bloque", "Enlace tag bloque"),
        ("  ..oculta..  ", "oculta"),
        ("...", "Nota"),
        ("", "Nota"),
        ("CON", "CON_"),
        ("x" * 300, "x" * 100),
    ],
)
def test_safe_note_name(title, expected):
    assert safe_note_name(title) == expected


def test_writes_inside_copilot_folder(tmp_path):
    path = write_copilot_note(tmp_path, "LoRA", "# LoRA\n\nTexto")

    assert path == "_copilot/LoRA.md"
    assert (tmp_path / "_copilot" / "LoRA.md").read_text(encoding="utf-8") == "# LoRA\n\nTexto\n"


def test_never_overwrites_existing_notes(tmp_path):
    first = write_copilot_note(tmp_path, "LoRA", "primera")
    second = write_copilot_note(tmp_path, "LoRA", "segunda")

    assert (first, second) == ("_copilot/LoRA.md", "_copilot/LoRA (2).md")
    assert (tmp_path / first).read_text(encoding="utf-8") == "primera\n"


def test_path_traversal_titles_stay_inside(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()

    path = write_copilot_note(vault, "../../fuera", "x")

    assert path.startswith("_copilot/")
    assert not (tmp_path / "fuera.md").exists()
    assert list(tmp_path.iterdir()) == [vault]


@pytest.mark.skipif(os.name == "nt", reason="los enlaces simbólicos requieren permisos en Windows")
def test_refuses_copilot_symlink_pointing_outside(tmp_path):
    vault = tmp_path / "vault"
    outside = tmp_path / "fuera"
    vault.mkdir()
    outside.mkdir()
    (vault / "_copilot").symlink_to(outside, target_is_directory=True)

    with pytest.raises(UnsafeWriteError):
        write_copilot_note(vault, "LoRA", "x")
    assert list(outside.iterdir()) == []


def test_approved_note_fills_the_gap_in_the_graph(tmp_path):
    (tmp_path / "SLM.md").write_text("Ver [[LoRA]].", encoding="utf-8")
    assert "LoRA" in parse_vault(tmp_path).unresolved_links()

    write_copilot_note(tmp_path, "LoRA", "# LoRA\n\nVer [[SLM]].")

    vault = parse_vault(tmp_path)
    assert vault.unresolved_links() == {}
    assert vault.notes["SLM"].links == ("_copilot/LoRA",)
