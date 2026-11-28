import json
import math
import re
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .universal_engine import (
    compute_control_values,
    extract_negative_constraints,
    extract_semantic_roles,
    inspect_attached_payload,
    split_request_payload,
    synthesize_universal_directives,
)
from .scientific_eval import (
    classify_hybrid_action,
    invalidate_scientific_cache,
    match_overlay_rules,
)

ENGINE_VERSION = "v7.2"

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
    "ensename": "ensenar",
    "ensenamelo": "ensenar",
    "ensenar": "ensenar",
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
    "es", "son", "ser", "estan", "muy", "mas", "menos", "pero", "si",
}

# v7.0: muletillas de pedido que no aportan señal semántica al clasificador.
REQUEST_FILLERS = {
    "necesito", "necesitaria", "quiero", "quisiera", "puedo", "podes", "podrias",
    "dame", "ayuda", "ayudar", "hacer", "favor", "hola", "porfa", "porfavor",
    "gracias", "che", "buenas", "please", "algo",
}

# v7.0: léxico de verbos (infinitivos sin tilde) que habilita el recorte de clíticos.
VERB_LEXICON = set(CLITIC_STEM_MAP.values()) | {
    "armar", "explicar", "pasar", "decir", "hacer", "resumir", "comparar", "analizar",
    "escribir", "redactar", "corregir", "arreglar", "depurar", "planificar", "organizar",
    "ensenar", "solucionar", "ayudar", "calcular", "evaluar", "sintetizar", "refactorizar",
    "optimizar", "predecir", "convertir", "revisar", "simular", "auditar", "extraer",
    "clasificar", "traducir", "pulir", "recomendar", "dar", "mostrar", "contar", "mandar",
    "enviar", "generar", "crear", "preparar", "buscar", "listar", "ordenar", "agrupar",
    "sacar", "poner", "dejar", "traer", "leer", "mirar", "chequear", "controlar", "proponer",
    "sugerir", "detallar", "aclarar", "definir", "guiar", "indicar", "marcar", "corregir",
    "reescribir", "mejorar", "acortar", "adaptar", "transformar", "estructurar", "formatear",
    "categorizar", "etiquetar", "decidir", "elegir", "diagnosticar", "resolver", "deducir",
    "demostrar", "practicar", "entrenar", "idear", "proyectar", "modelar", "inventar",
    "pensar", "averiguar", "investigar", "completar", "llenar", "anotar", "tomar",
}

# v7.0: vocabulario protegido (sustantivos, adjetivos y términos técnicos que terminan
# en me/te/lo/la/le/nos pero NO son verbos con clítico).
PROTECTED_WORDS = {
    "clausula", "sqlite", "dataframe", "modelo", "cliente", "principiante", "tramite",
    "informe", "reporte", "articulo", "modulo", "componente", "calculo", "calcula",
    "terminos", "termino", "cuello", "botella", "dependiente", "independiente", "escuela",
    "regla", "tabla", "lista", "planilla", "ejemplo", "titulo", "capitulo", "estado",
    "resultado", "dato", "texto", "proyecto", "archivo", "producto", "negocio", "comercio",
    "contrato", "alquiler", "presupuesto", "formato", "objeto", "criterio", "estilo",
    "nivel", "perfil", "detalle", "parte", "fuente", "limite", "soporte", "paquete",
    "variable", "constante", "siguiente", "diferente", "importante", "excelente", "urgente",
    "frecuente", "docente", "estudiante", "ambiente", "sistema", "problema", "esquema",
    "tema", "programa", "idioma", "norma", "forma", "plataforma", "columna", "pagina",
    "rutina", "oficina", "venta", "cuenta", "nota", "carta", "propuesta", "respuesta",
    "consulta", "pregunta", "alerta", "oferta", "meta", "fecha", "etiqueta", "carpeta",
    "receta", "planeta", "dieta", "simple", "pequeno", "chiquito", "puntaje", "mensaje",
    "correo", "intervalo", "titulo", "vehiculo", "pueblo", "ciclo", "calendario", "vale",
    "simula", "revisa", "audita", "formula", "molecula", "celula", "pelicula", "escala",
    "sala", "mala", "bola", "escuela", "vela", "pantalla", "ventana", "semana", "persona",
}


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def _build_protected_vocabulary() -> set:
    vocab = set(PROTECTED_WORDS)
    for terms in KNOWLEDGE_BASE.get("entities_lexicon", {}).values():
        for term in terms:
            vocab.update(re.findall(r"[a-z0-9_+#.-]+", _strip_accents(term.lower())))
    for section in ("domains", "actions", "deliverables"):
        for cfg in KNOWLEDGE_BASE.get(section, {}).values():
            for kw in cfg.get("keywords", []):
                for tok in re.findall(r"[a-z0-9_+#.-]+", _strip_accents(kw.lower())):
                    if tok not in CLITIC_STEM_MAP:
                        vocab.add(tok)
    for cfg in KNOWLEDGE_BASE.get("object_ontology", {}).values():
        for alias in cfg.get("aliases", []):
            vocab.update(re.findall(r"[a-z0-9_+#.-]+", _strip_accents(alias.lower())))
    return vocab


PROTECTED_VOCAB = _build_protected_vocabulary()

_CLITIC_SUFFIXES = (
    "noslo", "nosla", "melos", "melas", "selos", "selas", "telos", "telas",
    "melo", "mela", "selo", "sela", "telo", "tela", "nos", "les", "los", "las",
    "me", "te", "lo", "la", "le", "se",
)


def _strip_clitic(token: str) -> Optional[str]:
    """
    Devuelve el infinitivo si `token` es un verbo (imperativo voseante o infinitivo)
    con pronombre enclítico. Nunca recorta sustantivos/términos protegidos.
    """
    if token in PROTECTED_VOCAB or len(token) < 5:
        return None
    for suf in _CLITIC_SUFFIXES:
        if not token.endswith(suf):
            continue
        root = token[: -len(suf)]
        if len(root) < 3:
            continue
        # Infinitivo + clítico ("explicarme", "pasarlo")
        if root in VERB_LEXICON:
            return root
        # Imperativo voseante + clítico ("armame" -> arma -> armar, "decime" -> deci -> decir)
        if root[-1] in "aei" and (root + "r") in VERB_LEXICON:
            return root + "r"
    return None


_VERB_SUFFIXES = (
    "aciones", "iciones", "amiento", "imiento", "ieron", "aron", "iendo", "mente",
    "ando", "aste", "iste", "emos", "imos", "aba", "iba", "ado", "ido",
    "ar", "er", "ir", "an", "en",
)


def _light_stem(token: str) -> str:
    if len(token) <= 4 or token in PROTECTED_WORDS:
        return token
    for suffix in _VERB_SUFFIXES:
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
            base = CLITIC_STEM_MAP.get(sub_tok) or _strip_clitic(sub_tok) or sub_tok
            normalized_tokens.append(base)
            lemmas.append(_light_stem(base))

    normalized_text = " ".join(normalized_tokens)
    return normalized_text, normalized_tokens, lemmas


_KW_NORM_CACHE: Dict[str, str] = {}
_KW_BOUNDARY_RE_CACHE: Dict[str, re.Pattern] = {}
_ENT_BOUNDARY_RE_CACHE: Dict[str, re.Pattern] = {}


def _get_kw_boundary_re(kw_norm: str) -> re.Pattern:
    pat = _KW_BOUNDARY_RE_CACHE.get(kw_norm)
    if pat is None:
        pat = re.compile(rf"(?<![a-z0-9]){re.escape(kw_norm)}(?![a-z0-9])")
        _KW_BOUNDARY_RE_CACHE[kw_norm] = pat
    return pat


def _get_ent_boundary_re(term: str) -> re.Pattern:
    pat = _ENT_BOUNDARY_RE_CACHE.get(term)
    if pat is None:
        pat = re.compile(rf"(?<![a-z0-9_]){re.escape(term)}(?![a-z0-9_])")
        _ENT_BOUNDARY_RE_CACHE[term] = pat
    return pat


def _norm_kw(kw: str) -> str:
    """Normaliza una keyword del KB con el mismo pipeline que el texto del usuario
    (así 'armame un plan' -> 'armar un plan' y deja de ser código muerto)."""
    cached = _KW_NORM_CACHE.get(kw)
    if cached is None:
        cached = normalize_and_lemmatize(kw)[0]
        _KW_NORM_CACHE[kw] = cached
    return cached


