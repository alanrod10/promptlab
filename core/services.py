import json
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .universal_engine import (
    compute_control_values,
    extract_semantic_roles,
    inspect_attached_payload,
    split_request_payload,
    synthesize_universal_directives,
)

ENGINE_VERSION = "v6.0"

KB_PATH = Path(__file__).resolve().parent / "rules" / "knowledge_base.json"


def _load_knowledge_base() -> Dict[str, Any]:
    with open(KB_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


KNOWLEDGE_BASE = _load_knowledge_base()

# Mapeo de categorías heredadas (v1-v3) a los 10 dominios especializados (v4.0-v6.0)
LEGACY_DOMAIN_ALIASES = {
    "Aprender y enseñar": "Estudio y academia",
    "Crear y comunicar": "Redacción y comunicación",
    "Trabajo y productividad": "Planificación y productividad",
    "Vida personal y organización": "Planificación y productividad",
    "Otro / No sé": "Otro / General",
    "Ninguna especificada": "",
}

PHASES = ["entender", "preparar", "ejecutar", "validar", "entregar"]

CORE_V5_ACTIONS = {
    "depurar_error",
    "generar_codigo",
    "analizar_datos",
    "comparar_evaluar",
    "resumir_sintetizar",
    "planificar_pasos",
    "redactar_contenido",
    "explicar_concepto",
}

UNIVERSAL_V6_ACTIONS = {
    "transformar_formato",
    "extraer_informacion",
    "clasificar_categorizar",
    "traducir_adaptar",
    "reescribir_mejorar",
    "auditar_criticar",
    "simular_practicar",
    "idear_alternativas",
    "calcular_modelar",
    "razonar_resolver",
    "decidir_recomendar",
    "diagnosticar_resolver",
    "consultar_dato",
}

TECHNIQUE_BLOCKS = {
    "Estándar": {
        "name": "Estructura Estándar",
        "block": "",
        "desc": "Organización por bloques con micro-directivas específicas.",
    },
    "Paso a Paso": {
        "name": "Razonamiento Paso a Paso",
        "block": (
            "# Método de Resolución (Paso a Paso)\n"
            "1. **Diagnóstico inicial:** Identifica los datos y restricciones clave antes de ejecutar.\n"
            "2. **Desarrollo secuencial:** Resuelve cada sub-tarea en orden lógico verificando resultados intermedios.\n"
            "3. **Cierre accionable:** Entrega el resultado final listo para aplicar."
        ),
        "desc": "Divide problemas complejos en etapas lógicas verificables (Chain-of-Thought).",
    },
    "Con Ejemplos": {
        "name": "Guiado con Ejemplos (Few-Shot)",
        "block": (
            "# Guía de Ejemplo (Referencia de Calidad)\n"
            "- Incluye al menos **2 ejemplos prácticos** (Caso de entrada → Resultado esperado) para ilustrar cada punto clave.\n"
            "- Si muestras código o fórmulas, acompaña cada bloque con un caso de uso concreto."
        ),
        "desc": "Exige casos prácticos de muestra (Entrada → Salida) para asegurar respuestas concretas.",
    },
    "Pedagógico": {
        "name": "Modo Pedagógico / Explicativo",
        "block": (
            "# Enfoque Didáctico\n"
            "- Explica cada término técnico con una analogía sencilla de la vida cotidiana.\n"
            "- Ordena la explicación de menor a mayor dificultad.\n"
            "- Al finalizar, incluye preguntas de autoevaluación con respuestas."
        ),
        "desc": "Ideal para estudiar: usa analogías simples, progresión gradual y preguntas de repaso.",
    },
    "Verificación": {
        "name": "Control de Calidad y Precisión",
        "block": (
            "# Reglas de Control y Verificación\n"
            "- **Cero suposiciones:** No inventes datos, cifras, leyes ni funciones que no existan.\n"
            "- **Datos faltantes:** Señala explícitamente qué falta o usa `[COMPLETAR: ...]`.\n"
            "- **Revisión final:** Comprueba el cumplimiento de cada restricción antes de entregar."
        ),
        "desc": "Añade restricciones estrictas contra errores y datos inventados.",
    },
}

TRIVIAL_GREETINGS = {
    "hola", "holi", "buenas", "buen dia", "buenos dias", "buenas tardes",
    "buenas noches", "hey", "que tal", "como estas", "test", "prueba", "ayuda",
}

CLITIC_STEM_MAP = {
    "armame": "armar",
    "armamelo": "armar",
    "explicame": "explicar",
    "explicamelo": "explicar",
    "pasame": "pasar",
    "pasamelo": "pasar",
    "decime": "decir",
    "decimelo": "decir",
    "haceme": "hacer",
    "hacemelo": "hacer",
    "resumime": "resumir",
    "resumimelo": "resumir",
    "comparame": "comparar",
    "comparamelo": "comparar",
    "analizame": "analizar",
    "analizamelo": "analizar",
    "escribime": "escribir",
    "redactame": "redactar",
    "corregime": "corregir",
    "arreglame": "arreglar",
    "depurame": "depurar",
    "planificame": "planificar",
    "organizame": "organizar",
    "enseñame": "enseñar",
    "ensenamelo": "enseñar",
    "solucioname": "solucionar",
    "ayudame": "ayudar",
    "calculame": "calcular",
    "evaluame": "evaluar",
    "sintetizame": "sintetizar",
    "refactorizame": "refactorizar",
    "optimizame": "optimizar",
    "predecime": "predecir",
    "converti": "convertir",
    "convertime": "convertir",
    "revisa": "revisar",
    "revisame": "revisar",
    "simula": "simular",
    "audita": "auditar",
    "auditame": "auditar",
    "extraeme": "extraer",
    "clasificame": "clasificar",
    "traducime": "traducir",
    "pulime": "pulir",
    "recomendame": "recomendar",
}

SPANISH_STOPWORDS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al",
    "a", "en", "con", "por", "para", "sobre", "entre", "hacia", "desde",
    "y", "o", "u", "e", "que", "como", "cual", "este", "esta", "estos", "estas",
    "ese", "esa", "mi", "tu", "su", "me", "te", "se", "nos", "lo", "le", "les",
    "es", "son", "ser", "esta", "estan", "muy", "mas", "menos", "pero", "si",
}

SEGMENT_CONNECTORS_RE = re.compile(
    r"\s*(?:;|(?:\by\s+(?:además|ademas|también|tambien))|(?:\bpor otro lado\b)|(?:\bluego\b))\s*",
    flags=re.IGNORECASE,
)


