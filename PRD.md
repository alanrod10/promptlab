# Product Requirements Document (PRD) — PromptLab v7.2.4

**Versión de interfaz:** `v7.2.4` · **Motor NLP:** `Motor Universal v7.2` (100 % Offline)  
**Contexto académico:** Proyecto de tesis — Tecnicatura Superior en Ciencia de Datos e Inteligencia Artificial (IES N° 11).

---

## 1. Visión del Producto

Construir una plataforma web local de Ingeniería de Prompts que elimine la fricción y la ambigüedad en la comunicación humano-IA sin depender de servicios en la nube ni APIs externas. PromptLab transforma ideas cotidianas o incompletas en instrucciones estructuradas de alta precisión (*Cero Relleno*), evaluando su calidad de forma transparente y protegiendo la privacidad de los datos del usuario en todo momento.

---

## 2. Público Objetivo (Casos de Uso Principales)

* **Estudiantes y Docentes (Estudio y Academia):** Planes de estudio por días, autoevaluaciones tipo parcial y resúmenes jerárquicos sin invención de datos.
* **Data Scientists y Desarrolladores (Tecnología y Ciencia de Datos e IA):** Scripts reproducibles sin librerías externas, consultas SQL con `JOIN`, depuración de errores, checklists de EDA con Pandas y comparativas técnicas.
* **Comerciantes y Emprendedores (Negocios y Comercio):** Cálculo de punto de equilibrio y escenarios, control de stock y vencimientos, y negociación comercial con proveedores.
* **Comunicación y Carrera Profesional:** Guiones breves para video vertical, reescritura de borradores con ajuste de tono, reclamos formales documentados, adaptación de CV y simulaciones de entrevistas.

---

## 3. Especificaciones Funcionales (v7.2.4)

### 3.1 Espacio de Trabajo Progresivo (`/`)
* **3 Modos de Profundidad Unificados:**
  * **Express:** salida breve y directa para resolver consultas cotidianas sin sobrecarga visual.
  * **Guiado:** estructura por secciones + **Asistente Guiado** con preguntas dinámicas (*Smart Slots*) y reglas rápidas en 1 clic que suman puntos reales.
  * **Estudio Pro:** máximo detalle con casos borde, validaciones previas, restricciones negativas, ejemplos *few-shot*, chips editables de detección en vivo y **Mapa de Origen (Caja Blanca)** (*De dónde sale cada frase*).
* **Diagnóstico en Vivo (*Active Learning*):** inferencia en tiempo real (`/api/analyze-live/`, debounce 350 ms) de dominio, acción, entregable, contradicciones e insumos pegados. Las correcciones del usuario se registran como señales de aprendizaje activo local en SQLite.
* **Protección de Privacidad (PII Argentino):** detección y enmascaramiento sincronizado (backend Python + frontend JS) de DNI/CUIL/CUIT, teléfonos, correos, CBU y alias bancarios, excluyendo falsos positivos en números de facturas AFIP (`XXXX-XXXXXXXX`).

### 3.2 Catálogo Didáctico de Plantillas (`/plantillas/`)
* **18 plantillas curadas en 6 categorías** (3 por categoría), cada una con modo recomendado, micro-tip educativo (*"Por qué funciona:"*) y placeholders resaltados entre `[corchetes]`.
* Guía visual de uso en 3 pasos, búsqueda y filtrado instantáneo 100 % *client-side* (`templates_gallery.js`), copia rápida y carga directa en el Espacio de Trabajo con activación automática del modo sugerido y aviso descartable.

### 3.3 Mi Historial (`/historial/`) y Favoritos (`/favoritos/`)
* Persistencia automática de todos los prompts generados, filtrado local por texto, área, modo (`Express`, `Guiado`, `Estudio Pro`) y estilo de respuesta.
* Etiquetas legibles en lenguaje natural (sin claves técnicas ni nombres internos), badges de calidad y privacidad, confirmación inline de borrado y reapertura en el Espacio de Trabajo (`/?load=<id>`).

### 3.4 Estadísticas y Datos (`/analitica/`)
* Dashboard **100 % offline** con **5 gráficos SVG interactivos nativos** (`analytics_charts.js`, sin Chart.js ni CDNs) que responden al cambio de tema (`themeChanged`):
  1. Barras horizontales con eje numérico por área temática.
  2. Dona interactiva con conmutador entre *Estilos de respuesta* y *Modos de profundidad*.
  3. Líneas con área sombreada (*Evolución: Antes vs. Después*).
  4. Barras verticales agrupadas por técnica o modo.
  5. Barras verticales agrupadas por tipo de tarea.
* Barra segmentada 100 % de distribución de calidad, 4 KPIs con ayuda contextual, filtros por período (`?periodo=all|30d|7d`), estados vacíos diferenciados (sin historial vs. período sin actividad) y recomendaciones automáticas deterministas (*"Qué podés aprovechar mejor"*).

---

## 4. Especificaciones del Motor Heurístico (`v7.2`)

* **Arquitectura de 2 carriles y 21 arquetipos cognitivos:** clasificación híbrida (reglas + TF-IDF + léxico + gramática de roles) soportada por `core/rules/knowledge_base.json`, `core/services.py` y `core/universal_engine.py`.
* **Reescritura determinística y fidelidad:** extracción de verbo nuclear y roles semánticos preservando entidades, nombres de archivo, trazas de error y restricciones negativas del usuario sin inventar contenido.
* **Inspector estructural de insumos y cálculo exacto:** reconocimiento de listas, tablas, código, trazas y cláusulas pegadas; cálculo determinístico sin `eval` (con `Decimal`/`Fraction`) para escenarios financieros y punto de equilibrio.
* **Linter Anti-Relleno:** garantiza cobertura de *Datos útiles* ≥ 90 % y *Texto de relleno* < 10 %, eliminando frases genéricas vacías.

---

## 5. Ciencia de Datos, Telemetría y Coherencia de Producto

* **Rúbrica No Circular v2:** mide por separado el puntaje de la idea original, el aporte interactivo del usuario y el puntaje estructural final (0–100) sobre 5 criterios objetivos.
* **Exportación `.CSV` de 38 columnas (`/analitica/exportar-csv/`):** dataset tabular UTF-8 listo para análisis exploratorio y modelado en Python/Pandas/Scikit-Learn.
* **Minería Estadística Offline (*Log-Odds*):** detección local de términos y bigramas recurrentes en consultas difíciles para ampliar reglas sin conexión.
* **Sistema visual y de lenguaje unificado (`v7.2.4`):** tokens CSS `--pl-*` compatibles con Modo Oscuro y Modo Claro, cache-busting `?v=7.2.4`, voseo consistente en la interfaz, español neutro en los prompts compilados y validación automática mediante **64 tests en verde** (`core/tests.py`).
