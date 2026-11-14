import json
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ENGINE_VERSION = "v4.0"

KB_PATH = Path(__file__).resolve().parent / "rules" / "knowledge_base.json"


def _load_knowledge_base() -> Dict[str, Any]:
    with open(KB_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


KNOWLEDGE_BASE = _load_knowledge_base()

# Mapeo de categorías heredadas (v1-v3) a los 10 dominios especializados (v4.0)
LEGACY_DOMAIN_ALIASES = {
    "Aprender y enseñar": "Estudio y academia",
    "Crear y comunicar": "Redacción y comunicación",
    "Trabajo y productividad": "Planificación y productividad",
    "Vida personal y organización": "Planificación y productividad",
    "Otro / No sé": "Otro / General",
    "Ninguna especificada": "",
}

TECHNIQUE_BLOCKS = {
    "Estándar": {
        "name": "Estructura Estándar",
        "block": "",
        "desc": "Organización clásica por bloques (Rol, Objetivo, Contexto, Instrucciones y Formato).",
    },
    "Paso a Paso": {
        "name": "Razonamiento Paso a Paso",
        "block": (
            "# Método de Resolución (Paso a Paso)\n"
            "1. **Análisis inicial:** Comprende el problema e identifica los datos clave antes de responder.\n"
            "2. **Desarrollo secuencial:** Resuelve la solicitud dividiendo la explicación en etapas ordenadas y lógicas.\n"
            "3. **Conclusión práctica:** Cierra con una recomendación o resultado listo para aplicar."
        ),
        "desc": "Guía a la IA para que divida problemas complejos en etapas lógicas (Chain-of-Thought).",
    },
    "Con Ejemplos": {
        "name": "Guiado con Ejemplos (Few-Shot)",
        "block": (
            "# Guía de Ejemplo (Referencia de Calidad)\n"
            "- Incluye al menos **2 ejemplos prácticos** (Caso de entrada → Resultado esperado) para ilustrar cada punto importante.\n"
            "- Si muestras código o fórmulas, acompaña cada bloque con un caso de uso real comentado."
        ),
        "desc": "Exige casos prácticos de muestra (Entrada → Salida) para asegurar respuestas concretas.",
    },
    "Pedagógico": {
        "name": "Modo Pedagógico / Explicativo",
        "block": (
            "# Enfoque Didáctico\n"
            "- Explica cada término técnico con una analogía sencilla de la vida cotidiana.\n"
            "- Ordena la explicación de menor a mayor dificultad.\n"
            "- Al finalizar, incluye 3 preguntas breves de autoevaluación para comprobar lo aprendido."
        ),
        "desc": "Ideal para estudiar: usa analogías simples, progresión gradual y preguntas de repaso.",
    },
    "Verificación": {
        "name": "Control de Calidad y Precisión",
        "block": (
            "# Reglas de Control y Verificación\n"
            "- **Cero suposiciones:** No inventes datos, cifras ni funciones que no existan.\n"
            "- **Datos faltantes:** Si falta algún dato indispensable para dar una respuesta exacta, indícalo claramente al inicio.\n"
            "- **Revisión final:** Comprueba que la respuesta cumpla con todas las restricciones antes de entregarla."
        ),
        "desc": "Añade restricciones estrictas contra errores y datos inventados (Auditoría de Calidad).",
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

    # Etapa 4: Clasificación Ortogonal
    domain: str = "Otro / General"
    action: str = "explicar_concepto"
    action_label: str = "Explicar concepto"
    secondary_actions: List[str] = field(default_factory=list)
    deliverable: str = "informe estructurado"
    audience: str = ""
    tone: str = ""
    language: str = ""
    confidence: float = 0.0
    margin: float = 0.0
    needs_disambiguation: bool = False
    suggested_slots: List[Dict[str, Any]] = field(default_factory=list)
    needs_placeholder: bool = False
    placeholder_label: str = "DATOS O TEXTO"

    # Etapa 5 & 6: Trazabilidad
    trace: List[Dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# ETAPA 1: Normalización, Voseo y Lematización Ligera
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

    # Separación de clíticos verbales rioplatenses/españoles
    raw_tokens = re.findall(r"[a-z0-9_+#.-]+", lowered)
    normalized_tokens: List[str] = []
    lemmas: List[str] = []

    for tok in raw_tokens:
        base = CLITIC_STEM_MAP.get(tok)
        if not base:
            m = re.match(r"^([a-z]{4,})(?:melo|mela|melos|melas|noslo|me|te|lo|la|nos)$", tok)
            if m and len(m.group(1)) >= 4:
                base = m.group(1)
            else:
                base = tok
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

    # Detección de contradicciones
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
# ETAPA 4: Clasificación Ortogonal + Multi-Intención + TF-IDF Coseno
# ---------------------------------------------------------------------------

def _tokenize_for_tfidf(text: str) -> List[str]:
    _, tokens, lemmas = normalize_and_lemmatize(text)
    filtered = [t for t in tokens if t not in SPANISH_STOPWORDS and len(t) > 1]
    filtered_lemmas = [l for l in lemmas if l not in SPANISH_STOPWORDS and len(l) > 1]
    return filtered + filtered_lemmas


class _ActionTfIdfIndex:
    """Índice TF-IDF en Python puro sobre los prototipos de acciones."""

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
        vec = {
            term: (cnt / total) * self.idf.get(term, 1.0)
            for term, cnt in counts.items()
            if term in self.idf
        }
        return vec

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
                    lex_hits += 1.4
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
    }
    return default_by_action.get(action, "informe estructurado")


def _select_suggested_slots(domain: str, action: str, form_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    catalog = KNOWLEDGE_BASE.get("slot_catalog", {})
    candidates: List[Dict[str, Any]] = []
    candidates.extend(catalog.get("by_domain", {}).get(domain, []))
    candidates.extend(catalog.get("by_action", {}).get(action, []))

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
    if any(w in normalized_text for w in ("este texto", "este correo", "este codigo", "este csv", "este dataset", "este error", "estos datos")):
        needs_placeholder = True
        if "codigo" in normalized_text or "error" in normalized_text:
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

    # Etapa 1
    norm_text, tokens, lemmas = normalize_and_lemmatize(req.raw_text)
    req.normalized_text = norm_text
    req.tokens = tokens
    req.lemmas = lemmas
    req.word_count = len(req.raw_text.split())

    # Etapa 2
    masked_text, pii_warnings = detect_and_mask_pii(req.raw_text)
    req.masked_text = masked_text
    req.pii_warnings = pii_warnings
    req.has_pii_masked = bool(pii_warnings)

    # Etapa 3
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

    # Etapa 4: Dominio, Acción (Multi-intención + TF-IDF), Entregable
    domain_hint = override_domain or category
    req.domain, dom_trace = _classify_domain(norm_text, domain_hint)
    req.trace.extend(dom_trace)

    # Multi-intención: segmentación por conectores
    segments_raw = [s.strip() for s in SEGMENT_CONNECTORS_RE.split(req.raw_text) if s.strip()]
    if not segments_raw:
        segments_raw = [req.raw_text]

    global_scores = _score_actions(req.raw_text, norm_text)
    ranked = sorted(global_scores.items(), key=lambda kv: kv[1], reverse=True)
    top1_action, top1_score = ranked[0]
    top2_score = ranked[1][1] if len(ranked) > 1 else 0.0

    # Si no hay señal fuerte en absoluto, fallback a explicar_concepto
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
        req.deliverable = _classify_deliverable(norm_text, req.action, form_data)

    mods = _extract_context_modifiers(norm_text)
    req.audience = mods["audience"]
    req.tone = mods["tone"]
    req.language = mods["language"]
    req.needs_placeholder = mods["needs_placeholder"] or (req.action == "depurar_error" and not req.code_snippets)
    req.placeholder_label = mods["placeholder_label"]

    if req.margin < 0.15 or req.word_count < 5:
        req.needs_disambiguation = True
    req.suggested_slots = _select_suggested_slots(req.domain, req.action, form_data)

    req.trace.append({
        "stage": "classification",
        "domain": req.domain,
        "action": req.action,
        "secondary_actions": req.secondary_actions,
        "deliverable": req.deliverable,
        "confidence": req.confidence,
        "margin": req.margin,
        "needs_disambiguation": req.needs_disambiguation,
    })
    return req


# ---------------------------------------------------------------------------
# ETAPA 5: Rúbrica v2 No Circular (calculate_rubric_v2) + compatibilidad
# ---------------------------------------------------------------------------

def calculate_rubric_v2(
    parsed: ParsedRequest,
    improved_prompt: str,
    form_data: Dict[str, Any],
    user_example: str = "",
    user_corrected: bool = False,
    level: str = "Completa",
) -> Dict[str, Any]:
    """
    Rúbrica v2 no circular:
    - user_score (0-100): evalúa únicamente la riqueza del texto original del usuario.
    - information_gain (0-40): puntos aportados por el usuario (slots, restricciones, ejemplos, chips).
    - final_score (0-100): evalúa las 5 dimensiones ponderadas por rubric_weights de la intención.
    """
    norm = parsed.normalized_text
    is_trivial = norm in TRIVIAL_GREETINGS or parsed.word_count < 3

    # 1. user_score (0-100) sobre el input crudo
    if is_trivial:
        user_score = 18 if parsed.word_count >= 2 else 12
    else:
        u_pts = 20  # base por tener solicitud
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
        user_score = min(u_pts, 100)

    # 2. information_gain (0-40) por aportes explícitos del usuario
    n_slots_used = sum(1 for v in form_data.values() if isinstance(v, str) and v.strip())
    info_gain = 0
    info_gain += min(n_slots_used * 6, 18)
    info_gain += min(len(parsed.neg_constraints) * 5, 10)
    if user_example and user_example.strip():
        info_gain += 8
    if user_corrected:
        info_gain += 4
    info_gain = min(info_gain, 40)

    # 3. final_score (0-100) ponderado por rubric_weights de la intención
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

    # Penalizaciones explícitas
    penalties = len(parsed.contradictions) * 8
    if "[PEGA AQUÍ" in improved_prompt or "[COMPLETAR" in improved_prompt:
        penalties += 5

    final_score = int(round(max(min(weighted_total - penalties, 100), 10)))
    if is_trivial:
        final_score = min(final_score, 48)

    # Desglose compatible con UI v3 + v4 (sobre 20 pts c/u para visualización uniforme)
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
# ETAPA 6: Ensamblado con Trazabilidad (segments y trace)
# ---------------------------------------------------------------------------

def _clean_objective_text(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return ""
    cleaned = cleaned[0].upper() + cleaned[1:]
    if cleaned[-1] not in ".!?":
        cleaned += "."
    return cleaned


def _assemble_prompt_with_segments(
    parsed: ParsedRequest,
    form_data: Dict[str, Any],
    level: str,
    technique: str,
    user_example: str = "",
    mask_pii: bool = False,
) -> Tuple[str, List[Dict[str, str]]]:
    domains_cfg = KNOWLEDGE_BASE.get("domains", {})
    actions_cfg = KNOWLEDGE_BASE.get("actions", {})
    deliv_cfg = KNOWLEDGE_BASE.get("deliverables", {})

    dom_info = domains_cfg.get(parsed.domain, domains_cfg.get("Otro / General", {}))
    act_info = actions_cfg.get(parsed.action, actions_cfg.get("explicar_concepto", {}))

    custom_role = form_data.get("Rol que debe asumir la IA")
    if custom_role:
        role_text = f"Actúa como un {custom_role} con amplia experiencia práctica en el área."
        role_source = "user"
        role_rule = "Rol personalizado ingresado por el usuario"
    else:
        role_text = dom_info.get("role", "Actúa como un asistente experto multidisciplinario.")
        role_source = "inferred"
        role_rule = f"Rol especializado del dominio '{parsed.domain}'"

    objective_src_text = parsed.masked_text if mask_pii else parsed.raw_text
    objetivo_text = _clean_objective_text(objective_src_text)

    # Contexto y parámetros
    ctx_lines = [f"- **Dominio:** {parsed.domain}", f"- **Intención principal:** {parsed.action_label}"]
    if parsed.secondary_actions:
        sec_labels = [actions_cfg.get(a, {}).get("label", a) for a in parsed.secondary_actions]
        ctx_lines.append(f"- **Intenciones complementarias:** {', '.join(sec_labels)}")
    if parsed.entities:
        ctx_lines.append(f"- **Tecnologías / Conceptos clave:** {', '.join(parsed.entities[:8])}")
    if parsed.audience:
        ctx_lines.append(f"- **Público / Nivel:** {parsed.audience}")
    if parsed.tone:
        ctx_lines.append(f"- **Tono:** {parsed.tone}")
    if parsed.language:
        ctx_lines.append(f"- **Idioma:** {parsed.language}")

    for k, v in form_data.items():
        if v and k not in ("Rol que debe asumir la IA", "Formato de Salida"):
            ctx_lines.append(f"- **{k}:** {v}")

    # Instrucciones
    inst_list = list(act_info.get("instructions", []))
    for sec in parsed.secondary_actions:
        sec_inst = actions_cfg.get(sec, {}).get("instructions", [])
        if sec_inst:
            inst_list.append(sec_inst[0])
    for nc in parsed.neg_constraints:
        inst_list.append(f"Restricción estricta: {nc}.")
    for qc in parsed.quant_constraints:
        inst_list.append(f"Límite cuantitativo: {qc}.")
    for gr in dom_info.get("guardrails", []):
        inst_list.append(gr)

    instructions_block = "\n".join(f"{i + 1}. {line}" for i, line in enumerate(inst_list))

    # Formato
    deliv_info = deliv_cfg.get(parsed.deliverable, {})
    fmt_instruction = deliv_info.get(
        "format_instruction",
        f"Presenta la respuesta en formato **{parsed.deliverable}**, con títulos claros en Markdown.",
    )

    tech_info = TECHNIQUE_BLOCKS.get(technique, TECHNIQUE_BLOCKS["Estándar"])
    tech_block = tech_info.get("block", "")

    example_block = ""
    if user_example and user_example.strip():
        example_block = f"\n\n# Ejemplo de Referencia (Provisto por el Usuario)\n{user_example.strip()}"

    placeholder_block = ""
    if parsed.needs_placeholder:
        placeholder_block = (
            f"\n\n# Datos de Entrada (Delimitados)\n"
            f"Analiza únicamente el contenido ubicado dentro de las siguientes etiquetas:\n"
            f"<datos_entrada>\n[PEGA AQUÍ TU {parsed.placeholder_label}]\n</datos_entrada>"
        )

    segments: List[Dict[str, str]] = []

    if level == "Ligera":
        parts = [f"({role_text})", f"Objetivo: {objetivo_text}", f"Formato esperado: {fmt_instruction}"]
        if parsed.neg_constraints:
            parts.append("Restricciones: " + "; ".join(parsed.neg_constraints))
        if technique != "Estándar":
            parts.append(f"Nota de técnica ({tech_info['name']}): {tech_info['desc']}")
        improved = "\n\n".join(parts) + example_block + placeholder_block

        segments.append({"source": role_source, "block": "Rol", "text": role_text, "rule": role_rule})
        segments.append({"source": "user", "block": "Objetivo", "text": objetivo_text, "rule": "Texto original del usuario"})
        segments.append({"source": "inferred", "block": "Formato", "text": fmt_instruction, "rule": f"Entregable '{parsed.deliverable}'"})
        return improved, segments

    # Completa o Profunda
    sections: List[str] = [
        f"# Rol\n{role_text}",
        f"# Objetivo\n{objetivo_text}",
        "# Contexto y Parámetros\n" + "\n".join(ctx_lines),
        f"# Instrucciones\n{instructions_block}",
    ]
    segments.append({"source": role_source, "block": "Rol", "text": role_text, "rule": role_rule})
    segments.append({"source": "user", "block": "Objetivo", "text": objetivo_text, "rule": "Texto original del usuario"})
    segments.append({"source": "inferred", "block": "Contexto", "text": "\n".join(ctx_lines), "rule": "Entidades y parámetros detectados"})
    segments.append({"source": "scaffold", "block": "Instrucciones", "text": instructions_block, "rule": f"Pasos de '{parsed.action_label}' + guardrails"})

    if tech_block:
        sections.append(tech_block)
        segments.append({"source": "scaffold", "block": "Técnica", "text": tech_block, "rule": f"Técnica '{technique}'"})
    elif level == "Profunda":
        deep_default = (
            "# Metodología Paso a Paso\n"
            "1. **Comprensión:** Revisa todos los requisitos antes de redactar.\n"
            "2. **Desarrollo:** Explica cada punto en orden lógico.\n"
            "3. **Validación:** Verifica exactitud y cumplimiento del formato."
        )
        sections.append(deep_default)
        segments.append({"source": "scaffold", "block": "Metodología", "text": deep_default, "rule": "Andamiaje de Mejora Profunda"})

    if level == "Profunda":
        quality_sec = (
            "# Criterios de Calidad\n"
            "- Ve directo al grano sin relleno innecesario.\n"
            "- Si falta un dato indispensable, indícalo explícitamente."
        )
        sections.append(quality_sec)
        segments.append({"source": "scaffold", "block": "Criterios de Calidad", "text": quality_sec, "rule": "Criterios de calidad Profunda"})

    sections.append(f"# Formato de Salida\n- {fmt_instruction}")
    segments.append({"source": "inferred", "block": "Formato de Salida", "text": fmt_instruction, "rule": f"Entregable '{parsed.deliverable}'"})

    improved = "\n\n".join(sections) + example_block + placeholder_block
    if placeholder_block:
        segments.append({"source": "scaffold", "block": "Datos de Entrada", "text": placeholder_block.strip(), "rule": "Delimitador seguro <datos_entrada>"})

    return improved, segments


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
        "secondary_actions": parsed.secondary_actions,
        "deliverable": parsed.deliverable,
        "audience": parsed.audience,
        "tone": parsed.tone,
        "confidence": parsed.confidence,
        "margin": parsed.margin,
        "needs_disambiguation": parsed.needs_disambiguation,
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

    improved_prompt, segments = _assemble_prompt_with_segments(
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
    )

    analysis = [
        f"Motor {ENGINE_VERSION} | Dominio: '{parsed.domain}' | Acción: '{parsed.action_label}' (confianza {int(parsed.confidence * 100)}%).",
        f"Entregable objetivo: '{parsed.deliverable}'.",
        f"Rúbrica v2: entrada {rubric['user_score']}/100 → salida {rubric['final_score']}/100 (+{rubric['quality_gain']} pts, aporte usuario +{rubric['information_gain']} pts).",
    ]
    if parsed.contradictions:
        analysis.append("Advertencia: " + " ".join(parsed.contradictions))
    if parsed.pii_warnings:
        analysis.append(f"Privacidad: se detectaron {len(parsed.pii_warnings)} tipo(s) de datos sensibles.")

    stored_original = parsed.masked_text if (mask_pii and parsed.has_pii_masked) else clean_input

    return {
        "engine_version": ENGINE_VERSION,
        "raw_objective": stored_original,
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
        "user_corrected": user_corrected,
        "has_pii_masked": bool(mask_pii and parsed.has_pii_masked),
        "pii_warnings": parsed.pii_warnings,
        "needs_disambiguation": parsed.needs_disambiguation,
        "suggested_slots": parsed.suggested_slots,
        "segments": segments,
        "trace": parsed.trace,
    }
