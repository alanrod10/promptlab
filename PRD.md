# Product Requirements Document (PRD) — PromptLab v8.0.2

**Versión de interfaz:** `v8.0` (`v8.0.2` pestaña didáctica Glosario IA + `v8.0.1` blindaje de seguridad y rigor científico) · **Arquitectura NLP:** `Motor Universal v7.2` (Caja Blanca determinístico) + `Capa Híbrida Científica, Seguridad y Gestión de Prompts v8.0.2` (100 % Offline)  
**Contexto académico:** Proyecto de tesis — Tecnicatura Superior en Ciencia de Datos e Inteligencia Artificial (IES N° 11).

---

## 1. Visión del Producto

Construir una plataforma web local e institucional de Ingeniería de Prompts que elimine la fricción y la ambigüedad en la comunicación humano-IA sin depender de servicios en la nube, APIs externas ni librerías pesadas de ML. **PromptLab v8.0.2** combina un motor heurístico determinístico auditado (`v7.2`) con una capa verificable de Ciencia de Datos en **Python puro** (*Multinomial Naive Bayes* sobre los 21 arquetipos, validación cruzada estratificada 5-Fold balanceada + CV repetida 10×5, IC 95 % de Wilson, test exacto de McNemar y capa incremental supervisada *Human-in-the-Loop*), junto a herramientas de versionado, intercambio seguro `.JSON`, endurecimiento de seguridad en producción y un **Glosario IA** didáctico 100 % offline.

---

## 2. Público Objetivo (Casos de Uso Principales)

* **Estudiantes y Docentes (Estudio y Academia):** Planes de estudio por días, autoevaluaciones tipo parcial, resúmenes jerárquicos sin invención de datos y colecciones curriculares portables en `.JSON`.
* **Data Scientists y Desarrolladores (Tecnología y Ciencia de Datos e IA):** Scripts reproducibles sin librerías externas, consultas SQL con `JOIN`, depuración de errores, checklists de EDA y evaluación transparente con Matriz de Confusión 5-Fold y auditoría caso por caso.
* **Comerciantes y Emprendedores (Negocios y Comercio):** Cálculo de punto de equilibrio y escenarios, control de stock/ventas y negociación comercial con proveedores.
* **Gestión Pública, Docencia y Comunicación:** Notas oficiales, minutas y comunicaciones institucionales con anonimización verificada de datos personales argentinos y resguardo automático de numeración AFIP y montos monetarios.

---

## 3. Especificaciones Funcionales (`v7.3` + `v8.0` + `v8.0.1` + `v8.0.2`)

### 3.1 Espacio de Trabajo Inteligente (`/`)
* **3 Modos de Profundidad Unificados:**
  * **Express:** salida breve y directa para consultas cotidianas sin sobrecarga visual.
  * **Guiado:** estructura por secciones + **Asistente Guiado** con preguntas dinámicas (*Smart Slots*) y reglas rápidas en 1 clic que suman puntos reales.
  * **Estudio Pro:** máximo detalle con casos borde, validaciones previas, restricciones negativas, ejemplos *few-shot*, chips editables de detección en vivo y **Mapa de Origen (Caja Blanca)** (*De dónde sale cada frase*).
* **Ejemplos Rápidos Auto-Ocultables (4 casos):** 4 chips breves sobre el editor (ventas/Excel, análisis CSV, punto de equilibrio y nota oficial con resguardo PII/AFIP y desglose de nota formal) que se pliegan automáticamente al escribir o cargar un prompt.
* **Diagnóstico en Vivo:** inferencia en tiempo real (`/api/analyze-live/`, debounce 350 ms, protección CSRF real y tope de `15.000` caracteres) de dominio, acción, entregable, contradicciones e insumos pegados.
* **Protección de Privacidad y Sello Verificado (sincronizado Python + `workspace.js`):**
  * Detección y enmascaramiento de DNI, CUIL/CUIT con guiones, CUIT de 11 dígitos sin guiones validado por **Módulo 11 oficial**, teléfonos fijos, celulares con `15`, correos electrónicos, CBU (22 dígitos) y alias bancarios (etiquetados o en prosa con punto).
  * Exclusión verificada de facturas AFIP (`XXXX-XXXXXXXX`) y cifras monetarias (`$`, `pesos`, `usd`, `presupuesto`, `gastos`, `monto`, `precio`, `importe`, `cuota`).
  * `mask_pii=True` por defecto en `/api/improve/`, cubriendo también `form_data`, ejemplo de referencia, tema y restricciones negativas; sello `.pl-privacy-seal` y resaltado inline `.pl-fmt-pii-mask`.