@dataclass
class ParsedRequest:
    raw_text: str
    instruction_text: str = ""
    payload_text: str = ""
    normalized_text: str = ""
    tokens: List[str] = field(default_factory=list)
    lemmas: List[str] = field(default_factory=list)
    word_count: int = 0

    # Etapa 2: PII
    masked_text: str = ""
    pii_warnings: List[Dict[str, Any]] = field(default_factory=list)
    has_pii_masked: bool = False

    # Etapa 3: Entidades y Restricciones
    entities: List[str] = field(default_factory=list)
    versions: List[str] = field(default_factory=list)
    filenames: List[str] = field(default_factory=list)
    errors_detected: List[str] = field(default_factory=list)
    code_snippets: List[str] = field(default_factory=list)
    neg_constraints: List[str] = field(default_factory=list)
    quant_constraints: List[str] = field(default_factory=list)
    contradictions: List[str] = field(default_factory=list)

    # Etapa 4: Clasificación Ortogonal + Sub-intención + Ontología + Universal v6.0
    domain: str = "Otro / General"
    action: str = "explicar_concepto"
    action_label: str = "Explicar concepto"
    subintent: str = "general"
    subintents_matched: List[str] = field(default_factory=list)
    ontology_objects: List[str] = field(default_factory=list)
    secondary_actions: List[str] = field(default_factory=list)
    deliverable: str = "informe estructurado"
    audience: str = ""
    tone: str = ""
    language: str = ""
    confidence: float = 0.0
    margin: float = 0.0
    needs_disambiguation: bool = False
    is_vague: bool = False
    suggested_paths: List[Dict[str, str]] = field(default_factory=list)
    suggested_slots: List[Dict[str, Any]] = field(default_factory=list)
    needs_placeholder: bool = False
    placeholder_label: str = "DATOS O TEXTO"
    placeholder_custom: str = ""
    facets: List[str] = field(default_factory=list)
    rewritten_goal: str = ""

    # v6.0 Universal Engine
    payload_info: Dict[str, Any] = field(default_factory=dict)
    roles: Dict[str, Any] = field(default_factory=dict)
    calc_info: Dict[str, Any] = field(default_factory=dict)

    # Etapa 5 & 6: Trazabilidad
    trace: List[Dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# ETAPA 1: Normalización, Abreviaturas, Voseo y Lematización Ligera
# ---------------------------------------------------------------------------

def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def _light_stem(token: str) -> str:
    if len(token) <= 4:
        return token
    for suffix in ("aciones", "iciones", "mente", "ando", "iendo", "ar", "er", "ir"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: -len(suffix)]
    if token.endswith("es") and len(token) > 5:
        return token[:-2]
    if token.endswith("s") and len(token) > 4 and not token.endswith("ss"):
        return token[:-1]
    return token


def normalize_and_lemmatize(text: str) -> Tuple[str, List[str], List[str]]:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    lowered = _strip_accents(cleaned.lower())

    abbr_map = KNOWLEDGE_BASE.get("abbreviations_map", {})
    raw_tokens = re.findall(r"[a-z0-9_+#.-]+", lowered)
    normalized_tokens: List[str] = []
    lemmas: List[str] = []

    for tok in raw_tokens:
        expanded = _strip_accents(abbr_map.get(tok, tok).lower())
        for sub_tok in expanded.split():
            base = CLITIC_STEM_MAP.get(sub_tok)
            if not base:
                m = re.match(r"^([a-z]{4,})(?:melo|mela|melos|melas|noslo|me|te|lo|la|nos)$", sub_tok)
                if m and len(m.group(1)) >= 4:
                    base = m.group(1)
                else:
                    base = sub_tok
            normalized_tokens.append(base)
            lemmas.append(_light_stem(base))

    normalized_text = " ".join(normalized_tokens)
    return normalized_text, normalized_tokens, lemmas


# ---------------------------------------------------------------------------
# ETAPA 2: Detección y Anonimización de Datos Sensibles (PII)
# ---------------------------------------------------------------------------

_RE_CBU = re.compile(r"\b\d{22}\b")
_RE_ALIAS_BANK = re.compile(r"\b(?:alias\s*(?:cbu|bancario)?\s*[:=]\s*)([a-z0-9._-]{6,30})\b", re.IGNORECASE)
_RE_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_RE_CUIL_DNI = re.compile(r"\b(?:\d{2}-\d{7,8}-\d|\d{2}\.\d{3}\.\d{3}|\d{7,8})\b")
_RE_PHONE = re.compile(
    r"(?<!\d)(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-])\d{3,4}[\s.-]?\d{4}(?!\d)"
)


def detect_and_mask_pii(text: str) -> Tuple[str, List[Dict[str, Any]]]:
    if not text:
        return "", []

    masked = text
    warnings: List[Dict[str, Any]] = []

    cbu_matches = _RE_CBU.findall(masked)
    if cbu_matches:
        masked = _RE_CBU.sub("[CBU_OCULTO]", masked)
        warnings.append({"type": "cbu", "label": "CBU bancario (22 dígitos)", "count": len(cbu_matches)})

    alias_matches = _RE_ALIAS_BANK.findall(masked)
    if alias_matches:
        masked = _RE_ALIAS_BANK.sub("alias: [ALIAS_OCULTO]", masked)
        warnings.append({"type": "alias_bancario", "label": "Alias bancario", "count": len(alias_matches)})

    email_matches = _RE_EMAIL.findall(masked)
    if email_matches:
        masked = _RE_EMAIL.sub("[EMAIL_OCULTO]", masked)
        warnings.append({"type": "email", "label": "Correo electrónico", "count": len(email_matches)})

    dni_matches = _RE_CUIL_DNI.findall(masked)
    if dni_matches:
        masked = _RE_CUIL_DNI.sub("[DNI_CUIL_OCULTO]", masked)
        warnings.append({"type": "dni_cuil", "label": "DNI / CUIL / CUIT", "count": len(dni_matches)})

    phone_matches = _RE_PHONE.findall(masked)
    if phone_matches:
        masked = _RE_PHONE.sub("[TELEFONO_OCULTO]", masked)
        warnings.append({"type": "telefono", "label": "Teléfono", "count": len(phone_matches)})

    return masked, warnings


# ---------------------------------------------------------------------------
# ETAPA 3: Extracción de Entidades, Restricciones y Contradicciones
# ---------------------------------------------------------------------------

def _build_entity_index() -> List[Tuple[str, str]]:
    items: List[Tuple[str, str]] = []
    for group, terms in KNOWLEDGE_BASE.get("entities_lexicon", {}).items():
        for term in terms:
            items.append((_strip_accents(term.lower()), group))
    items.sort(key=lambda x: len(x[0]), reverse=True)
    return items


_ENTITY_INDEX = _build_entity_index()

_RE_VERSION = re.compile(r"\b\d+(?:\.\d+)+\b")
_RE_FILENAME = re.compile(r"\b[\w-]+\.(?:csv|xlsx|py|sql|json|pdf|docx|txt)\b", re.IGNORECASE)
_RE_ERROR = re.compile(
    r"\b(?:Traceback|[A-Z][a-zA-Z]+(?:Error|Exception)|HTTP\s*(?:4\d{2}|5\d{2}))\b"
)
_RE_NEG_CONSTRAINT = re.compile(
    r"\b(sin|no uses|no usar|evita|evitar|nada de|excepto|no incluyas|no incluir)\s+((?:\S+\s*){1,6})",
    flags=re.IGNORECASE,
)
_RE_QUANT_CONSTRAINT = re.compile(
    r"\b((?:maximo|máximo|como maximo|como máximo|al menos|minimo|mínimo|hasta|entre \d+ y)\s+\d+(?:\s+\S+){0,3})",
    flags=re.IGNORECASE,
)


def _extract_entities_and_constraints(
    raw_text: str, normalized_text: str, technique: str
) -> Dict[str, Any]:
    entities: List[str] = []
    seen_ent = set()

    for term, _group in _ENTITY_INDEX:
        pattern = r"(?<![a-z0-9_])" + re.escape(term) + r"(?![a-z0-9_])"
        if re.search(pattern, normalized_text) and term not in seen_ent:
            seen_ent.add(term)
            entities.append(term)

    versions = list(dict.fromkeys(_RE_VERSION.findall(raw_text)))
    filenames = list(dict.fromkeys(_RE_FILENAME.findall(raw_text)))
    errors_detected = list(dict.fromkeys(_RE_ERROR.findall(raw_text)))

    code_snippets = re.findall(r"```[\s\S]*?```|`[^`]+`", raw_text)
    if not code_snippets and re.search(r"\b(?:def |SELECT |import |const |function )", raw_text):
        code_snippets = ["inline_code_fragment"]

    neg_constraints: List[str] = []
    for kw, phrase in _RE_NEG_CONSTRAINT.findall(raw_text):
        clean_phrase = re.split(r"[,.;\n]", phrase)[0].strip()
        words = clean_phrase.split()[:6]
        if words:
            neg_constraints.append(f"{kw.lower()} {' '.join(words)}")

    quant_constraints: List[str] = []
    for match in _RE_QUANT_CONSTRAINT.findall(raw_text):
        clean_q = re.split(r"[,.;\n]", match)[0].strip()
        if clean_q:
            quant_constraints.append(clean_q)

    contradictions: List[str] = []
    has_short = any(w in normalized_text for w in ("breve", "corto", "corta", "resumido", "conciso", "ultra breve"))
    has_long = any(w in normalized_text for w in ("exhaustivo", "exhaustiva", "detallado", "detallada", "extenso", "profundo"))
    if has_short and has_long:
        contradictions.append("Se pide extensión breve/resumida y al mismo tiempo exhaustiva/detallada.")

    if any("ejemplo" in nc for nc in neg_constraints) and technique == "Con Ejemplos":
        contradictions.append("Restricción negativa 'sin ejemplos' entra en conflicto con la técnica 'Con Ejemplos'.")

    if any("codigo" in _strip_accents(nc) for nc in neg_constraints) and any(
        w in normalized_text for w in ("generar codigo", "script", "funcion", "programa")
    ):
        contradictions.append("Se solicita generar código pero existe una restricción negativa sobre usar código.")

    return {
        "entities": entities,
        "versions": versions,
        "filenames": filenames,
        "errors_detected": errors_detected,
        "code_snippets": code_snippets,
        "neg_constraints": list(dict.fromkeys(neg_constraints)),
        "quant_constraints": list(dict.fromkeys(quant_constraints)),
        "contradictions": contradictions,
    }


# ---------------------------------------------------------------------------
# ETAPA 4: Clasificación Ortogonal (21 Arquetipos) + Sub-intenciones + Ontología
# ---------------------------------------------------------------------------

def _tokenize_for_tfidf(text: str) -> List[str]:
    _, tokens, lemmas = normalize_and_lemmatize(text)
    filtered = [t for t in tokens if t not in SPANISH_STOPWORDS and len(t) > 1]
    filtered_lemmas = [l for l in lemmas if l not in SPANISH_STOPWORDS and len(l) > 1]
    return filtered + filtered_lemmas


class _ActionTfIdfIndex:
    """Índice TF-IDF en Python puro sobre los prototipos de acciones/arquetipos."""

    def __init__(self, actions_cfg: Dict[str, Any]):
        self.action_docs: Dict[str, List[Counter]] = {}
        df: Counter = Counter()
        total_docs = 0

        for action_key, cfg in actions_cfg.items():
            protos = cfg.get("prototypes", [])
            doc_counters: List[Counter] = []
            for p in protos:
                toks = _tokenize_for_tfidf(p)
                c = Counter(toks)
                doc_counters.append(c)
                for term in c.keys():
                    df[term] += 1
                total_docs += 1
            self.action_docs[action_key] = doc_counters

        self.idf: Dict[str, float] = {
            term: math.log((1 + total_docs) / (1 + freq)) + 1.0
            for term, freq in df.items()
        }
        self.action_vectors: Dict[str, List[Dict[str, float]]] = {}
        for action_key, counters in self.action_docs.items():
            self.action_vectors[action_key] = [self._to_tfidf(c) for c in counters]

    def _to_tfidf(self, counts: Counter) -> Dict[str, float]:
        if not counts:
            return {}
        total = sum(counts.values())
        return {
            term: (cnt / total) * self.idf.get(term, 1.0)
            for term, cnt in counts.items()
            if term in self.idf
        }

    @staticmethod
    def _cosine(v1: Dict[str, float], v2: Dict[str, float]) -> float:
        if not v1 or not v2:
            return 0.0
        dot = sum(val * v2[k] for k, val in v1.items() if k in v2)
        if dot <= 0.0:
            return 0.0
        n1 = math.sqrt(sum(v * v for v in v1.values()))
        n2 = math.sqrt(sum(v * v for v in v2.values()))
        if n1 == 0.0 or n2 == 0.0:
            return 0.0
        return dot / (n1 * n2)

    def score_text(self, text: str) -> Dict[str, float]:
        q_vec = self._to_tfidf(Counter(_tokenize_for_tfidf(text)))
        scores: Dict[str, float] = {}
        for action_key, vecs in self.action_vectors.items():
            sims = [self._cosine(q_vec, pv) for pv in vecs]
            scores[action_key] = max(sims) if sims else 0.0
        return scores


_TFIDF_INDEX = _ActionTfIdfIndex(KNOWLEDGE_BASE.get("actions", {}))


def _score_actions(text: str, normalized_text: str) -> Dict[str, float]:
    tfidf_scores = _TFIDF_INDEX.score_text(text)
    actions_cfg = KNOWLEDGE_BASE.get("actions", {})
    combined: Dict[str, float] = {}

    for action_key, cfg in actions_cfg.items():
        lex_hits = 0.0
        for kw in cfg.get("keywords", []):
            kw_norm = _strip_accents(kw.lower())
            if " " in kw_norm:
                if kw_norm in normalized_text:
                    lex_hits += 1.5
            else:
                if re.search(rf"(?<![a-z0-9]){re.escape(kw_norm)}(?![a-z0-9])", normalized_text):
                    lex_hits += 1.0
        lex_norm = min(lex_hits / 3.0, 1.0)
        tfidf_val = tfidf_scores.get(action_key, 0.0)
        combined[action_key] = round(0.55 * lex_norm + 0.45 * tfidf_val, 4)

    return combined


def _classify_domain(normalized_text: str, explicit_category: str) -> Tuple[str, List[Dict[str, Any]]]:
    trace: List[Dict[str, Any]] = []
    mapped = LEGACY_DOMAIN_ALIASES.get(explicit_category, explicit_category)
    domains_cfg = KNOWLEDGE_BASE.get("domains", {})

    if mapped and mapped in domains_cfg and mapped != "Otro / General":
        trace.append({"stage": "domain", "rule": f"Dominio explícito/mapeado: {mapped}"})
        return mapped, trace

    best_domain = "Otro / General"
    best_score = 0.0
    matched_kws: List[str] = []

    for dom_name, cfg in domains_cfg.items():
        if dom_name == "Otro / General":
            continue
        score = 0.0
        hits = []
        for kw in cfg.get("keywords", []):
            kw_norm = _strip_accents(kw.lower())
            if " " in kw_norm:
                if kw_norm in normalized_text:
                    score += 1.5
                    hits.append(kw)
            else:
                if re.search(rf"(?<![a-z0-9]){re.escape(kw_norm)}(?![a-z0-9])", normalized_text):
                    score += 1.0
                    hits.append(kw)
        if score > best_score:
            best_score = score
            best_domain = dom_name
            matched_kws = hits[:5]

    trace.append({
        "stage": "domain",
        "rule": f"Inferencia léxica -> {best_domain}",
        "score": best_score,
        "matched_keywords": matched_kws,
    })
    return best_domain, trace


def _classify_deliverable(normalized_text: str, action: str, form_data: Dict[str, Any]) -> str:
    fmt = form_data.get("Formato de Salida") or form_data.get("deliverable") or ""
    if fmt:
        fmt_norm = _strip_accents(fmt.lower())
        for deliv_key in KNOWLEDGE_BASE.get("deliverables", {}):
            if _strip_accents(deliv_key.lower()) in fmt_norm or fmt_norm in _strip_accents(deliv_key.lower()):
                return deliv_key
        return fmt

    if action == "simular_practicar" and "json" not in normalized_text and "tabla" not in normalized_text:
        return "diálogo interactivo"

    if re.search(r"\b(?:(?:en|a|formato|como|quiero)\s+(?:un\s+)?json|json\s+limpio)\b", normalized_text):
        return "json"
    if re.search(r"\b(?:(?:a|formato)\s+(?:una\s+)?tabla|en\s+una\s+tabla|en\s+tabla)\b", normalized_text):
        return "tabla"

    best_deliv = ""
    best_hits = 0
    for deliv_key, cfg in KNOWLEDGE_BASE.get("deliverables", {}).items():
        hits = sum(
            1 for kw in cfg.get("keywords", [])
            if _strip_accents(kw.lower()) in normalized_text
        )
        if hits > best_hits:
            best_hits = hits
            best_deliv = deliv_key

    if best_deliv:
        return best_deliv

    default_by_action = {
        "depurar_error": "código",
        "generar_codigo": "código",
        "comparar_evaluar": "tabla",
        "planificar_pasos": "guía paso a paso",
        "resumir_sintetizar": "resumen ejecutivo",
        "redactar_contenido": "email / mensaje",
        "analizar_datos": "informe estructurado",
        "explicar_concepto": "informe estructurado",
        "transformar_formato": "json",
        "extraer_informacion": "tabla",
        "clasificar_categorizar": "tabla",
        "traducir_adaptar": "informe estructurado",
        "reescribir_mejorar": "email / mensaje",
        "auditar_criticar": "tabla",
        "simular_practicar": "diálogo interactivo",
        "idear_alternativas": "lista",
        "calcular_modelar": "tabla",
        "razonar_resolver": "guía paso a paso",
        "decidir_recomendar": "tabla",
        "diagnosticar_resolver": "informe estructurado",
        "consultar_dato": "resumen ejecutivo",
    }
    return default_by_action.get(action, "informe estructurado")


def _detect_subintents(raw_text: str, normalized_text: str, action: str) -> Tuple[str, List[str]]:
    subintents_cfg = KNOWLEDGE_BASE.get("subintents", {})
    action_subs = subintents_cfg.get(action, {})
    all_matched: List[str] = []

    def _score_group(group: Dict[str, Any]) -> List[Tuple[str, float]]:
        res = []
        for sub_name, cfg in group.items():
            s = 0.0
            for kw in cfg.get("keywords", []):
                kw_norm = _strip_accents(kw.lower())
                if " " in kw_norm:
                    if kw_norm in normalized_text:
                        s += 1.5
                elif re.search(rf"(?<![a-z0-9]){re.escape(kw_norm)}(?![a-z0-9])", normalized_text):
                    s += 1.0
            for rgx in cfg.get("regex", []):
                if re.search(rgx, raw_text, flags=re.IGNORECASE):
                    s += 2.0
            if s > 0:
                res.append((sub_name, s))
        return res

    scored = _score_group(action_subs)
    scored.sort(key=lambda x: x[1], reverse=True)
    primary = scored[0][0] if scored else "general"
    for name, _ in scored:
        if name not in all_matched:
            all_matched.append(name)

    for act_k, group in subintents_cfg.items():
        if act_k == action:
            continue
        for name, sc in _score_group(group):
            if sc >= 1.5 and name not in all_matched:
                all_matched.append(name)

    return primary, all_matched


def _detect_ontology_objects(normalized_text: str) -> List[str]:
    ontology = KNOWLEDGE_BASE.get("object_ontology", {})
    matched: List[str] = []
    for obj_key, cfg in ontology.items():
        for alias in cfg.get("aliases", []):
            al_norm = _strip_accents(alias.lower())
            if re.search(rf"(?<![a-z0-9]){re.escape(al_norm)}(?![a-z0-9])", normalized_text):
                if obj_key not in matched:
                    matched.append(obj_key)
                break
    return matched


def _select_suggested_slots(domain: str, action: str, form_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    catalog = KNOWLEDGE_BASE.get("slot_catalog", {})
    candidates: List[Dict[str, Any]] = []
    candidates.extend(catalog.get("by_action", {}).get(action, []))
    candidates.extend(catalog.get("by_domain", {}).get(domain, []))

    answered_keys = {_strip_accents(str(k).lower()) for k, v in form_data.items() if v}
    filtered: List[Dict[str, Any]] = []
    seen_ids = set()
    for slot in candidates:
        sid = slot["id"]
        if sid in seen_ids:
            continue
        if _strip_accents(sid.lower()) in answered_keys:
            continue
        seen_ids.add(sid)
        filtered.append(slot)

    filtered.sort(key=lambda s: s.get("impact_pts", 5), reverse=True)
    return filtered[:3]


def _extract_context_modifiers(normalized_text: str) -> Dict[str, Any]:
    audience = ""
    if any(w in normalized_text for w in ("principiante", "desde cero", "basico", "no se nada", "facil")):
        audience = "Principiante / Sin conocimientos previos"
    elif any(w in normalized_text for w in ("senior", "avanzado", "experto", "produccion")):
        audience = "Nivel avanzado / Técnico"
    elif any(w in normalized_text for w in ("cliente", "gerencia", "directivo", "jefe")):
        audience = "Directivo / Cliente"
    elif any(w in normalized_text for w in ("universitario", "facultad", "examen", "parcial", "final")):
        audience = "Académico / Universitario"

    tone = ""
    if any(w in normalized_text for w in ("formal", "profesional", "cordial")):
        tone = "Formal y profesional"
    elif any(w in normalized_text for w in ("cercano", "amigable", "informal")):
        tone = "Cercano y claro"

    language = ""
    if "en ingles" in normalized_text:
        language = "Inglés"
    elif "en español" in normalized_text or "en espanol" in normalized_text:
        language = "Español"

    needs_placeholder = False
    placeholder_label = "DATOS O TEXTO"
    if any(w in normalized_text for w in ("este texto", "este correo", "este codigo", "este csv", "este dataset", "este error", "estos datos", "esta clausula", "este contrato")):
        needs_placeholder = True
        if "clausula" in normalized_text or "contrato" in normalized_text:
            placeholder_label = "TEXTO DE LA CLÁUSULA"
        elif "codigo" in normalized_text or "error" in normalized_text:
            placeholder_label = "CÓDIGO O ERROR"
        elif "csv" in normalized_text or "dataset" in normalized_text or "datos" in normalized_text:
            placeholder_label = "DATOS / CSV"
        elif "correo" in normalized_text or "mail" in normalized_text:
            placeholder_label = "CORREO O MENSAJE"

    return {
        "audience": audience,
        "tone": tone,
        "language": language,
        "needs_placeholder": needs_placeholder,
        "placeholder_label": placeholder_label,
    }


def _build_facets(req: ParsedRequest) -> List[str]:
    facets = {
        f"domain:{req.domain}",
        f"action:{req.action}",
        f"sub:{req.subintent}",
        f"deliv:{req.deliverable}",
    }
    for sec in req.secondary_actions:
        facets.add(f"action:{sec}")
    for sub_m in req.subintents_matched:
        facets.add(f"sub:{sub_m}")
    for ent in req.entities:
        facets.add(f"entity:{ent}")
    for fn in req.filenames:
        ext = fn.rsplit(".", 1)[-1].lower()
        facets.add(f"entity:{ext}")
    for obj in req.ontology_objects:
        facets.add(f"obj:{obj}")

    if "Principiante" in req.audience:
        facets.add("audience:principiante")
    elif "avanzado" in req.audience.lower():
        facets.add("audience:avanzado")

    if req.language == "Español":
        facets.add("lang:espanol")

    neg_joined = _strip_accents(" ".join(req.neg_constraints).lower())
    if any(k in neg_joined for k in ("grafico", "graficos", "plot", "chart")):
        facets.add("neg:sin_graficos")
    if any(k in neg_joined for k in ("tecnicismo", "jerga")):
        facets.add("neg:sin_tecnicismos")
    if any(k in neg_joined for k in ("libreria", "paquete", "externa")):
        facets.add("neg:sin_librerias")
    if "ejemplo" in neg_joined:
        facets.add("neg:sin_ejemplos")

    return sorted(facets)


def _build_suggested_paths(raw_text: str) -> List[Dict[str, str]]:
    topic = raw_text.strip() or "este tema"
    return [
        {
            "label": f"Explicar qué es {topic} desde cero",
            "prompt": f"Explicame qué es {topic} desde cero para principiantes con ejemplos simples",
        },
        {
            "label": f"Armar un plan paso a paso sobre {topic}",
            "prompt": f"Armame una guía paso a paso práctica para organizar y controlar {topic}",
        },
        {
            "label": f"Analizar o resolver un problema con {topic}",
            "prompt": f"Analizar datos o depurar un problema relacionado con {topic} paso a paso",
        },
    ]


# ---------------------------------------------------------------------------
# ETAPA 4B: Reescritura Determinística con Fidelidad (v5.0 + v6.0)
# ---------------------------------------------------------------------------

def rewrite_goal(parsed: ParsedRequest, mask_pii: bool = False) -> Tuple[str, List[str]]:
    """
    Limpia marcos conversacionales, expande abreviaturas, promueve verbos por clase
    y traduce adjetivos vagos en criterios observables sin inventar hechos.
    """
    if parsed.payload_text and parsed.instruction_text:
        src = parsed.instruction_text
        if mask_pii:
            src, _ = detect_and_mask_pii(src)
    else:
        src = parsed.masked_text if mask_pii else parsed.raw_text

    cleaned = re.sub(r"\s+", " ", src or "").strip()

    for frame_rgx in KNOWLEDGE_BASE.get("request_frames", []):
        cleaned = re.sub(frame_rgx, "", cleaned, flags=re.IGNORECASE).strip()

    if not cleaned:
        cleaned = src.strip()

    abbr_map = KNOWLEDGE_BASE.get("abbreviations_map", {})
    words_out: List[str] = []
    for tok in cleaned.split(" "):
        low = tok.lower().strip(",.;:!?")
        if low in abbr_map and tok.lower() == low:
            words_out.append(abbr_map[low])
        else:
            words_out.append(tok)
    cleaned = " ".join(words_out)

    first_tok = cleaned.split(" ")[0].lower() if cleaned else ""
    first_norm = _strip_accents(first_tok)
    verb_classes = KNOWLEDGE_BASE.get("verb_classes", {})
    promoted = False

    infinitive = CLITIC_STEM_MAP.get(first_norm, first_norm)
    rest = " ".join(cleaned.split(" ")[1:]).strip()

    if rest:
        for vclass_name, vcfg in verb_classes.items():
            if infinitive in vcfg.get("verbs", []):
                if vclass_name == "produccion":
                    tpl = vcfg.get("by_deliverable", {}).get(
                        parsed.deliverable, vcfg.get("default_template", "Elaborar {obj}")
                    )
                    cleaned = tpl.format(inf=infinitive, obj=rest)
                else:
                    tpl = vcfg.get("template", "{inf} {obj}")
                    cleaned = tpl.format(inf=infinitive, obj=rest)
                promoted = True
                break

        if not promoted and infinitive != first_norm:
            cleaned = f"{infinitive.capitalize()} {rest}"

    adj_map = KNOWLEDGE_BASE.get("lint_rules", {}).get("adjective_translations", {})
    adj_notes: List[str] = []
    norm_cleaned = _strip_accents(cleaned.lower())
    for adj, translation in adj_map.items():
        if re.search(rf"\b{re.escape(adj)}\b", norm_cleaned):
            adj_notes.append(f"Criterio de '{adj}': {translation}.")

    if cleaned:
        cleaned = cleaned[0].upper() + cleaned[1:]
        if cleaned[-1] not in ".!?":
            cleaned += "."

    return cleaned, adj_notes


def check_fidelity(user_text: str, rewritten_goal: str, parsed: ParsedRequest) -> Dict[str, Any]:
    """
    Verifica que todas las entidades, archivos y errores del usuario sigan presentes
    y que no se hayan inventado hechos sobre el usuario.
    """
    rew_low = _strip_accents(rewritten_goal.lower())
    missing: List[str] = []
    for fn in parsed.filenames:
        if fn.lower() not in rewritten_goal.lower():
            missing.append(fn)
    for err in parsed.errors_detected:
        if err.lower() not in rewritten_goal.lower():
            missing.append(err)
    for ent in parsed.entities[:5]:
        if ent not in rew_low:
            missing.append(ent)

    repaired_goal = rewritten_goal
    if missing:
        repaired_goal = f"{rewritten_goal.rstrip('.')} (involucrando: {', '.join(missing)})."

    return {
        "fidelity_ok": len(missing) == 0,
        "restored_items": missing,
        "goal": repaired_goal,
    }


def parse_request(
    user_text: str,
    category: str = "",
    form_data: Optional[Dict[str, Any]] = None,
    technique: str = "Estándar",
    override_domain: str = "",
    override_action: str = "",
    override_deliverable: str = "",
    negative_constraints: Optional[List[str]] = None,
) -> ParsedRequest:
    form_data = form_data or {}
    req = ParsedRequest(raw_text=(user_text or "").strip())

    # Etapa 0 (v6.0): Separar pedido vs. insumo pegado
    instr_part, payload_part = split_request_payload(req.raw_text)
    req.instruction_text = instr_part
    req.payload_text = payload_part
    req.payload_info = inspect_attached_payload(payload_part, instr_part)

    # Etapa 1: Normalización sobre el pedido completo (y sobre el pedido núcleo para clasificar)
    norm_text, tokens, lemmas = normalize_and_lemmatize(req.raw_text)
    norm_instr, _, _ = normalize_and_lemmatize(instr_part)
    req.normalized_text = norm_text
    req.tokens = tokens
    req.lemmas = lemmas
    req.word_count = len(req.raw_text.split())

    # Etapa 2: PII
    masked_text, pii_warnings = detect_and_mask_pii(req.raw_text)
    req.masked_text = masked_text
    req.pii_warnings = pii_warnings
    req.has_pii_masked = bool(pii_warnings)

    # Etapa 3: Entidades y Restricciones
    ext = _extract_entities_and_constraints(req.raw_text, norm_text, technique)
    req.entities = ext["entities"]
    req.versions = ext["versions"]
    req.filenames = ext["filenames"]
    req.errors_detected = ext["errors_detected"]
    req.code_snippets = ext["code_snippets"]
    req.neg_constraints = list(ext["neg_constraints"])
    if negative_constraints:
        for nc in negative_constraints:
            if isinstance(nc, str) and nc.strip() and nc.strip() not in req.neg_constraints:
                req.neg_constraints.append(nc.strip())
    req.quant_constraints = ext["quant_constraints"]
    req.contradictions = ext["contradictions"]

    # Etapa 4: Dominio, Acción (21 Arquetipos), Sub-intención, Roles y Cálculo
    classify_src = instr_part if payload_part else req.raw_text
    classify_norm = norm_instr if payload_part else norm_text

    domain_hint = override_domain or category
    req.domain, dom_trace = _classify_domain(classify_norm, domain_hint)
    req.trace.extend(dom_trace)

    segments_raw = [s.strip() for s in SEGMENT_CONNECTORS_RE.split(classify_src) if s.strip()]
    if not segments_raw:
        segments_raw = [classify_src]

    global_scores = _score_actions(classify_src, classify_norm)
    ranked = sorted(global_scores.items(), key=lambda kv: kv[1], reverse=True)
    top1_action, top1_score = ranked[0]
    top2_score = ranked[1][1] if len(ranked) > 1 else 0.0

    if top1_score == 0.0:
        top1_action = "explicar_concepto"

    secondary: List[str] = []
    if len(segments_raw) > 1:
        for seg in segments_raw[1:]:
            seg_norm, _, _ = normalize_and_lemmatize(seg)
            seg_scores = _score_actions(seg, seg_norm)
            seg_top, seg_val = max(seg_scores.items(), key=lambda kv: kv[1])
            if seg_top != top1_action and seg_val >= max(0.6 * top1_score, 0.20) and seg_top not in secondary:
                secondary.append(seg_top)
    else:
        for act_k, act_s in ranked[1:3]:
            if top1_score > 0.25 and act_s >= 0.65 * top1_score:
                secondary.append(act_k)

    if override_action and override_action in KNOWLEDGE_BASE.get("actions", {}):
        req.action = override_action
        req.trace.append({"stage": "action", "rule": f"Override usuario -> {override_action}"})
    else:
        req.action = top1_action

    actions_cfg = KNOWLEDGE_BASE.get("actions", {})
    req.action_label = actions_cfg.get(req.action, {}).get("label", req.action)
    req.secondary_actions = secondary

    req.confidence = round(min(max(top1_score, 0.15 if req.word_count >= 3 else 0.05), 0.99), 3)
    req.margin = round(max(top1_score - top2_score, 0.0), 3)

    if override_deliverable:
        req.deliverable = override_deliverable
    else:
        req.deliverable = _classify_deliverable(classify_norm, req.action, form_data)

    mods = _extract_context_modifiers(classify_norm)
    req.audience = mods["audience"]
    req.tone = mods["tone"]
    req.language = mods["language"]

    if req.payload_info.get("missing_payload"):
        req.needs_placeholder = True
        req.placeholder_custom = req.payload_info.get("placeholder_tag", "[PEGÁ ACÁ LOS DATOS O TEXTO]")
        req.placeholder_label = mods["placeholder_label"]
    else:
        req.needs_placeholder = mods["needs_placeholder"] or (req.action == "depurar_error" and not req.code_snippets and not payload_part)
        req.placeholder_label = mods["placeholder_label"]

    req.subintent, req.subintents_matched = _detect_subintents(req.raw_text, norm_text, req.action)
    req.ontology_objects = _detect_ontology_objects(norm_text)

    # Extractor de roles semánticos y calculador determinístico (v6.0)
    req.roles = extract_semantic_roles(classify_src, payload_info=req.payload_info)
    req.calc_info = compute_control_values(req.raw_text, roles=req.roles)

    useful_words = [t for t in req.tokens if t not in SPANISH_STOPWORDS]
    if len(useful_words) < 4 and (len(useful_words) <= 2 or (not req.entities and not req.errors_detected and req.confidence < 0.35)):
        req.is_vague = True
        req.suggested_paths = _build_suggested_paths(req.raw_text)

    if req.margin < 0.15 or req.word_count < 5 or req.is_vague:
        req.needs_disambiguation = True
    req.suggested_slots = _select_suggested_slots(req.domain, req.action, form_data)
    req.facets = _build_facets(req)

    rewritten, _ = rewrite_goal(req)
    req.rewritten_goal = check_fidelity(req.raw_text, rewritten, req)["goal"]

    req.trace.append({
        "stage": "classification",
        "domain": req.domain,
        "action": req.action,
        "subintent": req.subintent,
        "payload_kind": req.payload_info.get("payload_kind", "sin_insumo"),
        "roles_filled": req.roles.get("roles_filled", 0.0),
        "ontology_objects": req.ontology_objects,
        "secondary_actions": req.secondary_actions,
        "deliverable": req.deliverable,
        "confidence": req.confidence,
        "margin": req.margin,
        "needs_disambiguation": req.needs_disambiguation,
        "is_vague": req.is_vague,
    })
    return req


# ---------------------------------------------------------------------------
# ETAPA 5: Selector de Micro-Directivas + Linter Anti-Relleno + Rúbrica v2
# ---------------------------------------------------------------------------

def select_directives(parsed: ParsedRequest, level: str = "Completa") -> List[Dict[str, Any]]:
    level_key = (level or "Completa").lower()
    if level_key not in ("ligera", "completa", "profunda"):
        level_key = "completa"

    facet_set = set(parsed.facets)
    candidates: List[Dict[str, Any]] = []

    for d in KNOWLEDGE_BASE.get("directives", []):
        if level_key not in d.get("levels", ["completa"]):
            continue
        when = d.get("when", {})
        all_req = when.get("all", [])
        any_req = when.get("any", [])
        when_not = d.get("when_not", [])

        if any(f in facet_set for f in when_not):
            continue
        if all_req and not all(f in facet_set for f in all_req):
            continue
        if any_req and not any(f in facet_set for f in any_req):
            continue
        if not all_req and not any_req:
            continue
        candidates.append(d)

    candidates.sort(key=lambda x: x.get("priority", 50), reverse=True)
    selected: List[Dict[str, Any]] = []
    blocked_ids = set()
    for d in candidates:
        did = d["id"]
        if did in blocked_ids:
            continue
        selected.append(d)
        for m in d.get("mutex", []):
            blocked_ids.add(m)

    phase_rank = {p: idx for idx, p in enumerate(PHASES)}
    selected.sort(key=lambda x: (phase_rank.get(x.get("phase", "ejecutar"), 2), -x.get("priority", 50)))
    return selected


def lint_prompt(
    text: str,
    parsed: ParsedRequest,
    directives: List[Dict[str, Any]],
    extra_anchors: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Elimina frases de relleno genérico (banned_patterns) y calcula:
    - noise_ratio (< 0.10 objetivo)
    - anchor_coverage (>= 0.90 objetivo)
    """
    banned = KNOWLEDGE_BASE.get("lint_rules", {}).get("banned_patterns", [])
    cleaned = text
    removed_hits = 0
    for pat in banned:
        new_cleaned, n = re.subn(pat, "", cleaned, flags=re.IGNORECASE)
        if n > 0:
            removed_hits += n
            cleaned = new_cleaned
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    content_lines = [
        ln.strip() for ln in cleaned.splitlines()
        if ln.strip() and not ln.strip().startswith("#") and ln.strip() not in ("<datos_entrada>", "</datos_entrada>")
    ]
    if not content_lines:
        return {"text": cleaned, "noise_ratio": 0.0, "anchor_coverage": 1.0, "removed_hits": removed_hits}

    anchor_terms = set(
        [e.lower() for e in parsed.entities]
        + [f.lower() for f in parsed.filenames]
        + [er.lower() for er in parsed.errors_detected]
        + [o.lower() for o in parsed.ontology_objects]
        + [str(a).lower() for a in (extra_anchors or []) if a]
        + [
            "objetivo", "dominio", "intención", "entregable", "formato", "criterio",
            "completar", "pega aquí", "pegá acá", "fefo", "iqr", "pearson", "spearman", "keyerror",
            "df.", "sql", "join", "markdown", "tabla", "autoevaluación", "párrafo",
            "restricción", "prohibido", "supuesto", "borde", "validación", "ejemplo",
            "datos", "archivo", "columna", "código", "error", "causa", "encabezado",
            "firma", "licencia", "comprobante", "lote", "venta", "vencimiento",
            "reposición", "planilla", "semanal", "diaria", "mensual", "rutina",
            "correlación", "regresión", "gráfico", "definición", "analogía",
            "hallazgos", "métricas", "nulos", "outliers", "causalidad", "checklist",
            "asunto", "saludo", "destinatario", "desglose", "herramientas", "público",
            "tono", "idioma", "reproducible", "python", "pandas", "excel", "sheets",
            "etapa", "paso", "rotación", "negocio", "mercadería", "vencer", "promociones",
            "json", "objeto", "precio", "categoría", "sin_categoria", "null", "unidad",
            "cláusula", "riesgo", "gravedad", "abogado", "inquilino", "obligación",
            "whatsapp", "instagram", "turno", "oraciones", "personaje", "fin", "devolución",
            "margen", "escenario", "fórmula", "costo", "venta", "gastos",
            "gancho", "límite honesto", "promesa", "cifra", "fuente", "no consta", "registros",
        ]
    )

    anchored = 0
    for ln in content_lines:
        ln_low = ln.lower()
        has_anchor = (
            any(term in ln_low for term in anchor_terms)
            or bool(re.search(r"\d+", ln_low))
            or bool(re.search(r"`[^`]+`", ln))
            or ln_low.startswith(("actúa como", "objetivo:", "formato", "restricciones:", "analiza únicamente", "procesa únicamente"))
        )
        if has_anchor:
            anchored += 1

    anchor_coverage = round(anchored / len(content_lines), 3)
    noise_ratio = round(max(1.0 - anchor_coverage, 0.0), 3)
    return {
        "text": cleaned,
        "noise_ratio": noise_ratio,
        "anchor_coverage": anchor_coverage,
        "removed_hits": removed_hits,
    }


def calculate_rubric_v2(
    parsed: ParsedRequest,
    improved_prompt: str,
    form_data: Dict[str, Any],
    user_example: str = "",
    user_corrected: bool = False,
    level: str = "Completa",
    noise_ratio: float = 0.04,
    anchor_coverage: float = 0.95,
) -> Dict[str, Any]:
    """
    Rúbrica v2 no circular:
    - user_score (0-100): evalúa únicamente la riqueza del texto original del usuario.
    - information_gain (0-40): puntos aportados por el usuario (slots, restricciones, ejemplos, chips).
    - final_score (0-100): evalúa las 5 dimensiones ponderadas por rubric_weights de la intención.
    """
    norm = parsed.normalized_text
    is_trivial = norm in TRIVIAL_GREETINGS or parsed.word_count < 3

    if is_trivial:
        user_score = 18 if parsed.word_count >= 2 else 12
    else:
        u_pts = 20
        if parsed.word_count >= 6:
            u_pts += 12
        if parsed.word_count >= 12:
            u_pts += 10
        if parsed.confidence >= 0.45:
            u_pts += 14
        u_pts += min(len(parsed.entities) * 7, 18)
        u_pts += min((len(parsed.neg_constraints) + len(parsed.quant_constraints)) * 8, 16)
        if parsed.audience or parsed.tone:
            u_pts += 10
        if parsed.payload_text:
            u_pts = min(u_pts + 8, 100)
        user_score = min(u_pts, 100)

    n_slots_used = sum(1 for v in form_data.values() if isinstance(v, str) and v.strip())
    info_gain = 0
    info_gain += min(n_slots_used * 6, 18)
    info_gain += min(len(parsed.neg_constraints) * 5, 10)
    if user_example and user_example.strip():
        info_gain += 8
    if user_corrected:
        info_gain += 4
    info_gain = min(info_gain, 40)

    actions_cfg = KNOWLEDGE_BASE.get("actions", {})
    weights = actions_cfg.get(parsed.action, {}).get(
        "rubric_weights",
        {"rol": 0.15, "objetivo": 0.25, "contexto": 0.20, "instrucciones": 0.25, "formato": 0.15},
    )

    if is_trivial:
        dim_scores = {"rol": 0.55, "objetivo": 0.35, "contexto": 0.30, "instrucciones": 0.45, "formato": 0.50}
    else:
        has_role = "# Rol" in improved_prompt or "Actúa como" in improved_prompt
        has_obj = "# Objetivo" in improved_prompt or "Objetivo:" in improved_prompt
        has_inst = "# Instrucciones" in improved_prompt or "1." in improved_prompt
        has_fmt = "# Formato" in improved_prompt or bool(parsed.deliverable)

        has_audience_or_slot = bool(
            parsed.audience
            or n_slots_used > 0
            or parsed.roles.get("perspectiva")
            or parsed.roles.get("canal")
            or parsed.roles.get("rol_simular")
            or any(k in form_data for k in ("Nivel Educativo", "Público", "comm_audience", "edu_level"))
        )

        dim_scores = {
            "rol": 1.0 if has_role else 0.4,
            "objetivo": 1.0 if (has_obj and parsed.word_count >= 5) else 0.7,
            "contexto": 1.0 if has_audience_or_slot else 0.70,
            "instrucciones": 1.0 if (has_inst and level in ("Completa", "Profunda")) else 0.78,
            "formato": 1.0 if has_fmt else 0.7,
        }

    weighted_total = sum(dim_scores[d] * weights.get(d, 0.2) for d in dim_scores) * 100.0

    penalties = len(parsed.contradictions) * 8
    if "[PEGA AQUÍ" in improved_prompt or "[PEGÁ ACÁ" in improved_prompt:
        penalties += 5

    final_score = int(round(max(min(weighted_total - penalties, 100), 10)))
    if is_trivial:
        final_score = min(final_score, 48)

    breakdown = {
        "Rol y Experiencia": int(round(dim_scores["rol"] * 20)),
        "Objetivo y Claridad": int(round(dim_scores["objetivo"] * 20)),
        "Contexto y Público": int(round(dim_scores["contexto"] * 20)),
        "Instrucciones y Pasos": int(round(dim_scores["instrucciones"] * 20)),
        "Formato y Delimitación": int(round(dim_scores["formato"] * 20)),
    }

    n_intents = 1 + len(parsed.secondary_actions)
    info_density = round(
        (len(parsed.entities) + len(parsed.neg_constraints) + n_slots_used + n_intents)
        / max(parsed.word_count, 1),
        3,
    )

    return {
        "user_score": user_score,
        "information_gain": info_gain,
        "final_score": final_score,
        "quality_gain": max(final_score - user_score, 0),
        "n_slots_used": n_slots_used,
        "n_intents": n_intents,
        "info_density": info_density,
        "noise_ratio": noise_ratio,
        "anchor_coverage": anchor_coverage,
        "breakdown": breakdown,
        "weights_used": weights,
        "penalties": penalties,
    }


def calculate_rubric_score(text: str) -> Dict[str, Any]:
    """Función compatible para evaluación rápida de textos ya guardados o sueltos."""
    clean = (text or "").strip()
    norm = _strip_accents(clean.lower())
    words = len(clean.split())
    if words < 3 or norm in TRIVIAL_GREETINGS:
        return {
            "total": 25,
            "breakdown": {
                "Rol y Experiencia": 5,
                "Objetivo y Claridad": 5,
                "Contexto y Público": 5,
                "Instrucciones y Pasos": 5,
                "Formato y Delimitación": 5,
            },
        }
    has_role = 20 if ("# rol" in norm or "actua como" in norm) else 8
    has_obj = 20 if ("# objetivo" in norm or words >= 8) else 10
    has_ctx = 20 if ("# contexto" in norm or "publico" in norm or "nivel" in norm) else 12
    has_inst = 20 if ("# instrucciones" in norm or "1." in norm) else 10
    has_fmt = 20 if ("# formato" in norm or "<datos_entrada>" in norm) else 10
    total = has_role + has_obj + has_ctx + has_inst + has_fmt
    return {
        "total": total,
        "breakdown": {
            "Rol y Experiencia": has_role,
            "Objetivo y Claridad": has_obj,
            "Contexto y Público": has_ctx,
            "Instrucciones y Pasos": has_inst,
            "Formato y Delimitación": has_fmt,
        },
    }


# ---------------------------------------------------------------------------
# ETAPA 6: Ensamblador Composicional Híbrido (v5.0 Micro-Directivas + v6.0 Cola Larga)
# ---------------------------------------------------------------------------

def _assemble_prompt_with_segments(
    parsed: ParsedRequest,
    form_data: Dict[str, Any],
    level: str,
    technique: str,
    user_example: str = "",
    mask_pii: bool = False,
) -> Tuple[str, List[Dict[str, str]], Dict[str, Any]]:
    domains_cfg = KNOWLEDGE_BASE.get("domains", {})
    actions_cfg = KNOWLEDGE_BASE.get("actions", {})
    deliv_cfg = KNOWLEDGE_BASE.get("deliverables", {})
    success_cfg = KNOWLEDGE_BASE.get("success_criteria", {})

    dom_info = domains_cfg.get(parsed.domain, domains_cfg.get("Otro / General", {}))
    act_info = actions_cfg.get(parsed.action, actions_cfg.get("explicar_concepto", {}))

    custom_role = form_data.get("Rol que debe asumir la IA")
    if custom_role:
        role_text = f"Actúa como {custom_role} con experiencia práctica en el área."
        role_source = "user"
        role_rule = "Rol personalizado ingresado por el usuario"
        role_plain = f"Agregado porque definiste el rol '{custom_role}'."
    elif parsed.action == "simular_practicar" and parsed.roles.get("rol_simular"):
        role_text = f"Actúa estrictamente como {parsed.roles['rol_simular']} en una simulación interactiva realista."
        role_source = "inferred"
        role_rule = "Rol dramático extraído para simulación"
        role_plain = f"Elegido automáticamente porque pediste simular ser '{parsed.roles['rol_simular']}'."
    elif parsed.action == "auditar_criticar" and parsed.roles.get("perspectiva"):
        role_text = f"Actúa como un Revisor de Riesgos y Contratos que defiende los intereses del {parsed.roles['perspectiva']}."
        role_source = "inferred"
        role_rule = "Rol auditor adaptado a la perspectiva del usuario"
        role_plain = f"Elegido automáticamente porque revisás riesgos como '{parsed.roles['perspectiva']}'."
    else:
        role_text = dom_info.get("role", "Actúa como un asistente experto multidisciplinario.")
        role_source = "inferred"
        role_rule = f"Rol especializado del dominio '{parsed.domain}'"
        role_plain = f"Elegido automáticamente porque tu pedido trata sobre '{parsed.domain}'."

    rewritten, adj_notes = rewrite_goal(parsed, mask_pii=mask_pii)
    fidelity = check_fidelity(parsed.raw_text, rewritten, parsed)
    objetivo_text = fidelity["goal"]

    # Seleccionar micro-directivas de tema (v5.0) + sintetizador universal (v6.0)
    directives = select_directives(parsed, level=level)
    use_universal = (
        parsed.action in UNIVERSAL_V6_ACTIONS
        or (len(directives) == 0 and parsed.action not in CORE_V5_ACTIONS)
        or (parsed.calc_info.get("has_calculation") and not directives)
        or (parsed.payload_info.get("payload_kind") == "lista_registros")
    )

    univ = synthesize_universal_directives(
        archetype=parsed.action,
        roles=parsed.roles,
        payload_info=parsed.payload_info,
        calc_info=parsed.calc_info,
        level=level,
    ) if use_universal else None

    # Contexto real (sin secciones vacías)
    ctx_lines: List[str] = []
    if parsed.filenames:
        ctx_lines.append(f"- **Archivos:** {', '.join(parsed.filenames)}")
    if parsed.entities:
        ctx_lines.append(f"- **Herramientas / Conceptos:** {', '.join(parsed.entities[:8])}")
    if parsed.errors_detected:
        ctx_lines.append(f"- **Errores detectados:** {', '.join(parsed.errors_detected)}")
    if parsed.roles.get("perspectiva"):
        ctx_lines.append(f"- **Perspectiva:** {parsed.roles['perspectiva']}")
    if parsed.roles.get("canal"):
        ctx_lines.append(f"- **Canal:** {parsed.roles['canal']}")
    if parsed.roles.get("formato_destino"):
        ctx_lines.append(f"- **Formato solicitado:** {parsed.roles['formato_destino']}")
    if parsed.roles.get("campos_esquema"):
        ctx_lines.append(f"- **Campos esperados:** {', '.join(parsed.roles['campos_esquema'])}")
    if parsed.payload_info.get("payload_kind") != "sin_insumo":
        ctx_lines.append(f"- **Insumo adjunto:** {parsed.payload_info.get('summary_label')}")
    if parsed.audience:
        ctx_lines.append(f"- **Público / Nivel:** {parsed.audience}")
    if parsed.tone:
        ctx_lines.append(f"- **Tono:** {parsed.tone}")
    if parsed.language:
        ctx_lines.append(f"- **Idioma:** {parsed.language}")
    if parsed.ontology_objects and not use_universal:
        ontology = KNOWLEDGE_BASE.get("object_ontology", {})
        for obj_k in parsed.ontology_objects:
            delivs = ontology.get(obj_k, {}).get("deliverables", [])
            if delivs:
                ctx_lines.append(f"- **Desglose de {obj_k}:** {'; '.join(delivs)}")

    for k, v in form_data.items():
        if v and k not in ("Rol que debe asumir la IA", "Formato de Salida"):
            ctx_lines.append(f"- **{k}:** {v}")

    # Instrucciones composicionales
    inst_lines: List[str] = []
    seen_inst = set()
    if univ and univ["instructions"]:
        for ul in univ["instructions"]:
            if ul not in seen_inst:
                seen_inst.add(ul)
                inst_lines.append(ul)
        # Cuando sintetizamos por arquetipo universal, solo anexamos restricciones estrictas de usuario (prioridad 95)
        active_directives = [d for d in directives if d.get("priority", 0) >= 95]
    else:
        active_directives = directives

    for d in active_directives:
        txt = d["text_short"] if level == "Ligera" else d["text"]
        if txt not in seen_inst:
            seen_inst.add(txt)
            inst_lines.append(txt)

    if len(inst_lines) < 2:
        for base_inst in act_info.get("instructions", []):
            if base_inst not in seen_inst:
                seen_inst.add(base_inst)
                inst_lines.append(base_inst)
                if len(inst_lines) >= 4:
                    break

    for note in adj_notes:
        if note not in seen_inst:
            seen_inst.add(note)
            inst_lines.append(note)

    # Restricciones reales (solo si existen)
    restr_lines: List[str] = []
    if univ and univ["restrictions"]:
        for ur in univ["restrictions"]:
            restr_lines.append(f"- {ur}")
    for nc in parsed.neg_constraints:
        line_nc = f"- Restricción del usuario: {nc}."
        if line_nc not in restr_lines:
            restr_lines.append(line_nc)
    for qc in parsed.quant_constraints:
        restr_lines.append(f"- Límite cuantitativo: {qc}.")

    # Formato de salida
    deliv_info = deliv_cfg.get(parsed.deliverable, {})
    fmt_instruction = (
        univ["format_override"]
        if (univ and univ.get("format_override"))
        else deliv_info.get(
            "format_instruction",
            f"Presenta la respuesta en formato **{parsed.deliverable}**, con títulos claros en Markdown.",
        )
    )

    # Criterio de éxito verificable
    success_parts: List[str] = []
    if univ and univ["success_criteria"]:
        for sc in univ["success_criteria"]:
            success_parts.append(f"- {sc}")
    act_crit = success_cfg.get("by_action", {}).get(parsed.action, "")
    if act_crit and not (univ and univ["success_criteria"]):
        success_parts.append(f"- {act_crit}")
    deliv_crit = success_cfg.get("by_deliverable", {}).get(parsed.deliverable, "")
    if deliv_crit:
        success_parts.append(f"- {deliv_crit}")
    for d in active_directives[:3]:
        if d.get("verifiable"):
            success_parts.append(f"- {d['verifiable']}")

    verifiable_ratio = univ["verifiable_ratio"] if univ else round(min(max(len(success_parts) / max(len(inst_lines), 1), 0.75), 1.0), 3)

    tech_info = TECHNIQUE_BLOCKS.get(technique, TECHNIQUE_BLOCKS["Estándar"])
    tech_block = tech_info.get("block", "")

    example_block = ""
    if user_example and user_example.strip():
        example_block = f"\n\n# Ejemplo de referencia\n{user_example.strip()}"

    placeholder_block = ""
    if parsed.payload_text:
        p_txt = parsed.payload_text
        if mask_pii:
            p_txt, _ = detect_and_mask_pii(p_txt)
        placeholder_block = (
            f"\n\n# Entrada / Datos disponibles\n"
            f"Procesa únicamente el insumo delimitado a continuación:\n"
            f"<datos_entrada>\n{p_txt}\n</datos_entrada>"
        )
    elif parsed.needs_placeholder:
        ph_tag = parsed.placeholder_custom or f"[PEGA AQUÍ TU {parsed.placeholder_label}]"
        placeholder_block = (
            f"\n\n# Entrada / Datos disponibles\n"
            f"Analiza únicamente el contenido delimitado aquí:\n"
            f"<datos_entrada>\n{ph_tag}\n</datos_entrada>"
        )

    segments: List[Dict[str, str]] = []
    anchor_hint = ", ".join(
        parsed.filenames
        or parsed.entities[:3]
        or ([parsed.payload_info["summary_label"]] if parsed.payload_info.get("payload_kind") != "sin_insumo" else [])
        or [parsed.roles.get("tema")] if parsed.roles.get("tema") else [parsed.domain]
    )

    if univ and univ.get("compact_mode") and level != "Profunda":
        raw_improved = f"Objetivo: {objetivo_text}\n1. " + "\n2. ".join(inst_lines[:2])
        segments.append({
            "source": "user", "block": "Consulta directa", "text": objetivo_text,
            "rule": "Modo consulta directa breve",
            "rule_plain": "Formato directo sin encabezados para consultas puntuales.",
        })
    elif level == "Ligera":
        lines = [f"({role_text})" if custom_role else "", f"Objetivo: {objetivo_text}"]
        lines = [ln for ln in lines if ln]
        for idx, il in enumerate(inst_lines[:4], 1):
            lines.append(f"{idx}. {il}")
        lines.append(f"Formato: {fmt_instruction}")
        if restr_lines:
            lines.append("Restricciones: " + "; ".join(parsed.neg_constraints or parsed.quant_constraints or [r.lstrip("- ") for r in restr_lines]))
        if technique != "Estándar":
            lines.append(f"Nota de técnica ({tech_info['name']}): {tech_info['desc']}")
        raw_improved = "\n".join(lines) + example_block + placeholder_block

        segments.append({
            "source": "user", "block": "Objetivo", "text": objetivo_text,
            "rule": "Reescritura fiel del pedido",
            "rule_plain": f"Tu pedido original limpiado y enfocado en {anchor_hint}.",
        })
        segments.append({
            "source": "scaffold", "block": "Micro-directivas", "text": "\n".join(inst_lines[:4]),
            "rule": "Directivas seleccionadas",
            "rule_plain": f"Agregado porque mencionaste {anchor_hint}.",
        })
        segments.append({
            "source": "inferred", "block": "Formato", "text": fmt_instruction,
            "rule": f"Entregable '{parsed.deliverable}'",
            "rule_plain": f"Formato elegido para entregar '{parsed.deliverable}'.",
        })
    else:
        sections: List[str] = [
            f"# Rol\n{role_text}",
            f"# Objetivo\n{objetivo_text}",
        ]
        segments.append({
            "source": role_source, "block": "Rol", "text": role_text,
            "rule": role_rule, "rule_plain": role_plain,
        })
        segments.append({
            "source": "user", "block": "Objetivo", "text": objetivo_text,
            "rule": "Reescritura fiel del pedido",
            "rule_plain": f"Tu idea original limpiada conservando tus datos ({anchor_hint}).",
        })

        if ctx_lines:
            ctx_txt = "\n".join(ctx_lines)
            sections.append(f"# Contexto\n{ctx_txt}")
            segments.append({
                "source": "inferred", "block": "Contexto", "text": ctx_txt,
                "rule": "Roles, insumos y parámetros detectados",
                "rule_plain": f"Detectado automáticamente a partir de {anchor_hint}.",
            })

        inst_txt = "\n".join(f"{i + 1}. {line}" for i, line in enumerate(inst_lines))
        sections.append(f"# Instrucciones\n{inst_txt}")
        segments.append({
            "source": "scaffold", "block": "Instrucciones", "text": inst_txt,
            "rule": "Síntesis universal" if use_universal else f"Micro-directivas ({len(directives)} activadas)",
            "rule_plain": f"Pasos específicos agregados para '{parsed.action_label}' ({anchor_hint}).",
        })

        if restr_lines:
            restr_txt = "\n".join(restr_lines)
            sections.append(f"# Restricciones\n{restr_txt}")
            segments.append({
                "source": "user", "block": "Restricciones", "text": restr_txt,
                "rule": "Restricciones operacionales",
                "rule_plain": "Reglas estrictas que pediste evitar o limitar.",
            })

        if tech_block:
            sections.append(tech_block)
            segments.append({
                "source": "scaffold", "block": "Técnica", "text": tech_block,
                "rule": f"Técnica '{technique}'",
                "rule_plain": f"Bloque agregado porque elegiste la técnica '{technique}'.",
            })

        if level == "Profunda":
            missing_items = [s["question"] for s in parsed.suggested_slots[:3]]
            if missing_items:
                sup_txt = "\n".join(f"- Si no se especifica, indicar qué aplica para: {q}" for q in missing_items)
                sections.append(f"# Supuestos y datos faltantes\n{sup_txt}")

            edge_list = [d["edge_cases"] for d in directives if d.get("edge_cases")]
            if univ and univ.get("edge_cases"):
                edge_list.extend(univ["edge_cases"])
            if edge_list:
                edge_txt = "\n".join(f"- {ec}" for ec in edge_list[:5])
                sections.append(f"# Casos borde a contemplar\n{edge_txt}")

            val_list = [d["verifiable"] for d in directives if d.get("verifiable")]
            if univ and univ.get("success_criteria"):
                val_list.extend(univ["success_criteria"])
            if val_list:
                val_txt = "\n".join(f"- Verificar: {v}" for v in val_list[:5])
                sections.append(f"# Validación previa a responder\n{val_txt}")

            dont_list = list(dom_info.get("guardrails", []))
            if parsed.neg_constraints:
                dont_list.extend(f"No violar: {nc}" for nc in parsed.neg_constraints)
            if dont_list:
                dont_txt = "\n".join(f"- {dl}" for dl in dont_list[:4])
                sections.append(f"# Qué no hacer\n{dont_txt}")

        sections.append(f"# Formato de salida\n- {fmt_instruction}")
        segments.append({
            "source": "inferred", "block": "Formato de salida", "text": fmt_instruction,
            "rule": f"Entregable '{parsed.deliverable}'",
            "rule_plain": f"Define la estructura final ({parsed.deliverable}).",
        })

        if success_parts:
            succ_txt = "\n".join(dict.fromkeys(success_parts))
            sections.append(f"# Criterio de éxito\n{succ_txt}")
            segments.append({
                "source": "scaffold", "block": "Criterio de éxito", "text": succ_txt,
                "rule": "Verificación observable",
                "rule_plain": "Lista de chequeo para confirmar que la respuesta de la IA sirve.",
            })

        raw_improved = "\n\n".join(sections) + example_block + placeholder_block
        if placeholder_block:
            segments.append({
                "source": "scaffold", "block": "Entrada / Datos disponibles", "text": placeholder_block.strip(),
                "rule": "Delimitador seguro <datos_entrada>",
                "rule_plain": "Espacio delimitado para tus datos o cláusula de forma segura.",
            })

    extra_anchors = list(parsed.roles.get("campos_esquema") or [])
    if parsed.roles.get("canal"):
        extra_anchors.append(parsed.roles["canal"])
    if parsed.roles.get("perspectiva"):
        extra_anchors.append(parsed.roles["perspectiva"])
    if parsed.roles.get("rol_simular"):
        extra_anchors.append(parsed.roles["rol_simular"])
    if parsed.payload_info.get("extracted_prices"):
        extra_anchors.extend(str(p) for p in parsed.payload_info["extracted_prices"])
    if parsed.calc_info.get("has_calculation"):
        extra_anchors.extend([
            parsed.calc_info["ventas_sobre_venta_fmt"],
            parsed.calc_info["ventas_sobre_costo_fmt"],
        ])

    linted = lint_prompt(raw_improved, parsed, directives, extra_anchors=extra_anchors)
    meta = {
        "directives_used": [d["id"] for d in directives],
        "n_directives": len(directives),
        "noise_ratio": linted["noise_ratio"],
        "anchor_coverage": linted["anchor_coverage"],
        "verifiable_ratio": verifiable_ratio,
        "fidelity_ok": fidelity["fidelity_ok"],
        "used_universal": use_universal,
    }
    return linted["text"], segments, meta


# ---------------------------------------------------------------------------
# API Pública del Servicio (Live Preview + Mejora Completa)
# ---------------------------------------------------------------------------

def analyze_live_preview(
    text: str,
    category: str = "",
    form_data: Optional[Dict[str, Any]] = None,
    technique: str = "Estándar",
    override_domain: str = "",
    override_action: str = "",
    override_deliverable: str = "",
    negative_constraints: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Diagnóstico en vivo (<20ms) sin persistencia en base de datos."""
    form_data = form_data or {}
    parsed = parse_request(
        user_text=text,
        category=category,
        form_data=form_data,
        technique=technique,
        override_domain=override_domain,
        override_action=override_action,
        override_deliverable=override_deliverable,
        negative_constraints=negative_constraints,
    )
    rubric = calculate_rubric_v2(
        parsed=parsed,
        improved_prompt="",
        form_data=form_data,
        level="Completa",
    )
    return {
        "engine_version": ENGINE_VERSION,
        "domain": parsed.domain,
        "action": parsed.action,
        "action_label": parsed.action_label,
        "subintent": parsed.subintent,
        "ontology_objects": parsed.ontology_objects,
        "secondary_actions": parsed.secondary_actions,
        "deliverable": parsed.deliverable,
        "audience": parsed.audience,
        "tone": parsed.tone,
        "confidence": parsed.confidence,
        "margin": parsed.margin,
        "needs_disambiguation": parsed.needs_disambiguation,
        "is_vague": parsed.is_vague,
        "suggested_paths": parsed.suggested_paths,
        "entities": parsed.entities,
        "versions": parsed.versions,
        "filenames": parsed.filenames,
        "errors_detected": parsed.errors_detected,
        "neg_constraints": parsed.neg_constraints,
        "quant_constraints": parsed.quant_constraints,
        "contradictions": parsed.contradictions,
        "pii_warnings": parsed.pii_warnings,
        "has_pii": parsed.has_pii_masked,
        "suggested_slots": parsed.suggested_slots,
        "payload_kind": parsed.payload_info.get("payload_kind", "sin_insumo"),
        "payload_summary": parsed.payload_info.get("summary_label", "Sin insumo pegado"),
        "roles_filled": parsed.roles.get("roles_filled", 0.0),
        "has_calculation": parsed.calc_info.get("has_calculation", False),
        "calc_info": parsed.calc_info,
        "user_score": rubric["user_score"],
        "info_density": rubric["info_density"],
        "trace": parsed.trace,
    }


def get_gemini_response(
    user_text: str,
    category: str = "Otro / General",
    form_data: Optional[Dict[str, Any]] = None,
    level: str = "Completa",
    technique: str = "Estándar",
    override_domain: str = "",
    override_action: str = "",
    override_deliverable: str = "",
    negative_constraints: Optional[List[str]] = None,
    user_example: str = "",
    mask_pii: bool = False,
) -> Dict[str, Any]:
    form_data = form_data or {}
    clean_input = (user_text or "").strip()
    if len(clean_input) < 3:
        return {"error": "Por favor escribe al menos 3 caracteres para poder analizar y mejorar tu prompt."}

    if technique not in TECHNIQUE_BLOCKS:
        technique = "Estándar"
    if level not in ("Ligera", "Completa", "Profunda"):
        level = "Completa"

    user_corrected = bool(override_domain or override_action or override_deliverable)

    parsed = parse_request(
        user_text=clean_input,
        category=category,
        form_data=form_data,
        technique=technique,
        override_domain=override_domain,
        override_action=override_action,
        override_deliverable=override_deliverable,
        negative_constraints=negative_constraints,
    )

    improved_prompt, segments, meta = _assemble_prompt_with_segments(
        parsed=parsed,
        form_data=form_data,
        level=level,
        technique=technique,
        user_example=user_example,
        mask_pii=mask_pii,
    )

    rubric = calculate_rubric_v2(
        parsed=parsed,
        improved_prompt=improved_prompt,
        form_data=form_data,
        user_example=user_example,
        user_corrected=user_corrected,
        level=level,
        noise_ratio=meta["noise_ratio"],
        anchor_coverage=meta["anchor_coverage"],
    )

    analysis = [
        f"Motor {ENGINE_VERSION} | Dominio: '{parsed.domain}' | Arquetipo: '{parsed.action_label}' ({parsed.subintent}) — confianza {int(parsed.confidence * 100)}%.",
        f"Directivas: {meta['n_directives']} | Datos útiles: {int(meta['anchor_coverage'] * 100)}% | Relleno: {int(meta['noise_ratio'] * 100)}% | Verificables: {int(meta['verifiable_ratio'] * 100)}%.",
        f"Puntaje: entrada {rubric['user_score']}/100 → final {rubric['final_score']}/100 (+{rubric['quality_gain']} pts, aporte usuario +{rubric['information_gain']} pts).",
    ]
    if parsed.payload_info.get("payload_kind") != "sin_insumo":
        analysis.append(f"Insumo detectado: {parsed.payload_info.get('summary_label')}.")
    if parsed.calc_info.get("has_calculation"):
        analysis.append(
            f"Cálculo determinístico verificado: venta base {parsed.calc_info['ventas_sobre_venta_fmt']} "
            f"(markup sobre costo {parsed.calc_info['ventas_sobre_costo_fmt']})."
        )
    if parsed.contradictions:
        analysis.append("Advertencia: " + " ".join(parsed.contradictions))
    if parsed.pii_warnings:
        analysis.append(f"Privacidad: se detectaron {len(parsed.pii_warnings)} tipo(s) de datos sensibles.")

    stored_original = parsed.masked_text if (mask_pii and parsed.has_pii_masked) else clean_input

    return {
        "engine_version": ENGINE_VERSION,
        "raw_objective": stored_original,
        "rewritten_goal": parsed.rewritten_goal,
        "improved_prompt": improved_prompt,
        "analysis": analysis,
        "initial_score": rubric["user_score"],
        "user_score": rubric["user_score"],
        "information_gain": rubric["information_gain"],
        "final_score": rubric["final_score"],
        "quality_gain": rubric["quality_gain"],
        "rubric_breakdown": rubric["breakdown"],
        "rubric_weights": rubric["weights_used"],
        "technique": technique,
        "category": parsed.domain,
        "domain": parsed.domain,
        "detected_action": parsed.action,
        "action_label": parsed.action_label,
        "subintent": parsed.subintent,
        "ontology_objects": parsed.ontology_objects,
        "secondary_actions": parsed.secondary_actions,
        "detected_deliverable": parsed.deliverable,
        "intent_confidence": parsed.confidence,
        "intent_margin": parsed.margin,
        "n_intents": rubric["n_intents"],
        "n_entities": len(parsed.entities),
        "entities": parsed.entities,
        "n_neg_constraints": len(parsed.neg_constraints),
        "neg_constraints": parsed.neg_constraints,
        "quant_constraints": parsed.quant_constraints,
        "contradictions": parsed.contradictions,
        "n_slots_used": rubric["n_slots_used"],
        "info_density": rubric["info_density"],
        "noise_ratio": meta["noise_ratio"],
        "anchor_coverage": meta["anchor_coverage"],
        "verifiable_ratio": meta["verifiable_ratio"],
        "payload_kind": parsed.payload_info.get("payload_kind", "sin_insumo"),
        "payload_summary": parsed.payload_info.get("summary_label", "Sin insumo pegado"),
        "payload_info": parsed.payload_info,
        "roles_filled": parsed.roles.get("roles_filled", 0.0),
        "roles": parsed.roles,
        "has_calculation": parsed.calc_info.get("has_calculation", False),
        "calc_info": parsed.calc_info,
        "directives_used": meta["directives_used"],
        "n_directives": meta["n_directives"],
        "fidelity_ok": meta["fidelity_ok"],
        "user_corrected": user_corrected,
        "has_pii_masked": bool(mask_pii and parsed.has_pii_masked),
        "pii_warnings": parsed.pii_warnings,
        "needs_disambiguation": parsed.needs_disambiguation,
        "is_vague": parsed.is_vague,
        "suggested_paths": parsed.suggested_paths,
        "suggested_slots": parsed.suggested_slots,
        "segments": segments,
        "trace": parsed.trace,
    }
