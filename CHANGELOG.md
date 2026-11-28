# Changelog — PromptLab

Todas las mejoras relevantes de **PromptLab** se documentan en este archivo.

---

## [v8.0.3] — Auditoría Editorial Final, Voseo Unificado y Sistema de Tooltips Accesibles (96 tests)

- **Auditoría editorial integral (`core/rules/knowledge_base.json`, `core/glossary_data.py`, `core/scientific_eval.py`, `core/views.py`, `analytics.html`, `base.html`):**
  - Unificadas a voseo argentino las 12 preguntas restantes en tuteo dentro de `slot_catalog` (`buscás`, `necesitás`, `preferís`, `tenés`, `contás`, `querés`, `comparás`).
  - Afinadas las referencias de `in_promptlab` en `core/glossary_data.py` para reflejar los nombres exactos de botones, secciones y técnicas de la interfaz.
  - Unificados los decimales visibles en `verdict_text` y `mcnemar_p_display` a coma decimal en español (`0,1250`, `50,0 %`, `80,0 %`) y reemplazados `prompt(s)` / `registro(s)` por pluralización natural sin alterar los valores numéricos ni el comando `evaluate_engine`.
  - Actualizado el atributo `title` del cartel `Motor Híbrido v8.0 • 100% Offline` en `base.html` para describir el motor determinístico + desempate probabilístico Naive Bayes offline.
- **Componente global de tooltips accesibles (`core/static/js/tooltips.js`, `core/static/css/promptlab.css`, `base.html`):**
  - Implementado módulo liviano 100 % nativo sin Popper ni CDNs (`role="tooltip"`, cero `innerHTML`), activable por *hover*, foco de teclado (`Tab`), toque móvil y cierre con `Escape`, con *clamping* automático al viewport (`1280×720` y `390px`) y contraste WCAG AA en Modo Oscuro y Modo Claro.
  - Incorporados tooltips `.pl-tip` / `.pl-tip-icon` sobre siglas y conceptos clave en `analytics.html` (`NLP`, `5-Fold`, `12×5`, `CV repetida 10×5`, `pp`, `Exactitud`, `F1 Macro`, `F1 Ponderado`, `Recall`, `IC 95 %`, `McNemar`, `NB 21/21`, `Jaccard`, `out-of-fold`, `arquetipos`, `Capa Overlay`, `Roles resueltos`, `Criterios verificables`, `Relevancia`, `Dataset (.CSV)` + puente `/glosario/#validacion-cruzada`), `workspace.html` (modos, `128K`/`1M`/`200K`, `.MD`/`.JSON`, `vN`, `AFIP`, `[corchetes]`), `templates_gallery.html` (`.JSON`, `[corchetes]`), `history.html` (`vN`, `Ver evolución`) y `glossary.html` (ancla `#` con copia de enlace y feedback).
- **Cache-busting, tests y documentación (`?v=8.0.3`, `core/tests.py`):**
  - Actualizado *cache-busting* a `?v=8.0.3` e incorporada la suite **`PromptLabV803EditorialAndTooltipsTests` (3 tests)** alcanzando **96 tests en verde** en **17 suites**, con `makemigrations --check --dry-run` sin cambios pendientes.

---

## [v8.0.2] — Nueva pestaña didáctica Glosario IA (18 conceptos offline) (93 tests)

- **Catálogo curado y vista read-only (`core/glossary_data.py`, `core/views.py`, `core/urls.py`):**
  - Incorporado `GLOSSARY_CATALOG` con **18 conceptos curados** en voseo argentino claro distribuidos en **4 categorías**: *Lo básico para empezar* (5), *Cómo pedir mejor* (6), *Límites y cuidados* (4) y *Cómo funciona por dentro* (3).
  - Agregada la ruta `GET /glosario/` (`name="glossary"`, total **20 rutas** en `core/urls.py`) y la vista `glossary_view` con conteos por categoría, URLs relacionadas validadas y contexto estándar de cuenta (`_get_active_user_info`).
