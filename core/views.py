import csv
from datetime import timedelta
import html
import json
import re
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.db.models import Count
from django.utils.http import url_has_allowed_host_and_scheme
from .services import (
    get_gemini_response,
    calculate_rubric_score,
    analyze_live_preview,
    invalidate_learned_boosts_cache,
)
from .universal_engine import mine_long_tail_candidates
from .models import Prompt

GUEST_DEFAULT_USERNAME = "alan"
GUEST_FALLBACK_USERNAME = "invitado"
_USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _get_active_user(request):
    if request.user.is_authenticated:
        return request.user
    guest = User.objects.filter(username=GUEST_DEFAULT_USERNAME).first()
    if guest is not None:
        return guest
    fallback = User.objects.filter(username=GUEST_FALLBACK_USERNAME).first()
    if fallback is not None:
        return fallback
    first_user = User.objects.order_by("id").first()
    if first_user is not None:
        return first_user
    return User.objects.create_user(username=GUEST_DEFAULT_USERNAME, password="123")


def login_view(request):
    if request.user.is_authenticated:
        return redirect("workspace")

    raw_next = (request.POST.get("next") or request.GET.get("next") or "").strip()
    safe_next = (
        raw_next
        if raw_next
        and url_has_allowed_host_and_scheme(
            raw_next,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        )
        else ""
    )

    error = ""
    username_value = ""

    if request.method == "POST":
        username_value = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        if not username_value or not password:
            error = "Completá tu nombre de usuario y tu contraseña para ingresar."
        else:
            user = authenticate(request, username=username_value, password=password)
            if user is not None:
                login(request, user)
                return redirect(safe_next or "workspace")
            error = "El nombre de usuario o la contraseña no son correctos. Revisalos e intentá de nuevo."

    return render(
        request,
        "core/login.html",
        {
            "error": error,
            "username_value": username_value,
            "next_url": safe_next,
        },
    )


def register_view(request):
    if request.user.is_authenticated:
        return redirect("workspace")

    error = ""
    username_value = ""

    if request.method == "POST":
        username_value = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        password_confirm = request.POST.get("password_confirm") or ""

        if len(username_value) < 3:
            error = "El nombre de usuario debe tener al menos 3 caracteres."
        elif len(username_value) > 50:
            error = "El nombre de usuario no puede superar los 50 caracteres."
        elif not _USERNAME_RE.fullmatch(username_value):
            error = "Usá solo letras sin espacios, números, punto (.), guion bajo (_) o guion medio (-)."
        elif User.objects.filter(username__iexact=username_value).exists():
            error = "Ese nombre de usuario ya está en uso. Elegí otro diferente."
        elif len(password) < 6:
            error = "La contraseña debe tener al menos 6 caracteres."
        elif password != password_confirm:
            error = "Las contraseñas no coinciden. Volvé a escribirlas."
        else:
            if not User.objects.exists():
                guest_name = (
                    GUEST_FALLBACK_USERNAME
                    if username_value.lower() == GUEST_DEFAULT_USERNAME
                    else GUEST_DEFAULT_USERNAME
                )
                User.objects.create_user(username=guest_name, password="123")
            new_user = User.objects.create_user(username=username_value, password=password)
            login(request, new_user)
            return redirect("workspace")

    return render(
        request,
        "core/register.html",
        {
            "error": error,
            "username_value": username_value,
        },
    )


@require_POST
def logout_view(request):
    logout(request)
    return redirect("workspace")

TEMPLATE_CATEGORIES = [
    "Tecnología y Programación",
    "Ciencia de Datos e IA",
    "Negocios y Comercio",
    "Estudio y Academia",
    "Redacción y Comunicación",
    "Carrera y Productividad",
]

_MODE_META = {
    "express": {"mode": "express", "modo_label": "Express", "level": "Ligera"},
    "guiado": {"mode": "guiado", "modo_label": "Guiado", "level": "Completa"},
    "estudio_pro": {"mode": "pro", "modo_label": "Estudio Pro", "level": "Profunda"},
}


def _highlight_template_placeholders(prompt_text: str) -> str:
    escaped = html.escape(prompt_text)
    return re.sub(
        r"(\[[^\[\]\n]+\])",
        r'<span class="tpl-placeholder">\1</span>',
        escaped,
    )


def _build_template_entry(
    slug: str,
    categoria: str,
    titulo: str,
    descripcion: str,
    modo: str,
    por_que_funciona: str,
    prompt: str,
    technique: str = "Estándar",
) -> dict:
    meta = _MODE_META[modo]
    return {
        "id": slug,
        "slug": slug,
        "categoria": categoria,
        "category": categoria,
        "titulo": titulo,
        "title": titulo,
        "descripcion": descripcion,
        "description": descripcion,
        "modo": modo,
        "mode": meta["mode"],
        "modo_label": meta["modo_label"],
        "level": meta["level"],
        "technique": technique,
        "por_que_funciona": por_que_funciona,
        "prompt": prompt,
        "text": prompt,
        "prompt_highlighted_html": _highlight_template_placeholders(prompt),
    }


