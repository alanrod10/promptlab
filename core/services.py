import re

CATEGORY_ROLES = {
    "Aprender y enseñar": "Actúa como un pedagogo senior y especialista en diseño instruccional, experto en explicar conceptos complejos de forma clara y progresiva.",
    "Crear y comunicar": "Actúa como un estratega de contenidos y copywriter senior, especializado en comunicación persuasiva y adaptación de tono según la audiencia.",
    "Trabajo y productividad": "Actúa como un consultor senior de operaciones y productividad empresarial, enfocado en eficiencia, claridad ejecutiva y resultados accionables.",
    "Tecnología y programación": "Actúa como un arquitecto de software senior y desarrollador full-stack, experto en buenas prácticas, código limpio y resolución de problemas técnicos.",
    "Investigar y analizar": "Actúa como un analista senior de investigación y ciencia de datos, especializado en pensamiento crítico, síntesis estructurada y rigor metodológico.",
    "Vida personal y organización": "Actúa como un coach de organización personal y planificación práctica, enfocado en soluciones realistas, claras y fáciles de ejecutar.",
    "Otro / No sé": "Actúa como un especialista multidisciplinario senior, experto en estructurar soluciones claras, precisas y orientadas a objetivos."
}

def _clean_light(text):
    cleaned = text.strip()
    # Eliminar inicios informales comunes para dar tono profesional
    cleaned = re.sub(r'^(por favor\s+)?(creame|créame|hazme|dime|necesito que me hagas|quiero que me hagas)\s+', '', cleaned, flags=re.IGNORECASE)
    if cleaned:
        cleaned = cleaned[0].upper() + cleaned[1:]
    if cleaned and cleaned[-1] not in '.!?':
        cleaned += '.'
    return cleaned

def get_gemini_response(user_text, category, form_data, level):
    clean_input = user_text.strip()
    if not clean_input:
        return {"error": "El texto de entrada está vacío."}

    form_data = form_data or {}
    analysis = []

    # Determinar categoría y rol
    cat_key = category if category in CATEGORY_ROLES else "Otro / No sé"
    role_text = form_data.get("Rol que debe asumir la IA")
    if role_text:
        role_block = f"Actúa como un {role_text} con amplia experiencia práctica en el área."
        analysis.append(f"Se asignó el rol explícito solicitado: '{role_text}'.")
    else:
        role_block = CATEGORY_ROLES[cat_key]
        if category and category != "Ninguna especificada":
            analysis.append(f"Se asignó un perfil experto alineado con la categoría '{category}'.")
        else:
            analysis.append("Se asignó un rol experto generalista al no especificarse una categoría.")

    # Extraer parámetros del asistente guiado
    extra_params = []
    formato_salida = None
    tono_estilo = None

    for k, v in form_data.items():
        if not v:
            continue
        if "Formato" in k:
            formato_salida = v
        elif "Tono" in k or "Estilo" in k:
            tono_estilo = v
        elif k != "Rol que debe asumir la IA":
            extra_params.append(f"- **{k}:** {v}")

    if extra_params:
        analysis.append(f"Se integraron {len(extra_params)} parámetro(s) personalizado(s) del Asistente Guiado.")

    # NIVEL 1: MEJORA LIGERA
    if level == "Ligera":
        improved = _clean_light(clean_input)
        extras = []
        if tono_estilo:
            extras.append(f"Utiliza un tono {tono_estilo.lower()}.")
        if formato_salida:
            extras.append(f"Presenta el resultado en formato: {formato_salida}.")
        if extras:
            improved = f"{improved} {' '.join(extras)}"
        
        analysis.append("Se optimizó la redacción y claridad directa manteniendo la estructura original (Mejora Ligera).")
        return {
            "improved_prompt": improved,
            "analysis": analysis
        }

    # Preparar bloques comunes para Completa y Profunda
    objetivo = _clean_light(clean_input)
    contexto_lines = []
    if category and category != "Ninguna especificada":
        contexto_lines.append(f"- **Área / Categoría:** {category}")
    contexto_lines.extend(extra_params)
    if tono_estilo:
        contexto_lines.append(f"- **Tono y estilo requerido:** {tono_estilo}")
    if not contexto_lines:
        contexto_lines.append("- **Contexto:** Solicitud general abierta; priorizar claridad, precisión y utilidad práctica.")

    formato_block = (
        f"- Estructura la respuesta utilizando el formato: **{formato_salida}**.\n"
        "- Emplea encabezados claros y viñetas para facilitar la lectura."
        if formato_salida else
        "- Organiza la salida con encabezados Markdown, listas con viñetas y un resumen accionable al final."
    )

    # NIVEL 2: MEJORA COMPLETA
    if level == "Completa":
        improved = (
            f"# Rol\n{role_block}\n\n"
            f"# Objetivo\n{objetivo}\n\n"
            f"# Contexto y Parámetros\n" + "\n".join(contexto_lines) + "\n\n"
            f"# Instrucciones\n"
            f"1. Analiza el objetivo planteado y desarrolla una respuesta completa, estructurada y directa al punto.\n"
            f"2. Adapta el vocabulario y la profundidad técnica según los parámetros definidos en el contexto.\n"
            f"3. Incluye ejemplos concretos o pasos accionables que faciliten su aplicación inmediata.\n\n"
            f"# Formato de Salida\n{formato_block}"
        )
        analysis.append("Se estructuró la idea en 5 bloques estándar (Rol, Objetivo, Contexto, Instrucciones y Formato).")
        if not formato_salida:
            analysis.append("Se añadió una estructura de salida recomendada para evitar respuestas desordenadas.")

        return {
            "improved_prompt": improved,
            "analysis": analysis
        }

    # NIVEL 3: MEJORA PROFUNDA
    improved = (
        f"# Rol\n{role_block}\n\n"
        f"# Objetivo Principal\n{objetivo}\n\n"
        f"# Contexto y Parámetros Específicos\n" + "\n".join(contexto_lines) + "\n\n"
        f"# Metodología de Razonamiento (Paso a Paso)\n"
        f"1. **Diagnóstico:** Identifica los conceptos clave y requisitos implícitos del objetivo.\n"
        f"2. **Estructuración:** Organiza la solución de lo general a lo particular, asegurando coherencia lógica.\n"
        f"3. **Desarrollo:** Desarrolla cada punto con rigor, incorporando ejemplos prácticos y casos de uso reales.\n"
        f"4. **Verificación:** Revisa que la respuesta cumpla con el tono y formato solicitados antes de finalizar.\n\n"
        f"# Restricciones y Reglas de Calidad\n"
        f"- Evita rellenos innecesarios, ambigüedades o generalidades superficiales.\n"
        f"- Si algún dato del contexto admite múltiples interpretaciones, explicita tus supuestos brevemente.\n"
        f"- Mantén consistencia terminológica en toda la respuesta.\n\n"
        f"# Formato de Salida\n{formato_block}"
    )

    analysis.append("Se aplicó ingeniería de prompts avanzada con cadena de razonamiento (Chain-of-Thought) y reglas de calidad.")
    if not form_data:
        analysis.append("Sugerencia: Puedes usar el Asistente Guiado a la derecha para definir público objetivo, tono o formato específico.")

    return {
        "improved_prompt": improved,
        "analysis": analysis
    }
