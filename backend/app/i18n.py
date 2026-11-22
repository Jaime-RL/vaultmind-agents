"""Idiomas de VaultMind: español, inglés, francés, alemán y portugués.

Dos idiomas distintos en cada investigación:
- **contenido** (`language`): en qué se escriben las notas y las respuestas. Con «auto» se
  detecta del tema o de la pregunta, sin llamar al LLM.
- **interfaz** (`ui_language`): en qué se escriben los mensajes de los agentes del panel.

Los prompts siguen en español (el modelo los entiende igual); solo se les añade una
instrucción con el idioma de salida.
"""

import re
import unicodedata

from app.contracts import ContentLanguage, Language

LANGUAGES: tuple[Language, ...] = ("es", "en", "fr", "de", "pt")

# Nombre del idioma en inglés: es como mejor siguen los modelos la instrucción.
LANGUAGE_NAMES: dict[Language, str] = {
    "es": "Spanish",
    "en": "English",
    "fr": "French",
    "de": "German",
    "pt": "Portuguese",
}

# Palabras muy frecuentes y casi exclusivas de cada idioma (sin tildes, en minúscula).
# Bastan para un tema o una pregunta corta; los términos técnicos no cuentan.
# fmt: off
_MARKERS: dict[Language, set[str]] = {
    "es": set("el la los las que de del para por con una como es son cual cuales donde cuando sobre entre mi mis tu se lo hay esta este estos muy tambien pero porque".split()),  # noqa: SIM905
    "en": set("the of and to is are what how why which with for in on does do can my your this that these between about from it be".split()),  # noqa: SIM905
    "fr": set("le la les des du est sont que qui quoi comment pourquoi avec pour dans une un sur entre ce cette ces mon ma mes et au aux".split()),  # noqa: SIM905
    "de": set("der die das und ist sind was wie warum welche mit fur ein eine im zum zur uber zwischen ich mein meine nicht auch den dem des".split()),  # noqa: SIM905
    "pt": set("o a os as que de do da dos das para por com uma um como e sao qual quais onde quando sobre entre meu minha voce isso esta este nao".split()),  # noqa: SIM905
}
# fmt: on
# Letras que delatan un idioma aunque no haya palabras frecuentes.
_LETTERS: dict[Language, str] = {"es": "ñ¿¡", "de": "äöüß", "pt": "ãõç", "fr": "èêàùœç"}


def _words(text: str) -> list[str]:
    plain = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    return re.findall(r"[a-z]+", plain)


def detect_language(text: str, fallback: Language = "es") -> Language:
    """Idioma más probable de un texto corto. Si no hay pistas (p. ej. «multi-token
    prediction», solo términos técnicos), devuelve `fallback` (el idioma de la interfaz)."""
    words = _words(text)
    scores = {lang: sum(w in markers for w in words) for lang, markers in _MARKERS.items()}
    lower = text.lower()
    for lang, letters in _LETTERS.items():
        scores[lang] += 2 * sum(lower.count(c) for c in letters)
    best = max(scores.values())
    if best == 0:
        return fallback
    winners = [lang for lang in LANGUAGES if scores[lang] == best]
    return fallback if fallback in winners else winners[0]


def resolve_language(requested: ContentLanguage, text: str, ui: Language = "es") -> Language:
    return detect_language(text, fallback=ui) if requested == "auto" else requested


def language_instruction(lang: Language) -> str:
    """Línea que se añade a un prompt para fijar el idioma de salida."""
    return (
        f"\n\nOUTPUT LANGUAGE: write ALL the text of your answer in {LANGUAGE_NAMES[lang]}, "
        "even if the instructions above are in Spanish. Keep [[wikilink]] titles exactly as given."
    )