TEMPLATES_CATALOG = {
    # 1. Tecnología y Programación
    "python-csv-sin-librerias": _build_template_entry(
        slug="python-csv-sin-librerias",
        categoria="Tecnología y Programación",
        titulo="Script Python sin librerías externas (con datos CSV)",
        descripcion="Procesa un archivo CSV y agrupa métricas usando solo la librería estándar de Python.",
        modo="estudio_pro",
        por_que_funciona="Delimita los datos de entrada y fija una restricción técnica clara.",
        prompt=(
            "escribime un script en python sin librerias externas que lea este csv de [tema, ej: caja diaria] "
            "y me devuelva un resumen por [columna de agrupacion, ej: medio de pago], comentado en español "
            "y manejando valores invalidos:\n[pega aqui 3 o 4 filas de ejemplo de tu CSV]"
        ),
    ),
    "sql-join-metricas": _build_template_entry(
        slug="sql-join-metricas",
        categoria="Tecnología y Programación",
        titulo="Consulta SQL con JOIN y métricas",
        descripcion="Combina múltiples tablas en SQL para calcular indicadores filtrados por período y condiciones.",
        modo="estudio_pro",
        por_que_funciona="Especifica motor SQL, tablas, período, orden y exclusiones.",
        prompt=(
            "escribime una consulta SQL en [motor, ej: PostgreSQL / MySQL] que una las tablas [tabla 1], "
            "[tabla 2] y [tabla 3] para mostrar [metrica, ej: total facturado y cantidad de compras] "
            "por [entidad] durante los ultimos [cantidad] dias, ordenado de mayor a menor y excluyendo "
            "[condicion a excluir, ej: ventas canceladas]"
        ),
    ),
    "debug-corregir-codigo": _build_template_entry(
        slug="debug-corregir-codigo",
        categoria="Tecnología y Programación",
        titulo="Detectar y corregir un error en mi código",
        descripcion="Encuentra la causa raíz de un fallo o excepción en tu código y entrega la versión corregida.",
        modo="guiado",
        por_que_funciona="Entrega el código y el error exacto, pidiendo causa raíz y solución comentada.",
        prompt=(
            "necesito encontrar y corregir un error en este codigo de [lenguaje, ej: Python / JavaScript]. "
            "El problema que me aparece es: [pega el mensaje de error o comportamiento incorrecto]. "
            "Explicame cual es la causa paso a paso y dame la version corregida:\n[pega tu fragmento de codigo aqui]"
        ),
    ),
    # 2. Ciencia de Datos e IA
    "explicar-concepto-analogia": _build_template_entry(
        slug="explicar-concepto-analogia",
        categoria="Ciencia de Datos e IA",
        titulo="Explicar un concepto técnico con analogía simple",
        descripcion="Aterriza conceptos complejos de IA o datos con comparaciones cotidianas para principiantes.",
        modo="express",
        por_que_funciona="Define el nivel del lector, pide una analogía cotidiana y bloquea jerga o fórmulas.",
        prompt=(
            "explicame la diferencia entre [concepto A, ej: overfitting] y [concepto B, ej: underfitting] "
            "en [area, ej: machine learning] como si se lo contaras a alguien que recien empieza, usando una "
            "analogia de la vida cotidiana y sin usar formulas matematicas"
        ),
    ),
    "checklist-eda-pandas": _build_template_entry(
        slug="checklist-eda-pandas",
        categoria="Ciencia de Datos e IA",
        titulo="Checklist de limpieza de dataset (EDA)",
        descripcion="Diseña un flujo estructurado en Pandas para auditar calidad de datos, nulos, duplicados y outliers.",
        modo="estudio_pro",
        por_que_funciona="Precisa el tipo de dataset, las columnas críticas y el objetivo del análisis.",
        prompt=(
            "armame un plan de analisis exploratorio y limpieza de datos en Python con Pandas para un dataset "
            "de [tema, ej: ventas de un comercio] que tiene [cantidad aproximada] filas y columnas de "
            "[tipos, ej: fechas, precios y categorias], priorizando deteccion de nulos, duplicados y valores atipicos"
        ),
    ),
    "comparar-modelos-enfoques": _build_template_entry(
        slug="comparar-modelos-enfoques",
        categoria="Ciencia de Datos e IA",
        titulo="Comparar 2 modelos, herramientas o enfoques",
        descripcion="Contrasta dos alternativas técnicas bajo tus restricciones reales y sugiere la más adecuada.",
        modo="guiado",
        por_que_funciona="Pide criterios homogéneos y una decisión práctica según tu caso real.",
        prompt=(
            "comparame [opcion A, ej: Arbol de Decision] frente a [opcion B, ej: Random Forest] para un proyecto "
            "de [objetivo, ej: predecir abandono de clientes] con [restriccion, ej: pocos datos y necesidad de "
            "explicar los resultados], incluyendo una tabla comparativa y una recomendacion final"
        ),
    ),
    # 3. Negocios y Comercio
    "negociar-plazo-proveedor": _build_template_entry(
        slug="negociar-plazo-proveedor",
        categoria="Negocios y Comercio",
        titulo="Negociar plazo de pago con un proveedor",
        descripcion="Redacta un pedido de prórroga comercial claro, respetuoso y cuidando el vínculo con el proveedor.",
        modo="express",
        por_que_funciona="Define tono exacto, monto/plazo concreto y límite de lo que querés evitar.",
        prompt=(
            "redactame un mensaje cordial pero firme para pedirle a mi proveedor que me extienda [cantidad] dias "
            "el plazo de pago de la factura [numero de factura] por [monto] pesos, sin sonar desesperado ni "
            "perder la buena relacion"
        ),
    ),
    "calcular-punto-equilibrio": _build_template_entry(
        slug="calcular-punto-equilibrio",
        categoria="Negocios y Comercio",
        titulo="Calcular punto de equilibrio y margen real",
        descripcion="Estima ventas mínimas para cubrir costos fijos y proyecta escenarios de rentabilidad.",
        modo="estudio_pro",
        por_que_funciona="Aporta números reales y pide escenarios concretos para tomar decisiones.",
        prompt=(
            "ayudame a calcular el punto de equilibrio y el margen de ganancia para mi [tipo de negocio o "
            "emprendimiento]. Mis costos fijos mensuales son [monto] pesos, el costo variable por unidad es "
            "[monto] pesos y vendo a [precio] pesos. Armame 3 escenarios (conservador, base y optimista)"
        ),
    ),
    "control-stock-vencimientos": _build_template_entry(
        slug="control-stock-vencimientos",
        categoria="Negocios y Comercio",
        titulo="Plan de control de stock y vencimientos",
        descripcion="Organiza el inventario, alertas de reposición y fechas de vencimiento con una rutina semanal.",
        modo="guiado",
        por_que_funciona="Baja una necesidad operativa a una rutina simple y medible para el día a día.",
        prompt=(
            "armame un sistema practico y simple para controlar stock, reposicion y vencimientos en un "
            "[tipo de local, ej: comercio de barrio / deposito] con aproximadamente [cantidad] productos, usando "
            "una planilla ordenada y una rutina semanal que tome menos de [tiempo, ej: 30 minutos]"
        ),
    ),
    # 4. Estudio y Academia
    "plan-estudio-parcial": _build_template_entry(
        slug="plan-estudio-parcial",
        categoria="Estudio y Academia",
        titulo="Plan de estudio por días para un parcial",
        descripcion="Distribuye temas, práctica y repaso día por día según tus horas reales disponibles.",
        modo="estudio_pro",
        por_que_funciona="Indica plazo exacto, horas disponibles y prioridad práctica con restricción real.",
        prompt=(
            "armame un plan de estudio de [cantidad] dias para preparar un parcial de [materia, ej: estadistica "
            "y probabilidad], tengo [cantidad] horas cada noche despues de cursar y necesito priorizar ejercicios "
            "practicos y un simulacro el ultimo dia, sin trasnochar"
        ),
    ),
    "autoevaluacion-parcial": _build_template_entry(
        slug="autoevaluacion-parcial",
        categoria="Estudio y Academia",
        titulo="Autoevaluación tipo parcial con respuestas",
        descripcion="Genera un simulacro de examen con preguntas teóricas y prácticas para ponerte a prueba.",
        modo="guiado",
        por_que_funciona="Pide preguntas exigentes, errores comunes y respuestas explicadas para estudiar activo.",
        prompt=(
            "creame una autoevaluacion tipo parcial universitario sobre [tema o unidad] con 5 preguntas variadas "
            "(teoricas y practicas), errores comunes que suelen cometer los estudiantes y las respuestas correctas "
            "explicadas paso a paso"
        ),
    ),
    "resumir-apunte-puntos-clave": _build_template_entry(
        slug="resumir-apunte-puntos-clave",
        categoria="Estudio y Academia",
        titulo="Resumir un apunte largo en puntos clave",
        descripcion="Sintetiza textos académicos extensos en ideas esenciales fáciles de repasar antes de rendir.",
        modo="express",
        por_que_funciona="Separa el texto propio y exige síntesis jerárquica lista para repasar.",
        prompt=(
            "resumime este apunte de [materia] en [cantidad, ej: 5] puntos clave faciles de memorizar para un "
            "examen, sin inventar informacion que no este en el texto:\n[pega aqui el fragmento de tu apunte]"
        ),
    ),
    # 5. Redacción y Comunicación
    "guion-corto-tiktok-reels": _build_template_entry(
        slug="guion-corto-tiktok-reels",
        categoria="Redacción y Comunicación",
        titulo="Guion de 30 segundos para TikTok o Reels",
        descripcion="Estructura un video corto con gancho inicial, desarrollo visual y llamado a la acción natural.",
        modo="guiado",
        por_que_funciona="Especifica canal, duración exacta, tono cercano y bloquea frases cliché.",
        prompt=(
            "armame un guion de [duracion, ej: 30 segundos] para un video corto de TikTok o Reels promocionando "
            "[producto o servicio, ej: un combo de desayuno en un local de barrio], con tono cercano y sin "
            "frases cliche de vendedor"
        ),
    ),
    "reescribir-borrador-tono": _build_template_entry(
        slug="reescribir-borrador-tono",
        categoria="Redacción y Comunicación",
        titulo="Reescribir un borrador con otro tono",
        descripcion="Pule cualquier mensaje en bruto para que suene claro, breve y adecuado al destinatario.",
        modo="express",
        por_que_funciona="Parte de tu borrador real y le dice a la IA exactamente cómo ajustarlo.",
        prompt=(
            "reescribi este mensaje para enviarlo por [canal, ej: WhatsApp / correo] a [destinatario, ej: un "
            "cliente o jefe] con un tono [tono deseado, ej: profesional, claro y amable], manteniendo la idea "
            "principal pero haciendolo mas breve:\n[pega tu borrador aqui]"
        ),
    ),
    "reclamo-formal-documentado": _build_template_entry(
        slug="reclamo-formal-documentado",
        categoria="Redacción y Comunicación",
        titulo="Reclamo formal claro y documentado",
        descripcion="Presenta una queja administrativa o comercial con todos los datos de respaldo y solución pedida.",
        modo="express",
        por_que_funciona="Ordena hechos, fecha/comprobante y pedido concreto sin perder firmeza.",
        prompt=(
            "redactame un reclamo formal pero respetuoso dirigido a [empresa o servicio] por [problema concreto "
            "ocurrido el dia fecha], numero de comprobante o tramite [numero], solicitando [solucion esperada, "
            "ej: reintegro o reemplazo] en un plazo razonable"
        ),
    ),
    # 6. Carrera y Productividad
    "adaptar-cv-puesto": _build_template_entry(
        slug="adaptar-cv-puesto",
        categoria="Carrera y Productividad",
        titulo="Adaptar mi CV o presentación a un puesto",
        descripcion="Alinea tu perfil y experiencia real con lo que busca una oferta laboral específica.",
        modo="guiado",
        por_que_funciona="Cruza tu experiencia real contra los requisitos del aviso sin inventar logros.",
        prompt=(
            "ayudame a adaptar mi perfil profesional y 4 puntos fuertes de mi CV para postularme al puesto de "
            "[nombre del puesto] en [rubro]. No inventes experiencia que no tengo. Mi experiencia actual es: "
            "[resume en 3 lineas tu experiencia] y el aviso pide: [pega requisitos clave]"
        ),
    ),
    "simular-entrevista-exigente": _build_template_entry(
        slug="simular-entrevista-exigente",
        categoria="Carrera y Productividad",
        titulo="Simular una entrevista laboral exigente",
        descripcion="Entrena preguntas técnicas y situacionales de una entrevista real con guía de respuesta.",
        modo="estudio_pro",
        por_que_funciona="Define el rol entrevistador, el puesto real y pide devolución concreta tras responder.",
        prompt=(
            "actua como entrevistador para un puesto de [puesto, ej: analista de datos / logistica y "
            "administracion] en [rubro]. Haceme 6 preguntas clave (tecnicas y situacionales), explicame que "
            "evalua cada una y dame una guia de como estructurar respuestas solidas con ejemplos reales"
        ),
    ),
    "extraer-decisiones-chat-correo": _build_template_entry(
        slug="extraer-decisiones-chat-correo",
        categoria="Carrera y Productividad",
        titulo="Extraer decisiones de un correo o chat caótico",
        descripcion="Convierte una cadena larga de mensajes en una lista limpia de acuerdos, responsables y pasos.",
        modo="express",
        por_que_funciona="Aísla lo accionable (decisiones, responsables y fechas) sin ruido del texto original.",
        prompt=(
            "resumime en 3 puntos clave las decisiones tomadas, responsables y proximos pasos a partir de este "
            "texto desordenado:\n[pega aqui el correo o conversacion]"
        ),
    ),
}

