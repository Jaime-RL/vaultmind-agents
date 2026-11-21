"""Casos de evaluación por tipo de tarea, con los MISMOS prompts que producción.

Cada caso define los mensajes que recibe el modelo y una función `check` que
decide si la respuesta es aceptable. Las comprobaciones son automáticas y
deliberadamente objetivas (formato, que no se inventen datos, que detecten lo
que deben detectar): no miden el estilo de redacción.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field

from agents.prompts import EXPLORER, RESEARCHER, REVIEWER, WRITER
from llm import LLMError, LLMResponse
from llm.base import Message, ToolSpec
from router.validators import strip_code_fence
from vault.parser import WIKILINK_RE

Check = Callable[[LLMResponse], tuple[bool, str]]

SEARCH_TOOL: ToolSpec = {
    "type": "function",
    "function": {
        "name": "search_arxiv",
        "description": "Busca papers científicos en arXiv. Úsala con consultas cortas en inglés.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
}


@dataclass(frozen=True)
class Case:
    id: str
    task: str  # mismo nombre de tarea que usa SmartRoute
    messages: list[Message]
    check: Check
    tools: list[ToolSpec] | None = field(default=None)


def parse_json(response: LLMResponse) -> dict:
    data = json.loads(strip_code_fence(response.content or ""))
    if not isinstance(data, dict):
        raise ValueError("no es un objeto JSON")
    return data


# --- find_gaps (Explorador) ------------------------------------------------------


def explorer_case(case_id: str, topic: str, gaps: list[str], relevant: set[str]) -> Case:
    """`relevant` vacío = ninguna laguna tiene relación: lo correcto es no elegir ninguna."""

    def check(response: LLMResponse) -> tuple[bool, str]:
        try:
            data = parse_json(response)
        except (ValueError, json.JSONDecodeError):
            return False, "JSON inválido"
        title, selected = data.get("topic_note"), data.get("selected")
        if not isinstance(title, str) or not title.strip():
            return False, "sin título para la nota del tema"
        if not isinstance(selected, list):
            return False, "selected no es una lista"
        if len(selected) > 2:
            return False, f"eligió {len(selected)} (máximo 2)"
        invented = [s for s in selected if s not in gaps]
        if invented:
            return False, f"inventó o reescribió: {invented}"
        unrelated = [s for s in selected if s not in relevant]
        if unrelated:
            return False, f"eligió lagunas sin relación: {unrelated}"
        if relevant and not selected:
            return False, "no eligió ninguna laguna relacionada"
        return True, f"«{title.strip()}» + {selected}"

    candidates = "\n".join(f"- {g}" for g in gaps)
    return Case(
        id=case_id,
        task="find_gaps",
        messages=[
            {"role": "system", "content": EXPLORER.format(max_related=2)},
            {"role": "user", "content": f"Tema: {topic}\n\nLagunas:\n{candidates}"},
        ],
        check=check,
    )


# --- summarize_paper (Investigador, paso final) ------------------------------------

PAPERS = [
    {
        "title": "A Study of Tool Use in Small Language Models",
        "url": "http://arxiv.org/abs/0000.00011v1",
        "summary": "Small models select the right tool most of the time but often produce "
        "malformed JSON arguments. Constrained decoding reduces these errors.",
    },
    {
        "title": "Cascading Language Models for Cost-Efficient Inference",
        "url": "http://arxiv.org/abs/0000.00012v1",
        "summary": "A cheap model answers first and a larger model is invoked only when a "
        "verifier rejects the answer, cutting cost with small quality loss.",
    },
]


def researcher_case(case_id: str, concept: str, papers: list[dict]) -> Case:
    urls = {p["url"] for p in papers}

    def check(response: LLMResponse) -> tuple[bool, str]:
        if response.tool_calls:
            # Pedir otra búsqueda es válido en el bucle ReAct si la llamada está bien formada.
            call = response.tool_calls[0]
            ok = call.name == "search_arxiv" and bool(str(call.arguments.get("query", "")).strip())
            return ok, "pidió otra búsqueda" if ok else "llamada a herramienta mal formada"
        try:
            data = parse_json(response)
        except (ValueError, json.JSONDecodeError):
            return False, "JSON inválido"
        if not str(data.get("summary", "")).strip():
            return False, "sin resumen"
        sources = data.get("sources")
        if not isinstance(sources, list):
            return False, "sources no es una lista"
        cited = {s.get("url") for s in sources if isinstance(s, dict)}
        if cited - urls:
            return False, f"fuentes inventadas: {sorted(cited - urls)}"
        if papers and not cited:
            return False, "no citó ninguna fuente disponible"
        return True, f"{len(cited)} fuentes válidas"

    return Case(
        id=case_id,
        task="summarize_paper",
        messages=[
            {"role": "system", "content": RESEARCHER},
            {
                "role": "user",
                "content": f"Tema del TFG: chatbot de clima con SLMs\n"
                f"Concepto a investigar: {concept}",
            },  # fmt: skip
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "search_arxiv",
                            "arguments": json.dumps({"query": concept}),
                        },
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": json.dumps(papers)},
        ],
        check=check,
        tools=[SEARCH_TOOL],
    )


# --- write_note (Redactor) ------------------------------------------------------

EXISTING_TITLES = ["SLM", "LLM", "Tool calling", "Fine-tuning", "Cuantización", "RAG"]


def writer_case(case_id: str, title: str, summary: str) -> Case:
    def check(response: LLMResponse) -> tuple[bool, str]:
        text = strip_code_fence(response.content or "").strip()
        if not text.startswith("#"):
            return False, "no empieza con encabezado"
        words = len(text.split())
        if not 100 <= words <= 450:
            return False, f"{words} palabras (esperado 150-300 aprox.)"
        links = [m.group(1).strip() for m in WIKILINK_RE.finditer(text)]
        invented = [link for link in links if link not in EXISTING_TITLES]
        if invented:
            return False, f"enlaces a notas que no existen: {invented}"
        if len(links) < 2:
            return False, f"solo {len(links)} enlaces"
        return True, f"{words} palabras, {len(set(links))} enlaces válidos"

    return Case(
        id=case_id,
        task="write_note",
        messages=[
            {"role": "system", "content": WRITER.replace("{title}", title)},
            {
                "role": "user",
                "content": f"Tema del TFG: chatbot de clima con SLMs\nConcepto: {title}\n\n"
                f"Resumen de la investigación:\n{summary}\n\nFuentes:\n- (ver resumen)\n\n"
                "Notas existentes:\n" + "\n".join(f"- {t}" for t in EXISTING_TITLES),
            },
        ],
        check=check,
    )


# --- verify_claims (Revisor) -------------------------------------------------------


def reviewer_case(case_id: str, summary: str, note: str, expect_issue: bool) -> Case:
    def check(response: LLMResponse) -> tuple[bool, str]:
        try:
            data = parse_json(response)
            claims, supported = int(data["claims"]), int(data["supported"])
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            return False, "JSON inválido o sin claims/supported"
        if not 0 <= supported <= claims:
            return False, f"cifras incoherentes ({supported}/{claims})"
        flagged = supported < claims or bool(data.get("issues"))
        if flagged != expect_issue:
            return False, "no detectó el problema" if expect_issue else "falso positivo"
        return True, f"{supported}/{claims} respaldadas"

    return Case(
        id=case_id,
        task="verify_claims",
        messages=[
            {"role": "system", "content": REVIEWER},
            {
                "role": "user",
                "content": f"Resumen de la investigación:\n{summary}\n\nNota:\n{note}",
            },
        ],
        check=check,
    )


LORA_SUMMARY = (
    "LoRA congela los pesos del modelo y entrena matrices de bajo rango añadidas a algunas "
    "capas. Reduce mucho los parámetros entrenables y la memoria necesaria para el ajuste."
)

CASES: list[Case] = [
    explorer_case(
        "explorer-tfg",
        "Function calling con modelos pequeños",
        ["LoRA", "Function calling en SLMs", "Reanálisis", "Llama", "Evaluación de agentes"],
        {"Function calling en SLMs", "Evaluación de agentes"},
    ),
    explorer_case(
        "explorer-clima",
        "Fuentes de datos climáticos históricos",
        ["Reanálisis", "LoRA", "Routing de modelos", "Qwen"],
        {"Reanálisis"},
    ),
    explorer_case(
        "explorer-coste",
        "Reducir el coste de inferencia",
        ["Routing de modelos", "Cuantización", "Reanálisis", "Patrón ReAct"],
        {"Routing de modelos", "Cuantización"},
    ),
    explorer_case(
        "explorer-una",
        "Ajuste fino eficiente",
        ["LoRA"],
        {"LoRA"},
    ),
    explorer_case(
        "explorer-sin-relacion",
        "Multi-token prediction",
        ["LoRA", "Reanálisis", "Qwen"],
        set(),
    ),
    researcher_case("researcher-two-papers", "Function calling en SLMs", PAPERS),
    researcher_case("researcher-one-paper", "Routing de modelos", PAPERS[1:]),
    researcher_case("researcher-cascade", "Cascadas de modelos", PAPERS),
    researcher_case("researcher-empty", "Tema sin resultados", []),
    writer_case("writer-lora", "LoRA", LORA_SUMMARY),
    writer_case(
        "writer-routing",
        "Routing de modelos",
        "Un router envía cada petición al modelo más barato capaz de resolverla y escala a "
        "un modelo grande si la respuesta no pasa una validación.",
    ),
    writer_case(
        "writer-function-calling",
        "Function calling en SLMs",
        "Los modelos pequeños eligen bien la herramienta pero suelen generar argumentos JSON "
        "mal formados; la decodificación restringida reduce esos errores.",
    ),
    reviewer_case(
        "reviewer-clean",
        LORA_SUMMARY,
        "# LoRA\n\nLoRA congela los pesos del modelo y entrena matrices de bajo rango. "
        "Así reduce los parámetros entrenables y la memoria del ajuste.",
        expect_issue=False,
    ),
    reviewer_case(
        "reviewer-invented-number",
        LORA_SUMMARY,
        "# LoRA\n\nLoRA entrena matrices de bajo rango. Reduce el coste exactamente un 97 % y "
        "fue inventado por Google en 2015.",
        expect_issue=True,
    ),
    reviewer_case(
        "reviewer-contradiction",
        LORA_SUMMARY,
        "# LoRA\n\nLoRA reentrena todos los pesos del modelo, por lo que necesita más memoria "
        "que el ajuste completo.",
        expect_issue=True,
    ),
    reviewer_case(
        "reviewer-partial",
        LORA_SUMMARY,
        "# LoRA\n\nLoRA congela los pesos y entrena matrices de bajo rango. Es la técnica más "
        "usada del mundo en 2026.",
        expect_issue=True,
    ),
]


def safe_check(case: Case, response: LLMResponse) -> tuple[bool, str]:
    """Un check que lanza una excepción cuenta como fallo, no rompe la evaluación."""
    try:
        return case.check(response)
    except (LLMError, ValueError, KeyError, TypeError) as exc:
        return False, f"error al comprobar: {exc}"
