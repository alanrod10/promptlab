import re
import unicodedata

CATEGORY_KEYWORDS = {
    "Tecnología y programación": [
        "codigo", "código", "python", "django", "sql", "javascript", "html", "css", "react",
        "api", "bug", "error", "funcion", "función", "script", "base de datos", "algoritmo",
        "git", "linux", "servidor", "backend", "frontend", "web", "app", "software", "debug", "consulta"
    ],
    "Aprender y enseñar": [
        "aprender", "enseñar", "estudiar", "explica", "explicame", "explícame", "curso", "clase",
        "examen", "parcial", "resumen de estudio", "concepto", "teoria", "teoría", "guia de estudio",
        "ejercicio", "matematica", "fisica", "historia", "logica", "lógica", "machine learning", "ia"
    ],
    "Crear y comunicar": [
        "escribir", "redacta", "redactar", "post", "instagram", "linkedin", "correo", "email",
        "carta", "guion", "guión", "video", "copy", "anuncio", "publicidad", "articulo", "artículo",
        "historia", "cuento", "discurso", "mensaje", "slogan", "marca"
    ],
    "Trabajo y productividad": [
        "negocio", "empresa", "ventas", "cliente", "estrategia", "proyecto", "reunion", "reunión",
        "agenda", "cronograma", "kpi", "proceso", "cv", "curriculum", "entrevista", "presupuesto",
        "inventario", "stock", "vencimientos", "comercio", "factura", "proveedor", "marketing", "productividad"
    ],
    "Investigar y analizar": [
        "analizar", "analiza", "comparar", "compara", "ventajas", "desventajas", "pros y contras",
        "investigar", "datos", "estadistica", "estadística", "tendencia", "diagnostico", "diagnóstico",
        "evaluar", "evalua", "evalúa", "informe", "reporte", "sintetizar", "resumir"
    ],
    "Vida personal y organización": [
        "viaje", "itinerario", "receta", "cocina", "rutina", "entrenamiento", "gimnasio", "dieta",
        "ahorro", "finanzas personales", "habito", "hábito", "organizar", "evento", "casa", "compra", "regalo"
    ]
}

CATEGORY_ROLES = {
    "Aprender y enseñar": "Actúa como un pedagogo senior y especialista en diseño instruccional, experto en transformar temas complejos en explicaciones claras, progresivas y memorables.",
    "Crear y comunicar": "Actúa como un estratega de contenidos y copywriter senior, especializado en comunicación persuasiva, narrativa clara y adaptación de tono según la audiencia.",
    "Trabajo y productividad": "Actúa como un consultor senior de operaciones, estrategia y productividad, enfocado en soluciones ejecutivas, prácticas y orientadas a resultados medibles.",
    "Tecnología y programación": "Actúa como un arquitecto de software senior y desarrollador full-stack, experto en código limpio, buenas prácticas, seguridad y optimización de rendimiento.",
    "Investigar y analizar": "Actúa como un analista senior de investigación y ciencia de datos, especializado en pensamiento crítico, rigor metodológico y síntesis estructurada.",
    "Vida personal y organización": "Actúa como un coach experto en organización personal y planificación práctica, enfocado en planes realistas, accionables y fáciles de seguir.",
    "Otro / No sé": "Actúa como un especialista multidisciplinario senior, experto en analizar requerimientos y entregar soluciones estructuradas, precisas y de alta calidad."
}

