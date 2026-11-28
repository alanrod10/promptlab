# Product Requirements Document (PRD) — PromptLab v8.0

**Versión de interfaz:** `v8.0` · **Arquitectura NLP:** `Motor Universal v7.2` (Caja Blanca determinístico) + `Capa Híbrida Científica y Gestión de Prompts v8.0` (100 % Offline)  
**Contexto académico:** Proyecto de tesis — Tecnicatura Superior en Ciencia de Datos e Inteligencia Artificial (IES N° 11).

---

## 1. Visión del Producto

Construir una plataforma web local e institucional de Ingeniería de Prompts que elimine la fricción y la ambigüedad en la comunicación humano-IA sin depender de servicios en la nube, APIs externas ni librerías pesadas de ML. **PromptLab v8.0** combina un motor heurístico determinístico auditado (`v7.2`) con una capa verificable de Ciencia de Datos en **Python puro** (*Multinomial Naive Bayes*, validación cruzada estratificada 5-Fold y *Active Learning* reversible) más herramientas sistemáticas de versionado e intercambio seguro offline de colecciones de plantillas.

---

## 2. Público Objetivo (Casos de Uso Principales)

* **Estudiantes y Docentes (Estudio y Academia):** Planes de estudio por días, autoevaluaciones tipo parcial, resúmenes jerárquicos sin invención de datos y colecciones curriculares portables en `.JSON`.
* **Data Scientists y Desarrolladores (Tecnología y Ciencia de Datos e IA):** Scripts reproducibles sin librerías externas, consultas SQL con `JOIN`, depuración de errores, checklists de EDA y validación objetiva con Matriz de Confusión 5-Fold.
* **Comerciantes y Emprendedores (Negocios y Comercio):** Cálculo de punto de equilibrio y escenarios, control de stock/ventas y negociación comercial con proveedores.
* **Gestión Pública, Docencia y Comunicación:** Notas oficiales, minutas y comunicaciones institucionales con anonimización verificada de datos personales argentinos y resguardo automático de numeración AFIP.

---

## 3. Especificaciones Funcionales (v7.3 + v8.0)

### 3.1 Espacio de Trabajo Inteligente (`/`)
* **3 Modos de Profundidad Unificados:**
  * **Express:** salida breve y directa para consultas cotidianas sin sobrecarga visual.
  * **Guiado:** estructura por secciones + **Asistente Guiado** con preguntas dinámicas (*Smart Slots*) y reglas rápidas en 1 clic que suman puntos reales.
  * **Estudio Pro:** máximo detalle con casos borde, validaciones previas, restricciones negativas, ejemplos *few-shot*, chips editables de detección en vivo y **Mapa de Origen (Caja Blanca)** (*De dónde sale cada frase*).
* **Ejemplos Rápidos Auto-Ocultables (4 casos):** 4 chips breves sobre el editor (ventas/Excel, análisis CSV, punto de equilibrio y nota oficial con resguardo PII/AFIP) que se pliegan automáticamente al escribir o cargar un prompt.
* **Diagnóstico en Vivo:** inferencia en tiempo real (`/api/analyze-live/`, debounce 350 ms) de dominio, acción, entregable, contradicciones e insumos pegados.
* **Protección de Privacidad y Sello Verificado:** detección y enmascaramiento sincronizado (Python + `workspace.js`) de DNI/CUIL/CUIT, teléfonos, correos, CBU y alias bancarios, excluyendo facturas AFIP (`XXXX-XXXXXXXX`), con sello `.pl-privacy-seal` en la salida y resaltado inline `.pl-fmt-pii-mask`.
* **Estimador Comparativo Offline de Tokens (ChatGPT · Gemini · Claude):** calibrado localmente para español (±10 % sin APIs ni tokenizadores externos) combinando conteo de palabras, longitud de prosa, tildes/`ñ`, símbolos, saltos de línea y bloques de código para estimar uso sobre ventanas de **128K** (ChatGPT), **1M** (Gemini) y **200K** (Claude), acompañado de ayuda pedagógica (*"1 token ≈ ¾ de palabra; un prompt sin relleno consume menos y responde mejor."*).
* **Versionado Iterativo (`v1 → v2 → v3`) y Guardado como Plantilla:** permite iterar sobre cualquier salida (`/?load=<id>&iterate=1`), registrar nota de cambio (`version_note`), enlazar `parent_prompt` y `root_prompt`, y convertir el prompt estructurado en plantilla propia reutilizable.

### 3.2 Catálogo de Plantillas y Mis Plantillas (`/plantillas/`)
* **18 Plantillas Oficiales Curadas en 6 Categorías:** intactas y validadas por `PromptLabTemplatesCatalogTests`, con modo recomendado, micro-tip *"Por qué funciona:"* y marcadores `[corchetes]`.
* **Mis Plantillas Guardadas (`UserTemplate`):** aisladas por usuario activo (`_get_active_user`), creables desde el Workspace o desde `/plantillas/propias/crear/`, con borrado seguro en 2 pasos (`/plantillas/propias/eliminar/<id>/`) y carga inteligente en Workspace (`/?user_tpl=<id>`).
* **Portabilidad Offline `.JSON` (`promptlab-collection-v1`):**
  * Exportación vía `GET /plantillas/propias/exportar-json/`.
  * Importación vía `POST /plantillas/propias/importar-json/` con tope de `512 KB`, validación estricta UTF-8/esquema, deduplicación por cuerpo/título y escaneo automático de privacidad (`detect_and_mask_pii`) preservando comprobantes AFIP.