- **Interfaz, filtrado client-side y puente contextual (`glossary.html`, `glossary.js`, `base.html`, `workspace.html`, `promptlab.css`):**
  - Agregado el enlace **Glosario IA** con ícono SVG de libro abierto y `aria-current="page"` en el sidebar de escritorio y en el menú móvil, ajustando la media query de proyector (`1280×720`) para alojar cómodamente los 6 enlaces de navegación, tarjeta de cuenta, selector de tema y estado sin cortes.
  - Creada la vista `glossary.html` y el script `glossary.js` (100 % *client-side*, cero CDNs, sin `innerHTML`) con buscador instantáneo insensible a tildes/mayúsculas, chips de categoría con contadores, filtro por nivel (`Inicial` / `Intermedio`), estado vacío con botón **`Limpiar filtros`** y resaltado accesible (`.pl-glossary-highlight`) al navegar con hash (`#token`, `#alucinacion`, `#datos-sensibles-pii`, etc.).
  - Agregado el enlace puente `¿Qué es un token? Ver Glosario →` (`/glosario/#token`) en la tarjeta **Consumo estimado al copiar a una IA** del Espacio de Trabajo y unificado el *cache-busting* a **`?v=8.0.2`** en `base.html`, `workspace.html`, `templates_gallery.html`, `analytics.html`, `glossary.html` y `core/tests.py`.
- **Tests y documentación (`core/tests.py`, `README.md`, `PRD.md`, `CHANGELOG.md`):**
  - Actualizada `PromptLabSiteCoherenceTests` para cubrir `/glosario/` y `?v=8.0.2`, e incorporada la suite **`PromptLabV802GlossaryTests` (3 tests)** alcanzando **93 tests en verde** en **16 suites**, sin cambios de modelos ni migraciones (`No changes detected`).

---

## [v8.0.1] — Blindaje de Seguridad, Privacidad PII, Rigor Científico 10×5 y Sincronización Documental (90 tests)