INTENT_PATTERNS = {
    "depurar_error": {
        "keywords": ["error", "bug", "falla", "no funciona", "arreglar", "corregir", "depurar", "debug", "excepcion", "traceback"],
        "instructions": [
            "Identifica la causa raíz del problema técnico o lógico presentado.",
            "Explica brevemente por qué ocurre el fallo en lenguaje claro.",
            "Proporciona la solución corregida lista para implementar y señala cómo prevenirlo a futuro."
        ]
    },
    "generar_codigo": {
        "keywords": ["codigo", "código", "script", "funcion", "función", "programa", "consulta sql", "query", "api", "componente", "clase"],
        "instructions": [
            "Escribe código limpio, modular, bien indentado y siguiendo las mejores prácticas del lenguaje.",
            "Incluye comentarios breves únicamente en las partes críticas de la lógica.",
            "Contempla el manejo básico de errores y casos borde (edge cases).",
            "Añade un breve ejemplo de uso o ejecución al finalizar."
        ]
    },
    "comparar_evaluar": {
        "keywords": ["comparar", "compara", "diferencia", "vs", "contra", "mejor opcion", "pros y contras", "ventajas", "evaluar"],
        "instructions": [
            "Define criterios objetivos y relevantes para realizar la comparación.",
            "Analiza las fortalezas, debilidades y casos de uso ideales de cada alternativa.",
            "Concluye con una recomendación clara según distintos escenarios."
        ]
    },
    "resumir_sintetizar": {
        "keywords": ["resumir", "resume", "resumen", "sintetizar", "sintetiza", "puntos clave", "ideas principales", "extraer"],
        "instructions": [
            "Extrae únicamente las ideas centrales, datos críticos y conclusiones principales sin perder precisión.",
            "Elimina redundancias, ejemplos accesorios y relleno.",
            "Jerarquiza la información de lo más importante a lo secundario."
        ]
    },
    "planificar_pasos": {
        "keywords": ["plan", "ruta", "paso a paso", "cronograma", "guia", "guía", "estrategia", "como hacer", "cómo hacer", "itinerario", "rutina", "controlar"],
        "instructions": [
            "Divide el objetivo en fases o etapas secuenciales y lógicas.",
            "Detalla acciones concretas, herramientas o recursos necesarios en cada paso.",
            "Incluye recomendaciones prácticas para evitar los errores más comunes."
        ]
    },
    "redactar_contenido": {
        "keywords": ["redacta", "redactar", "escribe", "escribir", "correo", "email", "post", "mensaje", "carta", "guion", "anuncio", "copy", "respuesta"],
        "instructions": [
            "Capta la atención desde la primera línea con un gancho claro y relevante.",
            "Desarrolla el mensaje manteniendo coherencia, fluidez y orientación a la acción.",
            "Asegura que el vocabulario y el registro encajen perfectamente con el público destinatario."
        ]
    },
    "explicar_concepto": {
        "keywords": ["explica", "explicame", "explícame", "que es", "qué es", "como funciona", "cómo funciona", "enseñar", "aprender", "concepto"],
        "instructions": [
            "Comienza con una definición clara y directa antes de entrar en detalles técnicos.",
            "Utiliza analogías cotidianas y ejemplos prácticos para facilitar la comprensión.",
            "Avanza de forma progresiva desde los fundamentos hasta los aspectos más avanzados."
        ]
    }
}

INFINITIVE_MAP = [
    (r'^(por favor[,\s]+)?(armame|ármame|hazme|creame|créame|generame|genérame|genera)\s+', 'Elaborar '),
    (r'^(por favor[,\s]+)?(redactame|redáctame|redacta|escribime|escribe)\s+', 'Redactar '),
    (r'^(por favor[,\s]+)?(explicame|explícame|explica|enseñame|enséñame)\s+', 'Explicar '),
    (r'^(por favor[,\s]+)?(analizame|analízame|analiza)\s+', 'Analizar '),
    (r'^(por favor[,\s]+)?(comparame|compárame|compara)\s+', 'Comparar '),
    (r'^(por favor[,\s]+)?(resumime|resúmeme|resume)\s+', 'Resumir '),
    (r'^(por favor[,\s]+)?(dime|necesito que me hagas|necesito|quiero que me hagas|quiero|ayudame a)\s+', '')
]

def _normalize(text):
    return ''.join(
        c for c in unicodedata.normalize('NFD', text.lower())
        if unicodedata.category(c) != 'Mn'
    )