* **Estimación Heurística Orientativa Offline de Tokens (ChatGPT · Gemini · Claude):** estimación heurística local para español (**100 % offline sin APIs ni tokenizadores externos**) sobre ventanas referenciales de **128K** (ChatGPT), **1M** (Gemini) y **200K** (Claude), acompañada de ayuda pedagógica (*"1 token ≈ ¾ de palabra; un prompt sin relleno consume menos y responde mejor."*) y enlace directo al Glosario (`/glosario/#token`).
* **Versionado Iterativo (`v1 → v2 → v3`) y Guardado como Plantilla:** permite iterar sobre cualquier salida (`/?load=<id>&iterate=1`), registrar nota de cambio (`version_note`), enlazar `parent_prompt` y `root_prompt`, y convertir el prompt estructurado en plantilla propia reutilizable.

### 3.2 Catálogo de Plantillas y Mis Plantillas (`/plantillas/`)
* **18 Plantillas Oficiales Curadas en 6 Categorías:** intactas y validadas por `PromptLabTemplatesCatalogTests`, con modo recomendado, micro-tip *"Por qué funciona:"* y marcadores `[corchetes]`.
* **Mis Plantillas Guardadas (`UserTemplate`):** creables desde el Workspace o desde `/plantillas/propias/crear/`, con borrado seguro en 2 pasos (`/plantillas/propias/eliminar/<id>/`) y carga inteligente en Workspace (`/?user_tpl=<id>`).
* **Portabilidad Offline `.JSON` (`promptlab-collection-v1`):** exportación vía `GET /plantillas/propias/exportar-json/` e importación vía `POST /plantillas/propias/importar-json/` con tope de `512 KB`, validación estricta UTF-8/esquema, deduplicación por contenido y escaneo automático de privacidad respetando comprobantes AFIP.

### 3.3 Mi Historial (`/historial/`) y Favoritos (`/favoritos/`)
* Persistencia automática por usuario, filtrado instantáneo por búsqueda, área, modo y estilo de respuesta.
* Badges de versión `vN`, nota de cambio, **línea de tiempo comparativa** de la familia (`root_prompt`) con variación de puntaje entre iteraciones, promoción atómica de nueva raíz al eliminar `v1` y botones `Nueva versión` / `Cargar`.

### 3.4 Estadísticas, Evaluación Científica y Capa Supervisada (`/analitica/`)
* **5 gráficos SVG interactivos nativos** (`analytics_charts.js`, cero Chart.js ni CDNs) reactivos al tema (`themeChanged`) y barra segmentada 100 % de calidad.
* **Bloque de Evaluación Científica:** evalúa `60` casos curados (`10` de `21` arquetipos, similitud máxima Jaccard intra-clase `0,278 < 0,35`), completamente aislado de SQLite y Overlay:
  * **Baseline v7.2 vs. Híbrido v8.0** en 5-Fold balanceado (`12×5`, `seed=42`): Exactitud **`86,7 % → 93,3 %`**, Macro F1 y Weighted F1 **`89,8 % → 94,2 %`**, **`4/8`** errores totales rescatados (**`50,0 %`**), **`4/5`** de baja certeza rescatados (**`80,0 %`**), **`0`** regresiones (`56/60` en diagonal).
  * **Rigor estadístico en Python puro:** IC 95 % de Wilson (`[75,8 %; 93,1 %]` → `[84,1 %; 97,4 %]`), CV Repetida **10×5** (`91,8 % ± 0,9 pp`, rango `90,0 %–93,3 %`; Macro F1 `93,0 % ± 0,7 pp`), Test exacto de McNemar (`p = 0,1250`), recuadro de **Alcance y límites declarados** y acordeón desplegable de **Auditoría caso por caso**.
* **Capa Incremental Supervisada (*Human-in-the-Loop*, Overlay):** descubrimiento local *Log-Odds* + aprobación/reversión en `ActiveLearningRule` exclusiva para cuentas administradoras (`is_staff=True`) con bloqueo anti-PII y caché TTL 10 s, sin mutar `knowledge_base.json`.

