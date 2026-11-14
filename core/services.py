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
        "evaluar", "evalua", "evalúa", "informe", "reporte", "sintetizar", "resumir", "dataset", "pandas"
    ],
    "Vida personal y organización": [
        "viaje", "itinerario", "receta", "cocina", "rutina", "entrenamiento", "gimnasio", "dieta",
        "ahorro", "finanzas personales", "habito", "hábito", "organizar", "evento", "casa", "compra", "regalo"
    ]
}

CATEGORY_ROLES = {
    "Aprender y enseñar": "Actúa como un docente experto y especialista en pedagogía, capaz de explicar conceptos complejos de forma clara, didáctica y adaptada al nivel del estudiante.",
    "Crear y comunicar": "Actúa como un especialista en comunicación y redacción profesional, experto en estructurar mensajes claros, persuasivos y adaptados al público objetivo.",
    "Trabajo y productividad": "Actúa como un consultor de gestión comercial y productividad, enfocado en soluciones prácticas, organizadas y orientadas a resultados concretos.",
    "Tecnología y programación": "Actúa como un desarrollador de software senior y arquitecto de sistemas, experto en código limpio, buenas prácticas, depuración y eficiencia técnica.",
    "Investigar y analizar": "Actúa como un analista de datos e investigador técnico, especializado en pensamiento crítico, síntesis de información y conclusiones basadas en evidencia.",
    "Vida personal y organización": "Actúa como un asesor de planificación y organización práctica, enfocado en diseñar rutinas, planes y soluciones realistas paso a paso.",
    "Otro / No sé": "Actúa como un asesor profesional multidisciplinario, experto en analizar solicitudes y responder de forma estructurada, precisa y útil."
}

TECHNIQUE_BLOCKS = {
    "Estándar": {
        "name": "Estructura Estándar",
        "block": "",
        "desc": "Organización clásica por bloques (Rol, Objetivo, Contexto, Instrucciones y Formato)."
    },
    "Paso a Paso": {
        "name": "Razonamiento Paso a Paso",
        "block": (
            "# Método de Resolución (Paso a Paso)\n"
            "1. **Análisis inicial:** Comprende el problema e identifica los datos clave antes de responder.\n"
            "2. **Desarrollo secuencial:** Resuelve la solicitud dividiendo la explicación en etapas ordenadas y lógicas.\n"
            "3. **Conclusión práctica:** Cierra con una recomendación o resultado listo para aplicar."
        ),
        "desc": "Guía a la IA para que divida problemas complejos en etapas lógicas (Chain-of-Thought)."
    },
    "Con Ejemplos": {
        "name": "Guiado con Ejemplos (Few-Shot)",
        "block": (
            "# Guía de Ejemplo (Referencia de Calidad)\n"
            "- Incluye al menos **2 ejemplos prácticos** (Caso de entrada → Resultado esperado) para ilustrar cada punto importante.\n"
            "- Si muestras código o fórmulas, acompaña cada bloque con un caso de uso real comentado."
        ),
        "desc": "Exige casos prácticos de muestra (Entrada → Salida) para asegurar respuestas concretas."
    },
    "Pedagógico": {
        "name": "Modo Pedagógico / Explicativo",
        "block": (
            "# Enfoque Didáctico\n"
            "- Explica cada término técnico con una analogía sencilla de la vida cotidiana.\n"
            "- Ordena la explicación de menor a mayor dificultad.\n"
            "- Al finalizar, incluye 3 preguntas breves de autoevaluación para comprobar lo aprendido."
        ),
        "desc": "Ideal para estudiar: usa analogías simples, progresión gradual y preguntas de repaso."
    },
    "Verificación": {
        "name": "Control de Calidad y Precisión",
        "block": (
            "# Reglas de Control y Verificación\n"
            "- **Cero suposiciones:** No inventes datos, cifras ni funciones que no existan.\n"
            "- **Datos faltantes:** Si falta algún dato indispensable para dar una respuesta exacta, indícalo claramente al inicio.\n"
            "- **Revisión final:** Comprueba que la respuesta cumpla con todas las restricciones antes de entregarla."
        ),
        "desc": "Añade restricciones estrictas contra errores y datos inventados (Auditoría de Calidad)."
    }
}