def _extract_raw_objective(text):
    # Si el usuario presiona "Mejorar" sobre un prompt ya estructurado, extraer el bloque # Objetivo
    match = re.search(r'# Objetivo(?: Principal)?\s*\n+(.+?)(?=\n+# |\Z)', text, flags=re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()

def _infer_category(text):
    norm_text = _normalize(text)
    scores = {cat: 0 for cat in CATEGORY_KEYWORDS}
    for cat, words in CATEGORY_KEYWORDS.items():
        for w in words:
            if re.search(r'\b' + re.escape(_normalize(w)) + r'\b', norm_text):
                scores[cat] += 1
    best_cat = max(scores, key=scores.get)
    return best_cat if scores[best_cat] > 0 else "Otro / No sé"

def _infer_intent(text):
    norm_text = _normalize(text)
    for intent, data in INTENT_PATTERNS.items():
        for kw in data["keywords"]:
            if re.search(r'\b' + re.escape(_normalize(kw)) + r'\b', norm_text):
                return intent, data["instructions"]
    return "general", [
        "Analiza el objetivo planteado y desarrolla una respuesta completa, estructurada y directa al punto.",
        "Adapta la profundidad y el vocabulario al contexto especificado.",
        "Incluye ejemplos concretos o pasos accionables que faciliten su aplicación inmediata."
    ]

def _extract_implicit_modifiers(text):
    norm_text = _normalize(text)
    detected = {}

    if "tabla" in norm_text or "cuadro comparativo" in norm_text:
        detected["format"] = "Tabla comparativa estructurada en Markdown"
    elif "json" in norm_text:
        detected["format"] = "Objeto JSON válido y bien estructurado"
    elif "lista" in norm_text or "viñetas" in norm_text or "bullets" in norm_text:
        detected["format"] = "Lista organizada con viñetas y encabezados claros"
    elif "paso a paso" in norm_text:
        detected["format"] = "Guía numerada paso a paso"

    if any(k in norm_text for k in ["desde cero", "principiante", "principiantes", "basico", "sencillo", "facil"]):
        detected["audience"] = "Principiantes sin conocimientos previos (explicación clara y accesible)"
    elif any(k in norm_text for k in ["niños", "infantil", "primaria"]):
        detected["audience"] = "Público infantil / escolar (lenguaje ameno, visual y con ejemplos simples)"
    elif any(k in norm_text for k in ["avanzado", "experto", "senior", "tecnico"]):
        detected["audience"] = "Nivel avanzado / profesional (rigor técnico y profundidad)"

    if any(k in norm_text for k in ["breve", "corto", "resumido", "en pocas palabras"]):
        detected["length"] = "Respuesta concisa y directa al grano (sin rodeos)"
    elif any(k in norm_text for k in ["extenso", "detallado", "completo", "profundo"]):
        detected["length"] = "Desarrollo exhaustivo y detallado"

    if "en ingles" in norm_text:
        detected["language"] = "Inglés"
    elif "en portugues" in norm_text:
        detected["language"] = "Portugués"

    needs_placeholder = False
    placeholder_label = "DATOS / TEXTO DE REFERENCIA"
    code_refs = ["este codigo", "mi codigo", "el codigo", "este script", "mi script", "el script", "esta consulta", "mi consulta", "esta funcion", "mi funcion"]
    text_refs = ["este texto", "mi texto", "el siguiente texto", "este articulo", "este documento", "este pdf", "este parrafo"]
    data_refs = ["estos datos", "mis datos", "esta tabla", "este csv", "mi cv", "este correo", "mi correo", "este mensaje"]

    if any(k in norm_text for k in code_refs):
        needs_placeholder = True
        placeholder_label = "CÓDIGO FUENTE"
    elif any(k in norm_text for k in text_refs):
        needs_placeholder = True
        placeholder_label = "TEXTO A PROCESAR"
    elif any(k in norm_text for k in data_refs):
        needs_placeholder = True
        placeholder_label = "INFORMACIÓN / DATOS DE ENTRADA"

    return detected, needs_placeholder, placeholder_label

def _clean_light(text):
    cleaned = text.strip()
    for pattern, replacement in INFINITIVE_MAP:
        new_cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
        if new_cleaned != cleaned:
            cleaned = new_cleaned
            break
    if cleaned:
        cleaned = cleaned[0].upper() + cleaned[1:]
    if cleaned and cleaned[-1] not in '.!?':
        cleaned += '.'
    return cleaned

def get_gemini_response(user_text, category, form_data, level):
    raw_text = _extract_raw_objective(user_text)
    if len(raw_text) < 3:
        return {"error": "Por favor, describe tu idea con al menos unas palabras para poder estructurarla."}

    form_data = form_data or {}
    analysis = []

    if raw_text != user_text.strip():
        analysis.append("Se detectó un prompt ya estructurado y se re-optimizó su objetivo base sin duplicar bloques.")

    # 1. Resolver Categoría
    is_explicit_cat = category and category not in ["Ninguna especificada", "Otro / No sé", ""]
    if is_explicit_cat and category in CATEGORY_ROLES:
        cat_key = category
        analysis.append(f"Se aplicó el enfoque especializado de la categoría '{cat_key}'.")
    else:
        cat_key = _infer_category(raw_text)
        if cat_key != "Otro / No sé":
            analysis.append(f"Se detectó automáticamente el dominio '{cat_key}' a partir de tu solicitud.")
        else:
            analysis.append("Se aplicó una estructura universal adaptable a múltiples dominios.")

    # 2. Resolver Rol (prioridad absoluta al Asistente Guiado)
    role_text = form_data.get("Rol que debe asumir la IA")
    if role_text:
        role_block = f"Actúa como un {role_text} con amplia experiencia práctica y dominio del sector."
        analysis.append(f"Se configuró el rol específico elegido en el asistente: '{role_text}'.")
    else:
        role_block = CATEGORY_ROLES[cat_key]

    # 3. Inferir intención y modificadores implícitos
    intent_name, intent_instructions = _infer_intent(raw_text)
    implicit_mods, needs_placeholder, placeholder_label = _extract_implicit_modifiers(raw_text)

    if intent_name != "general":
        analysis.append(f"Se identificó la intención principal ({intent_name.replace('_', ' ')}) para generar instrucciones a medida.")

    # 4. Combinar parámetros del Asistente Guiado (prioridad) + Modificadores implícitos
    extra_params = []
    formato_salida = None
    tono_estilo = None

    for k, v in form_data.items():
        if not v:
            continue
        if "Formato" in k:
            formato_salida = v
            analysis.append(f"Se aplicó el formato elegido en el asistente: '{v}'.")
        elif "Tono" in k or "Estilo" in k:
            tono_estilo = v
        elif k != "Rol que debe asumir la IA":
            extra_params.append(f"- **{k}:** {v}")

    if not formato_salida and "format" in implicit_mods:
        formato_salida = implicit_mods["format"]
        analysis.append(f"Se extrajo el formato solicitado directamente de tu texto: '{formato_salida}'.")

    if "audience" in implicit_mods and not any("Nivel" in p or "Público" in p for p in extra_params):
        extra_params.append(f"- **Audiencia / Nivel:** {implicit_mods['audience']}")
        analysis.append("Se detectó el nivel de audiencia implícito en la redacción.")

    if "length" in implicit_mods and not any("Longitud" in p for p in extra_params):
        extra_params.append(f"- **Extensión esperada:** {implicit_mods['length']}")

    if "language" in implicit_mods:
        extra_params.append(f"- **Idioma de salida:** {implicit_mods['language']}")
        analysis.append(f"Se configuró el idioma de respuesta a {implicit_mods['language']}.")

    if extra_params:
        analysis.append(f"Se integraron {len(extra_params)} parámetro(s) de contexto para acotar la respuesta.")

    # NIVEL 1: MEJORA LIGERA
    if level == "Ligera":
        improved = _clean_light(raw_text)
        extras = []
        if tono_estilo:
            extras.append(f"Mantén un tono {tono_estilo.lower()}.")
        if formato_salida:
            extras.append(f"Formato de entrega: {formato_salida}.")
        if "language" in implicit_mods:
            extras.append(f"Responde en {implicit_mods['language']}.")
        if extras:
            improved = f"{improved} {' '.join(extras)}"
        if needs_placeholder:
            improved += f"\n\n[{placeholder_label}: PEGA AQUÍ EL CONTENIDO]"
            analysis.append("Se añadió un marcador de posición para que pegues el material de referencia.")

        analysis.append("Se depuró la redacción manteniendo la estructura directa (Mejora Ligera).")
        return {"improved_prompt": improved, "analysis": analysis}

    objetivo = _clean_light(raw_text)
    contexto_lines = [f"- **Dominio:** {cat_key}"]
    contexto_lines.extend(extra_params)
    if tono_estilo:
        contexto_lines.append(f"- **Tono y estilo:** {tono_estilo}")

    formato_block = (
        f"- Presenta la salida utilizando estrictamente el formato: **{formato_salida}**.\n"
        "- Usa jerarquía visual clara (encabezados y viñetas) para facilitar su lectura."
        if formato_salida else
        "- Estructura la respuesta con encabezados Markdown claros, listas con viñetas y conclusiones accionables."
    )

    instructions_block = "\n".join([f"{i+1}. {inst}" for i, inst in enumerate(intent_instructions)])
    placeholder_block = f"\n\n# Material de Entrada\n```\n[PEGA AQUÍ TU {placeholder_label}]\n```" if needs_placeholder else ""
    if needs_placeholder:
        analysis.append(f"Se incluyó un bloque preparado para insertar tu {placeholder_label.lower()}.")

    # NIVEL 2: MEJORA COMPLETA
    if level == "Completa":
        improved = (
            f"# Rol\n{role_block}\n\n"
            f"# Objetivo\n{objetivo}\n\n"
            f"# Contexto y Parámetros\n" + "\n".join(contexto_lines) + "\n\n"
            f"# Instrucciones\n{instructions_block}\n\n"
            f"# Formato de Salida\n{formato_block}"
            f"{placeholder_block}"
        )
        analysis.append("Se estructuró la solicitud en bloques estándar de Ingeniería de Prompts (Rol, Objetivo, Contexto, Instrucciones y Formato).")
        return {"improved_prompt": improved, "analysis": analysis}

    # NIVEL 3: MEJORA PROFUNDA
    improved = (
        f"# Rol\n{role_block}\n\n"
        f"# Objetivo Principal\n{objetivo}\n\n"
        f"# Contexto y Parámetros\n" + "\n".join(contexto_lines) + "\n\n"
        f"# Instrucciones Específicas\n{instructions_block}\n\n"
        f"# Metodología de Razonamiento (Paso a Paso)\n"
        f"1. **Comprensión:** Identifica los requisitos explícitos e implícitos antes de redactar.\n"
        f"2. **Estructuración:** Organiza los argumentos o pasos de forma lógica y progresiva.\n"
        f"3. **Validación:** Verifica que cada punto aporte valor práctico y cumpla con el formato exigido.\n\n"
        f"# Restricciones y Calidad\n"
        f"- Evita generalidades, introducciones innecesarias o relleno.\n"
        f"- Si algún dato admite múltiples interpretaciones, aclara brevemente el criterio asumido.\n"
        f"- Mantén rigor y consistencia terminológica en toda la respuesta.\n\n"
        f"# Formato de Salida\n{formato_block}"
        f"{placeholder_block}"
    )

    analysis.append("Se aplicó arquitectura avanzada con instrucciones específicas de tarea, Chain-of-Thought y reglas de control de calidad.")
    if not form_data and len(implicit_mods) == 0:
        analysis.append("Tip: Si deseas mayor precisión, puedes especificar formato o público en el Asistente Guiado de la derecha.")

    return {"improved_prompt": improved, "analysis": analysis}
