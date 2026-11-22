"""Búsqueda léxica BM25 sobre las notas de la bóveda, sin dependencias.

Para «Pregunta a tu bóveda» basta con encontrar las 5 notas más relevantes y dárselas al
modelo. BM25 es el estándar de la búsqueda léxica: premia las palabras raras de la
pregunta que aparecen en la nota y no premia de más una palabra repetida muchas veces.
El título cuenta triple: si una nota se llama «LoRA», es la nota de LoRA.

Limitación conocida: no entiende sinónimos («ajuste fino» ≠ «fine-tuning»). El siguiente
paso sería añadir embeddings, pero así funciona sin modelos ni red.
"""

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

from app.i18n import _MARKERS
from vault.parser import Vault

K1, B = 1.5, 0.75  # parámetros habituales de BM25
TITLE_WEIGHT = 3

# fmt: off
STOPWORDS = frozenset({
    "a", "al", "algo", "como", "con", "cual", "cuales", "cuando", "de", "del", "el", "ella",
    "en", "entre", "es", "esa", "ese", "eso", "esta", "este", "esto", "hay", "la", "las", "le",
    "lo", "los", "mas", "me", "mi", "mis", "muy", "no", "o", "para", "pero", "por", "que",
    "qué", "se", "ser", "si", "sin", "sobre", "su", "sus", "te", "tu", "un", "una", "uno",
    "unos", "y", "ya", "yo", "the", "of", "and", "or", "to", "in", "on", "for", "is", "are",
    "what", "how", "why", "which", "with", "by", "an", "be", "it", "this", "that",
})
# fmt: on


# Palabras vacías también en inglés, francés, alemán y portugués (las de la detección de
# idioma), más verbos de pregunta frecuentes que no aportan nada a la búsqueda.
ALL_STOPWORDS = (
    STOPWORDS
    | set().union(*_MARKERS.values())
    | {
        "funciona",
        "function",
        "works",
        "work",
        "fonctionne",
        "funktioniert",
        "explain",
        "explica",
        "explique",
        "erklare",
        "sei",
        "sais",
        "know",
        "weiss",
    }
)
STEM_LENGTH = 4


@dataclass(frozen=True)
class Hit:
    note_id: str
    title: str
    score: float


def tokenize(text: str) -> list[str]:
    """Minúsculas, sin tildes ni signos, sin palabras vacías. «Función» y «funcion» coinciden."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return [w for w in re.findall(r"[a-z0-9]+", text) if w not in ALL_STOPWORDS and len(w) > 1]


def stem(word: str) -> str:
    """Raíz muy simple: las 4 primeras letras. Une palabras emparentadas entre idiomas
    («routing», «routage» → «rout»; «modelos», «modèles», «Modelle», «models» → «mode»)."""
    return word[:STEM_LENGTH] if len(word) > STEM_LENGTH else word


def search(vault: Vault, query: str, k: int = 5) -> list[Hit]:
    """Las k notas más relevantes. Primero por palabras exactas; si no hay ninguna (p. ej.
    una pregunta en francés sobre notas escritas en español), por raíces."""
    hits = _bm25(vault, query, k, lambda words: words)
    if hits:
        return hits
    return _bm25(vault, query, k, lambda words: [stem(w) for w in words])


def _bm25(vault: Vault, query: str, k: int, normalize) -> list[Hit]:
    terms = set(normalize(tokenize(query)))
    if not terms or not vault.notes:
        return []

    docs = {
        note_id: Counter(normalize(tokenize(note.title) * TITLE_WEIGHT + tokenize(note.content)))
        for note_id, note in vault.notes.items()
    }
    lengths = {note_id: sum(tf.values()) for note_id, tf in docs.items()}
    avg_len = sum(lengths.values()) / len(lengths) or 1.0
    n = len(docs)

    hits = []
    for note_id, tf in docs.items():
        score = 0.0
        for term in terms:
            freq = tf.get(term, 0)
            if not freq:
                continue
            df = sum(1 for other in docs.values() if term in other)
            idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
            norm = freq + K1 * (1 - B + B * lengths[note_id] / avg_len)
            score += idf * freq * (K1 + 1) / norm
        if score > 0:
            hits.append(Hit(note_id, vault.notes[note_id].title, score))
    return sorted(hits, key=lambda h: (-h.score, h.note_id))[:k]