_T: dict[str, dict[Language, str]] = {
    # --- Mensajes de los agentes (idioma de la interfaz) ---
    "explorer.reading": {
        "es": "Leo la bóveda: {n} notas. Busco conceptos enlazados que no tienen nota.",
        "en": "Reading the vault: {n} notes. Looking for linked concepts without a note.",
        "fr": "Je lis le coffre : {n} notes. Je cherche les concepts liés sans note.",
        "de": "Ich lese den Vault: {n} Notizen. Ich suche verlinkte Konzepte ohne Notiz.",
        "pt": "Leio o cofre: {n} notas. Procuro conceitos ligados que não têm nota.",
    },
    "explorer.gaps": {
        "es": "{n} lagunas: {names}",
        "en": "{n} gaps: {names}",
        "fr": "{n} lacunes : {names}",
        "de": "{n} Lücken: {names}",
        "pt": "{n} lacunas: {names}",
    },
    "explorer.no_gaps": {
        "es": "ninguna laguna",
        "en": "no gaps",
        "fr": "aucune lacune",
        "de": "keine Lücken",
        "pt": "nenhuma lacuna",
    },
    "explorer.investigating": {
        "es": "Investigo: {names}.",
        "en": "Researching: {names}.",
        "fr": "Je recherche : {names}.",
        "de": "Ich recherchiere: {names}.",
        "pt": "Pesquiso: {names}.",
    },
    "explorer.already": {
        "es": "Ya tienes una nota sobre «{title}».",
        "en": "You already have a note on “{title}”.",
        "fr": "Vous avez déjà une note sur « {title} ».",
        "de": "Du hast bereits eine Notiz zu „{title}“.",
        "pt": "Já tens uma nota sobre «{title}».",
    },
    "explorer.nothing": {
        "es": "Ya tienes una nota sobre «{title}» y no hay lagunas relacionadas.",
        "en": "You already have a note on “{title}” and there are no related gaps.",
        "fr": "Vous avez déjà une note sur « {title} » et aucune lacune liée.",
        "de": "Du hast bereits eine Notiz zu „{title}“ und es gibt keine verwandten Lücken.",
        "pt": "Já tens uma nota sobre «{title}» e não há lacunas relacionadas.",
    },
    "researcher.start": {
        "es": "Investigo «{gap}» para el tema «{topic}».",
        "en": "Researching “{gap}” for the topic “{topic}”.",
        "fr": "Je recherche « {gap} » pour le sujet « {topic} ».",
        "de": "Ich recherchiere „{gap}“ für das Thema „{topic}“.",
        "pt": "Pesquiso «{gap}» para o tema «{topic}».",
    },
    "researcher.done": {
        "es": "«{gap}»: resumen listo con {n} fuentes verificadas.",
        "en": "“{gap}”: summary ready with {n} verified sources.",
        "fr": "« {gap} » : résumé prêt avec {n} sources vérifiées.",
        "de": "„{gap}“: Zusammenfassung fertig, {n} geprüfte Quellen.",
        "pt": "«{gap}»: resumo pronto com {n} fontes verificadas.",
    },
    "researcher.failed": {
        "es": "No pude investigar «{gap}»: {error}",
        "en": "I could not research “{gap}”: {error}",
        "fr": "Impossible de rechercher « {gap} » : {error}",
        "de": "„{gap}“ konnte nicht recherchiert werden: {error}",
        "pt": "Não consegui pesquisar «{gap}»: {error}",
    },
    "researcher.dropped": {
        "es": "Descarto «{gap}»: no encontré fuentes que la relacionen con el tema.",
        "en": "Dropping “{gap}”: no sources link it to the topic.",
        "fr": "J’écarte « {gap} » : aucune source ne la relie au sujet.",
        "de": "Ich verwerfe „{gap}“: keine Quelle verbindet sie mit dem Thema.",
        "pt": "Descarto «{gap}»: não encontrei fontes que a liguem ao tema.",
    },
    "writer.start": {
        "es": "Redacto la nota «{title}».",
        "en": "Writing the note “{title}”.",
        "fr": "Je rédige la note « {title} ».",
        "de": "Ich schreibe die Notiz „{title}“.",
        "pt": "Escrevo a nota «{title}».",
    },
    "writer.failed": {
        "es": "No pude redactar «{title}»: {error}",
        "en": "I could not write “{title}”: {error}",
        "fr": "Impossible de rédiger « {title} » : {error}",
        "de": "„{title}“ konnte nicht geschrieben werden: {error}",
        "pt": "Não consegui escrever «{title}»: {error}",
    },
    "writer.revising": {
        "es": "El Revisor solo respalda {supported} de {claims} afirmaciones: corrijo «{title}».",
        "en": "The Reviewer only backs {supported} of {claims} claims: fixing “{title}”.",
        "fr": "Le Réviseur ne valide que {supported} affirmations sur {claims} : je corrige « {title} ».",
        "de": "Der Prüfer stützt nur {supported} von {claims} Aussagen: ich korrigiere „{title}“.",
        "pt": "O Revisor só confirma {supported} de {claims} afirmações: corrijo «{title}».",
    },
    "writer.fix_failed": {
        "es": "No pude corregir «{title}»: {error}",
        "en": "I could not fix “{title}”: {error}",
        "fr": "Impossible de corriger « {title} » : {error}",
        "de": "„{title}“ konnte nicht korrigiert werden: {error}",
        "pt": "Não consegui corrigir «{title}»: {error}",
    },
    "reviewer.result": {
        "es": "{supported} de {claims} afirmaciones con respaldo",
        "en": "{supported} of {claims} claims backed by sources",
        "fr": "{supported} affirmations sur {claims} étayées",
        "de": "{supported} von {claims} Aussagen belegt",
        "pt": "{supported} de {claims} afirmações com respaldo",
    },
    "reviewer.issues": {
        "es": "En «{title}» revisa antes de aprobar: {issues}",
        "en": "In “{title}”, check before approving: {issues}",
        "fr": "Dans « {title} », vérifiez avant d’approuver : {issues}",
        "de": "In „{title}“ vor dem Freigeben prüfen: {issues}",
        "pt": "Em «{title}», revê antes de aprovar: {issues}",
    },
    "reviewer.failed": {
        "es": "No pude revisar «{title}»: {error}",
        "en": "I could not review “{title}”: {error}",
        "fr": "Impossible de réviser « {title} » : {error}",
        "de": "„{title}“ konnte nicht geprüft werden: {error}",
        "pt": "Não consegui rever «{title}»: {error}",
    },
    "tool.arxiv": {
        "es": "{n} resultados de arXiv",
        "en": "{n} arXiv results",
        "fr": "{n} résultats arXiv",
        "de": "{n} arXiv-Treffer",
        "pt": "{n} resultados do arXiv",
    },
    "tool.semantic_scholar": {
        "es": "{n} resultados de Semantic Scholar",
        "en": "{n} Semantic Scholar results",
        "fr": "{n} résultats Semantic Scholar",
        "de": "{n} Semantic-Scholar-Treffer",
        "pt": "{n} resultados do Semantic Scholar",
    },
    "tool.repeated": {
        "es": "búsqueda repetida",
        "en": "repeated search",
        "fr": "recherche répétée",
        "de": "wiederholte Suche",
        "pt": "pesquisa repetida",
    },
    "run.stopped": {
        "es": "La investigación se detuvo: {error}",
        "en": "The research stopped: {error}",
        "fr": "La recherche s’est arrêtée : {error}",
        "de": "Die Recherche wurde abgebrochen: {error}",
        "pt": "A pesquisa parou: {error}",
    },
    # --- Textos que van dentro de la nota (idioma del contenido) ---
    "note.sources": {
        "es": "Fuentes",
        "en": "Sources",
        "fr": "Sources",
        "de": "Quellen",
        "pt": "Fontes",
    },
    "note.no_sources": {
        "es": "Sin fuentes verificadas: revisa esta nota con cuidado.",
        "en": "No verified sources: check this note carefully.",
        "fr": "Aucune source vérifiée : relisez cette note avec soin.",
        "de": "Keine geprüften Quellen: prüfe diese Notiz sorgfältig.",
        "pt": "Sem fontes verificadas: revê esta nota com cuidado.",
    },
    "note.warning": {
        "es": "Nota sin fuentes verificadas: compruébala antes de usarla.",
        "en": "Note without verified sources: check it before using it.",
        "fr": "Note sans sources vérifiées : vérifiez-la avant de l’utiliser.",
        "de": "Notiz ohne geprüfte Quellen: vor der Verwendung prüfen.",
        "pt": "Nota sem fontes verificadas: confirma-a antes de a usar.",
    },
    "note.mentioned": {
        "es": "Mencionada en: {notes}. Propuesta por VaultMind.",
        "en": "Mentioned in: {notes}. Proposed by VaultMind.",
        "fr": "Mentionnée dans : {notes}. Proposée par VaultMind.",
        "de": "Erwähnt in: {notes}. Vorgeschlagen von VaultMind.",
        "pt": "Mencionada em: {notes}. Proposta pelo VaultMind.",
    },
    # --- Pregunta a tu bóveda (idioma de la respuesta) ---
    "ask.no_notes": {
        "es": "No encuentro nada sobre eso en tu bóveda. Puedes investigarlo con el buscador de "
        "arriba y aprobar las notas que te convenzan.",
        "en": "I can't find anything about that in your vault. You can research it with the "
        "search box above and approve the notes you like.",
        "fr": "Je ne trouve rien à ce sujet dans votre coffre. Vous pouvez le rechercher avec la "
        "barre ci-dessus et approuver les notes qui vous conviennent.",
        "de": "Dazu finde ich nichts in deinem Vault. Du kannst es oben recherchieren lassen und "
        "die passenden Notizen freigeben.",
        "pt": "Não encontro nada sobre isso no teu cofre. Podes pesquisá-lo com a caixa acima e "
        "aprovar as notas que te convençam.",
    },
    "ask.no_llm": {
        "es": "Ahora no puedo redactar una respuesta, pero estas notas tratan el tema: {links}.",
        "en": "I can't write an answer right now, but these notes cover the topic: {links}.",
        "fr": "Je ne peux pas rédiger de réponse pour l’instant, mais ces notes traitent du sujet : {links}.",
        "de": "Ich kann gerade keine Antwort schreiben, aber diese Notizen behandeln das Thema: {links}.",
        "pt": "Agora não consigo escrever uma resposta, mas estas notas tratam o tema: {links}.",
    },
}

# Cabeceras que añade el código a una nota, en todos los idiomas: para separar el cuerpo.
NOTE_SECTION_MARKERS = sorted(
    {f"\n## {v}\n" for v in _T["note.sources"].values()}
    | {"\n*" + v.split(":")[0] + ":" for v in _T["note.mentioned"].values()}
)


def tr(lang: Language, key: str, **params) -> str:
    """Texto traducido. Si faltara la traducción, se usa el español."""
    texts = _T[key]
    return texts.get(lang, texts["es"]).format(**params)
