import csv
import io
import json
import math
import re
import unicodedata
from collections import Counter
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from fractions import Fraction
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Utilidades de texto (100% Python estándar)
# ---------------------------------------------------------------------------

def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def _format_ars(val: Decimal) -> str:
    """Formatea un Decimal como moneda legible con punto de miles (ej. $4.000.000)."""
    rounded = int(val.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return "$" + f"{rounded:,}".replace(",", ".")


def _parse_ar_number(raw: str) -> Optional[Decimal]:
    """
    Convierte números en formato argentino/hispano a Decimal:
    '$1.200.000' -> Decimal('1200000')
    '$1.900,50'  -> Decimal('1900.50')
    '6800'       -> Decimal('6800')
    """
    if not raw:
        return None
    s = raw.strip().replace("$", "").replace(" ", "")
    if not s:
        return None
    if "," in s and "." in s:
        # Ej. 1.900,50 -> puntos son miles, coma es decimal
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    elif "." in s:
        parts = s.split(".")
        # Si todos los grupos tras el primero tienen 3 dígitos, son separadores de miles
        if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]):
            s = "".join(parts)
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


# ---------------------------------------------------------------------------
# 1. Separador y Detector Estructural de Insumos Pegados
# ---------------------------------------------------------------------------

_UNIT_PATTERN = re.compile(
    r"\b(?:x\s*\d+(?:[.,]\d+)?\s*(?:l|lt|lts|ml|kg|g|gr|u|un|unidades?)|"
    r"\d+(?:[.,]\d+)?\s*(?:l|lt|lts|ml|kg|g|gr|cc|oz|pack|u))\b",
    flags=re.IGNORECASE,
)

_PRICE_LINE_RE = re.compile(
    r"(?:^|\s)[-–—:]?\s*\$?\s*(\d{1,3}(?:\.\d{3})+|\d{3,6})(?:,(\d{1,2}))?\s*$"
)

_DEICTIC_CLAUSE_RE = re.compile(
    r"\b(?:esta\s+cl[aá]usula|este\s+contrato|esta\s+letra\s+chica|este\s+acuerdo|este\s+anexo)\b",
    flags=re.IGNORECASE,
)

_DEICTIC_GENERIC_RE = re.compile(
    r"\b(?:este\s+(?:texto|correo|mail|mensaje|c[oó]digo|archivo|error|listado)|estos\s+datos|esta\s+lista)\b",
    flags=re.IGNORECASE,
)


def split_request_payload(text: str) -> Tuple[str, str]:
    """
    Separa el pedido del usuario de los insumos pegados (bloques de código,
    listas multilínea, tablas CSV/TSV, JSON, tracebacks o cláusulas).
    """
    raw = (text or "").strip()
    if not raw:
        return "", ""

    # 1. Bloque cercado con triple backtick
    fenced = re.search(r"```[\s\S]*?```", raw)
    if fenced:
        instr = (raw[:fenced.start()] + " " + raw[fenced.end():]).strip()
        payload = fenced.group(0).strip()
        return instr or raw, payload

    # 2. Separación por salto de línea: primera(s) línea(s) de pedido + bloque de datos (3+ líneas o JSON/tabla)
    lines = raw.splitlines()
    if len(lines) >= 3:
        # Buscar dónde empieza el bloque estructurado o lista pegada
        split_idx = None
        for idx in range(1, len(lines)):
            ln = lines[idx].strip()
            if not ln:
                continue
            is_data_line = (
                bool(_PRICE_LINE_RE.search(ln))
                or ln.startswith(("{", "[", "|", "Traceback", "File \""))
                or ln.count(";") >= 2
                or ln.count(",") >= 2
                or "\t" in ln
                or bool(re.match(r"^(?:ART[ÍI]CULO|CL[ÁA]USULA|PRIMERA|SEGUNDA|\d+[.)])\b", ln, re.IGNORECASE))
            )
            if is_data_line:
                # Confirmar que haya al menos 2 líneas consecutivas o bloque de datos
                remaining = [l.strip() for l in lines[idx:] if l.strip()]
                if len(remaining) >= 2 or ln.startswith(("{", "[", "Traceback")):
                    split_idx = idx
                    break

        if split_idx is not None:
            instr = " ".join(l.strip() for l in lines[:split_idx] if l.strip())
            payload = "\n".join(l.rstrip() for l in lines[split_idx:] if l.strip())
            return instr, payload

    # 3. Separación por marcador explícito ("Cláusula:", "Texto:", "---")
    marker = re.split(r"\n\s*---+\s*\n|\b(?:cl[aá]usula|texto a revisar|datos):\s*\n", raw, maxsplit=1, flags=re.IGNORECASE)
    if len(marker) == 2 and marker[1].strip():
        return marker[0].strip(), marker[1].strip()

    # 4. (v7.0) Bloques pegados de 1-2 párrafos tras ':' + salto de línea, encabezados de mail/cláusula o comillas largas
    colon_nl = re.split(r":\s*\n+", raw, maxsplit=1)
    if len(colon_nl) == 2:
        cand_instr = colon_nl[0].strip()
        cand_pay = colon_nl[1].strip()
        if len(cand_instr) >= 8 and len(cand_pay) >= 20:
            return cand_instr, cand_pay

    if len(lines) >= 2:
        for idx in range(1, len(lines)):
            ln = lines[idx].strip()
            if not ln:
                continue
            if re.match(
                r"^(?:Asunto:|De:|Para:|Estimad[oa]\b|Hola,|CL[ÁA]USULA\b|ART[ÍI]CULO\b|PRIMERA\b|SEGUNDA\b|Traceback\b|SELECT\b|def\s+|import\s+)",
                ln,
                flags=re.IGNORECASE,
            ):
                instr = " ".join(l.strip() for l in lines[:idx] if l.strip())
                payload = "\n".join(l.rstrip() for l in lines[idx:] if l.strip())
                if instr and payload:
                    return instr, payload

    quoted_after_colon = re.search(r":\s*[\"«“]([\s\S]{25,})[\"»”]\s*$", raw)
    if quoted_after_colon:
        cand_instr = raw[:quoted_after_colon.start()].strip()
        cand_pay = quoted_after_colon.group(1).strip()
        if len(cand_instr) >= 8 and cand_pay:
            return cand_instr, cand_pay

    return raw, ""