def _kw_in(kw: str, normalized_text: str) -> bool:
    kw_norm = _norm_kw(kw)
    if not kw_norm:
        return False
    return bool(_get_kw_boundary_re(kw_norm).search(normalized_text))

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
    disambiguation_options: List[Dict[str, str]] = field(default_factory=list)
    is_vague: bool = False
    suggested_paths: List[Dict[str, str]] = field(default_factory=list)
    suggested_slots: List[Dict[str, Any]] = field(default_factory=list)
    active_slot_ids: List[str] = field(default_factory=list)
    topic_anchor: str = ""
    is_conceptual_no_data: bool = False
    needs_placeholder: bool = False
    placeholder_label: str = "DATOS O TEXTO"
    placeholder_custom: str = ""
    facets: List[str] = field(default_factory=list)
    rewritten_goal: str = ""

    # v6.0 Universal Engine
    payload_info: Dict[str, Any] = field(default_factory=dict)
    roles: Dict[str, Any] = field(default_factory=dict)
    calc_info: Dict[str, Any] = field(default_factory=dict)
    is_single_clause: bool = True

    # Etapa 5 & 6: Trazabilidad
    trace: List[Dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# ETAPA 1: Normalización, Abreviaturas, Voseo y Lematización Ligera
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# ETAPA 2: Detección y Anonimización de Datos Sensibles (PII)
# ---------------------------------------------------------------------------

_RE_CBU = re.compile(r"\b\d{22}\b")
_RE_ALIAS_BANK = re.compile(
    r"\b(?:alias(?:\s+(?:cbu|bancario))?\s*[:=]\s*([a-z0-9._-]{6,30})|"
    r"alias(?:\s+(?:cbu|bancario))?\s+(?:de\s+|es\s+)?([a-z0-9_-]{2,}(?:\.[a-z0-9_-]{2,})+))(?![a-z0-9._-])",
    re.IGNORECASE,
)
_RE_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_RE_CELL_15 = re.compile(
    r"(?<!\d)\b(?:11|2\d{2,3}|3\d{2,3})[\s.-]?15[\s.-]?\d{3,4}[\s.-]?\d{3,4}\b(?!\d)"
)
_RE_CUIT_11 = re.compile(r"(?<![$\d-])\b(?:20|23|24|27|30|33|34)\d{9}\b(?![-\d])")
_RE_CUIL_DNI = re.compile(r"(?<![$\d-])\b(?:\d{2}-\d{7,8}-\d|[1-9]\d?\.\d{3}\.\d{3}|\d{7,8})\b(?![-\d])")
_RE_INVOICE_PREFIX = re.compile(
    r"(?:\b(?:factura|fc|comprobante|remito|orden|ticket|recibo)(?:\s+(?:nro|n[°º]|numero|#))?\s*[:=-]?\s*(?:\d{4,5}\s*-\s*)?|\b\d{4,5}\s*-\s*)$",
    flags=re.IGNORECASE,
)
_RE_PII_DOC_LABEL = re.compile(
    r"\b(?:dni|cuil|cuit|documento|doc\.?)\s*[:=-]?\s*$",
    flags=re.IGNORECASE,
)
_RE_MONEY_CTX = re.compile(
    r"(?:\$|\b(?:pesos?|ars|usd|u\$s|d[oó]lares?|d[oó]lar|presupuesto|gastos?|monto|precios?|importe|cuotas?)\b)",
    flags=re.IGNORECASE,
)
_RE_PHONE = re.compile(
    r"(?<!\d)(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-])\d{3,4}[\s.-]?\d{4}(?!\d)"
)
_RE_LABELED_PHONE = re.compile(
    r"(\b(?:tel(?:[eé]fono)?|cel(?:ular)?|wa|wsp|whatsapp|contacto|llamar\s+al)\.?\s*[:=-]?\s*)"
    r"((?:\+?54\s*9?\s*)?(?:\d{10,11}|\d{2,4}\s+\d{6,8}))(?![\d-])",
    flags=re.IGNORECASE,
)


def _is_valid_cuit_mod11(cuit_digits: str) -> bool:
    """Valida CUIT/CUIL argentino de 11 dígitos usando Módulo 11 oficial."""
    if not re.fullmatch(r"(?:20|23|24|27|30|33|34)\d{9}", cuit_digits):
        return False
    weights = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
    acc = sum(int(d) * w for d, w in zip(cuit_digits[:10], weights))
    rem = 11 - (acc % 11)
    dv = int(cuit_digits[10])
    if rem == 11:
        return dv == 0
    if rem == 10:
        return cuit_digits.startswith("23") and dv in (9, 4)
    return dv == rem


def _is_money_context_around(full_text: str, start: int, end: int, token: str) -> bool:
    """Excluye cifras monetarias (ej. '$ 1.200.000', '1.500.000 pesos', '1200000 de gastos')."""
    if "-" in token:
        return False
    immediate_before = full_text[max(0, start - 20):start]
    if _RE_PII_DOC_LABEL.search(immediate_before):
        return False
    before_clause = re.split(r"[,;\n]", full_text[max(0, start - 22):start])[-1]
    after_clause = re.split(r"[,;\n]", full_text[end:min(len(full_text), end + 22)])[0]
    return bool(_RE_MONEY_CTX.search(before_clause) or _RE_MONEY_CTX.search(after_clause))


def _is_valid_dni_cuil_match(match: re.Match, full_text: str) -> bool:
    """Excluye comprobantes AFIP, secuencias 000... y cifras monetarias."""
    token = match.group(0)
    if token.isdigit():
        if token.startswith("000"):
            return False
        before = full_text[max(0, match.start() - 40):match.start()]
        if _RE_INVOICE_PREFIX.search(before):
            return False
    if _is_money_context_around(full_text, match.start(), match.end(), token):
        return False
    return True


def _is_valid_phone_match(match: re.Match, full_text: str) -> bool:
    """Excluye números de factura/comprobante AFIP (ej. 0004-00018291) de la detección de teléfonos."""
    token = match.group(0).strip()
    if re.fullmatch(r"\d{4,5}-\d{8}", token) or token.startswith("000"):
        return False
    before = full_text[max(0, match.start() - 40):match.start()]
    if _RE_INVOICE_PREFIX.search(before):
        return False
    return True


def detect_and_mask_pii(text: str) -> Tuple[str, List[Dict[str, Any]]]:
    if not text:
        return "", []

    masked = text
    warnings: List[Dict[str, Any]] = []

    cbu_matches = _RE_CBU.findall(masked)
    if cbu_matches:
        masked = _RE_CBU.sub("[CBU_OCULTO]", masked)
        warnings.append({"type": "cbu", "label": "CBU bancario (22 dígitos)", "count": len(cbu_matches)})

    alias_count = 0

    def _replace_alias(match: re.Match) -> str:
        nonlocal alias_count
        val = (match.group(1) or match.group(2) or "").strip()
        if not (6 <= len(val) <= 30):
            return match.group(0)
        alias_count += 1
        return "alias: [ALIAS_OCULTO]"

    masked = _RE_ALIAS_BANK.sub(_replace_alias, masked)
    if alias_count:
        warnings.append({"type": "alias_bancario", "label": "Alias bancario", "count": alias_count})

    email_matches = _RE_EMAIL.findall(masked)
    if email_matches:
        masked = _RE_EMAIL.sub("[EMAIL_OCULTO]", masked)
        warnings.append({"type": "email", "label": "Correo electrónico", "count": len(email_matches)})

    phone_count = 0
    labeled_phone_matches = _RE_LABELED_PHONE.findall(masked)
    if labeled_phone_matches:
        masked = _RE_LABELED_PHONE.sub(r"\1[TELEFONO_OCULTO]", masked)
        phone_count += len(labeled_phone_matches)

    def _replace_cell15(match: re.Match) -> str:
        nonlocal phone_count
        if _is_valid_phone_match(match, masked):
            phone_count += 1
            return "[TELEFONO_OCULTO]"
        return match.group(0)

    masked = _RE_CELL_15.sub(_replace_cell15, masked)

    dni_count = 0

    def _replace_cuit11(match: re.Match) -> str:
        nonlocal dni_count
        tok = match.group(0)
        if _is_valid_cuit_mod11(tok) and _is_valid_dni_cuil_match(match, masked):
            dni_count += 1
            return "[DNI_CUIL_OCULTO]"
        return tok

    masked = _RE_CUIT_11.sub(_replace_cuit11, masked)

    def _replace_dni(match: re.Match) -> str:
        nonlocal dni_count
        if _is_valid_dni_cuil_match(match, masked):
            dni_count += 1
            return "[DNI_CUIL_OCULTO]"
        return match.group(0)

    masked = _RE_CUIL_DNI.sub(_replace_dni, masked)
    if dni_count:
        warnings.append({"type": "dni_cuil", "label": "DNI / CUIL / CUIT", "count": dni_count})

    def _replace_phone(match: re.Match) -> str:
        nonlocal phone_count
        if _is_valid_phone_match(match, masked):
            phone_count += 1
            return "[TELEFONO_OCULTO]"
        return match.group(0)

    masked = _RE_PHONE.sub(_replace_phone, masked)

    if phone_count:
        warnings.append({"type": "telefono", "label": "Teléfono", "count": phone_count})

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


def _detect_contradictions(
    constr_norm: str,
    neg_constraints: List[str],
    technique: str,
    form_data: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Detecta contradicciones entre texto, restricciones negativas, técnica y opciones de slots/reglas."""
    form_data = form_data or {}
    contradictions: List[str] = []

    has_short = any(w in constr_norm for w in ("breve", "corto", "corta", "resumido", "conciso", "ultra breve"))
    has_long = any(w in constr_norm for w in ("exhaustivo", "exhaustiva", "detallado", "detallada", "extenso", "profundo"))
    if has_short and has_long:
        contradictions.append("Se pide extensión breve/resumida y al mismo tiempo exhaustiva/detallada.")

    if any("ejemplo" in _strip_accents(nc.lower()) for nc in neg_constraints) and technique == "Con Ejemplos":
        contradictions.append("Restricción negativa 'sin ejemplos' entra en conflicto con la técnica 'Con Ejemplos'.")

    if any("codigo" in _strip_accents(nc.lower()) for nc in neg_constraints) and any(
        w in constr_norm for w in ("generar codigo", "script", "funcion", "programa")
    ):
        contradictions.append("Se solicita generar código pero existe una restricción negativa sobre usar código.")

    # v7.1: Conflicto entre "Explicar sin tecnicismos" y profundidad/enfoque "Técnica..."
    quick_rules_norm = _strip_accents(str(form_data.get("Reglas Rápidas", "")).lower())
    wants_no_jargon = (
        "sin tecnicismos" in quick_rules_norm
        or "sin tecnicismos" in constr_norm
        or any("tecnicismo" in _strip_accents(nc.lower()) or "jerga" in _strip_accents(nc.lower()) for nc in neg_constraints)
    )
    tech_slot_val = ""
    for k, v in form_data.items():
        if k == "Reglas Rápidas" or not isinstance(v, str) or not v.strip():
            continue
        v_norm = _strip_accents(v.lower())
        if re.search(r"\b(?:tecnic[ao]|posgrado|nivel\s+avanzado)\b", v_norm):
            tech_slot_val = v.strip()
            break
    if wants_no_jargon and tech_slot_val:
        contradictions.append(
            f"Se combinó 'Explicar sin tecnicismos' con una opción técnica ('{tech_slot_val}'). "
            "Aclará si preferís lenguaje cotidiano o enfoque técnico."
        )

    return contradictions


_GENERIC_EVAL_TERMS = {"parcial", "examen", "final", "prueba", "tp", "recuperatorio"}


def _extract_entities_and_constraints(
    raw_text: str,
    normalized_text: str,
    technique: str,
    constraint_text: Optional[str] = None,
    form_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    v7.2 Carril A vs Carril B:
    - Entidades de negocio/tecnología y restricciones negativas/cuantitativas se extraen
      ÚNICAMENTE de `constraint_text` (`instruction_text`), nunca de `payload_text`.
    - Filenames/errores/snippets también se extraen aquí, y `parse_request` decide qué
      conservar del Carril B según el inspector de payload y el arquetipo.
    """
    constr_src = raw_text if constraint_text is None else constraint_text
    constr_norm = normalized_text if constraint_text is None else normalize_and_lemmatize(constraint_text)[0]
    constr_norm_no_al_final = re.sub(r"\b(?:al|hasta\s+el|hacia\s+el|por\s+el)\s+final\b", " ", constr_norm)
    entities: List[str] = []
    seen_ent = set()

    for term, _group in _ENTITY_INDEX:
        if term in _GENERIC_EVAL_TERMS:
            continue
        target_norm = constr_norm_no_al_final if term == "final" else constr_norm
        if _get_ent_boundary_re(term).search(target_norm) and term not in seen_ent:
            seen_ent.add(term)
            entities.append(term)

    versions = list(dict.fromkeys(_RE_VERSION.findall(constr_src)))
    filenames = list(dict.fromkeys(_RE_FILENAME.findall(constr_src)))
    errors_detected = list(dict.fromkeys(_RE_ERROR.findall(constr_src)))

    code_snippets = re.findall(r"```[\s\S]*?```|`[^`]+`", raw_text)
    if not code_snippets and re.search(r"\b(?:def |SELECT |import |const |function )", raw_text):
        code_snippets = ["inline_code_fragment"]

    neg_constraints = extract_negative_constraints(constr_src)

    quant_constraints: List[str] = []
    for match in _RE_QUANT_CONSTRAINT.findall(constr_src):
        clean_q = re.split(r"[,.;\n]", match)[0].strip()
        if clean_q:
            quant_constraints.append(clean_q)

    contradictions = _detect_contradictions(constr_norm, neg_constraints, technique, form_data=form_data)

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

_TFIDF_IGNORE = SPANISH_STOPWORDS | REQUEST_FILLERS


def _tokenize_for_tfidf(text: str) -> List[str]:
    """
    v7.0: Tokenización para TF-IDF sin duplicar tokens inalterados por el stemmer,
    filtrando muletillas de pedido y añadiendo bigramas útiles (`t1_t2`).
    """
    _, tokens, lemmas = normalize_and_lemmatize(text)
    features: List[str] = []
    useful_toks: List[str] = []
    useful_lems: List[str] = []

    for tok, lem in zip(tokens, lemmas):
        if len(tok) <= 1 or tok in _TFIDF_IGNORE:
            continue
        features.append(tok)
        useful_toks.append(tok)
        useful_lems.append(lem)
        if lem != tok and len(lem) > 2 and lem not in _TFIDF_IGNORE:
            features.append(lem)

    for i in range(len(useful_toks) - 1):
        bg_tok = f"{useful_toks[i]}_{useful_toks[i + 1]}"
        features.append(bg_tok)
        bg_lem = f"{useful_lems[i]}_{useful_lems[i + 1]}"
        if bg_lem != bg_tok:
            features.append(bg_lem)

    return features


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
            sims = sorted((self._cosine(q_vec, pv) for pv in vecs), reverse=True)
            if not sims:
                scores[action_key] = 0.0
            elif len(sims) >= 2 and sims[1] > 0.0:
                scores[action_key] = 0.80 * sims[0] + 0.20 * sims[1]
            else:
                scores[action_key] = sims[0]
        return scores


_TFIDF_INDEX = _ActionTfIdfIndex(KNOWLEDGE_BASE.get("actions", {}))


# ---------------------------------------------------------------------------
# Aprendizaje Activo Local desde SQLite (v7.0 — 100% Offline)
# ---------------------------------------------------------------------------

_LEARNED_BOOSTS_CACHE: Dict[int, Dict[str, Any]] = {}
_LEARNED_CACHE_TTL = 60.0


def invalidate_learned_boosts_cache(user_id: Optional[int] = None) -> None:
    """Invalida la caché de refuerzos aprendidos por usuario (o globalmente si user_id es None)."""
    if user_id is None:
        _LEARNED_BOOSTS_CACHE.clear()
    else:
        _LEARNED_BOOSTS_CACHE.pop(user_id, None)


def _get_learned_correction_boosts(user: Optional[Any] = None) -> Dict[str, Dict[str, Dict[str, float]]]:
    """
    Consulta `Prompt.objects.filter(user_id=user.id, user_corrected=True)` en SQLite y calcula
    refuerzos controlados (máx. +0.12) aislados por cuenta autenticada (nunca para anónimos
    ni para el usuario centinela compartido `invitado_demo`).
    """
    empty: Dict[str, Dict[str, Dict[str, float]]] = {"actions": {}, "domains": {}}
    if (
        user is None
        or not getattr(user, "is_authenticated", False)
        or getattr(user, "id", None) is None
        or getattr(user, "username", "") == "invitado_demo"
    ):
        return empty

    try:
        from django.apps import apps
        if not apps.ready:
            return empty

        uid = int(user.id)
        now = time.monotonic()
        cached_entry = _LEARNED_BOOSTS_CACHE.get(uid)
        if cached_entry is not None and (now - cached_entry["ts"]) < _LEARNED_CACHE_TTL:
            return cached_entry["data"]

        from .models import Prompt  # import local para evitar ciclo en carga inicial

        qs = Prompt.objects.filter(user_id=uid, user_corrected=True)
        if not qs.exists():
            _LEARNED_BOOSTS_CACHE[uid] = {"ts": now, "data": empty}
            return empty

        action_votes: Dict[str, Counter] = {}
        domain_votes: Dict[str, Counter] = {}

        for orig_text, cat, act in qs.values_list("original_text", "category", "detected_action"):
            _, toks, _ = normalize_and_lemmatize(orig_text or "")
            sig_toks = {
                t for t in toks
                if len(t) >= 3 and t not in _TFIDF_IGNORE and not t.isdigit()
            }
            for tok in sig_toks:
                if act:
                    action_votes.setdefault(tok, Counter())[act] += 1
                if cat and cat != "Otro / General":
                    domain_votes.setdefault(tok, Counter())[cat] += 1

        action_boosts: Dict[str, Dict[str, float]] = {}
        for tok, ctr in action_votes.items():
            for act, cnt in ctr.items():
                if cnt >= 2:
                    action_boosts.setdefault(tok, {})[act] = min(0.06 + 0.02 * (cnt - 2), 0.12)

        domain_boosts: Dict[str, Dict[str, float]] = {}
        for tok, ctr in domain_votes.items():
            for dom, cnt in ctr.items():
                if cnt >= 2:
                    domain_boosts.setdefault(tok, {})[dom] = min(0.06 + 0.02 * (cnt - 2), 0.12)

        data = {"actions": action_boosts, "domains": domain_boosts}
        _LEARNED_BOOSTS_CACHE[uid] = {"ts": now, "data": data}
        return data
    except Exception:
        return empty


def _lookup_token_boosts(tokens: List[str], boost_table: Dict[str, Dict[str, float]]) -> Dict[str, float]:
    """Acumula refuerzos por candidato con techo estricto en +0.12."""
    if not boost_table or not tokens:
        return {}
    totals: Dict[str, float] = {}
    for tok in set(tokens):
        for target, val in boost_table.get(tok, {}).items():
            totals[target] = min(totals.get(target, 0.0) + val, 0.12)
    return totals


_ACTION_SHORT_HINTS = {
    "depurar_error": "Encontrar la causa raíz de un error y corregir el código.",
    "generar_codigo": "Escribir un script, función, consulta o módulo desde cero.",
    "analizar_datos": "Explorar datos, calcular métricas y detectar patrones.",
    "comparar_evaluar": "Contrastar opciones o conceptos lado a lado con criterios claros.",
    "resumir_sintetizar": "Condensar un texto largo en puntos clave sin perder datos.",
    "planificar_pasos": "Ordenar una meta en pasos, etapas o cronograma accionable.",
    "redactar_contenido": "Escribir un correo, nota, mensaje o publicación desde cero.",
    "explicar_concepto": "Explicar qué es y cómo funciona un tema con ejemplos claros.",
    "transformar_formato": "Convertir una lista o texto desordenado a JSON, tabla o CSV.",
    "extraer_informacion": "Sacar datos puntuales (fechas, montos, nombres) sin inventar.",
    "clasificar_categorizar": "Agrupar elementos en categorías definidas con conteo.",
    "traducir_adaptar": "Traducir de idioma o adaptar el tono a otro destinatario.",
    "reescribir_mejorar": "Pulir un texto existente para hacerlo más claro o directo.",
    "auditar_criticar": "Revisar un texto o cláusula buscando riesgos y puntos débiles.",
    "simular_practicar": "Practicar un diálogo turno a turno con feedback al final.",
    "idear_alternativas": "Generar ideas variadas, ángulos o propuestas creativas.",
    "calcular_modelar": "Hacer cálculos numéricos, márgenes o escenarios paso a paso.",
    "razonar_resolver": "Resolver un problema lógico o matemático justificando pasos.",
    "decidir_recomendar": "Ponderar alternativas y recomendar la mejor opción.",
    "diagnosticar_resolver": "Formular causas probables de un problema y cómo comprobarlas.",
    "consultar_dato": "Responder un dato puntual o definición breve en pocas líneas.",
}


def _score_actions_detailed(
    text: str,
    normalized_text: str,
    tokens: Optional[List[str]] = None,
    learned_action_boosts: Optional[Dict[str, float]] = None,
    has_payload: bool = False,
    overlay_action_boosts: Optional[Dict[str, float]] = None,
) -> Tuple[Dict[str, float], Dict[str, Dict[str, Any]]]:
    """
    v7.2 + v8.0 Overlay: Combina reglas normalizadas (saturadas en 2.0 hits), TF-IDF con bigramas,
    desempates semánticos de pares cercanos, refuerzos aprendidos de SQLite (<= +0.12) y
    capa supervisada de Active Learning (overlay).
    """
    tfidf_scores = _TFIDF_INDEX.score_text(text)
    actions_cfg = KNOWLEDGE_BASE.get("actions", {})
    combined: Dict[str, float] = {}
    details: Dict[str, Dict[str, Any]] = {}
    learned = learned_action_boosts or {}
    overlay = overlay_action_boosts or {}

    for action_key, cfg in actions_cfg.items():
        lex_hits = 0.0
        phrase_hit = False
        seen_norms = set()

        for kw in cfg.get("keywords", []):
            kw_norm = _norm_kw(kw)
            if not kw_norm or kw_norm in seen_norms:
                continue
            seen_norms.add(kw_norm)
            if " " in kw_norm:
                if _get_kw_boundary_re(kw_norm).search(normalized_text):
                    lex_hits += 1.5
                    phrase_hit = True
            else:
                if _get_kw_boundary_re(kw_norm).search(normalized_text):
                    lex_hits += 1.0

        lex_norm = min(lex_hits / 2.0, 1.0)
        tfidf_val = tfidf_scores.get(action_key, 0.0)
        phrase_bonus = 0.08 if phrase_hit else 0.0
        learned_bonus = min(learned.get(action_key, 0.0), 0.12)
        overlay_bonus = min(overlay.get(action_key, 0.0), 0.52)
        score = min(0.55 * lex_norm + 0.45 * tfidf_val + phrase_bonus + learned_bonus + overlay_bonus, 0.99)
        combined[action_key] = round(score, 4)
        details[action_key] = {
            "lex_hits": lex_hits,
            "lex_norm": lex_norm,
            "tfidf": tfidf_val,
            "phrase_hit": phrase_hit,
            "learned_bonus": learned_bonus,
            "overlay_bonus": overlay_bonus,
        }

    # Desempate 1 (v7.0): reescribir_mejorar vs. redactar_contenido
    has_polish_verb = bool(re.search(
        r"\b(?:pulir|reescribir|corregir\s+estilo|corregir\s+ortografia|mejorar\s+(?:la\s+)?redaccion|mejorar\s+este\s+texto|hacer\s+mas\s+(?:claro|corto))\b",
        normalized_text,
    ))
    has_existing_ref = bool(re.search(
        r"\b(?:este\s+(?:correo|mail|texto|mensaje|parrafo|borrador)|esta\s+(?:nota|carta|redaccion)|la\s+redaccion\s+de)\b",
        normalized_text,
    ))
    if has_polish_verb and has_existing_ref and "reescribir_mejorar" in combined:
        combined["reescribir_mejorar"] = round(min(max(combined["reescribir_mejorar"] + 0.18, combined.get("redactar_contenido", 0.0) + 0.12), 0.98), 4)
        details["reescribir_mejorar"]["tiebreak"] = "reescribir_vs_redactar"

    # Desempate 2 (v7.0 / v7.2.1): explicación didáctica vs. comparar alternativas ante "diferencia(s) entre X y Y"
    has_didactic_explain = bool(re.search(
        r"\b(?:explicar|ensenar|entender|comprender|aclarar)\b",
        normalized_text,
    ))
    has_pedagogic_cue = bool(re.search(
        r"\b(?:recien\s+empieza|principiante|desde\s+cero|analogia|vida\s+cotidiana|sin\s+tecnicismos|sin\s+(?:usar\s+)?formulas|como\s+si|facil|sencillo)\b",
        normalized_text,
    ))
    has_eval_choice_cue = bool(re.search(
        r"\b(?:ventajas|desventajas|pros\s+y\s+contras|cual\s+(?:me\s+)?conviene|cual\s+es\s+mejor|elegir\s+entre|recomendar|alternativas|proveedores|propuestas)\b",
        normalized_text,
    ))
    if re.search(r"\bdiferencias?\s+entre\b", normalized_text):
        if has_didactic_explain and has_pedagogic_cue and not has_eval_choice_cue and "explicar_concepto" in combined:
            combined["explicar_concepto"] = round(
                min(max(combined["explicar_concepto"] + 0.22, combined.get("comparar_evaluar", 0.0) + 0.16, 0.86), 0.98),
                4,
            )
            if "comparar_evaluar" in combined:
                combined["comparar_evaluar"] = round(min(combined["comparar_evaluar"], combined["explicar_concepto"] - 0.18), 4)
            details["explicar_concepto"]["tiebreak"] = "didactic_comparison_explain"
        elif "comparar_evaluar" in combined:
            combined["comparar_evaluar"] = round(
                min(max(combined["comparar_evaluar"] + 0.18, combined.get("explicar_concepto", 0.0) + 0.10), 0.98),
                4,
            )
            details["comparar_evaluar"]["tiebreak"] = "diferencia_entre"

    # Desempate 3 (v7.2 P0.2.2): creación de artefactos técnicos ("escribime un script" / "haceme una consulta")
    has_tech_creation = bool(re.search(
        r"\b(?:escribir|hacer|armar|crear|generar|desarrollar|implementar)\s+(?:un|una|el|la)?\s*(?:script(?!\s+(?:de|para)\s+(?:video|tiktok|reel|reels|youtube|audio|podcast))|codigo|funcion|consulta|query|programa|endpoint|api|bot)\b",
        normalized_text,
    ))
    if has_tech_creation and "generar_codigo" in combined:
        combined["generar_codigo"] = round(max(combined["generar_codigo"], 0.90), 4)
        if "redactar_contenido" in combined:
            combined["redactar_contenido"] = round(min(combined["redactar_contenido"], 0.25), 4)
        if "analizar_datos" in combined and "analizar" not in normalized_text and "pandas" not in normalized_text:
            combined["analizar_datos"] = round(min(combined["analizar_datos"], 0.35), 4)
        details["generar_codigo"]["tiebreak"] = "tech_creation"

    # Desempate 4 (v7.2 P0.2.3): "mejorar"/"optimizar" sin artefacto textual ni payload NO puede activar reescribir_mejorar
    has_text_artifact = bool(re.search(
        r"\b(?:texto|mensaje|redaccion|mail|email|correo|nota|parrafo|respuesta|cv|curriculum|carta|borrador|post|publicacion|comunicado)\b",
        normalized_text,
    ))
    has_improve_verb = bool(re.search(r"\b(?:mejorar|optimizar|pulir|reescribir)\b", normalized_text))
    if has_improve_verb and not has_text_artifact and not has_payload:
        if "reescribir_mejorar" in combined:
            combined["reescribir_mejorar"] = 0.0
        if re.search(r"\b(?:ventas?|rentabilidad|margen|negocio|local|ingresos|conversion|flojo|cayo|bajaron|clientes?)\b", normalized_text):
            if "diagnosticar_resolver" in combined:
                combined["diagnosticar_resolver"] = round(max(combined["diagnosticar_resolver"], 0.72), 4)
                details["diagnosticar_resolver"]["tiebreak"] = "improve_metric_to_diagnose"
        elif "planificar_pasos" in combined:
            combined["planificar_pasos"] = round(max(combined["planificar_pasos"], 0.68), 4)
            details["planificar_pasos"]["tiebreak"] = "improve_process_to_plan"

    # Desempate 5 (v7.2 P0.2.4): pedido explícito de plan / cronograma no debe caer en redactar_contenido
    if re.search(
        r"\b(?:armar|hacer|crear|disenar|elaborar|planificar)\s+(?:un\s+)?(?:plan|cronograma|hoja\s+de\s+ruta|roadmap)\b",
        normalized_text,
    ) and "planificar_pasos" in combined:
        combined["planificar_pasos"] = round(max(combined["planificar_pasos"], 0.85), 4)
        if "redactar_contenido" in combined:
            combined["redactar_contenido"] = round(min(combined["redactar_contenido"], 0.25), 4)
        details["planificar_pasos"]["tiebreak"] = "explicit_plan"

    # Desempate 6 (v7.2.1): guion audiovisual o video corto único -> redactar_contenido (no idear_alternativas)
    has_explicit_script = bool(re.search(
        r"\b(?:guion|script\s+(?:de|para)\s+video|video\s+corto)\b",
        normalized_text,
    )) or (
        bool(re.search(r"\b(?:reel|reels|tiktok)\b", normalized_text))
        and bool(re.search(r"\b\d+\s*(?:segundos?|seg|s|minutos?|min)\b", normalized_text))
    )
    asks_multiple_ideas = bool(re.search(
        r"\b(?:\d+\s+ideas|ideas?\s+(?:de|para)|dame\s+ideas|lluvia\s+de\s+ideas|brainstorming|alternativas|opciones|lista\s+de\s+ideas)\b",
        normalized_text,
    ))
    if has_explicit_script and not asks_multiple_ideas and "redactar_contenido" in combined:
        combined["redactar_contenido"] = round(max(combined["redactar_contenido"], 0.88), 4)
        if "idear_alternativas" in combined:
            combined["idear_alternativas"] = round(min(combined["idear_alternativas"], 0.20), 4)
        details["redactar_contenido"]["tiebreak"] = "guion_video"

    return combined, details


def _score_actions(text: str, normalized_text: str) -> Dict[str, float]:
    scores, _ = _score_actions_detailed(text, normalized_text)
    return scores


_DOMAIN_ANCHORS: Dict[str, Tuple[set, float]] = {
    "Ciencia de Datos e IA": (
        {
            "pandas", "numpy", "scikit-learn", "sklearn", "dataset", "csv", "parquet",
            "jupyter", "colab", "machine learning", "deep learning", "regresion lineal",
            "regresion logistica", "random forest", "xgboost", "tf-idf", "clustering",
            "eda", "outliers", "valores nulos", "llm", "inteligencia artificial",
            "correlacion", "modelo",
        },
        0.30,
    ),
    "Tecnología y programación": (
        {
            "python", "django", "flask", "fastapi", "javascript", "typescript", "react",
            "vue", "html", "css", "sql", "postgresql", "postgres", "mysql", "sqlite",
            "mongodb", "docker", "git", "github", "bash", "linux", "api", "rest",
            "graphql", "regex", "keyerror", "typeerror", "valueerror", "traceback",
            "script", "codigo", "endpoint", "dataframe",
        },
        0.26,
    ),
    "Trámites y documentos": (
        {
            "clausula", "alquiler", "contrato", "inquilino", "locatario", "locador",
            "licencia", "nota formal", "tramite", "carta documento", "descargo",
            "afip", "arca", "anses", "monotributo", "defensa del consumidor", "nda",
            "declaracion jurada",
        },
        0.30,
    ),
    "Negocios y comercio": (
        {
            "negocio", "comercio", "pyme", "emprendimiento", "ventas", "stock",
            "inventario", "vencimientos", "margen", "rentabilidad", "gastos fijos",
            "punto de equilibrio", "cliente", "clientes", "proveedor", "proveedores",
            "facturacion", "kpi", "roi", "churn",
        },
        0.24,
    ),
    "Estudio y academia": (
        {
            "parcial", "examen", "final", "recuperatorio", "facultad", "universidad",
            "catedra", "tesis", "tesina", "monografia", "apa", "mitosis", "meiosis",
            "autoevaluacion", "trabajo practico", "principiante", "desde cero",
        },
        0.26,
    ),
    "Redacción y comunicación": (
        {
            "correo", "email", "mail", "whatsapp", "instagram", "linkedin", "tiktok",
            "reel", "reels", "guion", "video corto", "copywriting", "post", "publicacion",
            "carta", "comunicado", "pitch", "redaccion",
        },
        0.22,
    ),
    "Planificación y productividad": (
        {
            "cronograma", "roadmap", "hitos", "rutina", "agenda", "sprint", "kanban",
            "okr", "checklist", "itinerario",
        },
        0.24,
    ),
    "Toma de decisiones": (
        {
            "matriz de decision", "trade-off", "costo beneficio", "dilema",
            "me conviene", "comprar o alquilar",
        },
        0.26,
    ),
}


_EXPLICIT_TECH_RE = re.compile(
    r"\b(?:sqlite|postgresql|postgres|mysql|python|pandas|django|flask|fastapi|react|vue|"
    r"javascript|typescript|api|rest|graphql|sql|script|traceback|keyerror|typeerror|"
    r"valueerror|syntaxerror|docker|git)\b",
    flags=re.IGNORECASE,
)

_EXPLICIT_DS_RE = re.compile(
    r"\b(?:pandas|numpy|scipy|scikit-learn|sklearn|dataset|machine\s+learning|"
    r"deep\s+learning|regresion\s+(?:lineal|logistica)|random\s+forest|xgboost|"
    r"clustering|eda|analisis\s+exploratorio|valores\s+nulos|outliers|correlacion)\b",
    flags=re.IGNORECASE,
)


def _classify_domain(
    normalized_text: str,
    explicit_category: str,
    entities: Optional[List[str]] = None,
    learned_domain_boosts: Optional[Dict[str, float]] = None,
    overlay_domain_boosts: Optional[Dict[str, float]] = None,
) -> Tuple[str, List[Dict[str, Any]]]:
    trace: List[Dict[str, Any]] = []
    mapped = LEGACY_DOMAIN_ALIASES.get(explicit_category, explicit_category)
    domains_cfg = KNOWLEDGE_BASE.get("domains", {})

    if mapped and mapped in domains_cfg and mapped != "Otro / General":
        trace.append({"stage": "domain", "rule": f"Dominio explícito/mapeado: {mapped}"})
        return mapped, trace

    ent_set = set(entities or [])
    learned = learned_domain_boosts or {}
    overlay_dom = overlay_domain_boosts or {}
    norm_no_al_final = re.sub(r"\b(?:al|hasta\s+el|hacia\s+el|por\s+el)\s+final\b", " ", normalized_text)
    has_no_ext_lib = bool(re.search(
        r"\b(?:sin\s+librerias\s+externas|libreria\s+estandar|python\s+puro|sin\s+paquetes\s+externos)\b",
        normalized_text,
    ))
    has_explicit_tech = bool(_EXPLICIT_TECH_RE.search(normalized_text))
    has_explicit_ds = bool(_EXPLICIT_DS_RE.search(normalized_text)) and not has_no_ext_lib

    domain_scores: Dict[str, float] = {}
    domain_hits: Dict[str, List[str]] = {}

    for dom_name, cfg in domains_cfg.items():
        if dom_name == "Otro / General":
            continue
        target_norm = norm_no_al_final if dom_name == "Estudio y academia" else normalized_text
        raw_hits = 0.0
        hits: List[str] = []
        seen_norms = set()
        for kw in cfg.get("keywords", []):
            kw_norm = _norm_kw(kw)
            if not kw_norm or kw_norm in seen_norms:
                continue
            seen_norms.add(kw_norm)
            if " " in kw_norm:
                if _get_kw_boundary_re(kw_norm).search(target_norm):
                    raw_hits += 1.5
                    hits.append(kw)
            else:
                if _get_kw_boundary_re(kw_norm).search(target_norm):
                    raw_hits += 1.0
                    hits.append(kw)

        # Normalización por tamaño del vocabulario del dominio (v7.0)
        vocab_norm = math.sqrt(max(len(seen_norms), 1))
        score = raw_hits / vocab_norm

        # Afinidad con entidades y anclas de alta señal del dominio (v7.0)
        anchors, anchor_w = _DOMAIN_ANCHORS.get(dom_name, (set(), 0.0))
        anchor_hits = 0
        for anch in anchors:
            if anch == "csv" and has_no_ext_lib and dom_name == "Ciencia de Datos e IA":
                continue
            if anch in ent_set or _get_kw_boundary_re(anch).search(target_norm):
                anchor_hits += 1
                if anch not in hits:
                    hits.append(anch)
        if anchor_hits > 0:
            score += min(anchor_hits * anchor_w, 0.90)

        # Refuerzo aprendido de correcciones previas en SQLite (<= +0.12)
        learned_b = min(learned.get(dom_name, 0.0), 0.12)
        if learned_b > 0.0:
            score += learned_b

        # Refuerzo supervisado de Capa Active Learning (<= +0.45)
        overlay_b = min(overlay_dom.get(dom_name, 0.0), 0.45)
        if overlay_b > 0.0:
            score += overlay_b

        domain_scores[dom_name] = score
        domain_hits[dom_name] = hits

    # Desempate P0.2.1: tecnología explícita sin señales DS/ML gana sobre Negocios y Comunicación
    if (has_explicit_tech or "json" in normalized_text) and not has_explicit_ds:
        tech_sc = domain_scores.get("Tecnología y programación", 0.0)
        biz_sc = domain_scores.get("Negocios y comercio", 0.0)
        red_sc = domain_scores.get("Redacción y comunicación", 0.0)
        ds_sc = domain_scores.get("Ciencia de Datos e IA", 0.0)
        if tech_sc > 0.0:
            domain_scores["Tecnología y programación"] = max(tech_sc + 0.35, biz_sc + 0.15, red_sc + 0.15, ds_sc + 0.15)

    # En simulaciones de entrevista laboral, no clasificar como Planificación ni Ciencia de Datos
    if re.search(r"\b(?:entrevista\s+(?:laboral|t[eé]cnica|de\s+trabajo)|puesto\s+de)\b", normalized_text) and not has_explicit_ds:
        trace.append({
            "stage": "domain",
            "rule": "Simulación de entrevista laboral -> Otro / General",
            "score": 0.5,
            "matched_keywords": ["entrevista"],
        })
        return "Otro / General", trace

    best_domain = "Otro / General"
    best_score = 0.0
    matched_kws: List[str] = []
    for dom_name, score in domain_scores.items():
        if score > best_score:
            best_score = score
            best_domain = dom_name
            matched_kws = domain_hits.get(dom_name, [])[:5]

    trace.append({
        "stage": "domain",
        "rule": f"Inferencia normalizada -> {best_domain}",
        "score": round(best_score, 3),
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

    if action == "simular_practicar" and not _kw_in("json", normalized_text) and not _kw_in("tabla", normalized_text):
        return "diálogo interactivo"

    if re.search(r"\b(?:(?:en|a|formato|como|quiero)\s+(?:un\s+)?json|json\s+limpio)\b", normalized_text):
        return "json"
    if re.search(r"\b(?:(?:a|formato)\s+(?:una\s+)?tabla|en\s+una\s+tabla|en\s+tabla)\b", normalized_text):
        return "tabla"

    # P0.2.4: Prioridad de entregable 'plan / cronograma' sobre mención de canales (WhatsApp/correo)
    if re.search(
        r"\b(?:armar|hacer|disenar|elaborar|planificar|quiero|necesito)?\s*(?:un\s+)?(?:plan(?:\s+de\s+(?:\d+\s+\w+|accion|marketing|trabajo|estudio|lanzamiento))?|cronograma|hoja\s+de\s+ruta|roadmap)\b",
        normalized_text,
    ) and not re.search(r"\bpaso\s+a\s+paso\b", normalized_text):
        return "plan / cronograma"

    if action == "diagnosticar_resolver" and not re.search(r"\b(?:en\s+tabla|en\s+json|correo|mail)\b", normalized_text):
        return "informe estructurado"
    if action == "redactar_contenido" and re.search(
        r"\b(?:guion|script\s+(?:de|para)\s+video|video\s+corto)\b",
        normalized_text,
    ) and not re.search(r"\b(?:email|mail|correo|mensaje|whatsapp|carta)\b", normalized_text):
        return "informe estructurado"

    best_deliv = ""
    best_hits = 0
    for deliv_key, cfg in KNOWLEDGE_BASE.get("deliverables", {}).items():
        if action in ("comparar_evaluar", "transformar_formato", "extraer_informacion") and deliv_key == "email / mensaje":
            continue
        seen_norms = set()
        hits = 0
        for kw in cfg.get("keywords", []):
            kw_norm = _norm_kw(kw)
            if not kw_norm or kw_norm in seen_norms:
                continue
            seen_norms.add(kw_norm)
            if _get_kw_boundary_re(kw_norm).search(normalized_text):
                hits += 1
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
            seen_norms = set()
            for kw in cfg.get("keywords", []):
                kw_norm = _norm_kw(kw)
                if not kw_norm or kw_norm in seen_norms:
                    continue
                seen_norms.add(kw_norm)
                if " " in kw_norm:
                    if _get_kw_boundary_re(kw_norm).search(normalized_text):
                        s += 1.5
                elif _get_kw_boundary_re(kw_norm).search(normalized_text):
                    s += 1.0
            for rgx in cfg.get("regex", []):
                if re.search(rgx, raw_text, flags=re.IGNORECASE):
                    s += 2.0
            if s > 0:
                res.append((sub_name, s))
        return res

    scored = _score_group(action_subs)
    if action == "redactar_contenido" and re.search(
        r"\b(?:extiend[ae]|extender|prorroga|plazo\s+de\s+pago|mas\s+tiempo)\b",
        normalized_text,
    ):
        scored = [(sub_name, sc) for sub_name, sc in scored if sub_name != "reclamo"]
    scored.sort(key=lambda x: x[1], reverse=True)
    primary = scored[0][0] if scored else "general"
    for name, _ in scored:
        if name not in all_matched:
            all_matched.append(name)

    # Solo permitir subintenciones académicas de estudio en explicar/comparar, nunca filtrar subintenciones ajenas (rutina_negocio, email_formal, sql, etc.)
    if action in ("explicar_concepto", "comparar_evaluar"):
        for act_k in ("explicar_concepto",):
            if act_k == action:
                continue
            for name, sc in _score_group(subintents_cfg.get(act_k, {})):
                if sc >= 1.5 and name not in all_matched:
                    all_matched.append(name)

    return primary, all_matched


def _detect_ontology_objects(
    normalized_text: str,
    action: str = "",
    subintent: str = "",
) -> List[str]:
    ontology = KNOWLEDGE_BASE.get("object_ontology", {})
    matched: List[str] = []
    norm_no_al_final = re.sub(r"\b(?:al|hasta\s+el|hacia\s+el|por\s+el)\s+final\b", " ", normalized_text)
    has_no_ext_lib = bool(re.search(
        r"\b(?:sin\s+librerias\s+externas|libreria\s+estandar|python\s+puro|sin\s+paquetes\s+externos)\b",
        normalized_text,
    ))
    is_biz_ops_intent = (
        subintent == "rutina_negocio"
        or (
            action == "planificar_pasos"
            and subintent != "proyecto"
            and bool(re.search(r"\b(?:controlar|gestionar|registrar|llevar|administrar|manejar|caja|stock|vencimientos?)\b", normalized_text))
        )
    )
    disallowed_biz_actions = {
        "comparar_evaluar", "generar_codigo", "extraer_informacion",
        "transformar_formato", "diagnosticar_resolver", "calcular_modelar",
        "redactar_contenido", "simular_practicar",
    }

    for obj_key, cfg in ontology.items():
        if obj_key in ("ventas", "stock", "vencimientos", "precios"):
            if action in disallowed_biz_actions or not is_biz_ops_intent:
                continue
        if obj_key == "dataset":
            if has_no_ext_lib or (action == "generar_codigo" and "pandas" not in normalized_text and "dataframe" not in normalized_text):
                continue
        if obj_key == "parcial" and action == "planificar_pasos":
            continue
        target_norm = norm_no_al_final if obj_key == "parcial" else normalized_text
        for alias in cfg.get("aliases", []):
            al_norm = _strip_accents(alias.lower())
            if re.search(rf"(?<![a-z0-9]){re.escape(al_norm)}(?![a-z0-9])", target_norm):
                if obj_key not in matched:
                    matched.append(obj_key)
                break
    return matched


_CONCEPTUAL_ACTIONS = {"explicar_concepto", "comparar_evaluar", "resumir_sintetizar"}

_OPERATIONAL_DATA_RE = re.compile(
    r"\b(?:csv|xlsx|dataset|datasets|modelo|modelos|entrenar|entrenamiento|regresion|clasificacion|"
    r"clustering|pandas|numpy|sklearn|scikit-learn|sql|sqlite|postgresql|mysql|dataframe|"
    r"tabla\s+de\s+datos|archivo|archivos|planilla)\b",
    flags=re.IGNORECASE,
)

_OPERATIONAL_SLOT_IDS = {
    "data_shape", "ml_goal", "tech_stack", "code_constraints", "data_question", "code_io", "error_context",
}


def _build_slot_labels_map() -> Dict[str, str]:
    labels: Dict[str, str] = {
        "edu_level": "Nivel educativo",
        "explain_depth": "Nivel de profundidad",
        "study_focus": "Enfoque de estudio",
        "dataset_size": "Tamaño del dataset",
        "data_shape": "Estructura y tamaño del dataset",
        "ml_goal": "Prioridad del análisis o modelo",
        "audience": "Público / Nivel",
        "deliverable": "Formato de salida",
    }
    catalog = KNOWLEDGE_BASE.get("slot_catalog", {})
    for group_key in ("by_domain", "by_action"):
        for slots in catalog.get(group_key, {}).values():
            for slot in slots:
                sid = slot.get("id", "")
                lbl = slot.get("label", "")
                if sid and lbl:
                    labels[sid] = lbl
                    labels[sid.lower()] = lbl
    return labels


SLOT_LABELS_ES: Dict[str, str] = _build_slot_labels_map()


def _format_slot_label(key: str) -> str:
    """Resuelve siempre una etiqueta humana en español para cualquier clave de slot."""
    clean_k = str(key or "").strip()
    if not clean_k:
        return "Dato adicional"
    if clean_k in SLOT_LABELS_ES:
        return SLOT_LABELS_ES[clean_k]
    low = clean_k.lower()
    if low in SLOT_LABELS_ES:
        return SLOT_LABELS_ES[low]
    # Si ya viene legible en español (con espacios), devolverla tal cual
    if " " in clean_k and "_" not in clean_k:
        return clean_k
    return clean_k.replace("_", " ").strip().capitalize()


def _check_conceptual_no_data(
    action: str,
    payload_kind: str,
    filenames: List[str],
    normalized_text: str,
) -> bool:
    return (
        action in _CONCEPTUAL_ACTIONS
        and payload_kind == "sin_insumo"
        and not filenames
        and not bool(_OPERATIONAL_DATA_RE.search(normalized_text or ""))
    )


def _is_slot_already_covered(slot_id: str, classify_norm: str, req: Optional[ParsedRequest] = None) -> bool:
    if not classify_norm:
        return False
    roles = req.roles if req else {}
    if slot_id == "tech_stack":
        return bool(re.search(
            r"\b(?:python|django|flask|fastapi|javascript|typescript|react|vue|sql|sqlite|postgresql|postgres|mysql|bash|linux|java|c#|go|rust)\b",
            classify_norm,
        ))
    if slot_id == "code_io":
        is_sql = (req and req.subintent == "consulta_sql") or bool(re.search(r"\b(?:sql|postgresql|postgres|mysql|sqlite)\b", classify_norm))
        if is_sql and re.search(r"\b(?:tablas?|join|unir|una|select|from|mostrar|muestre|calcular|calcule|total|cantidad|listar|obtener)\b", classify_norm):
            return True
        has_in = bool(re.search(r"\b(?:lea|leer|reciba|recibe|entrada|archivo|csv|json|tablas?|input|parametro)\b", classify_norm))
        has_out = bool(re.search(r"\b(?:muestre|mostrar|devuelva|devolver|retorne|retornar|imprima|genere|calcule|total|salida|output)\b", classify_norm))
        return has_in and has_out
    if slot_id == "code_constraints":
        return bool(
            (req and req.neg_constraints)
            or re.search(r"\b(?:sin\s+librerias|libreria\s+estandar|python\s+puro|sin\s+paquetes|archivo\s+vacio|produccion|casos?\s+borde)\b", classify_norm)
        )
    if slot_id == "comm_tone":
        return bool(req and req.tone)
    if slot_id == "edu_level":
        return bool(
            (req and req.audience)
            or re.search(r"\b(?:universitario|facultad|universidad|secundaria|posgrado|terciario|parcial|examen|catedra)\b", classify_norm)
        )
    if slot_id == "study_focus":
        return bool(re.search(r"\b(?:ejercicios?|simulacros?|autoevaluacion|analogias?)\b", classify_norm))
    if slot_id == "error_context":
        return bool((req and req.errors_detected) or re.search(r"\b(?:traceback|keyerror|typeerror|valueerror|syntaxerror|error\s+500)\b", classify_norm))
    if slot_id == "compare_axes":
        has_two = bool(re.search(r"\b(?:vs\.?|versus|contra|entre\s+\S+\s+y\s+\S+)\b", classify_norm))
        has_axes = bool(re.search(r"\b(?:ventajas|desventajas|pros|contras|criterios|cual\s+(?:me\s+)?conviene|diferencias)\b", classify_norm))
        return has_two and has_axes
    if slot_id == "biz_scale":
        return bool(re.search(
            r"\b(?:negocio\s+chico|pyme|emprendimiento|kiosco|drugstore|minorista|local\s+chico|tienda|comercio\s+chico|b2b|ecommerce|e-commerce)\b",
            classify_norm,
        ))
    if slot_id in ("biz_horizon", "plan_timeframe"):
        return bool(
            roles.get("plazo")
            or roles.get("dedicacion")
            or re.search(r"\b(?:\d+\s+(?:semanas?|dias?|meses?|horas?)|mensual|semanal|trimestral|esta\s+semana|este\s+mes|sin\s+gastar|bajo\s+presupuesto)\b", classify_norm)
        )
    if slot_id in ("target_schema", "extract_fields"):
        return bool(roles.get("campos_esquema"))
    if slot_id == "sim_channel":
        return bool(roles.get("canal") or roles.get("es_entrevista"))
    if slot_id == "audit_role":
        return bool(roles.get("perspectiva"))
    if slot_id == "idea_channel":
        return bool(roles.get("canal"))
    if slot_id == "margin_base":
        return bool(re.search(r"\b(?:sobre\s+(?:venta|precio\s+de\s+venta|costo))\b", classify_norm))
    return False


def _get_slots_for_request(
    domain: str,
    action: str,
    form_data: Dict[str, Any],
    conceptual_no_data: bool = False,
    classify_norm: str = "",
    req: Optional[ParsedRequest] = None,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    catalog = KNOWLEDGE_BASE.get("slot_catalog", {})
    candidates: List[Dict[str, Any]] = []

    if conceptual_no_data:
        # Prioriza la acción y el aprendizaje conceptual; excluye slots operativos de dataset/modelo
        candidates.extend(catalog.get("by_action", {}).get(action, []))
        candidates.extend(catalog.get("by_domain", {}).get("Estudio y academia", []))
        for dom_slot in catalog.get("by_domain", {}).get(domain, []):
            if dom_slot["id"] not in _OPERATIONAL_SLOT_IDS:
                candidates.append(dom_slot)
    else:
        candidates.extend(catalog.get("by_action", {}).get(action, []))
        candidates.extend(catalog.get("by_domain", {}).get(domain, []))

    is_sql_only = (
        ((req and req.subintent == "consulta_sql") or bool(re.search(r"\b(?:sql|postgresql|postgres|mysql|sqlite)\b", classify_norm)))
        and not re.search(r"\b(?:python|javascript|django|flask|fastapi|react)\b", classify_norm)
    )

    eligible_all: List[Dict[str, Any]] = []
    seen_all = set()
    for slot in candidates:
        sid = slot["id"]
        if sid in seen_all:
            continue
        seen_all.add(sid)
        if _is_slot_already_covered(sid, classify_norm, req=req):
            continue
        if sid == "code_constraints" and is_sql_only:
            slot = {
                **slot,
                "options": [
                    "SQL estándar ANSI",
                    "Optimizada con índices",
                    "Compatible con producción",
                ],
            }
        eligible_all.append(slot)

    eligible_all.sort(key=lambda s: s.get("impact_pts", 5), reverse=True)
    active_slot_ids = [s["id"] for s in eligible_all]
    return eligible_all[:3], active_slot_ids


def _select_suggested_slots(
    domain: str,
    action: str,
    form_data: Dict[str, Any],
    conceptual_no_data: bool = False,
) -> List[Dict[str, Any]]:
    slots, _ = _get_slots_for_request(domain, action, form_data, conceptual_no_data=conceptual_no_data)
    return slots


def _extract_context_modifiers(normalized_text: str) -> Dict[str, Any]:
    norm_no_al_final = re.sub(r"\b(?:al|hasta\s+el|hacia\s+el|por\s+el)\s+final\b", " ", normalized_text)
    audience = ""
    if any(w in normalized_text for w in ("principiante", "desde cero", "basico", "no se nada", "facil", "recien empieza", "recien empiezan", "sin experiencia")):
        audience = "Principiante / Sin conocimientos previos"
    elif any(w in normalized_text for w in ("senior", "avanzado", "experto", "produccion")):
        audience = "Nivel avanzado / Técnico"
    elif re.search(
        r"\b(?:para\s+(?:un\s+|el\s+|mi\s+|los\s+)?clientes?|a\s+(?:un\s+|mi\s+|los\s+)?clientes?|dirigido\s+a\s+clientes?|presentar\s+a\s+(?:clientes?|directivos?)|gerencia|directivos?|directorio|jefe)\b",
        normalized_text,
    ):
        audience = "Directivo / Cliente"
    elif any(w in norm_no_al_final for w in ("universitario", "facultad", "examen", "parcial", "final")):
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


def _build_facets(req: ParsedRequest, classify_norm: str = "") -> List[str]:
    facets = {
        f"domain:{req.domain}",
        f"action:{req.action}",
        f"sub:{req.subintent}",
        f"deliv:{req.deliverable}",
    }
    if not req.is_single_clause:
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
    if any(k in neg_joined for k in ("libreria", "paquete", "externa")) or re.search(
        r"\b(?:sin\s+librerias\s+externas|libreria\s+estandar|python\s+puro|sin\s+paquetes\s+externos)\b",
        classify_norm or "",
    ):
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

    cleaned = re.sub(r"\s+", " ", src or "").strip().rstrip(":").strip()

    for frame_rgx in KNOWLEDGE_BASE.get("request_frames", []):
        cleaned = re.sub(frame_rgx, "", cleaned, flags=re.IGNORECASE).strip()

    # Limpieza gramatical de relleno genérico antes de armar # Objetivo (para proteger # Objetivo en el linter)
    cleaned = re.sub(
        r"^(?:necesito|quiero)\s+(?:una\s+)?respuesta\s+(?:clara|precisa|completa|detallada|bien\s+estructurada)"
        r"(?:\s+y\s+(?:clara|precisa|completa|detallada|bien\s+estructurada))?\s+(?:de|en|sobre|para)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    for pat in KNOWLEDGE_BASE.get("lint_rules", {}).get("banned_patterns", []):
        cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip()

    if not cleaned:
        cleaned = (src or "").strip().rstrip(":").strip()

    # Normalización de aperturas coloquiales e imperativas (v7.2 P2.3)
    if parsed.action == "diagnosticar_resolver" and re.match(r"^necesito\s+mejorar\b", cleaned, flags=re.IGNORECASE):
        cleaned = re.sub(r"^necesito\s+mejorar\b", "Diagnosticar y mejorar", cleaned, flags=re.IGNORECASE).strip()
    elif parsed.action == "depurar_error" and re.match(r"^tengo\s+(?:este\s+)?error\b", cleaned, flags=re.IGNORECASE):
        cleaned = re.sub(r"^tengo\s+(?:este\s+)?error\b", "Depurar y corregir este error", cleaned, flags=re.IGNORECASE).strip()
    else:
        cleaned = re.sub(
            r"^necesito\s+(mejorar|revisar|comparar|escribir|armar|pasar|planificar|simular|extraer|analizar|explicar)\b",
            r"\1",
            cleaned,
            flags=re.IGNORECASE,
        ).strip()

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
    rest = " ".join(cleaned.split(" ")[1:]).strip().rstrip(":").strip()

    if rest:
        if parsed.action == "transformar_formato" and infinitive in ("pasar", "convertir", "transformar"):
            cleaned = f"Transformar {rest}"
            promoted = True
        elif parsed.action == "planificar_pasos" and infinitive in ("armar", "planificar", "hacer", "disenar"):
            if re.match(r"^(?:un\s+plan|una\s+hoja|un\s+cronograma)\b", rest, flags=re.IGNORECASE):
                cleaned = f"Diseñar {rest}"
            else:
                cleaned = f"Planificar {rest}"
            promoted = True
        else:
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
        cleaned = re.sub(r":+(\s*[.!?])?$", r"\1", cleaned).strip()
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
        base_goal = rewritten_goal.rstrip(".").rstrip(":").strip()
        repaired_goal = f"{base_goal} (involucrando: {', '.join(missing)})."

    return {
        "fidelity_ok": len(missing) == 0,
        "restored_items": missing,
        "goal": repaired_goal,
    }


def _split_segments_safe(text: str) -> List[str]:
    """Divide por conectores de intención sin cortar `;` dentro de bloques o código inline."""
    if not text:
        return []
    placeholders: List[str] = []

    def _hide(match: re.Match) -> str:
        idx = len(placeholders)
        placeholders.append(match.group(0))
        return f"__CODE_SEG_{idx}__"

    masked = re.sub(r"```[\s\S]*?```|`[^`]+`", _hide, text)
    raw_parts = [s.strip() for s in SEGMENT_CONNECTORS_RE.split(masked) if s.strip()]
    restored: List[str] = []
    for part in raw_parts:
        for idx, orig in enumerate(placeholders):
            part = part.replace(f"__CODE_SEG_{idx}__", orig)
        restored.append(part)
    return restored or [text]


def parse_request(
    user_text: str,
    category: str = "",
    form_data: Optional[Dict[str, Any]] = None,
    technique: str = "Estándar",
    override_domain: str = "",
    override_action: str = "",
    override_deliverable: str = "",
    negative_constraints: Optional[List[str]] = None,
    enable_overlay: bool = True,
    enable_hybrid: bool = True,
    enable_learned_boosts: bool = True,
    active_user: Optional[Any] = None,
    nb_classifier: Optional[Any] = None,
    overlay_rules: Optional[List[Dict[str, Any]]] = None,
    classify_only: bool = False,
) -> ParsedRequest:
    form_data = form_data or {}
    req = ParsedRequest(raw_text=(user_text or "").strip())

    # Etapa 0 (v6.0/v7.0): Separar pedido vs. insumo pegado
    instr_part, payload_part = split_request_payload(req.raw_text)
    req.instruction_text = instr_part
    req.payload_text = payload_part
    req.payload_info = inspect_attached_payload(payload_part, instr_part)

    # Etapa 1: Normalización sobre el pedido completo (y sobre el pedido núcleo para clasificar)
    norm_text, tokens, lemmas = normalize_and_lemmatize(req.raw_text)
    norm_instr, instr_tokens, _ = normalize_and_lemmatize(instr_part)
    req.normalized_text = norm_text
    req.tokens = tokens
    req.lemmas = lemmas
    req.word_count = len(req.raw_text.split())

    # Etapa 2: PII
    if not classify_only:
        masked_text, pii_warnings = detect_and_mask_pii(req.raw_text)
        req.masked_text = masked_text
        req.pii_warnings = pii_warnings
        req.has_pii_masked = bool(pii_warnings)

    # Etapa 3: Entidades (todo el texto) y Restricciones (solo pedido, sin contaminar por insumo pegado)
    classify_src = instr_part if payload_part else req.raw_text
    classify_norm = norm_instr if payload_part else norm_text
    classify_tokens = instr_tokens if payload_part else tokens

    ext = _extract_entities_and_constraints(
        req.raw_text, norm_text, technique, constraint_text=classify_src, form_data=form_data
    )
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
    # Recalcular contradicciones contemplando negative_constraints explícitos + form_data
    req.contradictions = _detect_contradictions(
        classify_norm, req.neg_constraints, technique, form_data=form_data
    )

    # Etapa 4: Aprendizaje activo local + Capa Overlay v8.0 + Dominio + Acción (21 Arquetipos) + Sub-intención
    if enable_learned_boosts:
        learned_tables = _get_learned_correction_boosts(user=active_user)
    else:
        learned_tables = {"actions": {}, "domains": {}}
    learned_dom_boosts = _lookup_token_boosts(classify_tokens, learned_tables.get("domains", {}))
    learned_act_boosts = _lookup_token_boosts(classify_tokens, learned_tables.get("actions", {}))
    if learned_dom_boosts or learned_act_boosts:
        req.trace.append({
            "stage": "active_learning",
            "rule": f"Refuerzo SQLite aplicado (dominios={learned_dom_boosts}, acciones={learned_act_boosts})",
        })

    overlay_act_boosts: Dict[str, float] = {}
    overlay_dom_boosts: Dict[str, float] = {}
    if enable_overlay:
        overlay_act_boosts, overlay_dom_boosts, overlay_traces = match_overlay_rules(
            classify_src, classify_norm, overlay_rules=overlay_rules
        )
        req.trace.extend(overlay_traces)

    domain_hint = override_domain or category
    if not classify_only:
        req.domain, dom_trace = _classify_domain(
            classify_norm,
            domain_hint,
            entities=req.entities,
            learned_domain_boosts=learned_dom_boosts,
            overlay_domain_boosts=overlay_dom_boosts,
        )
        req.trace.extend(dom_trace)

    segments_raw = _split_segments_safe(classify_src)
    req.is_single_clause = len(segments_raw) <= 1

    global_scores, score_details = _score_actions_detailed(
        classify_src,
        classify_norm,
        tokens=classify_tokens,
        learned_action_boosts=learned_act_boosts,
        has_payload=bool(payload_part),
        overlay_action_boosts=overlay_act_boosts,
    )
    if len(segments_raw) > 1:
        seg0 = segments_raw[0]
        seg0_norm, seg0_toks, _ = normalize_and_lemmatize(seg0)
        seg0_scores, seg0_details = _score_actions_detailed(
            seg0,
            seg0_norm,
            tokens=seg0_toks,
            learned_action_boosts=learned_act_boosts,
            has_payload=bool(payload_part),
            overlay_action_boosts=overlay_act_boosts,
        )
        # En pedidos multi-cláusula ("X; y además Y"), la primera cláusula define la intención principal
        blended_scores = {
            k: round(min(0.65 * seg0_scores.get(k, 0.0) + 0.35 * global_scores.get(k, 0.0), 0.99), 4)
            for k in global_scores
        }
        ranked = sorted(blended_scores.items(), key=lambda kv: kv[1], reverse=True)
        score_details = seg0_details
    else:
        ranked = sorted(global_scores.items(), key=lambda kv: kv[1], reverse=True)

    top1_action, top1_score = ranked[0]
    top2_action, top2_score = ranked[1] if len(ranked) > 1 else ("explicar_concepto", 0.0)

    if top1_score == 0.0:
        top1_action = "explicar_concepto"

    secondary: List[str] = []
    if len(segments_raw) > 1:
        for seg in segments_raw[1:]:
            seg_norm, seg_toks, _ = normalize_and_lemmatize(seg)
            seg_scores, _ = _score_actions_detailed(
                seg,
                seg_norm,
                tokens=seg_toks,
                learned_action_boosts=learned_act_boosts,
                has_payload=bool(payload_part),
                overlay_action_boosts=overlay_act_boosts,
            )
            seg_top, seg_val = max(seg_scores.items(), key=lambda kv: kv[1])
            if seg_top != top1_action and seg_val >= max(0.55 * top1_score, 0.20) and seg_top not in secondary:
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

    # Carril B: conservar filenames/errores del Inspector de Tracebacks cuando es código/error o depurar/diagnosticar
    if req.payload_info.get("payload_kind") in ("error_consola", "codigo") or req.action in ("depurar_error", "diagnosticar_resolver"):
        for fn in req.payload_info.get("payload_filenames", []):
            if fn not in req.filenames:
                req.filenames.append(fn)
        for err in req.payload_info.get("payload_errors", []):
            if err not in req.errors_detected:
                req.errors_detected.append(err)

    # Calibración v7.0/v7.2 de confianza y margen
    raw_margin = max(top1_score - top2_score, 0.0)
    req.margin = round(raw_margin, 3)

    useful_words = [t for t in req.tokens if t not in SPANISH_STOPWORDS]
    is_short_or_trivial = (
        norm_text in TRIVIAL_GREETINGS
        or len(useful_words) <= 2
        or (req.word_count < 4 and not req.entities and not req.errors_detected)
    )

    if is_short_or_trivial:
        req.confidence = round(
            min(max(top1_score * 0.65, 0.15 if req.word_count >= 3 else 0.05), 0.45),
            3,
        )
    elif top1_score == 0.0:
        req.confidence = 0.15 if req.word_count >= 3 else 0.05
    else:
        top1_det = score_details.get(top1_action, {})
        cal = top1_score
        cal += min(raw_margin * 0.55, 0.22)
        if top1_det.get("lex_hits", 0.0) >= 1.0 and top1_det.get("tfidf", 0.0) >= 0.12:
            cal += 0.12
        if req.entities or req.filenames or req.errors_detected or payload_part:
            cal += 0.06
        if top1_det.get("tiebreak"):
            cal += 0.05
        if top1_det.get("overlay_bonus", 0.0) > 0.0:
            cal += 0.10
        req.confidence = round(min(max(cal, 0.15), 0.99), 3)

    # Desempate probabilístico híbrido v8.0 (únicamente en baja certeza, sin sobreescribir alta certeza)
    if enable_hybrid and not (override_action and override_action in actions_cfg):
        hyb = classify_hybrid_action(
            text=classify_src,
            det_action=req.action,
            det_confidence=req.confidence,
            det_margin=req.margin,
            nb_classifier=nb_classifier,
            word_count=req.word_count,
            is_trivial=(norm_text in TRIVIAL_GREETINGS),
        )
        if hyb["used_nb"] and hyb["final_action"] in actions_cfg:
            prev_action = req.action
            req.action = hyb["final_action"]
            req.action_label = actions_cfg.get(req.action, {}).get("label", req.action)
            req.confidence = hyb["final_confidence"]
            req.trace.append({
                "stage": "hybrid_tiebreak",
                "prev_action": prev_action,
                "nb_action": hyb["nb_action"],
                "nb_confidence": hyb["nb_confidence"],
                "rule": (
                    f"Desempate probabilístico Naive Bayes v8.0 (baja certeza): "
                    f"'{prev_action}' → '{req.action}' (p={hyb['nb_confidence']:.2f})"
                ),
            })

    if classify_only:
        return req

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

    req.subintent, req.subintents_matched = _detect_subintents(classify_src, classify_norm, req.action)
    req.ontology_objects = _detect_ontology_objects(classify_norm, action=req.action, subintent=req.subintent)

    # Extractor de roles semánticos y calculador determinístico (Carril A para roles/cálculo)
    req.roles = extract_semantic_roles(classify_src, payload_info=req.payload_info)
    req.calc_info = compute_control_values(classify_src, roles=req.roles)

    # v7.1/v7.2: Ancla temática visible cuando el pedido tiene tema explícito limpio
    tema_cand = (req.roles.get("tema") or "").strip()
    if tema_cand and len(tema_cand) >= 3 and tema_cand.lower() != "el tema solicitado":
        req.topic_anchor = tema_cand

    req.is_conceptual_no_data = _check_conceptual_no_data(
        action=req.action,
        payload_kind=req.payload_info.get("payload_kind", "sin_insumo"),
        filenames=req.filenames,
        normalized_text=classify_norm,
    )

    if len(useful_words) < 4 and (len(useful_words) <= 2 or (not req.entities and not req.errors_detected and req.confidence < 0.45)):
        req.is_vague = True
        req.suggested_paths = _build_suggested_paths(req.raw_text)

    if (req.margin < 0.15 or req.word_count < 5 or req.is_vague) and not (score_details.get(top1_action, {}).get("tiebreak") == "tech_creation" and req.confidence >= 0.85):
        req.needs_disambiguation = True
        cand_pair = [(top1_action, top1_score)]
        alt_action = top2_action if top2_score > 0.0 and top2_action != top1_action else (
            "planificar_pasos" if top1_action == "explicar_concepto" else "explicar_concepto"
        )
        alt_score = top2_score if alt_action == top2_action else 0.0
        cand_pair.append((alt_action, alt_score))
        req.disambiguation_options = [
            {
                "action": ak,
                "label": actions_cfg.get(ak, {}).get("label", ak),
                "hint": _ACTION_SHORT_HINTS.get(ak, ""),
                "score": round(as_, 3),
            }
            for ak, as_ in cand_pair
        ]

    req.suggested_slots, req.active_slot_ids = _get_slots_for_request(
        req.domain,
        req.action,
        form_data,
        conceptual_no_data=req.is_conceptual_no_data,
        classify_norm=classify_norm,
        req=req,
    )
    req.facets = _build_facets(req, classify_norm=classify_norm)

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

_PANDAS_TEXT_RE = re.compile(r"\b(?:pandas|numpy|scipy|sklearn)\b|df\.", flags=re.IGNORECASE)


def _directive_allowed_by_compatibility(d: Dict[str, Any], parsed: ParsedRequest, facet_set: set) -> bool:
    did = d.get("id", "")
    # Guarda Anti-Contradicción: sin librerías externas / librería estándar / generar código sin pandas
    if "neg:sin_librerias" in facet_set or (
        parsed.action == "generar_codigo"
        and "entity:pandas" not in facet_set
        and "entity:sklearn" not in facet_set
        and "entity:scikit-learn" not in facet_set
    ):
        if did.startswith(("pandas.", "sklearn.", "regresion.")):
            return False
        blob = " ".join(str(d.get(k, "")) for k in ("text", "text_short", "verifiable", "edge_cases"))
        if _PANDAS_TEXT_RE.search(blob):
            return False

    # Compuerta SQL: solo en generar_codigo, depurar_error o diagnosticar_resolver
    if did.startswith("sql.") and parsed.action not in ("generar_codigo", "depurar_error", "diagnosticar_resolver"):
        return False

    # Compuerta Negocios/Planilla de ventas: solo en gestión/control de ventas/caja, nunca en comparar/código/extracción/promoción
    if did.startswith("neg."):
        if parsed.action in (
            "comparar_evaluar", "generar_codigo", "extraer_informacion",
            "transformar_formato", "redactar_contenido", "simular_practicar",
            "diagnosticar_resolver", "calcular_modelar", "auditar_criticar",
        ):
            return False
        if parsed.subintent == "proyecto":
            return False
        if did in ("neg.rutina", "neg.herramienta") and "sub:rutina_negocio" not in facet_set:
            return False

    # Compuerta tabla comparativa: nunca en extracción/transformación/cálculo/clasificación/auditoría
    if did == "estudio.comparar" and parsed.action not in ("comparar_evaluar", "explicar_concepto", "decidir_recomendar"):
        return False

    return True


def select_directives(parsed: ParsedRequest, level: str = "Completa") -> List[Dict[str, Any]]:
    level_key = (level or "Completa").lower()
    if level_key not in ("ligera", "completa", "profunda"):
        level_key = "completa"

    facet_set = set(parsed.facets)
    candidates: List[Dict[str, Any]] = []

    for d in KNOWLEDGE_BASE.get("directives", []):
        if level_key not in d.get("levels", ["completa"]):
            continue
        if not _directive_allowed_by_compatibility(d, parsed, facet_set):
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
    Preserva intacta la indentación dentro de <datos_entrada>...</datos_entrada> y la oración de # Objetivo.
    """
    payload_blocks: List[str] = []

    def _hide_payload(match: re.Match) -> str:
        idx = len(payload_blocks)
        payload_blocks.append(match.group(0))
        return f"__PL_PAYLOAD_BLOCK_{idx}__"

    protected = re.sub(r"<datos_entrada>[\s\S]*?</datos_entrada>", _hide_payload, text)
    protected = re.sub(r"# Objetivo\n[^\n]+", _hide_payload, protected)
    banned = KNOWLEDGE_BASE.get("lint_rules", {}).get("banned_patterns", [])
    cleaned = protected
    removed_hits = 0
    for pat in banned:
        new_cleaned, n = re.subn(pat, "", cleaned, flags=re.IGNORECASE)
        if n > 0:
            removed_hits += n
            cleaned = new_cleaned
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\bde el\b", "del", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    for idx, orig_block in enumerate(payload_blocks):
        cleaned = cleaned.replace(f"__PL_PAYLOAD_BLOCK_{idx}__", orig_block)

    content_lines = [
        ln.strip() for ln in cleaned.splitlines()
        if ln.strip() and not ln.strip().startswith("#") and ln.strip() not in ("<datos_entrada>", "</datos_entrada>")
    ]
    if not content_lines:
        return {
            "text": cleaned,
            "noise_ratio": 0.0,
            "anchor_coverage": 1.0,
            "anchor_coverage_pct": 100,
            "noise_ratio_pct": 0,
            "removed_hits": removed_hits,
        }

    anchor_terms = set(
        [e.lower() for e in parsed.entities]
        + [f.lower() for f in parsed.filenames]
        + [er.lower() for er in parsed.errors_detected]
        + [o.lower() for o in parsed.ontology_objects]
        + [o.replace("_", " ").lower() for o in parsed.ontology_objects]
        + [str(a).lower() for a in (extra_anchors or []) if a]
        + [
            "objetivo", "dominio", "intención", "entregable", "formato", "criterio",
            "completar", "pega aquí", "pegá acá", "fefo", "iqr", "pearson", "spearman", "keyerror",
            "traceback", "excepción", "fragmento", "síntesis", "jerárquica", "nota formal",
            "aclaración", "hipótesis", "verificable",
            "df.", "sql", "join", "markdown", "tabla", "autoevaluación", "párrafo",
            "restricción", "restricciones", "prohibido", "supuesto", "borde", "validación", "ejemplo",
            "datos", "archivo", "columna", "código", "error", "causa", "encabezado",
            "firma", "licencia", "comprobante", "lote", "venta", "vencimiento",
            "reposición", "planilla", "semanal", "diaria", "mensual", "rutina", "cronograma", "días",
            "correlación", "regresión", "gráfico", "definición", "analogía",
            "hallazgos", "métricas", "nulos", "outliers", "causalidad", "checklist",
            "asunto", "saludo", "destinatario", "desglose", "herramientas", "público",
            "tono", "idioma", "reproducible", "python", "pandas", "excel", "sheets",
            "etapa", "paso", "rotación", "negocio", "mercadería", "vencer", "promociones",
            "json", "objeto", "precio", "categoría", "sin_categoria", "null", "unidad",
            "cláusula", "riesgo", "gravedad", "abogado", "inquilino", "obligación",
            "whatsapp", "instagram", "turno", "oraciones", "personaje", "fin", "devolución",
            "margen", "escenario", "fórmula", "costo", "venta", "gastos",
            "gancho", "llamado a la acción", "locución", "escena", "duración", "simulacro", "ejercicios", "diarias", "clichés", "cliche", "cercano", "promesa", "cifra", "fuente", "no consta", "registros",
            "jerga", "confusiones", "malentendidos", "coherencia", "conocimientos previos",
            "educativo", "profundidad", "enfoque", "autodidacta", "intuitiva", "tema principal",
            "término", "nivel", "bibliográficas", "citas", "claridad", "proveedor", "plazo", "pago", "prórroga",
        ]
    )

    anchored = 0
    for ln in content_lines:
        ln_low = ln.lower()
        ln_check = re.sub(r"^\s*\d+\.\s*", "", ln_low)
        has_anchor = (
            any(term in ln_low for term in anchor_terms)
            or bool(re.search(r"\d+", ln_check))
            or bool(re.search(r"`[^`]+`", ln))
            or ln_low.startswith(("actúa como", "objetivo:", "formato", "restricciones:", "analiza únicamente", "procesa únicamente"))
        )
        if has_anchor:
            anchored += 1

    anchor_coverage_pct = int(round((anchored / len(content_lines)) * 100))
    noise_ratio_pct = max(100 - anchor_coverage_pct, 0)
    anchor_coverage = round(anchor_coverage_pct / 100.0, 2)
    noise_ratio = round(noise_ratio_pct / 100.0, 2)
    return {
        "text": cleaned,
        "noise_ratio": noise_ratio,
        "anchor_coverage": anchor_coverage,
        "anchor_coverage_pct": anchor_coverage_pct,
        "noise_ratio_pct": noise_ratio_pct,
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
    if noise_ratio >= 0.10:
        # v7.1: ningún prompt con >=10% de relleno puede mostrar 100/100
        penalties += max(6, int(round((noise_ratio - 0.08) * 60)))
    # v7.2: penalizar contradicción estándar vs Pandas o ítems positivos en # Qué no hacer
    if "neg:sin_librerias" in parsed.facets and _PANDAS_TEXT_RE.search(improved_prompt):
        penalties += 12
    if "# Qué no hacer" in improved_prompt:
        qnh_block = improved_prompt.split("# Qué no hacer", 1)[1].split("# ", 1)[0]
        for qln in qnh_block.splitlines():
            qclean = qln.strip()
            if qclean.startswith("- "):
                qbody = _strip_accents(qclean[2:].strip().lower())
                if not qbody.startswith(("no ", "evita ", "nunca ", "prohibido ")):
                    penalties += 6
                    break

    final_score = int(round(max(min(weighted_total - penalties, 100), 10)))
    if noise_ratio >= 0.10:
        final_score = min(final_score, 92)
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

_EXAM_CONTEXT_RE = re.compile(
    r"\b(?:examen|examenes|parcial|parciales|final|finales|recuperatorio|facultad|universidad|"
    r"terciario|catedra|trabajo\s+practico|tp|autoevaluacion|rendir)\b",
    flags=re.IGNORECASE,
)


def _is_exam_context(parsed: ParsedRequest, form_data: Dict[str, Any]) -> bool:
    if _EXAM_CONTEXT_RE.search(parsed.normalized_text or ""):
        return True
    for k, v in form_data.items():
        if k == "Reglas Rápidas" or not isinstance(v, str):
            continue
        if _EXAM_CONTEXT_RE.search(_strip_accents(v.lower())):
            return True
    return False


def _parse_quick_rules(form_data: Dict[str, Any], tema_label: str) -> Tuple[List[str], List[str]]:
    """Convierte 'Reglas Rápidas' en instrucciones y restricciones operativas reales."""
    raw_rules = str(form_data.get("Reglas Rápidas") or "").strip()
    if not raw_rules:
        return [], []
    quick_insts: List[str] = []
    quick_restrs: List[str] = []
    for part in re.split(r"[,;\n]+", raw_rules):
        rule_norm = _strip_accents(part.strip().lower())
        if not rule_norm:
            continue
        if "ejemplo" in rule_norm:
            quick_insts.append(f"Incluye al menos 2 ejemplos reales y concretos aplicados a {tema_label}.")
        elif "tecnicismo" in rule_norm:
            quick_restrs.append(
                f"- Evita jerga técnica innecesaria al hablar de {tema_label}; si aparece un término técnico indispensable, defínelo en una línea simple."
            )
        elif "tabla comparativa" in rule_norm:
            quick_insts.append(
                f"Incluye una tabla comparativa en Markdown con criterios claros y comparables sobre {tema_label}."
            )
        elif "casos borde" in rule_norm or "errores" in rule_norm:
            quick_insts.append(
                f"Detalla casos borde o errores frecuentes al aplicar {tema_label} y cómo prevenirlos."
            )
        elif "relleno" in rule_norm:
            quick_restrs.append(
                f"- Responde de forma directa sobre {tema_label} sin introducciones vacías, rodeos ni cierres genéricos."
            )
    return quick_insts, quick_restrs


def _parse_study_slot_instructions(
    form_data: Dict[str, Any],
    tema_label: str,
    technique: str,
    active_directives: List[Dict[str, Any]],
) -> Tuple[List[str], List[str]]:
    """
    Operacionaliza las opciones de estudio elegidas en `study_focus` o `explain_depth`:
    - 'Con ejercicios resueltos' -> fase ejecutar
    - 'Con preguntas de examen' / 'Con preguntas de repaso' -> fase validar/entregar
      (evitando duplicar si ya está activa la técnica Pedagógico o `estudio.parcial`).
    """
    exec_insts: List[str] = []
    closing_insts: List[str] = []
    vals = [
        _strip_accents(str(form_data.get(k) or "").strip().lower())
        for k in ("study_focus", "explain_depth")
    ]
    joined = " | ".join(v for v in vals if v)
    if not joined:
        return exec_insts, closing_insts

    if "con ejercicios resueltos" in joined:
        exec_insts.append(
            f"Incluye al menos 2 ejercicios prácticos sobre {tema_label} resueltos paso a paso, explicando el porqué de cada paso."
        )

    has_pedagogic_or_parcial = (
        technique == "Pedagógico"
        or any(d.get("id") == "estudio.parcial" for d in active_directives)
    )
    if ("con preguntas de examen" in joined or "con preguntas de repaso" in joined) and not has_pedagogic_or_parcial:
        closing_insts.append(
            f"Incluye al final 3 preguntas de autoevaluación o examen sobre {tema_label} con sus respuestas justificadas."
        )

    return exec_insts, closing_insts


def _instruction_bucket(line: str) -> Optional[str]:
    low = _strip_accents(line.lower())
    if re.search(r"(?:empieza|comienza|inicia)\s+con\s+una\s+definicion|definicion\s+(?:simple|intuitiva)", low):
        return "opening_definition"
    if re.search(r"errores\s+(?:comunes|frecuentes)|confusiones\s+(?:frecuentes|habituales|tipicas)", low):
        return "common_errors"
    if re.search(r"ilustra\s+.*\b(?:ejemplo|analogia)|al\s+menos\s+(?:un|2)\s+ejemplos?", low):
        return "concrete_examples"
    if re.search(
        r"incluye\s+asunto,\s*saludo|estructura\s+el\s+(?:mensaje|correo|guion)|encabezado.*cuerpo.*cierre|gancho\s+inicial.*desarrollo.*cierre",
        low,
    ):
        return "message_structure"
    if re.search(r"(?:presenta|arma)\s+una\s+tabla\s+comparativa|establece\s+criterios\s+claros\s+y\s+homogeneos", low):
        return "comparison_criteria"
    return None


def _dedupe_instructions(lines: List[str]) -> List[str]:
    """Elimina duplicados literales, solapamientos semánticos y repeticiones de apertura."""
    result: List[str] = []
    seen_buckets = set()
    seen_word_sets: List[set] = []

    for line in lines:
        clean = (line or "").strip()
        if not clean:
            continue
        bucket = _instruction_bucket(clean)
        if bucket and bucket in seen_buckets:
            # Si llega una instrucción más rica de ejemplos reales (2 ejemplos), reemplazar la genérica de 1 ejemplo
            if bucket == "concrete_examples" and "2 ejemplos reales" in clean.lower():
                for i, prev in enumerate(result):
                    if _instruction_bucket(prev) == "concrete_examples":
                        result[i] = clean
                        break
            continue

        words = {
            w for w in re.findall(r"[a-z0-9]{4,}", _strip_accents(clean.lower()))
            if w not in SPANISH_STOPWORDS
        }
        is_near_dup = False
        if words:
            for prev_w in seen_word_sets:
                if not prev_w:
                    continue
                inter = len(words & prev_w)
                union = len(words | prev_w)
                if union > 0 and (inter / union) >= 0.62:
                    is_near_dup = True
                    break
        if is_near_dup:
            continue

        if bucket:
            seen_buckets.add(bucket)
        seen_word_sets.append(words)
        result.append(clean)

    return result


ONTOLOGY_OBJECT_LABELS = {
    "nota_formal": "nota formal",
    "licencia": "licencia",
    "parcial": "parcial",
    "stock": "stock",
    "ventas": "ventas",
    "vencimientos": "vencimientos",
    "precios": "precios",
    "dataset": "dataset",
}


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
    tema_label = (
        parsed.topic_anchor
        or parsed.roles.get("tema")
        or (", ".join(parsed.entities[:2]) if parsed.entities else parsed.domain)
    )
    exam_ctx = _is_exam_context(parsed, form_data)

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

    # Reglas Rápidas -> instrucciones y restricciones operativas reales (v7.1)
    quick_insts, quick_restrs = _parse_quick_rules(form_data, tema_label)

    # Contexto real (sin secciones vacías ni claves técnicas crudas)
    ctx_lines: List[str] = []
    if parsed.filenames:
        ctx_lines.append(f"- **Archivos:** {', '.join(parsed.filenames)}")
    if parsed.entities:
        ctx_lines.append(f"- **Herramientas / Conceptos:** {', '.join(parsed.entities[:8])}")
    elif parsed.topic_anchor:
        ctx_lines.append(f"- **Tema principal:** {parsed.topic_anchor}")
    if parsed.errors_detected:
        ctx_lines.append(f"- **Errores detectados:** {', '.join(parsed.errors_detected)}")
    if parsed.roles.get("perspectiva"):
        ctx_lines.append(f"- **Perspectiva:** {parsed.roles['perspectiva']}")
    if parsed.roles.get("canal"):
        ctx_lines.append(f"- **Canal:** {parsed.roles['canal']}")
    if parsed.action == "planificar_pasos":
        if parsed.roles.get("plazo"):
            ctx_lines.append(f"- **Plazo disponible:** {parsed.roles['plazo']}")
        if parsed.roles.get("dedicacion"):
            ctx_lines.append(f"- **Dedicación:** {parsed.roles['dedicacion']}")
        if parsed.roles.get("recursos"):
            ctx_lines.append(f"- **Canales / recursos disponibles:** {', '.join(parsed.roles['recursos'])}")
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
            if obj_k == "nota_formal" and "licencia" in parsed.ontology_objects:
                continue
            if obj_k in ("ventas", "stock", "vencimientos", "precios") and (
                parsed.subintent != "rutina_negocio"
                or parsed.action in (
                    "comparar_evaluar", "generar_codigo", "extraer_informacion",
                    "transformar_formato", "diagnosticar_resolver", "calcular_modelar",
                )
            ):
                continue
            if obj_k == "dataset" and (
                "neg:sin_librerias" in parsed.facets
                or (parsed.action == "generar_codigo" and "pandas" not in parsed.entities)
            ):
                continue
            delivs = ontology.get(obj_k, {}).get("deliverables", [])
            if delivs:
                obj_label = ONTOLOGY_OBJECT_LABELS.get(obj_k, obj_k.replace("_", " "))
                ctx_lines.append(f"- **Desglose de {obj_label}:** {'; '.join(delivs)}")

    for k, v in form_data.items():
        if v and k not in ("Rol que debe asumir la IA", "Formato de Salida", "Reglas Rápidas"):
            human_label = _format_slot_label(k)
            ctx_lines.append(f"- **{human_label}:** {v}")

    # Instrucciones composicionales (sin duplicación semántica y respetando fases de cierre)
    raw_inst_lines: List[str] = []
    closing_summary_lines: List[str] = []
    if univ and univ["instructions"]:
        raw_inst_lines.extend(univ["instructions"])
        active_directives = [d for d in directives if d.get("priority", 0) >= 95]
    else:
        active_directives = directives

    classify_low = _strip_accents((parsed.instruction_text or parsed.raw_text).lower())

    # P0.3: Python librería estándar sin librerías externas
    if parsed.action == "generar_codigo" and "neg:sin_librerias" in parsed.facets:
        raw_inst_lines.append(
            "Usa exclusivamente módulos de la librería estándar de Python (como `csv` y `collections`) sin importar paquetes externos."
        )
        if "vacio" in classify_low or "csv" in classify_low:
            raw_inst_lines.append(
                "Valida y maneja explícitamente el caso de archivo vacío, sin filas de datos o con encabezados faltantes."
            )
        if parsed.language == "Español" or "espanol" in classify_low:
            raw_inst_lines.append(
                "Escribe todos los comentarios del código y mensajes de salida en español claro."
            )
        raw_inst_lines.append("Incluye un ejemplo mínimo de uso o ejecución esperada.")

    # P0.3: Decisión justificada explícita en comparar_evaluar cuando el usuario pide recomendación
    if parsed.action == "comparar_evaluar" and re.search(
        r"\b(?:cual\s+(?:me\s+)?conviene|recomendame|que\s+elegir|mejor\s+opcion|cual\s+es\s+mejor)\b",
        classify_low,
    ):
        raw_inst_lines.append(
            "Detalla ventajas, desventajas y casos de uso de cada alternativa y cierra con una recomendación final justificada para el contexto planteado."
        )

    # P0.3: Código corregido listo para ejecutar en depurar_error (también en Express)
    if parsed.action == "depurar_error":
        raw_inst_lines.append(
            "Identifica la causa raíz exacta del fallo y entrega el fragmento o código corregido listo para ejecutar."
        )

    # P1.4: Reflejar plazo, dedicación y recursos/canales explícitos en planes
    is_days_plan = False
    if parsed.action == "planificar_pasos":
        plazo = parsed.roles.get("plazo")
        dedicacion = parsed.roles.get("dedicacion")
        recursos = parsed.roles.get("recursos") or []
        is_days_plan = bool(plazo and re.search(r"\bd[ií]as?\b", plazo, flags=re.IGNORECASE))
        unit_tasks = "tareas diarias concretas" if is_days_plan else "tareas semanales concretas"
        if plazo or dedicacion or recursos:
            partes_plan = []
            if plazo:
                partes_plan.append(f"en un cronograma de {plazo}")
            if dedicacion:
                partes_plan.append(f"ajustado a una dedicación de {dedicacion}")
            if recursos:
                partes_plan.append(f"apoyándote únicamente en {', '.join(recursos)}")
            raw_inst_lines.append(
                f"Organiza el plan {', '.join(partes_plan)}, detallando {unit_tasks} y métricas simples de avance."
            )
        if parsed.subintent == "estudio" and re.search(r"\b(?:ejercicios?|simulacros?)\b", classify_low):
            raw_inst_lines.append(
                "Prioriza la resolución de ejercicios prácticos en cada bloque diario y reserva el último día para un simulacro completo de evaluación."
            )

    # P1.5 (v7.2.1): Guion audiovisual corto con marcas de duración y escena/locución
    if parsed.action == "redactar_contenido" and parsed.subintent == "guion_video":
        m_dur = re.search(
            r"\b(\d+\s*(?:segundos?|seg|s|minutos?|min))\b",
            parsed.instruction_text or parsed.raw_text,
            flags=re.IGNORECASE,
        )
        dur_txt = m_dur.group(1).strip() if m_dur else "la duración solicitada"
        raw_inst_lines.append(
            f"Ajusta la extensión del guion a {dur_txt} (aprox. 65 a 75 palabras locutadas cada 30 segundos), "
            "indicando [Video / Escena] y [Audio / Locución] en cada tramo."
        )
        if parsed.tone:
            raw_inst_lines.append(
                f"Mantén un tono {parsed.tone.lower()} de conversación natural, evitando clichés publicitarios y frases hechas de vendedor."
            )

    for d in active_directives:
        if d["id"] == "estudio.errores_comunes" and not exam_ctx:
            txt = (
                f"Señala errores o confusiones frecuentes sobre {tema_label}."
                if level == "Ligera"
                else f"Incluye una sección breve de 'Errores o confusiones frecuentes sobre {tema_label}' señalando malentendidos habituales."
            )
        else:
            txt = d["text_short"] if level == "Ligera" else d["text"]

        # La ficha de repaso rápido ('estudio.resumen') va siempre al cierre final de # Instrucciones
        if d["id"] == "estudio.resumen":
            closing_summary_lines.append(txt)
        else:
            raw_inst_lines.append(txt)

    # Operacionalizar enfoque de estudio (study_focus / explain_depth)
    study_exec_insts, study_closing_insts = _parse_study_slot_instructions(
        form_data=form_data,
        tema_label=tema_label,
        technique=technique,
        active_directives=active_directives,
    )

    # En explicar_concepto (Completa/Profunda), garantizar 3-4 pasos progresivos en orden didáctico:
    # Definición -> Cómo funciona -> Ejemplos -> Ejercicios resueltos -> Errores frecuentes -> Preguntas -> Ficha de repaso
    if parsed.action == "explicar_concepto" and level in ("Completa", "Profunda") and not univ:
        non_err = [ln for ln in raw_inst_lines if _instruction_bucket(ln) != "common_errors"]
        err_only = [ln for ln in raw_inst_lines if _instruction_bucket(ln) == "common_errors"]
        raw_inst_lines = (
            non_err
            + [
                f"Desarrolla paso a paso cómo funciona {tema_label}, avanzando de lo simple a lo complejo con sus componentes clave.",
                f"Ilustra {tema_label} con al menos un ejemplo práctico y cotidiano fácil de visualizar.",
            ]
            + quick_insts
            + study_exec_insts
            + err_only
            + study_closing_insts
            + closing_summary_lines
        )
    else:
        raw_inst_lines.extend(quick_insts)
        raw_inst_lines.extend(study_exec_insts)
        raw_inst_lines.extend(study_closing_insts)
        raw_inst_lines.extend(closing_summary_lines)

    # Deduplicar antes de verificar si hace falta completar desde base_inst
    inst_lines = _dedupe_instructions(raw_inst_lines)

    if len(inst_lines) < 2 or (parsed.action == "explicar_concepto" and len(inst_lines) < 3):
        candidate_base = list(inst_lines)
        for base_inst in act_info.get("instructions", []):
            candidate_base.append(base_inst)
            candidate_base = _dedupe_instructions(candidate_base)
            if len(candidate_base) >= (3 if level == "Ligera" else 4):
                break
        inst_lines = candidate_base

    for note in adj_notes:
        if note not in inst_lines:
            inst_lines.append(note)

    # Restricciones reales (solo si existen, integrando Reglas Rápidas)
    restr_lines: List[str] = []
    if univ and univ["restrictions"]:
        for ur in univ["restrictions"]:
            restr_lines.append(f"- {ur}")
    for qr in quick_restrs:
        if qr not in restr_lines:
            restr_lines.append(qr)
    for nc in parsed.neg_constraints:
        nc_clean = nc.strip().rstrip(".")
        if not nc_clean:
            continue
        line_nc = f"- {nc_clean[0].upper()}{nc_clean[1:]}."
        if line_nc not in restr_lines:
            restr_lines.append(line_nc)
    for qc in parsed.quant_constraints:
        restr_lines.append(f"- Límite cuantitativo: {qc}.")

    # Formato de salida
    deliv_info = deliv_cfg.get(parsed.deliverable, {})
    if parsed.action == "redactar_contenido" and parsed.subintent == "guion_video":
        fmt_instruction = (
            "Presenta el guion dividido en 3 bloques de tiempo (0–3 s Gancho, Desarrollo central y Cierre con llamado a la acción), "
            "detallando [Video / Escena] y [Audio / Locución] en cada bloque."
        )
    else:
        fmt_instruction = (
            univ["format_override"]
            if (univ and univ.get("format_override"))
            else deliv_info.get(
                "format_instruction",
                f"Presenta la respuesta en formato **{parsed.deliverable}**, con títulos claros en Markdown.",
            )
        )
        if is_days_plan and parsed.deliverable == "plan / cronograma":
            fmt_instruction = fmt_instruction.replace("por etapas o semanas, detallando en cada una", "por días, detallando en cada día")
            fmt_instruction = fmt_instruction.replace("por etapas o semanas", "por días")

    # Criterio de éxito verificable y coherente (sin mencionar autoevaluación si no fue solicitada)
    has_self_eval = (
        technique == "Pedagógico"
        or any(d["id"] == "estudio.parcial" for d in active_directives)
        or any(
            "autoevaluaci" in x.lower() or "preguntas de examen" in x.lower() or "preguntas de repaso" in x.lower()
            for x in inst_lines + [str(v) for v in form_data.values()]
        )
    )

    success_parts: List[str] = []
    if univ and univ["success_criteria"]:
        for sc in univ["success_criteria"]:
            success_parts.append(f"- {sc}")
    act_crit = success_cfg.get("by_action", {}).get(parsed.action, "")
    if act_crit and not (univ and univ["success_criteria"]):
        if parsed.action == "explicar_concepto" and not has_self_eval:
            act_crit = (
                f"Un lector del nivel indicado comprende la definición y el funcionamiento de {tema_label} "
                "en una lectura y reconoce sus errores o confusiones frecuentes."
            )
        elif parsed.action == "redactar_contenido" and parsed.subintent == "guion_video":
            act_crit = (
                "El guion incluye gancho inicial (0–3 s), desarrollo de escena y locución, cierre con llamado a la acción "
                "y respeta la duración y tono solicitados sin frases cliché."
            )
        success_parts.append(f"- {act_crit}")
    deliv_crit = "" if (parsed.action == "redactar_contenido" and parsed.subintent == "guion_video") else success_cfg.get("by_deliverable", {}).get(parsed.deliverable, "")
    if deliv_crit:
        if is_days_plan and parsed.deliverable == "plan / cronograma":
            deliv_crit = deliv_crit.replace("por etapas o semanas", "por días")
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
        or ([parsed.topic_anchor] if parsed.topic_anchor else [parsed.domain])
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
            lines.append(
                "Restricciones: "
                + "; ".join(
                    [r.lstrip("- ").rstrip(".") for r in restr_lines]
                )
            )
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
            # 1. Supuestos derivados SOLO de slots faltantes relevantes (excluyendo los ya respondidos) y anclados al tema
            answered_norm = {_strip_accents(str(k).lower()) for k, v in form_data.items() if v}
            missing_items = [
                s["question"]
                for s in parsed.suggested_slots[:3]
                if _strip_accents(s["id"].lower()) not in answered_norm
            ]
            if missing_items:
                sup_txt = "\n".join(
                    f"- Si no se especifica respecto a {tema_label}, indicar qué aplica para: {q}"
                    for q in missing_items
                )
                sections.append(f"# Supuestos y datos faltantes\n{sup_txt}")

            # 2. Casos borde anclados naturalmente al tema (solo de directivas activas)
            edge_list = [d["edge_cases"] for d in active_directives if d.get("edge_cases")]
            if univ and univ.get("edge_cases"):
                edge_list.extend(univ["edge_cases"])
            if parsed.action == "generar_codigo" and "neg:sin_librerias" in parsed.facets:
                edge_list.extend([
                    "Archivo de entrada vacío, sin filas de datos o con encabezados inexistentes.",
                    "Filas con separador `;`, encoding UTF-8/Latin-1 o montos no numéricos.",
                ])
            if edge_list:
                anchored_edges = []
                valid_tema_anchor = bool(tema_label) and not re.match(r"^\d+\s+\w+$", tema_label.strip())
                for ec in list(dict.fromkeys(edge_list))[:5]:
                    if valid_tema_anchor and tema_label.lower() not in ec.lower() and not any(e in ec.lower() for e in parsed.entities):
                        anchored_edges.append(f"- {ec.rstrip('.')} al abordar {tema_label}.")
                    else:
                        anchored_edges.append(f"- {ec}")
                sections.append("# Casos borde a contemplar\n" + "\n".join(anchored_edges))

            # 3. Validación previa de proceso (distinta de # Criterio de éxito — cero copias textuales)
            success_norm_set = {
                _strip_accents(sp.lstrip("- ").strip().lower()) for sp in success_parts
            }
            val_candidates = [
                f"Comprobar que el nivel de explicación sobre {tema_label} sea coherente con el público definido sin introducir jerga sin aclarar.",
                f"Verificar ausencia de contradicciones internas, definiciones falsas o afirmaciones sin fundamento sobre {tema_label}.",
                f"Confirmar el cumplimiento de todas las restricciones declaradas y del formato de salida ({parsed.deliverable}) antes de entregar.",
            ]
            if parsed.filenames or parsed.entities:
                refs = ", ".join((parsed.filenames + parsed.entities)[:3])
                val_candidates.insert(
                    1,
                    f"Comprobar que todas las referencias técnicas ({refs}) aparezcan con nombres y parámetros exactos.",
                )
            val_unique = [
                v for v in val_candidates
                if _strip_accents(v.lower()) not in success_norm_set
            ]
            if val_unique:
                val_txt = "\n".join(f"- {v}" for v in val_unique[:4])
                sections.append(f"# Validación previa a responder\n{val_txt}")

            # 4. Guardrails (# Qué no hacer): 100% en negativo
            if parsed.is_conceptual_no_data:
                dont_list = [
                    f"No asumas conocimientos previos no declarados sobre {tema_label} ni uses jerga técnica sin definirla en su primera aparición.",
                    f"No inventes definiciones, cifras ni ejemplos falsos sobre {tema_label}; si un punto admite matices, acláralo brevemente.",
                ]
            else:
                dont_list = list(dom_info.get("guardrails", []))
            if parsed.neg_constraints:
                dont_list.extend(f"No violar la restricción: {nc.rstrip('.')}." for nc in parsed.neg_constraints)
            normalized_dont: List[str] = []
            for dl in dont_list:
                clean_dl = (dl or "").strip()
                if not clean_dl:
                    continue
                low_dl = _strip_accents(clean_dl.lower())
                if not low_dl.startswith(("no ", "evita ", "nunca ", "prohibido ")):
                    clean_dl = f"No omitas esta regla: {clean_dl[0].lower()}{clean_dl[1:]}"
                normalized_dont.append(clean_dl)
            if normalized_dont:
                dont_txt = "\n".join(f"- {dl}" for dl in normalized_dont[:4])
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
    extra_anchors.extend(nc.lower() for nc in parsed.neg_constraints if nc)
    extra_anchors.extend(parsed.filenames)
    extra_anchors.extend(parsed.errors_detected)
    if parsed.topic_anchor:
        extra_anchors.append(parsed.topic_anchor)
        for tw in re.findall(r"[a-záéíóúñ0-9]{4,}", parsed.topic_anchor.lower()):
            if _strip_accents(tw) not in SPANISH_STOPWORDS:
                extra_anchors.append(tw)
    if parsed.roles.get("tema"):
        extra_anchors.append(parsed.roles["tema"])
    if parsed.roles.get("canal"):
        extra_anchors.append(parsed.roles["canal"])
    if parsed.roles.get("plazo"):
        extra_anchors.append(parsed.roles["plazo"])
    if parsed.roles.get("dedicacion"):
        extra_anchors.append(parsed.roles["dedicacion"])
    for rec in parsed.roles.get("recursos") or []:
        extra_anchors.append(rec)
    if parsed.roles.get("perspectiva"):
        extra_anchors.append(parsed.roles["perspectiva"])
    if parsed.roles.get("rol_simular"):
        extra_anchors.append(parsed.roles["rol_simular"])
    if "neg:sin_librerias" in parsed.facets:
        extra_anchors.extend(["librería estándar", "estándar", "vacío", "csv", "collections", "comentarios"])
    if parsed.action == "extraer_informacion":
        extra_anchors.extend(["sin asignar", "no especificado", "responsable", "fecha"])
    if parsed.action == "comparar_evaluar":
        extra_anchors.extend(["recomendación", "ventajas", "desventajas", "alternativas"])
    if parsed.action == "simular_practicar":
        extra_anchors.extend(["entrevista", "repregunta", "profundidad", "turno"])
    if parsed.action in ("depurar_error", "diagnosticar_resolver"):
        extra_anchors.extend(["corregido", "ejecutar", "hipótesis", "causa"])
    if parsed.payload_info.get("extracted_prices"):
        extra_anchors.extend(str(p) for p in parsed.payload_info["extracted_prices"])
    if parsed.calc_info.get("has_calculation"):
        extra_anchors.extend([
            parsed.calc_info["ventas_sobre_venta_fmt"],
            parsed.calc_info["ventas_sobre_costo_fmt"],
        ])

    linted = lint_prompt(raw_improved, parsed, active_directives, extra_anchors=extra_anchors)
    meta = {
        "directives_used": [d["id"] for d in active_directives],
        "n_directives": len(active_directives),
        "noise_ratio": linted["noise_ratio"],
        "anchor_coverage": linted["anchor_coverage"],
        "anchor_coverage_pct": linted["anchor_coverage_pct"],
        "noise_ratio_pct": linted["noise_ratio_pct"],
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
    active_user: Optional[Any] = None,
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
        active_user=active_user,
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
        "disambiguation_options": parsed.disambiguation_options,
        "is_vague": parsed.is_vague,
        "suggested_paths": parsed.suggested_paths,
        "entities": parsed.entities,
        "topic_anchor": parsed.topic_anchor,
        "versions": parsed.versions,
        "filenames": parsed.filenames,
        "errors_detected": parsed.errors_detected,
        "neg_constraints": parsed.neg_constraints,
        "quant_constraints": parsed.quant_constraints,
        "contradictions": parsed.contradictions,
        "pii_warnings": parsed.pii_warnings,
        "has_pii": parsed.has_pii_masked,
        "suggested_slots": parsed.suggested_slots,
        "active_slot_ids": parsed.active_slot_ids,
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
    active_user: Optional[Any] = None,
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
        active_user=active_user,
    )

    safe_form_data = dict(form_data)
    safe_user_example = user_example
    if mask_pii:
        extra_pii_warnings: List[Dict[str, Any]] = []
        for fk, fv in list(safe_form_data.items()):
            if isinstance(fv, str) and fv.strip():
                masked_v, w_v = detect_and_mask_pii(fv)
                if w_v:
                    safe_form_data[fk] = masked_v
                    extra_pii_warnings.extend(w_v)
        if isinstance(safe_user_example, str) and safe_user_example.strip():
            masked_ex, w_ex = detect_and_mask_pii(safe_user_example)
            if w_ex:
                safe_user_example = masked_ex
                extra_pii_warnings.extend(w_ex)
        if parsed.topic_anchor:
            masked_ta, w_ta = detect_and_mask_pii(parsed.topic_anchor)
            if w_ta:
                parsed.topic_anchor = masked_ta
                extra_pii_warnings.extend(w_ta)
        if parsed.roles:
            for rk, rv in list(parsed.roles.items()):
                if isinstance(rv, str) and rv.strip():
                    masked_rv, w_rv = detect_and_mask_pii(rv)
                    if w_rv:
                        parsed.roles[rk] = masked_rv
                        extra_pii_warnings.extend(w_rv)
        if parsed.neg_constraints:
            cleaned_negs = []
            for nc in parsed.neg_constraints:
                masked_nc, w_nc = detect_and_mask_pii(nc)
                if w_nc:
                    extra_pii_warnings.extend(w_nc)
                cleaned_negs.append(masked_nc)
            parsed.neg_constraints = cleaned_negs
        if extra_pii_warnings:
            merged_w: Dict[str, Dict[str, Any]] = {
                w["type"]: dict(w) for w in parsed.pii_warnings if isinstance(w, dict) and w.get("type")
            }
            for ew in extra_pii_warnings:
                wt = ew["type"]
                if wt in merged_w:
                    merged_w[wt]["count"] = merged_w[wt].get("count", 0) + ew.get("count", 1)
                else:
                    merged_w[wt] = dict(ew)
            parsed.pii_warnings = list(merged_w.values())
            parsed.has_pii_masked = True

    improved_prompt, segments, meta = _assemble_prompt_with_segments(
        parsed=parsed,
        form_data=safe_form_data,
        level=level,
        technique=technique,
        user_example=safe_user_example,
        mask_pii=mask_pii,
    )

    rubric = calculate_rubric_v2(
        parsed=parsed,
        improved_prompt=improved_prompt,
        form_data=safe_form_data,
        user_example=safe_user_example,
        user_corrected=user_corrected,
        level=level,
        noise_ratio=meta["noise_ratio"],
        anchor_coverage=meta["anchor_coverage"],
    )

    analysis = [
        f"Motor {ENGINE_VERSION} | Dominio: '{parsed.domain}' | Arquetipo: '{parsed.action_label}' ({parsed.subintent}) — confianza {int(round(parsed.confidence * 100))}%.",
        f"Directivas: {meta['n_directives']} | Datos útiles: {meta['anchor_coverage_pct']}% | Relleno: {meta['noise_ratio_pct']}% | Verificables: {int(round(meta['verifiable_ratio'] * 100))}%.",
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
    for tr in parsed.trace:
        if tr.get("stage") in ("active_learning_overlay", "hybrid_tiebreak") and tr.get("rule"):
            analysis.append(tr["rule"])

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
        "topic_anchor": parsed.topic_anchor,
        "n_neg_constraints": len(parsed.neg_constraints),
        "neg_constraints": parsed.neg_constraints,
        "quant_constraints": parsed.quant_constraints,
        "contradictions": parsed.contradictions,
        "n_slots_used": rubric["n_slots_used"],
        "info_density": rubric["info_density"],
        "noise_ratio": meta["noise_ratio"],
        "anchor_coverage": meta["anchor_coverage"],
        "anchor_coverage_pct": meta["anchor_coverage_pct"],
        "noise_ratio_pct": meta["noise_ratio_pct"],
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
        "disambiguation_options": parsed.disambiguation_options,
        "is_vague": parsed.is_vague,
        "suggested_paths": parsed.suggested_paths,
        "suggested_slots": parsed.suggested_slots,
        "active_slot_ids": parsed.active_slot_ids,
        "segments": segments,
        "trace": parsed.trace,
    }


build_prompt = get_gemini_response