LEGACY_PRESETS = {
    "analisis-datos-pandas": {
        "title": "Análisis Exploratorio de Datos (Pandas)",
        "category": "Ciencia de Datos e IA",
        "technique": "Paso a Paso",
        "level": "Profunda",
        "mode": "pro",
        "description": "Estructura un flujo completo en Python y Pandas para limpiar datos, detectar valores nulos y obtener conclusiones estadísticas.",
        "text": "Analizar este dataset en Python con Pandas para limpiar valores nulos, calcular estadísticas descriptivas y encontrar patrones clave",
    },
    "programacion-debug": {
        "title": "Depuración y Corrección de Código",
        "category": "Tecnología y programación",
        "technique": "Verificación",
        "level": "Completa",
        "mode": "guiado",
        "description": "Ideal para encontrar la causa raíz de un error en Python, SQL o JavaScript y obtener el código corregido.",
        "text": "Depurar este error en mi script de Python explicando la causa del problema y cómo solucionarlo paso a paso",
    },
    "estudio-pedagogico": {
        "title": "Guía de Estudio con Ejemplos y Autoevaluación",
        "category": "Estudio y academia",
        "technique": "Pedagógico",
        "level": "Completa",
        "mode": "guiado",
        "description": "Explica cualquier tema complejo desde cero usando analogías sencillas y preguntas de repaso para exámenes.",
        "text": "Explicar los conceptos fundamentales de regresión lineal y logística para estudiantes de ciencia de datos desde cero",
    },
    "control-comercial-stock": {
        "title": "Plan de Control de Inventario y Ventas",
        "category": "Negocios y comercio",
        "technique": "Paso a Paso",
        "level": "Completa",
        "mode": "guiado",
        "description": "Diseña un plan práctico para organizar stock, controlar vencimientos y mejorar la rentabilidad de un comercio.",
        "text": "Armar un plan paso a paso para controlar el stock, vencimientos y reposición de mercadería en un comercio minorista",
    },
    "redaccion-profesional": {
        "title": "Redacción de Correo o Propuesta Profesional",
        "category": "Redacción y comunicación",
        "technique": "Estándar",
        "level": "Completa",
        "mode": "guiado",
        "description": "Estructura mensajes formales, claros y persuasivos para clientes, proveedores o presentaciones académicas.",
        "text": "Redactar una respuesta profesional para este correo presentando una propuesta de trabajo clara y cordial",
    },
    "tramites-nota-formal": {
        "title": "Nota Formal o Reclamo Administrativo",
        "category": "Trámites y documentos",
        "technique": "Verificación",
        "level": "Completa",
        "mode": "guiado",
        "description": "Redacta reclamos formales, descargos o solicitudes administrativas con estructura clara y marcadores seguros.",
        "text": "Redactame una nota formal de reclamo por demora en la entrega de un servicio indicando hechos, plazos y solicitud concreta",
    },
    "planificacion-roadmap": {
        "title": "Hoja de Ruta y Cronograma de Proyecto",
        "category": "Planificación y productividad",
        "technique": "Paso a Paso",
        "level": "Completa",
        "mode": "guiado",
        "description": "Divide metas complejas en hitos semanales, prioridades y entregables concretos.",
        "text": "Planificar un cronograma de 4 semanas con hitos, prioridades y entregables para lanzar una aplicación web",
    },
    "decision-comparativa": {
        "title": "Matriz de Decisión y Comparativa",
        "category": "Toma de decisiones",
        "technique": "Con Ejemplos",
        "level": "Completa",
        "mode": "guiado",
        "description": "Evalúa alternativas con criterios ponderados, ventajas, riesgos y recomendación fundamentada.",
        "text": "Comparar SQLite vs PostgreSQL en una tabla clara indicando ventajas, límites y cuándo conviene elegir cada uno",
    },
}