- **Seguridad de producción y limpieza de dependencias (`promptlab/settings.py`, `requirements.txt`):**
  - Configuración por variables de entorno (`DJANGO_SECRET_KEY`, `PYTHONANYWHERE_DOMAIN`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`), cookies/cabeceras HTTPS cuando `not DEBUG`, `STATIC_ROOT`, `LOGGING` a consola y eliminación de `MAILERS`.
  - `requirements.txt` depurado a únicamente `Django==6.1.3`, `asgiref==3.13.0`, `sqlparse==0.6.1` y `tzdata` en Windows (0 paquetes residuales de APIs/gRPC).
- **Autorización en Capa Overlay, invitado seguro y CSRF real (`core/views.py`, `core/templates/core/analytics.html`, `workspace.js`, `base.html`, `login.html`, `register.html`):**
  - `approve_learning_rule` y `toggle_learning_rule` restringidas exclusivamente a cuentas administradoras (`request.user.is_staff`, HTTP `403` si no cumple) con bloqueo anti-PII en términos candidatos y manejo seguro de `IntegrityError`.
  - Eliminado el fallback a `User.objects.order_by("id").first()` y la contraseña `"123"`: el modo invitado utiliza un usuario centinela compartido (`invitado_demo`) con `set_unusable_password()` y nombre reservado bloqueado en `/registro/`.
  - Eliminado `@csrf_exempt` de `/api/improve/` y `/api/analyze-live/`, agregado `@ensure_csrf_cookie` en `workspace`, envíos con `X-CSRFToken` desde JS, tope de `15.000` caracteres, captura segura de excepciones con `logger.exception`, `mask_pii=True` por defecto, neutralización de fórmulas en `.CSV` (`_sanitize_csv_cell`) y promoción atómica de nueva raíz al borrar `v1`.
  - Fallback `execCommand('copy')` + manejo de errores al copiar en Workspace e Historial, reemplazo seguro `() => html` en Markdown inline y `try/catch` en `localStorage`.
- **Endurecimiento PII argentino (Python + JS) y fixes de motor (`core/services.py`, `knowledge_base.json`):**
  - Exclusión de cifras monetarias (`$`, `pesos`, `usd`, `presupuesto`, `gastos`, `monto`, `precio`, `cuotas`), detección de CUIT de 11 dígitos sin guiones validado por **Módulo 11 oficial**, alias bancario en prosa con punto, celulares argentinos con `15`, y protección secundaria sobre `form_data`, `user_example`, `topic_anchor`, `roles` y `neg_constraints` con `mask_pii=True`.
  - Separación de `nota_formal` respecto de `licencia` en `object_ontology` (eliminando *"Desglose de licencia"* en notas oficiales), precedencia corregida en `_light_stem`, protección de `# Objetivo` en `lint_prompt` y stripping de numeración `^\s*\d+\.\s*` al medir líneas ancladas.
- **Rigor científico del benchmark, NB 21 clases y auditoría en `/analitica/` (`core/rules/benchmark_dataset.json`, `core/scientific_eval.py`, `evaluate_engine.py`, `analytics.html`):**
  - Eliminados pares espejo en los 20 casos `borde` (`max_intra_class_jaccard = 0,278 < 0,35`), folds estratificados balanceados `12×5`, aislamiento total de SQLite/Overlay en el benchmark y caché por `user.id` en `_get_learned_correction_boosts` (cero refuerzos compartidos en `invitado_demo`).
  - `get_production_nb_classifier` ampliado a los **21/21 arquetipos** (`126` prototipos + `60` casos) conservando siglas técnicas de 2 letras (`ia`, `ml`, `cv`, etc.) y caché TTL de 10 s en `get_active_overlay_rules`.
  - Incorporados en Python puro: **CV Repetida 10×5** (`91,8 % ± 0,9 pp`, Macro F1 `93,0 % ± 0,7 pp`), **IC 95 % de Wilson**, **Test exacto de McNemar** (`p = 0,1250`), recuadro de **Alcance y límites declarados** y tabla auditable caso por caso en `/analitica/`.
  - Contraste WCAG AA reforzado (`--pl-accent: #8f88ff` en oscuro, badges de auditoría), texto honesto del estimador de tokens, limpieza de comentarios `<!-- compat: ... -->` y suites actualizadas alcanzando **90 tests en verde**.

---

## [v8.0] — Plataforma Híbrida Científica, Versionado vN, Portabilidad .JSON y Auditoría WCAG AA (83 tests)

### Fase 3 — Cierre Integral, WCAG AA, Proyector 1280×720 y Documentación Oficial
- **Auditoría visual y proyector `1280×720` (`promptlab.css`, `workspace.html`, `base.html`):**
  - Agregada ayuda didáctica no técnica en el estimador heurístico offline de tokens (*"1 token ≈ ¾ de palabra; un prompt sin relleno consume menos y responde mejor."*).
  - Reforzado contraste en `#cmp-efficiency-badge`, categorías de *Mis Plantillas*, alertas `.alert-*` en Modo Oscuro, envolvente limpia de los 4 chips `.pl-example-pill` y diseño responsivo de barra lateral y grilla de 3 modelos en `1280×720` y `390px`.
  - Actualizada la etiqueta del cartel del sidebar en [base.html](file:///mnt/c/Proyecto%20PromptLab/core/templates/core/base.html) a `Motor Híbrido v8.0 • 100% Offline`.
- **Cache-busting unificado a `?v=8.0`:** actualizado en `base.html`, `workspace.html`, `templates_gallery.html`, `analytics.html` y `PromptLabSiteCoherenceTests`.

### Fase 2 — Versionado Iterativo `v1 → v2 → v3`, Mis Plantillas Propias y Portabilidad `.JSON`
- **Modelos y migración única `0009` (`core/models.py`):** agregados `parent_prompt`, `root_prompt`, `version_number` y `version_note` en `Prompt`, y creado `UserTemplate`.
- **Versionado en Workspace e Historial (`workspace.html`, `workspace.js`, `history.html`, `views.py`):** badge `vN`, flujo `/?load=<id>&iterate=1` con nota de cambio, línea de tiempo comparativa y guardado rápido como plantilla propia desde cualquier resultado.
- **Mis Plantillas e intercambio offline `.JSON` (`templates_gallery.html`, `templates_gallery.js`, `views.py`, `urls.py`):** 4 rutas nuevas (`/plantillas/propias/crear/`, `/plantillas/propias/eliminar/<id>/`, `/plantillas/propias/exportar-json/`, `/plantillas/propias/importar-json/`), esquema `promptlab-collection-v1` (límite `512 KB`), deduplicación y sanitización automática de PII preservando facturas AFIP.
- **Tests:** incorporada `PromptLabV80VersioningAndCollectionsTests` (5 tests) alcanzando **83 tests en verde**.

### Fase 1 — Benchmark Científico 5-Fold en Python Puro + Overlay Reversible de Active Learning
- **Dataset Curado (`core/rules/benchmark_dataset.json`):** 60 casos de referencia en español distribuidos en 10 arquetipos × 6 ejemplos (casos normales y casos borde).
- **Evaluador Científico sin dependencias (`core/scientific_eval.py`, `evaluate_engine.py`):** `MultinomialNaiveBayesClassifier` en Python estándar (`log-sum-exp`, suavizado $\alpha=1.0$), desempate híbrido conservador y Validación Cruzada Estratificada 5-Fold *out-of-fold*.
- **Capa Overlay Reversible (`ActiveLearningRule`, migración `0008`):** aprobación (`/analitica/aprendizaje/aprobar/`) y reversión (`/analitica/aprendizaje/revertir/<id>/`) en SQLite sin mutar `core/rules/knowledge_base.json`, junto con tabla comparativa y Matriz de Confusión 10 × 10 en `/analitica/`.
- **Tests:** incorporada `PromptLabV80ScientificAndActiveLearningTests` (5 tests) alcanzando **78 tests en verde**.

---

## [v7.3] — Espacio de Trabajo Inteligente, Privacidad Verificada, Tokens Offline y Cuenta Opcional (73 tests)

- **Ejemplos rápidos auto-ocultables (4 casos):** chips interactivos sobre el editor incluyendo el 4° caso institucional/AFIP (*Proteger datos en nota oficial*) con ocultamiento automático al escribir.
- **Sello de Privacidad verificada (`.pl-privacy-seal` y `.pl-fmt-pii-mask`):** indicador visible cuando se resguardan datos personales argentinos en Python/JS sin afectar facturas AFIP (`XXXX-XXXXXXXX`).
- **Estimador Heurístico Offline de Tokens (ChatGPT · Gemini · Claude):** estimación orientativa local para español en el Espacio de Trabajo y en el Comparador Antes vs. Después sin APIs ni tokenizadores externos.
- **Cuenta opcional privada (`/ingresar/`, `/registro/`, `/salir/`):** aislamiento estricto por usuario registrado manteniendo disponible el modo invitado compartido sin registro obligatorio.
- **Tests:** incorporadas `PromptLabV73WorkspaceSmartFeaturesTests` (4 tests) y `PromptLabV73OptionalAuthTests` (5 tests) alcanzando **73 tests en verde**.

---

## [v7.2.4] — Armonización Integral de Diseño, UX y Lenguaje (64 tests)

- **Sistema visual unificado (`promptlab.css`):** consolidación de tokens `--pl-*` (`--pl-text-muted`, `--pl-surface-elevated`, `--pl-radius-card`, `--pl-radius-pill`) y componentes compartidos (`.pl-page-shell`, `.pl-page-header`, `.pl-page-title`, `.pl-page-subtitle`, `.pl-mode-badge--*`, `.pl-empty-state`, `.btn-pl-danger`) para Modo Oscuro y Modo Claro.
- **Navegación y títulos coherentes (`base.html`):** `<title>` estandarizado `{Pestaña} · PromptLab`, íconos SVG uniformes en el menú lateral/móvil y atributo `aria-current="page"` en la vista activa.
- **Contrato de lenguaje unificado:** voseo argentino consistente en toda la interfaz (Espacio de Trabajo, Plantillas, Mi Historial, Favoritos y Estadísticas) y traducción completa de modos (`Express`, `Guiado`, `Estudio Pro`), tareas y privacidad (*Privacidad protegida*), manteniendo español neutro estándar en los prompts compilados.
- **Mi Historial mejorado (`history.html`, `views.py`):** nuevo filtro por modo, badges unificados de modo y calidad, acciones claras y estados vacíos homologados.
- **Cache-busting unificado:** actualización global a `?v=7.2.4` en `promptlab.css`, `workspace.js`, `templates_gallery.js` y `analytics_charts.js`.
- **Tests:** incorporada la suite `PromptLabSiteCoherenceTests` (4 tests) alcanzando **64 tests en verde**.

---

## [v7.2.3] — Dashboard Interactivo de Estadísticas y Datos 100 % Offline (60 tests)

- **5 gráficos SVG nativos interactivos (`analytics_charts.js`, sin Chart.js ni CDNs):**
  1. Barras horizontales con eje numérico (*¿Sobre qué temas consultás más?*).
  2. Dona interactiva con conmutador (*Estilos de respuesta* vs. *Modos de profundidad*).
  3. Líneas con área sombreada (*Evolución: Antes vs. Después*).
  4. Barras verticales agrupadas por técnica o modo.
  5. Barras verticales agrupadas por tipo de tarea con tildes corregidas.
- **Barra segmentada 100 % de distribución de calidad** + 4 mini-tarjetas de rango (*Excelente*, *Muy bueno*, *Bueno*, *Mejorable*).
- **Filtro real por período (`?periodo=all|30d|7d`):** manejo seguro de valores inválidos, estados vacíos diferenciados (sin historial vs. período sin actividad), tolerancia a registros legacy y consejos automáticos deterministas (*"Qué podés aprovechar mejor"*).
- **Adaptación automática de tema:** sincronización instantánea con Modo Oscuro y Modo Claro mediante el evento `themeChanged` y variables CSS.
- **Cero jerga interna en HTML y JSON:** payload seguro mediante `json_script:"analytics-chart-data"`.
- **Tests:** incorporada la suite `PromptLabStatsDashboardTests` (6 tests) alcanzando **60 tests en verde**.

---

## [v7.2.2] — Catálogo Multivariado y UX Didáctica de Plantillas (54 tests)

- **Catálogo curado de 18 plantillas en 6 categorías** (`Tecnología y Programación`, `Ciencia de Datos e IA`, `Negocios y Comercio`, `Estudio y Academia`, `Redacción y Comunicación`, `Carrera y Productividad`), con respaldo `LEGACY_PRESETS` para compatibilidad con enlaces `?preset=`.
- **UX didáctica (`templates_gallery.html`):** guía rápida en 3 pasos con íconos SVG, micro-leyenda de los 3 modos, placeholders resaltados entre `[corchetes]` y micro-tip *"Por qué funciona:"* en cada tarjeta.
- **Filtrado 100 % client-side (`templates_gallery.js`):** buscador instantáneo, chips de categoría con contadores, filtro por modo, copia rápida y estado vacío con botón *Limpiar filtros*.
- **Carga inteligente en el Espacio de Trabajo (`workspace.js`):** transferencia sin truncamiento vía `sessionStorage` + respaldo `?preset=<slug>`, activación automática del modo recomendado, disparo de detección en vivo y aviso descartable arriba del editor.
- **Tests:** incorporada la suite `PromptLabTemplatesCatalogTests` (3 tests) alcanzando **54 tests en verde**.

---

## [v7.2.1] — Parche de Precisión NLP (N1–N6) y Sincronización PII (51 tests)

- **Correcciones NLP basadas en auditoría real (N1–N6):** explicaciones con analogías sin fórmulas, consultas SQL sin falso público cliente, enrutamiento de guiones cortos (`guion_video`), prórrogas de pago a proveedores fieles a la intención y planes de estudio diarios con slots depurados.
- **Privacidad AFIP:** exclusión de números de facturas AFIP (`XXXX-XXXXXXXX`) en la detección de DNI/teléfono tanto en Python (`services.py`) como en JavaScript (`workspace.js`).
- **Tests:** incorporada la suite `PromptLabV721AuditRegressionTests` (6 tests) alcanzando **51 tests en verde**.

---

## [v7.2 / v7.1 / v6.0] — Base del Motor Universal y Plataforma Offline

- **v7.2:** Motor Universal de 2 carriles (`ENGINE_VERSION = "v7.2"`), sincronización PII argentino, isotipo SVG y pulido general del estudio.
- **v7.1:** Interfaz progresiva en 3 modos (`Express`, `Guiado`, `Estudio Pro`), lectura estructurada de salida y mejoras del motor NLP.
- **v6.0:** Motor universal de 21 arquetipos, inspector estructural de insumos, cálculo financiero determinístico sin `eval`, Rúbrica v2 no circular, minería estadística offline *Log-Odds* y exportación `.CSV` de 38 columnas.