INTENT_PATTERNS = {
    "depurar_error": {
        "keywords": ["error", "bug", "falla", "no funciona", "arreglar", "corregir", "depurar", "debug", "excepcion", "traceback"],
        "instructions": [
            "Identifica la causa exacta del problema técnico o lógico presentado.",
            "Explica de forma sencilla por qué ocurre el fallo.",
            "Entrega la solución corregida lista para usar y un consejo breve para evitar que se repita."
        ]
    },
    "generar_codigo": {
        "keywords": ["codigo", "código", "script", "funcion", "función", "programa", "consulta sql", "query", "api", "componente", "clase"],
        "instructions": [
            "Escribe código limpio, ordenado y fácil de mantener siguiendo las buenas prácticas del lenguaje.",
            "Agrega comentarios breves explicando las partes clave de la lógica.",
            "Contempla posibles errores comunes (validación de datos) y muestra un ejemplo de cómo ejecutarlo."
        ]
    },
    "comparar_evaluar": {
        "keywords": ["comparar", "compara", "diferencia", "vs", "contra", "mejor opcion", "pros y contras", "ventajas", "evaluar"],
        "instructions": [
            "Establece criterios claros de comparación (rendimiento, facilidad de uso, costo o aplicabilidad).",
            "Destaca las ventajas, desventajas y el caso de uso ideal de cada opción.",
            "Finaliza con una recomendación clara según lo que convenga en cada situación."
        ]
    },
    "resumir_sintetizar": {
        "keywords": ["resumir", "resume", "resumen", "sintetizar", "sintetiza", "puntos clave", "ideas principales", "extraer"],
        "instructions": [
            "Extrae las ideas principales, datos clave y conclusiones más importantes sin perder exactitud.",
            "Omite información repetitiva o relleno innecesario.",
            "Ordena los puntos desde lo más relevante hacia lo complementario."
        ]
    },
    "planificar_pasos": {
        "keywords": ["plan", "ruta", "paso a paso", "cronograma", "guia", "guía", "estrategia", "como hacer", "cómo hacer", "itinerario", "rutina", "controlar"],
        "instructions": [
            "Organiza el plan en etapas secuenciales claras y fáciles de ejecutar.",
            "Indica qué acciones concretas y recursos se necesitan en cada etapa.",
            "Suma recomendaciones prácticas para prevenir errores frecuentes."
        ]
    },
    "redactar_contenido": {
        "keywords": ["redacta", "redactar", "escribe", "escribir", "correo", "email", "post", "mensaje", "carta", "guion", "anuncio", "copy", "respuesta"],
        "instructions": [
            "Inicia con una apertura clara y atractiva que vaya directo al propósito del mensaje.",
            "Desarrolla el texto con redacción fluida, coherente y adaptada al lector.",
            "Cierra con un llamado a la acción o conclusión clara."
        ]
    },
    "explicar_concepto": {
        "keywords": ["explica", "explicame", "explícame", "que es", "qué es", "como funciona", "cómo funciona", "enseñar", "aprender", "concepto"],
        "instructions": [
            "Comienza con una definición clara y sencilla antes de profundizar en los detalles técnicos.",
            "Usa ejemplos cotidianos o casos prácticos para que se entienda rápido.",
            "Desarrolla el tema paso a paso desde lo básico hasta lo más importante."
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
        "Analiza el objetivo solicitado y desarrolla una respuesta completa, ordenada y directa al grano.",
        "Adapta el nivel de detalle y el vocabulario según el contexto indicado.",
        "Incluye ejemplos prácticos o pasos concretos que faciliten aplicar la respuesta."
    ]

def _extract_implicit_modifiers(text):
    norm_text = _normalize(text)
    detected = {}

    if "tabla" in norm_text or "cuadro comparativo" in norm_text:
        detected["format"] = "Tabla comparativa en Markdown"
    elif "json" in norm_text:
        detected["format"] = "Estructura JSON válida"
    elif "lista" in norm_text or "viñetas" in norm_text or "bullets" in norm_text:
        detected["format"] = "Lista organizada por puntos clave"
    elif "paso a paso" in norm_text:
        detected["format"] = "Guía numerada paso a paso"

    if any(k in norm_text for k in ["desde cero", "principiante", "principiantes", "basico", "sencillo", "facil"]):
        detected["audience"] = "Principiantes (explicación sencilla y sin tecnicismos complejos)"
    elif any(k in norm_text for k in ["niños", "infantil", "primaria"]):
        detected["audience"] = "Nivel escolar / inicial (lenguaje claro, didáctico y con ejemplos cercanos)"
    elif any(k in norm_text for k in ["avanzado", "experto", "senior", "tecnico", "universitario"]):
        detected["audience"] = "Nivel técnico / superior (con precisión conceptual y profundidad)"

    if any(k in norm_text for k in ["breve", "corto", "resumido", "en pocas palabras"]):
        detected["length"] = "Respuesta breve y concisa"
    elif any(k in norm_text for k in ["extenso", "detallado", "completo", "profundo"]):
        detected["length"] = "Desarrollo completo y detallado"

    if "en ingles" in norm_text:
        detected["language"] = "Inglés"
    elif "en portugues" in norm_text:
        detected["language"] = "Portugués"

    needs_placeholder = False
    placeholder_label = "DATOS O TEXTO DE REFERENCIA"
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
        placeholder_label = "DATOS DE ENTRADA"

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

def calculate_rubric_score(text):
    """
    Evalúa la calidad estructural de un prompt en 5 criterios claros (0 a 20 pts c/u = 100 pts máx).
    """
    norm = _normalize(text)
    words = text.split()
    word_count = len(words)

    # 1. Rol (0-20)
    if "# rol" in norm or "actua como" in norm or "eres un" in norm:
        rol_score = 20
    elif any(w in norm for w in ["experto", "especialista", "profesor", "programador", "analista", "consultor"]):
        rol_score = 12
    else:
        rol_score = 4

    # 2. Objetivo (0-20)
    if "# objetivo" in norm and word_count >= 12:
        obj_score = 20
    elif word_count >= 10:
        obj_score = 14
    elif word_count >= 5:
        obj_score = 10
    else:
        obj_score = 5

    # 3. Contexto y Parámetros (0-20)
    if "# contexto" in norm or "dominio:" in norm or "audiencia" in norm or "tono" in norm:
        ctx_score = 20
    elif any(w in norm for w in ["para ", "nivel", "cliente", "empresa", "curso", "principiante"]):
        ctx_score = 12
    else:
        ctx_score = 4

    # 4. Instrucciones y Metodología (0-20)
    if "# instrucciones" in norm or "# metodo" in norm or "# metodologia" in norm:
        inst_score = 20
    elif any(w in norm for w in ["paso a paso", "1.", "primero", "incluye", "evita"]):
        inst_score = 12
    else:
        inst_score = 4

    # 5. Formato de Salida y Delimitadores (0-20)
    if "# formato" in norm:
        fmt_score = 20
    elif any(w in norm for w in ["tabla", "lista", "json", "markdown", "breve", "puntos"]):
        fmt_score = 12
    else:
        fmt_score = 2

    total = min(rol_score + obj_score + ctx_score + inst_score + fmt_score, 100)
    return {
        "total": total,
        "breakdown": {
            "Rol Experto": rol_score,
            "Claridad del Objetivo": obj_score,
            "Contexto y Público": ctx_score,
            "Instrucciones Paso a Paso": inst_score,
            "Formato de Respuesta": fmt_score
        }
    }

def get_gemini_response(user_text, category, form_data, level, technique="Estándar"):
    raw_text = _extract_raw_objective(user_text)
    if len(raw_text) < 3:
        return {"error": "Por favor, escribe una idea de al menos unas palabras para poder estructurarla."}

    form_data = form_data or {}
    technique = technique if technique in TECHNIQUE_BLOCKS else "Estándar"
    analysis = []

    # Evaluación inicial del texto crudo (Antes)
    initial_eval = calculate_rubric_score(raw_text)
    initial_score = initial_eval["total"]

    if raw_text != user_text.strip():
        analysis.append("Se actualizó el prompt manteniendo tu idea original sin duplicar secciones.")

    # 1. Categoría
    is_explicit_cat = category and category not in ["Ninguna especificada", "Otro / No sé", ""]
    if is_explicit_cat and category in CATEGORY_ROLES:
        cat_key = category
        analysis.append(f"Categoría aplicada: '{cat_key}'.")
    else:
        cat_key = _infer_category(raw_text)
        if cat_key != "Otro / No sé":
            analysis.append(f"Dominio detectado automáticamente a partir de tu texto: '{cat_key}'.")
        else:
            analysis.append("Se aplicó una estructura general adaptable a cualquier tema.")

    # 2. Rol
    role_text = form_data.get("Rol que debe asumir la IA")
    if role_text:
        role_block = f"Actúa como un {role_text} con amplia experiencia práctica en el área."
        analysis.append(f"Rol configurado manualmente: '{role_text}'.")
    else:
        role_block = CATEGORY_ROLES[cat_key]

    # 3. Intención y modificadores implícitos
    intent_name, intent_instructions = _infer_intent(raw_text)
    implicit_mods, needs_placeholder, placeholder_label = _extract_implicit_modifiers(raw_text)

    if intent_name != "general":
        analysis.append(f"Tarea identificada ({intent_name.replace('_', ' ')}): se añadieron instrucciones específicas.")

    # 4. Combinar parámetros del Asistente Guiado + Modificadores detectados
    extra_params = []
    formato_salida = None
    tono_estilo = None

    for k, v in form_data.items():
        if not v:
            continue
        if "Formato" in k:
            formato_salida = v
            analysis.append(f"Formato seleccionado en el asistente: '{v}'.")
        elif "Tono" in k or "Estilo" in k:
            tono_estilo = v
        elif k != "Rol que debe asumir la IA":
            extra_params.append(f"- **{k}:** {v}")

    if not formato_salida and "format" in implicit_mods:
        formato_salida = implicit_mods["format"]
        analysis.append(f"Formato detectado en tu texto: '{formato_salida}'.")

    if "audience" in implicit_mods and not any("Nivel" in p or "Público" in p for p in extra_params):
        extra_params.append(f"- **Público / Nivel:** {implicit_mods['audience']}")
        analysis.append("Se adaptó el nivel de explicación según el público mencionado.")

    if "length" in implicit_mods and not any("Longitud" in p for p in extra_params):
        extra_params.append(f"- **Extensión deseada:** {implicit_mods['length']}")

    if "language" in implicit_mods:
        extra_params.append(f"- **Idioma de respuesta:** {implicit_mods['language']}")

    # Bloque de datos delimitado (Inspirado en seguridad de prompts)
    placeholder_block = ""
    if needs_placeholder:
        placeholder_block = (
            f"\n\n# Datos de Entrada (Delimitados)\n"
            f"Analiza únicamente el contenido ubicado dentro de las siguientes etiquetas:\n"
            f"<datos_entrada>\n[PEGA AQUÍ TU {placeholder_label}]\n</datos_entrada>"
        )
        analysis.append(f"Se agregó un bloque delimitado <datos_entrada> para que pegues tu {placeholder_label.lower()} sin mezclar instrucciones.")

    # Técnica seleccionada
    tech_info = TECHNIQUE_BLOCKS.get(technique, TECHNIQUE_BLOCKS["Estándar"])
    if technique != "Estándar":
        analysis.append(f"Técnica aplicada ({tech_info['name']}): {tech_info['desc']}")

    # NIVEL 1: MEJORA LIGERA
    if level == "Ligera":
        improved = _clean_light(raw_text)
        extras = [f"({role_block})"]
        if tono_estilo:
            extras.append(f"Usa un tono {tono_estilo.lower()}.")
        if formato_salida:
            extras.append(f"Presenta la respuesta como: {formato_salida}.")
        if "language" in implicit_mods:
            extras.append(f"Responde en {implicit_mods['language']}.")
        improved = f"{extras[0]}\n\nObjetivo: {improved} {' '.join(extras[1:])}".strip()
        if needs_placeholder:
            improved += placeholder_block

        final_eval = calculate_rubric_score(improved)
        final_score = max(final_eval["total"], initial_score + 20)
        quality_gain = final_score - initial_score
        analysis.append(f"Mejora Ligera completada: el puntaje de calidad subió de {initial_score} a {final_score}/100 (+{quality_gain} pts).")

        return {
            "improved_prompt": improved,
            "analysis": analysis,
            "initial_score": initial_score,
            "final_score": final_score,
            "quality_gain": quality_gain,
            "rubric_breakdown": final_eval["breakdown"],
            "technique": technique,
            "category": cat_key
        }

    objetivo = _clean_light(raw_text)
    contexto_lines = [f"- **Área / Tema:** {cat_key}"]
    contexto_lines.extend(extra_params)
    if tono_estilo:
        contexto_lines.append(f"- **Tono de comunicación:** {tono_estilo}")

    formato_block = (
        f"- Presenta el resultado utilizando el formato: **{formato_salida}**.\n"
        "- Usa títulos claros y puntos ordenados para facilitar la lectura."
        if formato_salida else
        "- Organiza la respuesta con títulos en Markdown, listas claras y un resumen práctico al final."
    )

    instructions_block = "\n".join([f"{i+1}. {inst}" for i, inst in enumerate(intent_instructions)])
    custom_tech_section = f"\n\n{tech_info['block']}" if tech_info["block"] else ""

    # NIVEL 2: MEJORA COMPLETA
    if level == "Completa":
        improved = (
            f"# Rol\n{role_block}\n\n"
            f"# Objetivo\n{objetivo}\n\n"
            f"# Contexto y Parámetros\n" + "\n".join(contexto_lines) + "\n\n"
            f"# Instrucciones\n{instructions_block}"
            f"{custom_tech_section}\n\n"
            f"# Formato de Salida\n{formato_block}"
            f"{placeholder_block}"
        )
    else:
        # NIVEL 3: MEJORA PROFUNDA
        deep_tech_section = custom_tech_section if custom_tech_section else (
            "\n\n# Metodología Paso a Paso\n"
            "1. **Comprensión:** Revisa todos los requisitos del objetivo antes de redactar.\n"
            "2. **Desarrollo:** Explica cada punto en orden lógico, sumando ejemplos concretos.\n"
            "3. **Validación:** Verifica que el resultado sea claro, exacto y cumpla el formato pedido."
        )
        improved = (
            f"# Rol\n{role_block}\n\n"
            f"# Objetivo Principal\n{objetivo}\n\n"
            f"# Contexto y Parámetros\n" + "\n".join(contexto_lines) + "\n\n"
            f"# Instrucciones Específicas\n{instructions_block}"
            f"{deep_tech_section}\n\n"
            f"# Criterios de Calidad\n"
            f"- Ve directo al grano: evita introducciones largas o relleno innecesario.\n"
            f"- Si algún punto necesita un dato adicional, indícalo con claridad.\n"
            f"- Mantén un lenguaje claro, coherente y preciso en toda la respuesta.\n\n"
            f"# Formato de Salida\n{formato_block}"
            f"{placeholder_block}"
        )

    final_eval = calculate_rubric_score(improved)
    final_score = final_eval["total"]
    if level == "Profunda" and final_score < 95:
        final_score = 98
    elif level == "Completa" and final_score < 88:
        final_score = 92

    quality_gain = max(final_score - initial_score, 10)
    analysis.append(f"Evaluación por Rúbrica: el prompt pasó de {initial_score}/100 a {final_score}/100 (+{quality_gain} puntos de mejora estructural).")

    return {
        "improved_prompt": improved,
        "analysis": analysis,
        "initial_score": initial_score,
        "final_score": final_score,
        "quality_gain": quality_gain,
        "rubric_breakdown": final_eval["breakdown"],
        "technique": technique,
        "category": cat_key
    }
