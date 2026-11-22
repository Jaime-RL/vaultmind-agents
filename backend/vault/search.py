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


@dataclass(frozen=True)
class Hit:
    note_id: str
    title: str
    score: float


def tokenize(text: str) -> list[str]:
    """Minúsculas, sin tildes ni signos, sin palabras vacías. «Función» y «funcion» coinciden."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return [w for w in re.findall(r"[a-z0-9]+", text) if w not in STOPWORDS and len(w) > 1]


def search(vault: Vault, query: str, k: int = 5) -> list[Hit]:
    terms = set(tokenize(query))
    if not terms or not vault.notes:
        return []

    docs = {
        note_id: Counter(tokenize(note.title) * TITLE_WEIGHT + tokenize(note.content))
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