### 3.3 Mi Historial (`/historial/`) y Favoritos (`/favoritos/`)
* Persistencia automática aislada por usuario/sesión, filtrado instantáneo por búsqueda, área, modo y estilo de respuesta.
* Badges de versión `vN`, nota de cambio y **línea de tiempo comparativa** de la familia (`root_prompt`) con variación de puntaje entre iteraciones y botones `Nueva versión` / `Cargar`.

### 3.4 Estadísticas, Evaluación Científica y Overlay (`/analitica/`)
* **5 gráficos SVG interactivos nativos** (`analytics_charts.js`, cero Chart.js ni CDNs) reactivos al tema (`themeChanged`) y barra segmentada 100 % de calidad.
* **Bloque de Evaluación Científica 5-Fold:** ejecuta el benchmark reproducible sobre 60 casos (`core/rules/benchmark_dataset.json`) comparando **Solo Reglas vs. Híbrido v8.0** (*Exactitud*, *Macro F1*, *Weighted F1*, casos rescatados, regresiones y **Matriz de Confusión 10 × 10** WCAG AA/AAA).
* **Capa de Aprendizaje Activo Reversible (*Overlay*):** permite aprobar términos candidatos descubiertos por *Log-Odds* (`POST /analitica/aprendizaje/aprobar/`) y activarlos/revertirlos (`POST /analitica/aprendizaje/revertir/<id>/`) en SQLite (`ActiveLearningRule`) sin mutar `knowledge_base.json`.

### 3.5 Cuenta Opcional Multiusuario (`/ingresar/`, `/registro/`, `/salir/`)
* Uso inmediato sin registro previo en modo **Invitado** con aislamiento por clave de sesión.
* Registro e inicio de sesión opcionales con migración automática de prompts y plantillas creados previamente como Invitado en la misma sesión.

---

## 4. Especificaciones del Motor y Capa Científica (`v7.2` + `v8.0`)

* **Núcleo Determinístico (`ENGINE_VERSION = "v7.2"`):** 21 arquetipos cognitivos, inspector estructural de insumos, cálculo exacto sin `eval` (`Decimal`/`Fraction`), extracción fiel de entidades y Linter Anti-Relleno (caché compilada de expresiones regulares por palabra/entidad para inferencia sub-milisegundo).
* **Clasificador Probabilístico en Python Puro (`core/scientific_eval.py`):** `MultinomialNaiveBayesClassifier` con tokenización en español, unigramas + bigramas, suavizado de Laplace ($\alpha = 1.0$) y normalización numéricamente estable `log-sum-exp` sin dependencias externas (`math`, `collections`, `re`, `json`).
* **Desempate Híbrido Conservador:** el clasificador Naive Bayes solo actúa ante empates o baja confianza heurística (o bajo umbral calibrado), elevando la exactitud del benchmark 5-Fold de **80,0 % (`48/60`) a 95,0 % (`57/60`)**, el **Macro F1 de 83,1 % a 95,5 %**, rescatando **9 de 11 errores** del motor base (**81,8 %**) con **0 regresiones** en **< 200 ms**.

---

## 5. Modelo de Datos, Rutas, Calidad y Despliegue

* **Modelos y Migraciones (`0001`–`0009`):**
  * `Prompt` (telemetría NLP, rúbrica v2 + `parent_prompt`, `root_prompt`, `version_number`, `version_note`).
  * `ActiveLearningRule` (capa overlay reversible auditada en `0008`).
  * `UserTemplate` (plantillas propias por usuario en `0009`).
* **19 rutas en `core/urls.py`:** incluyen vistas principales, APIs locales (`/api/improve/`, `/api/analyze-live/`), favoritos/historial, plantilla propia + colección JSON, evaluación/overlay, CSV de 38 columnas y autenticación opcional.
* **Sistema Visual WCAG AA/AAA (`?v=8.0`):** tokens `--pl-*` en `promptlab.css` para Modo Oscuro y Modo Claro, adaptabilidad verificada para proyector `1280×720` (sidebar sin recorte vertical y grilla de tokens balanceada) y móvil `390px`.
* **Validación Automatizada:** **83 tests en verde** distribuidos en **14 suites** en `core/tests.py` + comando CLI `./venv/bin/python manage.py evaluate_engine`.

---

## 6. Hoja de Ruta v9.0 (Escala Institucional)

1. **Base de datos PostgreSQL opcional multi-sede** conservando SQLite cero-configuración por defecto.
2. **Roles institucionales** (*Docente / Cátedra / Estudiante / Equipo*) con espacios curados compartidos.
3. **Paquetes curriculares firmados en `.JSON`** con verificación de integridad para distribuir consignas y reglas overlay aprobadas.
4. **Evaluación ciega A/B de salidas reales** para contrastar resultados entre prompts base y versiones iteradas `vN`.
5. **Exportación analítica extendida** (`.JSONL` / esquemas listos para cuadernos reproducibles de Ciencia de Datos).