def workspace(request):
    prompt_id = request.GET.get('load')
    preset_slug = request.GET.get('preset')
    active_user = _get_active_user(request)
    loaded_prompt = None
    preset_data = None
    loaded_rubric_json = 'null'

    loaded_rubric = None
    if prompt_id and str(prompt_id).isdigit():
        loaded_prompt = Prompt.objects.filter(id=int(prompt_id), user=active_user).first()
        if loaded_prompt:
            rubric = calculate_rubric_score(loaded_prompt.improved_text)
            loaded_rubric = rubric['breakdown']
            loaded_rubric_json = json.dumps(loaded_rubric)
    elif preset_slug:
        if preset_slug in TEMPLATES_CATALOG:
            preset_data = TEMPLATES_CATALOG[preset_slug]
        elif preset_slug in LEGACY_PRESETS:
            preset_data = LEGACY_PRESETS[preset_slug]

    boot_payload = {
        'loaded_prompt': {
            'id': loaded_prompt.id,
            'category': loaded_prompt.category or 'General',
            'level': loaded_prompt.improvement_level or 'Completa',
            'technique': loaded_prompt.technique or 'Estándar',
            'initial_score': loaded_prompt.initial_score,
            'information_gain': loaded_prompt.information_gain,
            'final_score': loaded_prompt.final_score,
            'quality_gain': loaded_prompt.quality_gain,
            'is_favorite': loaded_prompt.is_favorite,
        } if loaded_prompt else None,
        'loaded_rubric': loaded_rubric,
        'preset_data': preset_data,
    }

    loaded_action_label = ""
    loaded_mode_label = ""
    loaded_technique_label = ""
    if loaded_prompt:
        loaded_action_label = ACTION_TO_NATURAL_LABEL.get(
            (loaded_prompt.detected_action or "explicar_concepto").strip(),
            "Explicar concepto",
        )
        loaded_mode_label = LEVEL_TO_DISPLAY_MODE.get(
            loaded_prompt.improvement_level or "Completa",
            "Guiado",
        )
        loaded_technique_label = TECHNIQUE_TO_NATURAL_LABEL.get(
            (loaded_prompt.technique or "Estándar").strip(),
            loaded_prompt.technique or "Estándar",
        )

    return render(request, 'core/workspace.html', {
        'loaded_prompt': loaded_prompt,
        'loaded_action_label': loaded_action_label,
        'loaded_mode_label': loaded_mode_label,
        'loaded_technique_label': loaded_technique_label,
        'preset_data': preset_data,
        'loaded_rubric_json': loaded_rubric_json,
        'workspace_boot_json': json.dumps(boot_payload, ensure_ascii=False).replace('</', '<\\/'),
    })


def _prepare_history_prompts(queryset):
    items = list(queryset)
    for p in items:
        mode_label = LEVEL_TO_DISPLAY_MODE.get(p.improvement_level or "Completa", "Guiado")
        p.display_mode = mode_label
        p.display_mode_key = (
            "express" if mode_label == "Express" else "pro" if mode_label == "Estudio Pro" else "guiado"
        )
        p.display_action = ACTION_TO_NATURAL_LABEL.get(
            (p.detected_action or "explicar_concepto").strip(),
            "Explicar concepto",
        )
        p.display_technique = TECHNIQUE_TO_NATURAL_LABEL.get(
            (p.technique or "Estándar").strip(),
            p.technique or "Estándar",
        )
        p.quality_band = _quality_band_meta(p.final_score or 0)
    return items


def history(request):
    active_user = _get_active_user(request)
    prompts = _prepare_history_prompts(Prompt.objects.filter(user=active_user).order_by('-created_at'))
    categories = sorted({p.category or 'General' for p in prompts})
    techniques = sorted({p.display_technique for p in prompts})
    return render(request, 'core/history.html', {
        'prompts': prompts,
        'only_favorites': False,
        'categories': categories,
        'techniques': techniques,
        'modes': ['Express', 'Guiado', 'Estudio Pro'],
    })

def favorites(request):
    active_user = _get_active_user(request)
    prompts = _prepare_history_prompts(Prompt.objects.filter(user=active_user, is_favorite=True).order_by('-created_at'))
    categories = sorted({p.category or 'General' for p in prompts})
    techniques = sorted({p.display_technique for p in prompts})
    return render(request, 'core/history.html', {
        'prompts': prompts,
        'only_favorites': True,
        'categories': categories,
        'techniques': techniques,
        'modes': ['Express', 'Guiado', 'Estudio Pro'],
    })

@require_POST
def toggle_favorite(request, prompt_id):
    active_user = _get_active_user(request)
    prompt = get_object_or_404(Prompt, id=prompt_id, user=active_user)
    prompt.is_favorite = not prompt.is_favorite
    prompt.save()
    if (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
    ):
        return JsonResponse({'id': prompt.id, 'is_favorite': prompt.is_favorite})
    next_url = request.POST.get('next') or request.GET.get('next') or 'history'
    if next_url not in ('history', 'favorites'):
        next_url = 'history'
    return redirect(next_url)

@require_POST
def delete_prompt(request, prompt_id):
    active_user = _get_active_user(request)
    prompt = get_object_or_404(Prompt, id=prompt_id, user=active_user)
    prompt.delete()
    next_url = request.POST.get('next') or request.GET.get('next') or 'history'
    if next_url not in ('history', 'favorites'):
        next_url = 'history'
    return redirect(next_url)