def inspect_attached_payload(payload_text: str, instruction_text: str = "") -> Dict[str, Any]:
    """
    Clasifica estructuralmente el insumo pegado y extrae metadatos verificables
    sin confundir unidades de presentación (2.25lt, 500g, x1l) con precios.
    """
    payload = (payload_text or "").strip()
    instr = (instruction_text or "").strip()

    if not payload:
        missing_clause = bool(_DEICTIC_CLAUSE_RE.search(instr))
        missing_generic = bool(_DEICTIC_GENERIC_RE.search(instr))
        placeholder_tag = "[PEGÁ ACÁ EL TEXTO DE LA CLÁUSULA]" if missing_clause else "[PEGÁ ACÁ LOS DATOS O TEXTO]"
        return {
            "payload_kind": "sin_insumo",
            "n_lineas": 0,
            "missing_payload": missing_clause or missing_generic,
            "missing_clause": missing_clause,
            "placeholder_tag": placeholder_tag,
            "extracted_prices": [],
            "extracted_units": [],
            "items_preview": [],
            "summary_label": "Sin insumo pegado",
        }

    lines = [ln.strip() for ln in payload.splitlines() if ln.strip()]
    n_lines = len(lines)
    low_payload = _strip_accents(payload.lower())

    # 1. JSON / Log JSON
    if payload.startswith(("{", "[")) and (":" in payload or "}" in payload):
        return {
            "payload_kind": "json_log",
            "n_lineas": n_lines,
            "missing_payload": False,
            "missing_clause": False,
            "placeholder_tag": "",
            "extracted_prices": [],
            "extracted_units": [],
            "items_preview": lines[:3],
            "summary_label": f"JSON / Log ({n_lines} líneas)",
        }

    # 2. Error de consola / Traceback
    if "traceback" in low_payload or re.search(r"\b(?:keyerror|typeerror|valueerror|syntaxerror|operationalerror)\b", low_payload):
        return {
            "payload_kind": "error_consola",
            "n_lineas": n_lines,
            "missing_payload": False,
            "missing_clause": False,
            "placeholder_tag": "",
            "extracted_prices": [],
            "extracted_units": [],
            "items_preview": lines[:3],
            "summary_label": f"Error de consola ({n_lines} líneas)",
        }

    # 3. Código fuente
    if payload.startswith("```") or re.search(r"^\s*(?:def |class |import |from |SELECT |const |function )", payload, flags=re.MULTILINE):
        return {
            "payload_kind": "codigo",
            "n_lineas": n_lines,
            "missing_payload": False,
            "missing_clause": False,
            "placeholder_tag": "",
            "extracted_prices": [],
            "extracted_units": [],
            "items_preview": lines[:3],
            "summary_label": f"Bloque de código ({n_lines} líneas)",
        }

    # 4. Lista de registros / productos con precios (3+ líneas con precios o guiones)
    price_hits = 0
    extracted_prices: List[Any] = []
    extracted_units: List[str] = []
    items_preview: List[Dict[str, Any]] = []

    for ln in lines:
        units_in_ln = _UNIT_PATTERN.findall(ln)
        extracted_units.extend(units_in_ln)
        # Removemos temporalmente unidades (2.25lt, 500g, x1l) antes de buscar el precio final de la línea
        ln_no_units = _UNIT_PATTERN.sub(" ", ln)
        m_price = _PRICE_LINE_RE.search(ln_no_units)
        if m_price:
            price_hits += 1
            num_str = m_price.group(1) + ("," + m_price.group(2) if m_price.group(2) else "")
            dec_val = _parse_ar_number(num_str)
            if dec_val is not None:
                val_num: Any = int(dec_val) if dec_val == dec_val.to_integral_value() else float(dec_val)
                extracted_prices.append(val_num)
                name_part = ln[:m_price.start()].strip(" -–—:\t")
                items_preview.append({"raw_line": ln, "name": name_part or ln, "price": val_num})

    if price_hits >= 2 and n_lines >= 2:
        return {
            "payload_kind": "lista_registros",
            "n_lineas": n_lines,
            "missing_payload": False,
            "missing_clause": False,
            "placeholder_tag": "",
            "extracted_prices": extracted_prices,
            "extracted_units": list(dict.fromkeys(extracted_units)),
            "items_preview": items_preview,
            "summary_label": f"Lista de {n_lines} registros",
        }

    # 5. Tabla (Markdown o CSV/TSV)
    if all("|" in ln for ln in lines[:2]) or (n_lines >= 2 and (lines[0].count(",") >= 2 or lines[0].count(";") >= 2 or "\t" in lines[0])):
        return {
            "payload_kind": "tabla",
            "n_lineas": n_lines,
            "missing_payload": False,
            "missing_clause": False,
            "placeholder_tag": "",
            "extracted_prices": [],
            "extracted_units": [],
            "items_preview": lines[:3],
            "summary_label": f"Tabla ({n_lines} filas)",
        }

    # 6. Contrato o cláusula legal pegada
    if any(k in low_payload for k in ("locatario", "locador", "clausula", "arrendatario", "rescision", "indemnizacion", "jurisdiccion", "fiador")):
        return {
            "payload_kind": "contrato_legal",
            "n_lineas": n_lines,
            "missing_payload": False,
            "missing_clause": False,
            "placeholder_tag": "",
            "extracted_prices": [],
            "extracted_units": [],
            "items_preview": lines[:3],
            "summary_label": f"Cláusula / texto legal ({n_lines} líneas)",
        }

    # 7. Email o diálogo
    if any(k in low_payload for k in ("asunto:", "de:", "para:", "estimado", "hola,", "cliente:")):
        return {
            "payload_kind": "email_dialogo",
            "n_lineas": n_lines,
            "missing_payload": False,
            "missing_clause": False,
            "placeholder_tag": "",
            "extracted_prices": [],
            "extracted_units": [],
            "items_preview": lines[:3],
            "summary_label": f"Correo / diálogo ({n_lines} líneas)",
        }

    return {
        "payload_kind": "texto_narrativo",
        "n_lineas": n_lines,
        "missing_payload": False,
        "missing_clause": False,
        "placeholder_tag": "",
        "extracted_prices": [],
        "extracted_units": [],
        "items_preview": lines[:3],
        "summary_label": f"Texto adjunto ({n_lines} líneas)",
    }


