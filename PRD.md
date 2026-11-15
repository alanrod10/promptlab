# Product Requirements Document (PRD) - PromptLab v6.0

## 1. Visión del Producto
Construir una herramienta local de Ingeniería de Prompts que elimine la fricción y la ambigüedad en la comunicación humano-IA. PromptLab transforma ideas vagas o no estructuradas en instrucciones algorítmicas de altísima precisión (quirúrgicas), evaluando su calidad en tiempo real y garantizando la privacidad de la información del usuario (cero conexión a la nube).

## 2. Público Objetivo (Usuarios de Casos de Uso)
*   **Estudiantes y Docentes (Academia):** Para generar guías de estudio, resúmenes y comparaciones libres de sesgos y relleno.
*   **Data Scientists y Desarrolladores:** Para depurar código, generar scripts reproducibles y analizar datasets de forma estandarizada.
*   **Comerciantes y Emprendedores (Negocios):** Para calcular márgenes, diseñar rutinas operativas (ventas/vencimientos) y redactar comunicaciones formales o comerciales.

## 3. Especificaciones Funcionales (Core v6.0)
*   **Diagnóstico en Vivo (*Active Learning*):** Interfaz que infiere Dominio, Acción y Entregable mientras el usuario tipea (debounce 350ms). Si el usuario corrige una inferencia, el sistema lo registra como aprendizaje activo.
*   **Asistente Guiado Basado en Ganancia de Puntos:** En lugar de formularios estáticos, el sistema propone 2 a 3 preguntas de desambiguación dinámicas ("Slots de alto impacto") que elevan el puntaje de la rúbrica si son respondidas.
*   **Explicabilidad Visual (Caja Blanca):** Pestaña de trazabilidad que colorea el texto resultante según su origen (Texto del usuario, Inferencia del motor, Estructura agregada) para auditar el funcionamiento determinístico.

## 4. Especificaciones del Motor Heurístico (Backend)
*   **Reescritura Determinística:** Capacidad de extraer el "Verbo Nuclear" y los "Roles Semánticos" de oraciones coloquiales, limpiando modismos y elevando el registro lingüístico sin perder fidelidad (`fidelity_recall == 1.0`).
*   **Cálculo Seguro Integrado:** Módulo sin comandos `eval`, que detecta parámetros financieros (gastos, márgenes) e inyecta valores de control exactos como criterio de validación para la IA de destino.
*   **Linter Anti-Relleno:** Post-procesador que poda cualquier bloque generado que no posea un ancla contextual o un criterio de éxito verificable. 

## 5. Ciencia de Datos y Telemetría
*   **Rúbrica No Circular v2:** Separación estricta entre el puntaje de la idea original (`user_score`) y los puntos sumados por interacción (`information_gain`) para obtener el `final_score`.
*   **Exportación de Dataset CSV (38 Columnas):** Sistema de recolección de metadatos de uso que exporta instantáneamente un CSV estructurado con variables categóricas, continuas y binarias para análisis correlacional de calidad de prompts.
*   **Minería Estadística Offline:** Módulo de agrupamiento mediante función *Log-Odds* para descubrir patrones y temas de la "cola larga" que presentan baja confianza, facilitando su eventual promoción como nuevas reglas.