def templates_gallery(request):
    templates_list = list(TEMPLATES_CATALOG.values())
    categories = [
        {
            'name': cat,
            'count': sum(1 for t in templates_list if t['categoria'] == cat),
        }
        for cat in TEMPLATE_CATEGORIES
    ]
    return render(request, 'core/templates_gallery.html', {
        'templates': TEMPLATES_CATALOG,
        'templates_list': templates_list,
        'categories': categories,
        'total_templates': len(templates_list),
    })

@csrf_exempt
def analyze_live_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            if not isinstance(data, dict):
                return JsonResponse({"error": "Formato JSON inválido: se esperaba un objeto."}, status=400)

            user_text = data.get('text', '')
            if not isinstance(user_text, str):
                return JsonResponse({"error": "El campo 'text' debe ser una cadena de texto."}, status=400)

            category = data.get('category', '')
            form_data = data.get('form_data', {})
            if not isinstance(form_data, dict):
                form_data = {}
            technique = data.get('technique', 'Estándar')
            override_domain = data.get('override_domain', '') or ''
            override_action = data.get('override_action', '') or ''
            override_deliverable = data.get('override_deliverable', '') or ''
            negative_constraints = data.get('negative_constraints', [])
            if not isinstance(negative_constraints, list):
                negative_constraints = []

            result = analyze_live_preview(
                text=user_text,
                category=category,
                form_data=form_data,
                technique=technique,
                override_domain=override_domain,
                override_action=override_action,
                override_deliverable=override_deliverable,
                negative_constraints=negative_constraints,
            )
            return JsonResponse(result)
        except json.JSONDecodeError:
            return JsonResponse({"error": "JSON malformado en la solicitud."}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse({"error": "Método no permitido"}, status=405)


@csrf_exempt
def improve_prompt_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            if not isinstance(data, dict):
                return JsonResponse({"error": "Formato JSON inválido: se esperaba un objeto."}, status=400)

            user_text = data.get('text', '')
            if not isinstance(user_text, str):
                return JsonResponse({"error": "El campo 'text' debe ser una cadena de texto."}, status=400)

            category = data.get('category', 'Otro / No sé')
            form_data = data.get('form_data', {})
            if not isinstance(form_data, dict):
                form_data = {}
            level = data.get('level', 'Completa')
            if level not in ('Ligera', 'Completa', 'Profunda'):
                level = 'Completa'
            technique = data.get('technique', 'Estándar')

            override_domain = data.get('override_domain', '') or ''
            override_action = data.get('override_action', '') or ''
            override_deliverable = data.get('override_deliverable', '') or ''
            negative_constraints = data.get('negative_constraints', [])
            if not isinstance(negative_constraints, list):
                negative_constraints = []
            user_example = data.get('user_example', '') or ''
            mask_pii = bool(data.get('mask_pii', False))

            result = get_gemini_response(
                user_text=user_text,
                category=category,
                form_data=form_data,
                level=level,
                technique=technique,
                override_domain=override_domain,
                override_action=override_action,
                override_deliverable=override_deliverable,
                negative_constraints=negative_constraints,
                user_example=user_example,
                mask_pii=mask_pii,
            )

            if 'improved_prompt' in result:
                user = _get_active_user(request)

                resolved_cat = result.get('category') or category or 'General'
                raw_orig = result.get('raw_objective') or user_text
                created_prompt = Prompt.objects.create(
                    user=user,
                    original_text=raw_orig,
                    improved_text=result['improved_prompt'],
                    category=resolved_cat,
                    detected_action=result.get('detected_action', 'explicar_concepto'),
                    detected_deliverable=result.get('detected_deliverable', 'informe estructurado'),
                    subintent=result.get('subintent', 'general'),
                    improvement_level=level,
                    technique=result.get('technique', technique),
                    engine_version=result.get('engine_version', 'v7.2'),
                    initial_score=result.get('initial_score', 25),
                    information_gain=result.get('information_gain', 0),
                    final_score=result.get('final_score', 90),
                    quality_gain=result.get('quality_gain', 65),
                    intent_confidence=result.get('intent_confidence', 0.85),
                    intent_margin=result.get('intent_margin', 0.30),
                    n_intents=result.get('n_intents', 1),
                    n_entities=result.get('n_entities', 0),
                    n_neg_constraints=result.get('n_neg_constraints', 0),
                    n_slots_used=result.get('n_slots_used', 0),
                    info_density=result.get('info_density', 0.0),
                    noise_ratio=result.get('noise_ratio', 0.04),
                    anchor_coverage=result.get('anchor_coverage', 0.95),
                    payload_kind=result.get('payload_kind', 'sin_insumo'),
                    roles_filled=result.get('roles_filled', 0.80),
                    verifiable_ratio=result.get('verifiable_ratio', 0.85),
                    user_corrected=result.get('user_corrected', False),
                    has_pii_masked=result.get('has_pii_masked', False),
                )
                if created_prompt.user_corrected:
                    invalidate_learned_boosts_cache()
                result['prompt_id'] = created_prompt.id
                result['is_favorite'] = created_prompt.is_favorite

            return JsonResponse(result)
        except json.JSONDecodeError:
            return JsonResponse({"error": "JSON malformado en la solicitud."}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse({"error": "Método no permitido"}, status=405)

LEVEL_TO_DISPLAY_MODE = {
    "Ligera": "Express",
    "express": "Express",
    "Completa": "Guiado",
    "guiado": "Guiado",
    "Profunda": "Estudio Pro",
    "pro": "Estudio Pro",
    "estudio_pro": "Estudio Pro",
}

TECHNIQUE_TO_NATURAL_LABEL = {
    "Estándar": "Estándar",
    "Estandar": "Estándar",
    "Paso a Paso": "Paso a paso",
    "Paso a paso": "Paso a paso",
    "Con Ejemplos": "Con Ejemplos",
    "Con ejemplos": "Con Ejemplos",
    "Pedagógico": "Pedagógico",
    "Pedagogico": "Pedagógico",
    "Verificación": "Verificación",
    "Verificacion": "Verificación",
    "Crítico": "Crítico",
    "Critico": "Crítico",
}

ACTION_TO_NATURAL_LABEL = {
    "depurar_error": "Depurar error",
    "generar_codigo": "Generar código",
    "analizar_datos": "Analizar datos",
    "comparar_evaluar": "Comparar y evaluar",
    "resumir_sintetizar": "Resumir y sintetizar",
    "planificar_pasos": "Planificar pasos",
    "redactar_contenido": "Redactar contenido",
    "explicar_concepto": "Explicar concepto",
    "transformar_formato": "Transformar formato",
    "extraer_informacion": "Extraer información",
    "clasificar_categorizar": "Clasificar y categorizar",
    "traducir_adaptar": "Traducir y adaptar",
    "reescribir_mejorar": "Reescribir y mejorar",
    "auditar_criticar": "Revisar riesgos",
    "simular_practicar": "Simular diálogo",
    "idear_alternativas": "Idear alternativas",
    "calcular_modelar": "Calcular escenarios",
    "razonar_resolver": "Resolver problema lógico",
    "decidir_recomendar": "Evaluar y recomendar",
    "diagnosticar_resolver": "Diagnosticar fallas",
    "consultar_dato": "Consulta directa",
}


def _truncate_text(text: str, max_len: int = 56) -> str:
    clean = " ".join((text or "").split())
    if len(clean) <= max_len:
        return clean
    return clean[: max_len - 1].rstrip() + "…"


def _format_points_gain(value) -> str:
    if value is None:
        return "—"
    rounded = int(round(value))
    if rounded > 0:
        return f"+{rounded} pts"
    if rounded < 0:
        return f"{rounded} pts"
    return "0 pts"


def _quality_band_meta(score: float) -> dict:
    if score >= 90:
        return {"label": "Excelente", "badge_class": "stats-band-excellent"}
    if score >= 80:
        return {"label": "Muy bueno", "badge_class": "stats-band-verygood"}
    if score >= 70:
        return {"label": "Bueno", "badge_class": "stats-band-good"}
    return {"label": "Mejorable", "badge_class": "stats-band-fair"}


def analytics_dashboard(request):
    raw_period = request.GET.get("periodo", "all")
    period = raw_period if raw_period in ("all", "30d", "7d") else "all"

    period_labels = {
        "all": "todo el historial",
        "30d": "los últimos 30 días",
        "7d": "los últimos 7 días",
    }

    active_user = _get_active_user(request)
    all_qs = Prompt.objects.filter(user=active_user).order_by("-created_at", "-id")
    total_all_time = all_qs.count()

    if period == "7d":
        cutoff = timezone.now() - timedelta(days=7)
        filtered_qs = all_qs.filter(created_at__gte=cutoff)
    elif period == "30d":
        cutoff = timezone.now() - timedelta(days=30)
        filtered_qs = all_qs.filter(created_at__gte=cutoff)
    else:
        filtered_qs = all_qs

    prompts = list(filtered_qs)
    total_prompts = len(prompts)
    favorites_count = sum(1 for p in prompts if getattr(p, "is_favorite", False))
    pii_protected_count = sum(1 for p in prompts if getattr(p, "has_pii_masked", False))
    approval_rate = round((favorites_count / total_prompts) * 100, 1) if total_prompts > 0 else 0.0

    init_scores = []
    final_scores = []
    gains = []
    info_gains = []
    noise_ratios = []
    anchor_coverages = []
    roles_filled_list = []
    verifiable_ratios = []
    confidences = []
    corrected_count = 0

    domain_counts = {}
    mode_counts = {"Express": 0, "Guiado": 0, "Estudio Pro": 0}
    style_counts = {}
    tech_scores = {}
    mode_scores = {
        "Express": {"before": [], "after": []},
        "Guiado": {"before": [], "after": []},
        "Estudio Pro": {"before": [], "after": []},
    }
    task_scores = {}
    action_counts = {}
    band_counts = {"excellent": 0, "verygood": 0, "good": 0, "fair": 0}
    evaluated_rows = []

    for p in prompts:
        raw_init = getattr(p, "initial_score", None)
        raw_final = getattr(p, "final_score", None)

        # Cálculo en memoria para registros antiguos con 0 sin mutar la BD en una petición GET
        if raw_final is not None and raw_final == 0 and (p.improved_text or "").strip():
            i_score = calculate_rubric_score(p.original_text)["total"]
            f_score = calculate_rubric_score(p.improved_text)["total"]
        else:
            i_score = raw_init
            f_score = raw_final

        if i_score is not None:
            init_scores.append(i_score)
        if f_score is not None:
            final_scores.append(f_score)
            if f_score >= 90:
                band_counts["excellent"] += 1
            elif f_score >= 80:
                band_counts["verygood"] += 1
            elif f_score >= 70:
                band_counts["good"] += 1
            else:
                band_counts["fair"] += 1

        row_gain = (f_score - i_score) if (i_score is not None and f_score is not None) else None
        if row_gain is not None:
            gains.append(row_gain)

        if getattr(p, "information_gain", None) is not None:
            info_gains.append(p.information_gain)
        if getattr(p, "noise_ratio", None) is not None:
            noise_ratios.append(p.noise_ratio * 100.0)
        if getattr(p, "anchor_coverage", None) is not None:
            anchor_coverages.append(p.anchor_coverage * 100.0)
        if getattr(p, "roles_filled", None) is not None:
            roles_filled_list.append(p.roles_filled * 100.0)
        if getattr(p, "verifiable_ratio", None) is not None:
            verifiable_ratios.append(p.verifiable_ratio * 100.0)
        if getattr(p, "intent_confidence", None) is not None:
            confidences.append(p.intent_confidence * 100.0)
        if getattr(p, "user_corrected", False):
            corrected_count += 1

        domain_name = (p.category or "").strip() or "Otro / General"
        domain_counts[domain_name] = domain_counts.get(domain_name, 0) + 1

        mode_label = LEVEL_TO_DISPLAY_MODE.get(p.improvement_level or "Completa", "Guiado")
        mode_counts[mode_label] = mode_counts.get(mode_label, 0) + 1

        raw_tech = (getattr(p, "technique", None) or "Estándar").strip() or "Estándar"
        style_label = TECHNIQUE_TO_NATURAL_LABEL.get(raw_tech, raw_tech)
        style_counts[style_label] = style_counts.get(style_label, 0) + 1

        act_key = (p.detected_action or "explicar_concepto").strip()
        act_label = ACTION_TO_NATURAL_LABEL.get(act_key, act_key.replace("_", " ").capitalize())
        action_counts[act_label] = action_counts.get(act_label, 0) + 1

        if i_score is not None and f_score is not None:
            tech_bucket = tech_scores.setdefault(style_label, {"before": [], "after": []})
            tech_bucket["before"].append(i_score)
            tech_bucket["after"].append(f_score)

            mode_bucket = mode_scores[mode_label]
            mode_bucket["before"].append(i_score)
            mode_bucket["after"].append(f_score)

            task_bucket = task_scores.setdefault(act_label, {"before": [], "after": []})
            task_bucket["before"].append(i_score)
            task_bucket["after"].append(f_score)

        evaluated_rows.append({
            "id": p.id,
            "title_short": _truncate_text(p.original_text, 52),
            "original_text": p.original_text,
            "date_short": p.created_at.strftime("%d/%m %H:%M") if p.created_at else "—",
            "date_fmt": p.created_at.strftime("%d/%m/%Y %H:%M") if p.created_at else "—",
            "domain": domain_name,
            "mode_label": mode_label,
            "mode_key": (
                "express" if mode_label == "Express" else "pro" if mode_label == "Estudio Pro" else "guiado"
            ),
            "initial_score": i_score,
            "final_score": f_score,
            "initial_pct": max(0, min(int(round(i_score)), 100)) if i_score is not None else 0,
            "final_pct": max(0, min(int(round(f_score)), 100)) if f_score is not None else 0,
            "gain_fmt": _format_points_gain(row_gain),
            "gain_positive": (row_gain or 0) > 0,
        })

    avg_initial_score = round(sum(init_scores) / len(init_scores), 1) if init_scores else None
    avg_final_score = round(sum(final_scores) / len(final_scores), 1) if final_scores else None
    avg_gain_raw = round(sum(gains) / len(gains)) if gains else None
    avg_gain_fmt = _format_points_gain(avg_gain_raw)
    avg_info_gain = round(sum(info_gains) / len(info_gains), 1) if info_gains else None
    avg_noise_ratio = round(sum(noise_ratios) / len(noise_ratios), 1) if noise_ratios else None
    avg_anchor_coverage = round(sum(anchor_coverages) / len(anchor_coverages), 1) if anchor_coverages else None
    avg_roles_filled = round(sum(roles_filled_list) / len(roles_filled_list), 1) if roles_filled_list else 0.0
    avg_verifiable_ratio = round(sum(verifiable_ratios) / len(verifiable_ratios), 1) if verifiable_ratios else 0.0
    avg_confidence = round(sum(confidences) / len(confidences), 1) if confidences else 0.0

    quality_band = _quality_band_meta(avg_final_score) if avg_final_score is not None else {
        "label": "Sin datos",
        "badge_class": "stats-band-fair",
    }

    # Distribución de calidad (4 bandas)
    scored_total = len(final_scores)
    quality_distribution = [
        {
            "label": "Excelente (90–100)",
            "hint": "Listos para usar tal cual",
            "count": band_counts["excellent"],
            "pct": round((band_counts["excellent"] / scored_total) * 100) if scored_total else 0,
            "bar_class": "stats-bar-excellent",
        },
        {
            "label": "Muy bueno (80–89)",
            "hint": "Sólidos y bien estructurados",
            "count": band_counts["verygood"],
            "pct": round((band_counts["verygood"] / scored_total) * 100) if scored_total else 0,
            "bar_class": "stats-bar-verygood",
        },
        {
            "label": "Bueno (70–79)",
            "hint": "Claros, con margen para sumar contexto",
            "count": band_counts["good"],
            "pct": round((band_counts["good"] / scored_total) * 100) if scored_total else 0,
            "bar_class": "stats-bar-good",
        },
        {
            "label": "Mejorable (< 70)",
            "hint": "Conviene probar Guiado o Estudio Pro",
            "count": band_counts["fair"],
            "pct": round((band_counts["fair"] / scored_total) * 100) if scored_total else 0,
            "bar_class": "stats-bar-fair",
        },
    ]

    # Ranking de dominios
    sorted_domains = sorted(domain_counts.items(), key=lambda item: (-item[1], item[0]))
    domain_ranking = [
        {
            "name": name,
            "count": count,
            "pct": round((count / total_prompts) * 100) if total_prompts else 0,
        }
        for name, count in sorted_domains
    ]

    # Distribución por modo (Express / Guiado / Estudio Pro)
    mode_hints = {
        "Express": "Ideal para pedidos cortos, rápidos y directos.",
        "Guiado": "Equilibrado por secciones para sumar contexto paso a paso.",
        "Estudio Pro": "Máximo detalle, validaciones previas y casos borde.",
    }
    mode_distribution = [
        {
            "label": m_name,
            "hint": mode_hints[m_name],
            "count": mode_counts[m_name],
            "pct": round((mode_counts[m_name] / total_prompts) * 100) if total_prompts else 0,
            "key": "express" if m_name == "Express" else "pro" if m_name == "Estudio Pro" else "guiado",
        }
        for m_name in ("Express", "Guiado", "Estudio Pro")
    ]

    # Top 4 tareas frecuentes en lenguaje natural
    sorted_actions = sorted(action_counts.items(), key=lambda item: (-item[1], item[0]))[:4]
    top_actions = [
        {
            "label": act_label,
            "count": count,
            "pct": round((count / total_prompts) * 100) if total_prompts else 0,
        }
        for act_label, count in sorted_actions
    ]

    # Series estructuradas para gráficos SVG interactivos (100% sin jerga interna)
    sorted_styles = sorted(style_counts.items(), key=lambda item: (-item[1], item[0]))
    style_distribution = [
        {
            "label": style_label,
            "count": count,
            "pct": round((count / total_prompts) * 100) if total_prompts else 0,
        }
        for style_label, count in sorted_styles
    ]

    technique_score_comparison = []
    for style_label, count in sorted_styles:
        bucket = tech_scores.get(style_label)
        if not bucket or not bucket["before"]:
            continue
        b_avg = round(sum(bucket["before"]) / len(bucket["before"]))
        a_avg = round(sum(bucket["after"]) / len(bucket["after"]))
        technique_score_comparison.append({
            "label": style_label,
            "count": count,
            "before_avg": b_avg,
            "after_avg": a_avg,
            "gain_fmt": _format_points_gain(a_avg - b_avg),
        })

    mode_score_comparison = []
    for m_name in ("Express", "Guiado", "Estudio Pro"):
        bucket = mode_scores[m_name]
        if not bucket["before"]:
            continue
        b_avg = round(sum(bucket["before"]) / len(bucket["before"]))
        a_avg = round(sum(bucket["after"]) / len(bucket["after"]))
        mode_score_comparison.append({
            "label": m_name,
            "count": mode_counts[m_name],
            "before_avg": b_avg,
            "after_avg": a_avg,
            "gain_fmt": _format_points_gain(a_avg - b_avg),
        })

    sorted_task_counts = sorted(action_counts.items(), key=lambda item: (-item[1], item[0]))[:8]
    task_score_comparison = []
    for act_label, count in sorted_task_counts:
        bucket = task_scores.get(act_label)
        if not bucket or not bucket["before"]:
            continue
        b_avg = round(sum(bucket["before"]) / len(bucket["before"]))
        a_avg = round(sum(bucket["after"]) / len(bucket["after"]))
        task_score_comparison.append({
            "label": act_label,
            "count": count,
            "before_avg": b_avg,
            "after_avg": a_avg,
            "gain_fmt": _format_points_gain(a_avg - b_avg),
        })

    evolution_rows = [
        r for r in evaluated_rows[:10]
        if r["initial_score"] is not None and r["final_score"] is not None
    ]
    evolution_series = [
        {
            "order": idx + 1,
            "title": row["title_short"],
            "full_title": row["original_text"],
            "date": row["date_short"],
            "mode": row["mode_label"],
            "before": int(round(row["initial_score"])),
            "after": int(round(row["final_score"])),
            "gain_fmt": row["gain_fmt"],
        }
        for idx, row in enumerate(reversed(evolution_rows))
    ]

    chart_payload = {
        "total": total_prompts,
        "domains": domain_ranking,
        "donut": {
            "styles": style_distribution,
            "modes": [
                {"label": m["label"], "count": m["count"], "pct": m["pct"]}
                for m in mode_distribution
            ],
        },
        "evolution": evolution_series,
        "by_technique": technique_score_comparison,
        "by_mode": mode_score_comparison,
        "by_task": task_score_comparison,
        "quality_bands": quality_distribution,
    }

    # Reglas deterministas para "Qué podés aprovechar mejor" (2 a 3 consejos)
    personalized_tips = []
    if total_prompts > 0:
        pro_pct = (mode_counts["Estudio Pro"] / total_prompts) * 100.0
        if pro_pct < 20.0:
            personalized_tips.append({
                "icon": "bi-layers-half",
                "tone": "info",
                "title": "Probá Estudio Pro en pedidos complejos",
                "text": "Usaste Estudio Pro en menos del 20% de tus prompts. Activalo cuando necesites analizar código, SQL o casos borde detallados.",
            })
        if total_prompts >= 3 and favorites_count == 0:
            personalized_tips.append({
                "icon": "bi-star",
                "tone": "warning",
                "title": "Guardá tus mejores resultados en Favoritos",
                "text": "Todavía no marcaste prompts con estrella. Guardar los que mejor te funcionaron te permite reutilizarlos en un clic.",
            })
        if avg_initial_score is not None and avg_initial_score < 65:
            personalized_tips.append({
                "icon": "bi-bullseye",
                "tone": "primary",
                "title": "Sumá público o una restricción desde el inicio",
                "text": f"Tu idea inicial promedia {int(round(avg_initial_score))}/100. Aclarar a quién va dirigido o qué evitar eleva mucho la precisión final.",
            })
        if avg_final_score is not None and avg_final_score >= 88:
            personalized_tips.append({
                "icon": "bi-award",
                "tone": "success",
                "title": "Excelente nivel estructural",
                "text": f"Alcanzás {avg_final_score}/100 de calidad promedio. Podés partir de las Plantillas para acelerar pedidos repetitivos.",
            })
        if pii_protected_count > 0:
            personalized_tips.append({
                "icon": "bi-shield-check",
                "tone": "success",
                "title": "Privacidad activa en tus textos",
                "text": f"PromptLab protegió datos sensibles automáticamente en {pii_protected_count} prompt(s) de este período.",
            })
        if len(personalized_tips) < 2:
            personalized_tips.append({
                "icon": "bi-grid-1x2",
                "tone": "primary",
                "title": "Aprovechá las Plantillas listas para usar",
                "text": "Explorá la pestaña Plantillas para cargar estructuras probadas según tu área y adaptarlas en segundos.",
            })
    personalized_tips = personalized_tips[:3]

    top_domain = domain_ranking[0]["name"] if domain_ranking else "General"
    top_mode = max(mode_distribution, key=lambda m: m["count"])["label"] if total_prompts > 0 else "Guiado"

    summary_data = {
        "count": total_prompts,
        "avg_before": int(round(avg_initial_score)) if avg_initial_score is not None else "—",
        "avg_after": int(round(avg_final_score)) if avg_final_score is not None else "—",
        "avg_gain_fmt": avg_gain_fmt,
        "top_domain": top_domain,
        "top_mode": top_mode,
        "period_label": period_labels[period],
        "favorites_count": favorites_count,
        "pii_protected_count": pii_protected_count,
    }

    long_tail_candidates = mine_long_tail_candidates(prompts, top_n=8)
    for cand in long_tail_candidates:
        sugg = cand.get("suggested_action") or ""
        cand["suggested_action_label"] = ACTION_TO_NATURAL_LABEL.get(
            sugg, sugg.replace("_", " ").capitalize()
        )

    context = {
        "period": period,
        "total_all_time": total_all_time,
        "total_prompts": total_prompts,
        "favorites_count": favorites_count,
        "pii_protected_count": pii_protected_count,
        "approval_rate": approval_rate,
        "avg_initial_score": avg_initial_score,
        "avg_final_score": avg_final_score,
        "avg_final_pct": max(0, min(int(round(avg_final_score)), 100)) if avg_final_score is not None else 0,
        "avg_gain_fmt": avg_gain_fmt,
        "avg_info_gain": avg_info_gain,
        "avg_noise_ratio": avg_noise_ratio,
        "avg_anchor_coverage": avg_anchor_coverage,
        "avg_roles_filled": avg_roles_filled,
        "avg_verifiable_ratio": avg_verifiable_ratio,
        "avg_confidence": avg_confidence,
        "quality_band": quality_band,
        "summary_data": summary_data,
        "before_after_items": evaluated_rows[:8],
        "quality_distribution": quality_distribution,
        "domain_ranking": domain_ranking,
        "mode_distribution": mode_distribution,
        "top_actions": top_actions,
        "personalized_tips": personalized_tips,
        "recent_prompts": evaluated_rows[:5],
        "long_tail_candidates": long_tail_candidates,
        "chart_payload": chart_payload,
    }
    return render(request, "core/analytics.html", context)

def export_dataset_csv(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="promptlab_dataset.csv"'
    response.write('\ufeff')

    writer = csv.writer(response, quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
    writer.writerow([
        'id',
        'fecha_creacion',
        'engine_version',
        'categoria',
        'detected_action',
        'detected_deliverable',
        'subintent',
        'nivel_mejora',
        'tecnica_aplicada',
        'puntaje_inicial',
        'information_gain',
        'puntaje_final',
        'ganancia_calidad_pts',
        'intent_confidence',
        'intent_margin',
        'n_intents',
        'n_entities',
        'n_neg_constraints',
        'n_slots_used',
        'info_density',
        'noise_ratio',
        'anchor_coverage',
        'payload_kind',
        'roles_filled',
        'verifiable_ratio',
        'tiene_criterio_exito',
        'user_corrected',
        'has_pii_masked',
        'es_favorito',
        'palabras_entrada',
        'palabras_salida',
        'caracteres_entrada',
        'caracteres_salida',
        'factor_expansion',
        'bloques_estructura',
        'tiene_delimitadores',
        'texto_original',
        'prompt_mejorado'
    ])

    active_user = _get_active_user(request)
    for p in Prompt.objects.filter(user=active_user).order_by('id'):
        o_words = max(len(p.original_text.split()), 1)
        i_words = max(len(p.improved_text.split()), 1)
        o_chars = len(p.original_text)
        i_chars = len(p.improved_text)
        ratio = round(i_words / o_words, 2)
        blocks_count = len(re.findall(r'^#\s+.+', p.improved_text, flags=re.MULTILINE))
        has_delimiters = int('<datos_entrada>' in p.improved_text)
        has_success_criteria = int('# Criterio de éxito' in p.improved_text)

        writer.writerow([
            p.id,
            p.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            p.engine_version,
            p.category or 'General',
            p.detected_action,
            p.detected_deliverable,
            p.subintent,
            p.improvement_level,
            p.technique or 'Estándar',
            p.initial_score,
            p.information_gain,
            p.final_score,
            p.quality_gain,
            p.intent_confidence,
            p.intent_margin,
            p.n_intents,
            p.n_entities,
            p.n_neg_constraints,
            p.n_slots_used,
            p.info_density,
            p.noise_ratio,
            p.anchor_coverage,
            p.payload_kind,
            p.roles_filled,
            p.verifiable_ratio,
            has_success_criteria,
            int(p.user_corrected),
            int(p.has_pii_masked),
            int(p.is_favorite),
            o_words,
            i_words,
            o_chars,
            i_chars,
            ratio,
            blocks_count,
            has_delimiters,
            p.original_text,
            p.improved_text
        ])

    return response