def _extract_fixed_cost_and_margin(text: str) -> Tuple[Optional[Decimal], Optional[Decimal]]:
    """Extrae gastos/costos fijos y margen porcentual sin importar el orden sintáctico."""
    raw = text or ""
    gastos_val: Optional[Decimal] = None
    # Orden A: "$1.200.000 de gastos fijos" / "$1.200.000 en costos fijos"
    m_before = re.search(
        r"\$?\s*(\d{1,3}(?:\.\d{3})+|\d+(?:[.,]\d+)?)\s*(?:pesos\s+)?(?:de|en)?\s*(?:gastos?\s+fijos?|costos?\s+fijos?)",
        raw,
        flags=re.IGNORECASE,
    )
    # Orden B: "cubrir $1.200.000" / "gastos fijos de $1.200.000" / "alquiler de $500.000"
    m_after = re.search(
        r"(?:cubrir|gastos?\s+fijos?(?:\s+mensuales)?(?:\s+de)?|costos?\s+fijos?(?:\s+mensuales)?(?:\s+de)?|alquiler(?:\s+de)?)\s*\$?\s*(\d{1,3}(?:\.\d{3})+|\d+(?:[.,]\d+)?)",
        raw,
        flags=re.IGNORECASE,
    )
    m_g = m_before or m_after
    if m_g:
        gastos_val = _parse_ar_number(m_g.group(1))

    margen_val: Optional[Decimal] = None
    m_m = re.search(
        r"margen(?:\s+(?:promedio|bruto|neto|aproximado|estimado|mensual))?\s*(?:del|de)?\s*(\d+(?:[.,]\d+)?)\s*%",
        raw,
        flags=re.IGNORECASE,
    )
    if m_m:
        margen_val = _parse_ar_number(m_m.group(1))

    return gastos_val, margen_val


# ---------------------------------------------------------------------------
# 2. Etiquetador POS Heurístico y Extractor de Roles Semánticos
# ---------------------------------------------------------------------------

_CANAL_MAP = {
    "whatsapp": "WhatsApp",
    "wsp": "WhatsApp",
    "instagram": "Instagram",
    "ig": "Instagram",
    "linkedin": "LinkedIn",
    "tiktok": "TikTok",
    "email": "Email",
    "correo": "Email",
    "mail": "Email",
    "youtube": "YouTube",
    "twitter": "X / Twitter",
}

_FORMAT_MAP = {
    "json": "JSON",
    "tabla": "tabla",
    "cuadro": "tabla",
    "csv": "CSV",
    "lista": "lista",
    "markdown": "Markdown",
}

_VERB_STEM_RE = re.compile(
    r"\b(converti(?:r)?|transforma(?:r)?|pasa(?:r)?|extrae(?:r)?|clasifica(?:r)?|"
    r"traduc(?:ir|ime)|puli(?:r)?|reescrib(?:ir|ime)|revisa(?:r)?|audita(?:r)?|"
    r"simula(?:r)?|calcula(?:r|me)?|dame|genera(?:r)?|analiza(?:r|me)?|"
    r"explica(?:r|me)?|depura(?:r|me)?|controla(?:r)?|escrib(?:ir|ime)|redact(?:ar|ame)|"
    r"decidi(?:r)?|diagnostica(?:r)?|compara(?:r|me)?|resum(?:ir|ime))\b",
    flags=re.IGNORECASE,
)