### 3.5 Glosario IA Didáctico 100 % Offline (`/glosario/`)
* **Catálogo curado de 18 conceptos en 4 categorías (`core/glossary_data.py`):** *Lo básico para empezar* (`5`), *Cómo pedir mejor* (`6`), *Límites y cuidados* (`4`) y *Cómo funciona por dentro* (`3`).
* **Estructura pedagógica por tarjeta:** explicación breve (*En pocas palabras*), *Analogía cotidiana*, *Ejemplo práctico* y pie *Dónde lo ves en PromptLab* conectado por `reverse()` a la pestaña real donde se aplica.
* **Interacción client-side (`glossary.js`):** búsqueda instantánea sin tildes ni mayúsculas, chips de categoría con contadores, filtro por nivel (`Inicial` / `Intermedio`), estado vacío con botón `Limpiar filtros` y scroll/resaltado accesible por `location.hash`.

### 3.6 Modo Invitado y Cuenta Opcional Privada (`/ingresar/`, `/registro/`, `/salir/`)
* **Modo Invitado:** espacio compartido de demostración (`invitado_demo`, con contraseña inutilizable para impedir login directo). No aplica ni comparte refuerzos aprendidos por corrección entre sesiones.
* **Cuenta registrada:** espacio privado estrictamente aislado en historial, favoritos, plantillas propias, estadísticas, refuerzos aprendidos por usuario (`user_corrected`) y exportación `.CSV` de 38 columnas (con neutralización anti-fórmulas).

---

## 4. Especificaciones del Motor y Capa Científica (`v7.2` + `v8.0.1`)

* **Núcleo Determinístico (`ENGINE_VERSION = "v7.2"`):** 21 arquetipos cognitivos, inspector estructural de insumos, cálculo exacto sin `eval` (`Decimal`/`Fraction`), extracción fiel de entidades, normalización de relleno en `# Objetivo` y Linter Anti-Relleno verificando líneas reales sin contar numeración de listas.
* **Clasificador Probabilístico en Python Puro (`core/scientific_eval.py`):** `MultinomialNaiveBayesClassifier` con tokenización en español (conservando siglas técnicas `ia`, `ml`, `bi`, `cv`, `tp`, `db`, `bd`, `ui`, `ux`), unigramas + bigramas, suavizado de Laplace ($\alpha = 1.0$) y `log-sum-exp`. En producción se entrena sobre los **`21/21` arquetipos** (`126` prototipos de `knowledge_base.json` + `60` casos de referencia, sin inyectar reglas de SQLite).

---

## 5. Modelo de Datos, Despliegue y Calidad

* **Modelos y Migraciones (`0001`–`0009`):** `Prompt` (telemetría NLP + `parent_prompt`, `root_prompt`, `version_number`, `version_note`), `ActiveLearningRule` (`0008`) y `UserTemplate` (`0009`).
* **Seguridad de producción (`promptlab/settings.py`, `requirements.txt`):** variables de entorno (`DJANGO_SECRET_KEY`, `PYTHONANYWHERE_DOMAIN`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`), cabeceras y cookies HTTPS cuando `not DEBUG`, `STATIC_ROOT`, `LOGGING` a consola y `requirements.txt` limpio (`Django==6.1.3`, `asgiref==3.13.0`, `sqlparse==0.6.1`).
* **Sistema Visual WCAG AA (`?v=8.0.2`):** contraste WCAG AA verificado en Modo Oscuro (`--pl-accent: #8f88ff`) y Modo Claro, adaptabilidad para proyector `1280×720` (6 enlaces de navegación + tarjeta de cuenta + tema + estado) y móvil `390px`.
* **Validación Automatizada:** **93 tests en verde** distribuidos en **16 suites** en `core/tests.py` + comando CLI `./venv/bin/python manage.py evaluate_engine`.

---

## 6. Hoja de Ruta v9.0 (Escala Institucional)

1. **Base de datos PostgreSQL opcional multi-sede** conservando SQLite cero-configuración por defecto.
2. **Muestra externa (*hold-out* independiente) sobre los 21/21 arquetipos** curada con casos reales anonimizados de terceros.
3. **Roles institucionales** (*Docente / Cátedra / Estudiante / Equipo*) con espacios curados compartidos.
4. **Paquetes curriculares firmados en `.JSON`** con verificación de integridad para distribuir consignas y reglas overlay aprobadas.
5. **Evaluación ciega A/B de salidas reales** y exportación analítica extendida (`.JSONL`).