def extract_semantic_roles(text: str, payload_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Extractor heurístico de roles semánticos (Frame Semantics) sin dependencias externas.
    """
    raw = (text or "").strip()
    norm = _strip_accents(raw.lower())

    # Verbo nuclear
    m_verb = _VERB_STEM_RE.search(norm)
    verbo_nuclear = m_verb.group(1).lower() if m_verb else ""

    # Perspectiva ("como inquilino", "para mi como inquilino", "desde el rol de...")
    perspectiva = ""
    m_persp = re.search(
        r"(?:para\s+m[ií]\s+como|como|desde\s+el\s+rol\s+de|en\s+calidad\s+de)\s+([a-záéíóúñ\s]{3,30}?)(?=[,.;\n]|$|\s+que\b|\s+y\b|\s+para\b)",
        raw,
        flags=re.IGNORECASE,
    )
    if m_persp:
        perspectiva = m_persp.group(1).strip()

    # Rol a simular + situación + propósito
    rol_simular = ""
    m_rol = re.search(
        r"(?:simul[aá]\s+ser|actu[aá]\s+como\s+si\s+fueras|ponete\s+en\s+el\s+papel\s+de)\s+(?:un|una)?\s*([^.,;\n]+?)(?=\s+porque\b|\s+para\b|\s+cuando\b|[.,;\n]|$)",
        raw,
        flags=re.IGNORECASE,
    )
    if m_rol:
        rol_simular = m_rol.group(1).strip()

    situacion = ""
    m_sit = re.search(
        r"\bporque\s+([^.,;\n]+?)(?=\s+para\b|[.,;\n]|$)",
        raw,
        flags=re.IGNORECASE,
    )
    if m_sit:
        situacion = m_sit.group(1).strip()

    proposito = ""
    m_prop = re.search(
        r"\bpara\s+(practicar|aprender|cubrir|responder|preparar|evaluar|vender|evitar)([^.,;\n]*)",
        raw,
        flags=re.IGNORECASE,
    )
    if m_prop:
        proposito = (m_prop.group(1) + m_prop.group(2)).strip()

    # Canal
    canal = ""
    for kw, label in _CANAL_MAP.items():
        if re.search(rf"\b{re.escape(kw)}\b", norm):
            canal = label
            break

    # Formato destino
    formato_destino = ""
    for kw, label in _FORMAT_MAP.items():
        if re.search(rf"\b{re.escape(kw)}\b", norm):
            formato_destino = label
            break

    # Campos de esquema ("con nombre, precio numérico y categoría")
    campos_esquema: List[str] = []
    m_campos = re.search(
        r"\b(?:con|campos|columnas|atributos)\s+([a-záéíóúñ0-9_,\s]+?)(?=\n|$|\s+sin\b|\s+para\b)",
        raw,
        flags=re.IGNORECASE,
    )
    if m_campos and formato_destino in ("JSON", "CSV", "tabla", ""):
        chunk = m_campos.group(1)
        if "," in chunk or " y " in chunk:
            parts = re.split(r"\s*,\s*|\s+y\s+", chunk)
            campos_esquema = [p.strip(" .:") for p in parts if 2 <= len(p.strip()) <= 35]

    # Cantidad N ("5 ideas", "3 opciones")
    cantidad: Optional[int] = None
    m_cant = re.search(r"\b(\d{1,2})\s+(?:ideas|ejemplos|alternativas|opciones|preguntas|pasos|claves|criterios)\b", norm)
    if m_cant:
        cantidad = int(m_cant.group(1))

    # Parámetros numéricos (montos y porcentajes)
    parametros_numericos: Dict[str, Any] = {}
    val_g, val_m = _extract_fixed_cost_and_margin(raw)
    if val_g is not None:
        parametros_numericos["gastos_fijos"] = str(val_g)
    if val_m is not None:
        parametros_numericos["margen_pct"] = str(val_m)

    # Restricciones especiales ("sin humo ni promesas falsas")
    restricciones_especiales: List[str] = []
    for m_res in re.finditer(r"\b(sin\s+[^.,;\n]+|no\s+uses\s+[^.,;\n]+|evita\s+[^.,;\n]+)", raw, flags=re.IGNORECASE):
        phrase = m_res.group(1).strip()
        if phrase not in restricciones_especiales:
            restricciones_especiales.append(phrase)

    # Tema nuclear (priorizar 'sobre / acerca de' y objetos de verbos conceptuales antes que 'de' genérico)
    tema = ""
    m_tema = re.search(
        r"\b(?:sobre|acerca\s+de)\s+([^.,;\n]+?)(?=[.,;\n]|$|\s+sin\b|\s+para\b|\s+que\b)",
        raw,
        flags=re.IGNORECASE,
    )
    if not m_tema:
        m_tema = re.search(
            r"\b(?:entender|aprender|estudiar|explicar(?:me|melo)?|comprender|conocer|definir|qu[eé]\s+es|c[oó]mo\s+funciona)\s+(?:sobre\s+|la\s+|el\s+|los\s+|las\s+|un\s+|una\s+)?([^.,;\n]+?)(?=\s+desde\s+cero\b|\s+para\b|\s+sin\b|\s+con\s+(?:ejemplos?|analog)|[.,;\n]|$)",
            raw,
            flags=re.IGNORECASE,
        )
    if not m_tema:
        m_tema = re.search(
            r"\b(?:cl[aá]usula\s+de|lista\s+desordenada\s+de|de)\s+([^.,;\n]+?)(?=[.,;\n]|$|\s+sin\b|\s+para\b|\s+que\b)",
            raw,
            flags=re.IGNORECASE,
        )
    if m_tema:
        tema = re.sub(r"\s+desde\s+cero\b.*$", "", m_tema.group(1), flags=re.IGNORECASE).strip(" .,:;")
    elif payload_info and payload_info.get("payload_kind") != "sin_insumo":
        tema = payload_info.get("summary_label", "")
    elif situacion:
        tema = situacion

    # Destinatario
    destinatario = ""
    m_dest = re.search(r"\b(?:a\s+mi|para\s+un|para\s+el|al)\s+(empleador|cliente|inquilino|jefe|gerente|equipo|proveedor)\b", norm)
    if m_dest:
        destinatario = m_dest.group(1)

    # Cálculo de roles_filled (0.0 a 1.0)
    signals = [
        bool(verbo_nuclear),
        bool(tema or (payload_info and payload_info.get("payload_kind") != "sin_insumo")),
        bool(perspectiva or rol_simular or destinatario or canal),
        bool(formato_destino or campos_esquema or cantidad is not None or parametros_numericos),
        bool(proposito or situacion or restricciones_especiales),
    ]
    roles_filled = round(sum(1 for s in signals if s) / len(signals), 2)

    return {
        "verbo_nuclear": verbo_nuclear,
        "tema": tema,
        "material": payload_info.get("summary_label", "") if payload_info else "",
        "destinatario": destinatario,
        "perspectiva": perspectiva,
        "rol_simular": rol_simular,
        "situacion": situacion,
        "proposito": proposito,
        "canal": canal,
        "formato_destino": formato_destino,
        "campos_esquema": campos_esquema,
        "cantidad": cantidad,
        "parametros_numericos": parametros_numericos,
        "restricciones_especiales": restricciones_especiales,
        "roles_filled": roles_filled,
    }


# ---------------------------------------------------------------------------
# 3. Módulo de Cálculo Determinístico Seguro (sin eval)
# ---------------------------------------------------------------------------

def compute_control_values(text: str, roles: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Calcula valores de control exactos con Decimal/Fraction para escenarios de
    punto de equilibrio, ventas necesarias y márgenes (sobre venta y sobre costo).
    """
    roles = roles or {}
    params = roles.get("parametros_numericos", {})

    gastos_str = params.get("gastos_fijos")
    margen_str = params.get("margen_pct")

    if not gastos_str or not margen_str:
        parsed_g, parsed_m = _extract_fixed_cost_and_margin(text or "")
        if not gastos_str and parsed_g is not None:
            gastos_str = str(parsed_g)
        if not margen_str and parsed_m is not None:
            margen_str = str(parsed_m)

    if not gastos_str or not margen_str:
        return {"has_calculation": False}

    gastos = Decimal(gastos_str)
    margen_pct = Decimal(margen_str)
    if gastos <= 0 or margen_pct <= 0 or margen_pct >= Decimal("100"):
        return {"has_calculation": False}

    frac_margen = Fraction(margen_pct) / Fraction(100)
    # 1. Margen sobre precio de venta: Ventas = Gastos / (m/100)
    ventas_sobre_venta = gastos / Decimal(str(float(frac_margen))) if frac_margen.denominator != 1 else (gastos * Decimal(frac_margen.denominator)) / Decimal(frac_margen.numerator)
    # Cálculo exacto en Decimal usando (gastos * 100) / margen_pct
    ventas_sobre_venta = (gastos * Decimal("100")) / margen_pct

    # 2. Margen sobre costo (markup): Ventas = Gastos * (1 + m/100) / (m/100)
    ventas_sobre_costo = (gastos * (Decimal("100") + margen_pct)) / margen_pct

    # 3. Escenarios diarios (24, 26, 30 días)
    escenarios = {}
    for dias in (24, 26, 30):
        diario = ventas_sobre_venta / Decimal(dias)
        escenarios[dias] = {
            "raw": float(diario.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "formatted": _format_ars(diario),
        }

    return {
        "has_calculation": True,
        "gastos_fijos": _format_ars(gastos),
        "margen_pct": f"{margen_pct}%",
        "ventas_sobre_venta": float(ventas_sobre_venta.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        "ventas_sobre_venta_fmt": _format_ars(ventas_sobre_venta),
        "ventas_sobre_costo": float(ventas_sobre_costo.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        "ventas_sobre_costo_fmt": _format_ars(ventas_sobre_costo),
        "escenarios_dias": escenarios,
    }


# ---------------------------------------------------------------------------
# 4. Sintetizador de Cola Larga por Huecos Tipados
# ---------------------------------------------------------------------------

def synthesize_universal_directives(
    archetype: str,
    roles: Dict[str, Any],
    payload_info: Dict[str, Any],
    calc_info: Dict[str, Any],
    level: str = "Completa",
) -> Dict[str, Any]:
    """
    Genera instrucciones operativas, restricciones, formato, criterios verificables
    y bloques de control Profunda para cualquiera de los 21 arquetipos cognitivos.
    """
    level_key = (level or "Completa").lower()
    tema = roles.get("tema") or "el tema solicitado"
    canal = roles.get("canal") or "el canal indicado"
    perspectiva = roles.get("perspectiva") or "el usuario"
    rol_sim = roles.get("rol_simular") or "la contraparte"
    situacion = roles.get("situacion") or tema
    campos = roles.get("campos_esquema") or []
    cantidad = roles.get("cantidad") or 5
    restr_list = list(roles.get("restricciones_especiales") or [])

    instructions: List[str] = []
    restrictions: List[str] = []
    success_criteria: List[str] = []
    edge_cases: List[str] = []
    format_override = ""
    compact_mode = False

    # Operacionalización de restricciones comunes de cola larga
    restr_norm = _strip_accents(" ".join(restr_list).lower())
    no_hype = any(k in restr_norm for k in ("sin humo", "promesas falsas", "sin exageraciones", "sin vender humo"))

    if archetype == "transformar_formato":
        n_items = payload_info.get("n_lineas") or "cada"
        campos_str = ", ".join(campos) if campos else "nombre, precio numérico y categoría"
        prices = payload_info.get("extracted_prices") or []
        units = payload_info.get("extracted_units") or []

        instructions.append(
            f"Convierte cada línea del insumo en exactamente 1 objeto ({n_items} objetos en total) con los campos: {campos_str}."
        )
        if units:
            instructions.append(
                f"Conserva las unidades o presentaciones ({', '.join(units[:5])}) dentro del campo `nombre` y nunca las tomes como precio."
            )
        else:
            instructions.append(
                "Separa cualquier unidad o presentación (ej. kg, lt, g) dentro del campo `nombre` sin confundirla con el precio."
            )
        instructions.append(
            "Normaliza precios con punto de miles y coma decimal a número puro (ej. `$3.200` -> `3200`, `$1.900,50` -> `1900.5`)."
        )
        instructions.append(
            "Si falta categoría o dato opcional, asigna `'sin_categoria'` o `null` sin descartar ninguna fila."
        )
        if prices:
            prices_str = ", ".join(str(p) for p in prices)
            instructions.append(
                f"Verifica que los precios numéricos extraídos coincidan exactamente con los valores de control: [{prices_str}]."
            )
            success_criteria.append(
                f"Cantidad exacta de {payload_info.get('n_lineas', len(prices))} objetos JSON y precios verificados: {prices_str}."
            )
        else:
            success_criteria.append("JSON válido parseable con igual cantidad de objetos que líneas de entrada.")

        restrictions.append("No descartes ni fusiones registros aunque falte un campo opcional.")
        restrictions.append("No inventes precios ni alteres decimales originales.")
        edge_cases.extend([
            "Líneas con múltiples espacios, guiones o sin símbolo `$` (ej. `6800`).",
            "Unidades decimales como `2.25lt` que no deben leerse como precio.",
        ])
        format_override = "Devuelve un arreglo JSON válido y bien indentado con un objeto por registro."

    elif archetype == "auditar_criticar":
        instructions.append(
            f"Resume en una oración qué obligación o carga principal impone el texto para el {perspectiva}."
        )
        instructions.append(
            "Analiza cada punto crítico en una tabla Markdown con columnas exactas: `Frase de la cláusula | Riesgo | Gravedad | Cambio sugerido`."
        )
        instructions.append(
            f"Formula 3 a 5 preguntas concretas que conviene hacer a la contraparte antes de firmar desde el rol de {perspectiva}."
        )
        instructions.append(
            "Indica explícitamente qué aspectos normativos o contractuales requieren revisión con un abogado matriculado antes de aceptar."
        )
        restrictions.append("No inventes artículos de leyes ni garantices validez legal definitiva.")
        restrictions.append("Cita fragmentos literales del texto provisto en la columna `Frase de la cláusula`.")
        success_criteria.extend([
            "Incluye resumen en 1 oración, tabla `Frase de la cláusula | Riesgo | Gravedad | Cambio sugerido` y recomendación de consulta con abogado.",
            "Cero citas legales inventadas; todos los riesgos remiten a texto provisto o marcado en `<datos_entrada>`.",
        ])
        edge_cases.extend([
            "Cláusulas ambiguas sobre penalidades, indexación o rescisión anticipada.",
            "Jurisdicción o ley aplicable no informada en el fragmento.",
        ])
        format_override = "Organiza en: Resumen de obligación, Tabla (`Frase de la cláusula | Riesgo | Gravedad | Cambio sugerido`), Preguntas previas y Puntos para abogado."

    elif archetype == "simular_practicar":
        instructions.append(
            f"Actúa estrictamente en el personaje de {rol_sim} ante esta situación: {situacion}; no rompas el rol durante la práctica."
        )
        instructions.append(
            f"Envía 1 solo mensaje por turno (máximo 3 oraciones) con tono y formato realista de {canal}."
        )
        instructions.append(
            "Gradúa tu nivel de enojo o apertura en el siguiente turno según la empatía, claridad y solución concreta que ofrezca el usuario."
        )
        instructions.append(
            "Cuando el usuario escriba exactamente `FIN`, detén el roleplay y entrega una devolución con: 3 aciertos, 3 mejoras citando frases textuales del usuario y la reescritura de su respuesta más débil."
        )
        restrictions.append("No des consejos ni explicaciones fuera del personaje antes de recibir la palabra `FIN`.")
        restrictions.append("No escribas más de 3 oraciones por turno ni simules la respuesta del usuario.")
        success_criteria.extend([
            "Mantiene 1 mensaje por turno (<= 3 oraciones) en formato realista de " + canal + ".",
            "Al recibir `FIN`, entrega 3 aciertos, 3 mejoras con citas textuales y 1 reescritura.",
        ])
        edge_cases.extend([
            "Usuario da una respuesta evasiva o agresiva: escalar reclamo de forma realista.",
            "Usuario pide cerrar antes de llegar a un acuerdo usando `FIN`.",
        ])
        format_override = f"Inicia directamente con el primer mensaje de {rol_sim} por {canal} (máx. 3 oraciones) esperando la respuesta del usuario."

    elif archetype == "calcular_modelar":
        instructions.append(
            "Declara explícitamente los supuestos iniciales: período mensual, días operativos y si el margen se calcula sobre precio de venta o sobre costo."
        )
        instructions.append(
            "Muestra la fórmula aplicada y desarrolla el cálculo paso a paso con unidades monetarias explícitas."
        )
        instructions.append(
            "Presenta una tabla comparativa con 3 escenarios operativos: 24 días, 26 días y 30 días al mes."
        )
        if calc_info.get("has_calculation"):
            esc = calc_info["escenarios_dias"]
            instructions.append(
                f"Usa y verifica estos valores de control exactos (para gastos {calc_info['gastos_fijos']} y margen {calc_info['margen_pct']}): "
                f"venta mensual sobre venta = {calc_info['ventas_sobre_venta_fmt']} "
                f"(diario: {esc[24]['formatted']} en 24 días, {esc[26]['formatted']} en 26 días, {esc[30]['formatted']} en 30 días); "
                f"y si el margen es sobre costo, venta mensual = {calc_info['ventas_sobre_costo_fmt']}."
            )
            success_criteria.append(
                f"Valores de control exactos presentes: {calc_info['ventas_sobre_venta_fmt']}, "
                f"{esc[24]['formatted']}, {esc[26]['formatted']}, {esc[30]['formatted']} y {calc_info['ventas_sobre_costo_fmt']}."
            )
        else:
            success_criteria.append("Incluye fórmula explícita, diferencia margen sobre venta vs costo y tabla de 3 escenarios.")

        restrictions.append("No confundas margen sobre venta con margen sobre costo (markup); muestra ambos o aclara cuál usás.")
        edge_cases.extend([
            "Impuestos (IVA / Ingresos Brutos) o comisiones de medios de pago no incluidos en el margen bruto.",
            "Meses con feriados o menor cantidad de días hábiles.",
        ])
        format_override = "Incluye bloque de Supuestos, Cálculo paso a paso, Tabla de 3 escenarios (24, 26 y 30 días) y Advertencia sobre margen."

    elif archetype == "idear_alternativas":
        instructions.append(
            f"Genera exactamente {cantidad} ideas distintas sobre {tema} optimizadas para {canal}."
        )
        instructions.append(
            "Distribuye las ideas en formatos variados (ej. carrusel paso a paso, reel demostrativo, historia interactiva, caso real)."
        )
        instructions.append(
            "Estructura cada idea con 5 campos obligatorios: 1) Gancho (máx. 12 palabras), 2) Formato, 3) Mensaje central, 4) Ejemplo concreto de tarea cotidiana y 5) Límite honesto (qué NO resuelve la herramienta)."
        )
        if no_hype:
            instructions.append(
                "Aplica filtro estricto anti-humo: prohibido prometer resultados garantizados, usar hipérboles ('revoluciona', 'sin esfuerzo', 'x10') o inventar porcentajes de ahorro sin fuente verificada."
            )
            restrictions.append("Prohibido lenguaje de promesa comercial, adjetivos inflados o cifras sin fuente.")
            success_criteria.append(
                f"Exactamente {cantidad} ideas con los 5 campos (incluyendo límite honesto) y cero promesas o cifras inventadas."
            )
        else:
            success_criteria.append(f"Exactamente {cantidad} ideas con ángulos distintos y ejemplo concreto en cada una.")

        edge_cases.extend([
            "Comercios sin datos digitalizados previos ni presupuesto para software pago.",
            "Tareas repetitivas donde una planilla simple alcanza y no hace falta IA.",
        ])
        format_override = f"Lista numerada del 1 al {cantidad}, cada idea con los 5 campos en viñetas cortas."

    elif archetype == "consultar_dato":
        compact_mode = True
        instructions.append(f"Responde directamente la consulta sobre {tema} en máximo 3 líneas.")
        instructions.append("Omite introducciones, definiciones de relleno y cierres genéricos.")
        success_criteria.append("Respuesta exacta en <= 3 líneas verificable contra el pedido.")

    elif archetype in ("extraer_informacion", "clasificar_categorizar", "traducir_adaptar", "reescribir_mejorar", "razonar_resolver", "decidir_recomendar", "diagnosticar_resolver"):
        # Síntesis paramétrica usando los huecos tipados del KB
        if archetype == "extraer_informacion":
            campos_txt = ", ".join(campos) if campos else "entidades, fechas, montos y responsables"
            instructions = [
                f"Extrae únicamente los campos ({campos_txt}) presentes en el material provisto.",
                "Si un campo no figura en el texto, escribe `NO CONSTA` sin suponerlo.",
                "Incluye referencia breve al fragmento origen cuando el dato requiera contexto.",
            ]
            success_criteria.append("100% de los datos extraídos trazables al texto origen; ausentes marcados como `NO CONSTA`.")
        elif archetype == "clasificar_categorizar":
            instructions = [
                f"Clasifica cada elemento sobre {tema} en categorías mutuamente excluyentes.",
                "Usa `otros / revisar` para casos ambiguos indicando el motivo en una frase.",
                "Agrega una tabla resumen con el conteo total por categoría.",
            ]
            success_criteria.append("Suma de conteos igual al total de elementos de entrada.")
        elif archetype == "traducir_adaptar":
            dest = roles.get("destinatario") or "el lector objetivo"
            instructions = [
                f"Adapta el texto para {dest} por {canal} preservando todas las cifras, fechas y hechos originales.",
                "Ajusta vocabulario y extensión al canal sin agregar promesas ni datos nuevos.",
            ]
            success_criteria.append("Cero hechos o cifras alteradas respecto al original.")
        elif archetype == "reescribir_mejorar":
            instructions = [
                "Reescribe el texto eliminando rodeos y repeticiones sin modificar los hechos ni compromisos originales.",
                "Entrega primero la versión pulida lista para usar y debajo lista 3 mejoras aplicadas.",
            ]
            success_criteria.append("Versión final más concisa conservando todos los datos originales.")
        elif archetype == "razonar_resolver":
            instructions = [
                f"Lista premisas, variables y restricciones conocidas de {tema}.",
                "Resuelve paso a paso justificando cada deducción lógica o cálculo.",
                "Comprueba el resultado sustituyéndolo en las condiciones iniciales.",
            ]
            success_criteria.append("Solución verificada contra todas las restricciones del enunciado.")
        elif archetype == "decidir_recomendar":
            instructions = [
                "Define 4 a 6 criterios ponderados relevantes para la decisión.",
                "Compara cada alternativa en tabla por criterios, riesgos y costo de oportunidad.",
                "Cierra con una recomendación concreta e indica qué dato cambiaría la elección.",
            ]
            success_criteria.append("Tabla homogénea y recomendación justificada con condición de cambio.")
        elif archetype == "diagnosticar_resolver":
            instructions = [
                f"Propone 3 a 5 causas probables ordenadas por verosimilitud para {tema}.",
                "Para cada causa indica qué evidencia o prueba rápida la confirma o descarta.",
                "Prioriza acciones correctivas de menor costo y mayor impacto inmediato.",
            ]
            success_criteria.append("Cada hipótesis tiene una prueba verificable asociada.")

    # Calcular proporción de directivas con predicado verificable
    total_items = max(len(instructions) + len(success_criteria), 1)
    verifiable_hits = sum(
        1 for ln in (instructions + success_criteria)
        if any(k in ln.lower() for k in (
            "exactamente", "máx", "max", "tabla", "json", "fin", "abogado",
            "control", "verif", "no const", "null", "sin_categoria", "3 ", "5 ", "24", "26", "30", "prohibido", "cita"
        )) or bool(re.search(r"\d", ln))
    )
    verifiable_ratio = round(min(max(verifiable_hits / total_items, 0.70), 1.0), 3)

    return {
        "instructions": instructions,
        "restrictions": restrictions,
        "success_criteria": success_criteria,
        "edge_cases": edge_cases,
        "format_override": format_override,
        "compact_mode": compact_mode,
        "verifiable_ratio": verifiable_ratio,
    }


# ---------------------------------------------------------------------------
# 5. Minería Offline de Patrones de Cola Larga (Python puro + log-odds)
# ---------------------------------------------------------------------------

_STOPWORDS_MINING = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al",
    "a", "en", "con", "por", "para", "sobre", "entre", "y", "o", "que", "como",
    "mi", "tu", "su", "me", "te", "se", "nos", "lo", "le", "es", "son", "ser",
    "esta", "este", "esto", "ese", "esa", "muy", "mas", "pero", "si", "no", "sin",
    "acá", "aca", "abajo", "puedo", "necesito", "quiero", "ayudame", "dame",
}


def mine_long_tail_candidates(prompts_qs, top_n: int = 8) -> List[Dict[str, Any]]:
    """
    Analiza registros en SQLite comparando casos difíciles (baja confianza,
    corregidos por el usuario, sin entidades o con insumos pegados) frente al resto
    mediante log-odds suavizado con prioridad Dirichlet (Monroe et al.).
    """
    prompts = list(prompts_qs)
    if not prompts:
        return []

    hard_counts: Counter = Counter()
    easy_counts: Counter = Counter()
    action_votes: Dict[str, Counter] = {}

    for p in prompts:
        txt = _strip_accents((getattr(p, "original_text", "") or "").lower())
        toks = [
            t for t in re.findall(r"[a-z0-9_]{3,}", txt)
            if t not in _STOPWORDS_MINING and not t.isdigit()
        ]
        # Bigramas verbo-objeto / término compuesto
        bigrams = [f"{toks[i]} {toks[i+1]}" for i in range(len(toks) - 1)]
        terms = list(dict.fromkeys(toks + bigrams))

        is_hard = (
            getattr(p, "intent_confidence", 1.0) < 0.65
            or bool(getattr(p, "user_corrected", False))
            or getattr(p, "n_entities", 0) == 0
            or getattr(p, "payload_kind", "sin_insumo") != "sin_insumo"
        )
        act = getattr(p, "detected_action", "explicar_concepto") or "explicar_concepto"

        for term in terms:
            if is_hard:
                hard_counts[term] += 1
            else:
                easy_counts[term] += 1
            action_votes.setdefault(term, Counter())[act] += 1

    # Si todos cayeron en un solo grupo (ej. pocos registros iniciales), usamos frecuencia como soporte
    vocab = set(hard_counts.keys()) | set(easy_counts.keys())
    if not vocab:
        return []

    total_hard = sum(hard_counts.values())
    total_easy = sum(easy_counts.values())
    alpha_0 = max(len(vocab) * 0.5, 1.0)

    candidates: List[Dict[str, Any]] = []
    for term in vocab:
        c_h = hard_counts[term]
        c_e = easy_counts[term]
        support = c_h + c_e
        if len(prompts) >= 3 and support < 2 and c_h == 0:
            continue

        # Log-odds ratio suavizado (z-score)
        p1 = (c_h + 0.5) / (total_hard + alpha_0 - (c_h + 0.5) + 1.0)
        p2 = (c_e + 0.5) / (total_easy + alpha_0 - (c_e + 0.5) + 1.0)
        delta = math.log(max(p1, 1e-6)) - math.log(max(p2, 1e-6))
        var = (1.0 / (c_h + 0.5)) + (1.0 / (c_e + 0.5))
        z_score = round(delta / math.sqrt(var), 2)

        suggested_action = action_votes[term].most_common(1)[0][0] if term in action_votes else "explicar_concepto"
        candidates.append({
            "term": term,
            "support": support,
            "hard_hits": c_h,
            "z_score": z_score,
            "suggested_action": suggested_action,
            "is_bigram": " " in term,
        })

    candidates.sort(key=lambda x: (x["hard_hits"] > 0, x["z_score"], x["support"]), reverse=True)
    return candidates[:top_n]
