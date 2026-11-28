# PromptLab Studio · DS & IA (v8.0)

**PromptLab** es una plataforma web desarrollada en Django para diseñar, estructurar, versionar y evaluar *prompts* con una **arquitectura híbrida 100 % offline** (`Motor Universal v7.2` determinístico de Caja Blanca + `Capa Científica Probabilística y Gestión de Prompts v8.0`), **cero dependencias externas nuevas** en `requirements.txt`, cero CDNs y base de datos local SQLite por defecto.

Nació como proyecto académico para la **Tecnicatura Superior en Ciencia de Datos e Inteligencia Artificial (IES N° 11)** y combina un pipeline determinístico de Procesamiento de Lenguaje Natural (NLP), un desempate probabilístico liviano en **Python puro** (*Multinomial Naive Bayes*), evaluación científica reproducible mediante **Validación Cruzada Estratificada 5-Fold**, capa aditiva reversible de aprendizaje activo (*Overlay*), versionado iterativo `v1 → v2 → v3` y portabilidad `.JSON` con escaneo automático de datos personales argentinos.

> Ver historial detallado de cambios en [CHANGELOG.md](CHANGELOG.md) y especificaciones técnicas/funcionales en [PRD.md](PRD.md).

---

## Propuesta de valor y los 3 modos de profundidad

PromptLab transforma pedidos cotidianos o incompletos en instrucciones claras y accionables bajo el enfoque **Cero Relleno** (meta de **Datos útiles ≥ 90 %** y **Texto de relleno < 10 %**), adaptándose al nivel de detalle que necesitás mediante **3 modos progresivos**:

| Modo en la interfaz | Cuándo conviene usarlo | Qué entrega |
| :--- | :--- | :--- |
| **Express** | Consultas rápidas y pedidos cotidianos | Prompt breve y directo, listo para copiar sin pasos innecesarios. |
| **Guiado** | Pedidos con contexto que conviene afinar | Prompt estructurado por secciones + **Asistente Guiado** con preguntas rápidas (*Smart Slots*) y barra de puntaje. |
| **Estudio Pro** | Tareas técnicas, análisis de datos o casos críticos | Máximo detalle con **casos borde**, validaciones previas, restricciones negativas, detección editable en vivo, evaluación por 5 criterios y mapa de origen (*De dónde sale cada frase*). |

---

## Las 4 pestañas principales y cuenta opcional

### 1. Espacio de Trabajo (`/`)
- Editor principal con selector progresivo (`Express`, `Guiado`, `Estudio Pro`), **4 chips de ejemplos rápidos auto-ocultables** (incluyendo control de ventas en Excel, análisis CSV, cálculo de punto de equilibrio y nota oficial con resguardo de PII/facturas AFIP) y atajo `Ctrl + Enter`.
- **Detección en vivo** (`/api/analyze-live/`) mientras escribís: identifica área temática, tipo de tarea, entregable, restricciones negativas, contradicciones e insumos pegados (CSV, listas, código, trazas de error).
- **Protección de privacidad y Sello de Privacidad verificada:** detecta y anonimiza DNI/CUIL/CUIT, teléfonos, correos electrónicos, CBU y alias bancarios de forma sincronizada entre Python y JavaScript (`workspace.js`), excluyendo falsos positivos en números de facturas AFIP (`XXXX-XXXXXXXX`), mostrando badge de resguardo verificable y resaltado inline `.pl-fmt-pii-mask`.
- **Estimador comparativo offline de tokens (ChatGPT · Gemini · Claude):** estima en tiempo real el consumo en español (±10 % sin APIs externas ni dependencias) mostrando porcentaje de ventana (`128K`, `1M`, `200K`) y ayuda pedagógica para público no técnico tanto en la salida principal como en el **Comparador Antes vs. Después**.
- **Versionado iterativo (`v1 → v2 → v3`) y guardado como plantilla:** badge de versión `vN`, botón **`Iterar nueva versión`** con banner de nota de cambio opcional, trazabilidad hacia el prompt padre/raíz y modal **`Guardar como plantilla`** para transformar cualquier salida en plantilla propia reutilizable.
- **Asistente Guiado y calidad (0–100):** preguntas contextuales de alto impacto, reglas rápidas en 1 clic, evaluación no circular de 5 criterios y exportación a `.MD` y `.JSON`.

### 2. Plantillas (`/plantillas/`)
- **Catálogo oficial curado de 18 plantillas multivariadas en 6 categorías** (3 por categoría): *Tecnología y Programación*, *Ciencia de Datos e IA*, *Negocios y Comercio*, *Estudio y Academia*, *Redacción y Comunicación* y *Carrera y Productividad*.
- Guía visual compacta en **3 pasos**, buscador en vivo y filtros instantáneos por categoría y modo 100 % *client-side* (`templates_gallery.js`), placeholders resaltados entre `[corchetes]` y micro-tip didáctico *"Por qué funciona:"*.
- **Sección "Mis Plantillas guardadas (N)" (`UserTemplate`):** creación de plantillas personalizadas con selector de categoría/modo y marcadores `[corchetes]`, confirmación de borrado en 2 pasos sin cuadros nativos bloqueantes, carga directa en Workspace (`/?user_tpl=<id>`) y **portabilidad offline `.JSON`** (`promptlab-collection-v1`, tope `512 KB`, validación estricta, deduplicación por contenido y escaneo automático PII respetando facturas AFIP).

### 3. Mi Historial (`/historial/`) y Favoritos (`/favoritos/`)
- Registro automático en SQLite aislado por usuario (incluyendo sesión de Invitado) con vista dedicada de favoritos (`/favoritos/`).
- Filtros instantáneos por búsqueda de texto, área, estilo de respuesta y modo (`Express`, `Guiado`, `Estudio Pro`).
- **Trazabilidad de versiones (`vN`):** badge de versión, nota de iteración, **línea de tiempo comparativa** (`v1 → v2 → v3`) con variación de puntaje respecto de la versión anterior y botones **`Nueva versión`** (`/?load=<id>&iterate=1`) y **`Cargar`**.

### 4. Estadísticas y Datos (`/analitica/`)
- Dashboard **100 % offline** con **5 gráficos SVG nativos** en `analytics_charts.js` (cero Chart.js, cero CDNs), tooltips interactivos y actualización instantánea al alternar **Modo Oscuro / Modo Claro** (`themeChanged`):
  1. **Barras horizontales con eje numérico:** *¿Sobre qué temas consultás más?*
  2. **Dona interactiva con conmutador:** *¿Qué estilos y modos elegís más?* (*Estilos de respuesta* vs. *Modos de profundidad*).
  3. **Líneas con área sombreada:** *Evolución: Antes vs. Después*.
  4. **Barras verticales agrupadas (técnica/modo):** *¿Cuánto mejoran los prompts según la técnica elegida?*
  5. **Barras verticales agrupadas por tarea:** *¿Cuánto mejoran los prompts según la tarea?*
- **Evaluación Científica del Motor (Validación Cruzada 5-Fold sobre 60 casos):** comparativa verificable **Solo Reglas vs. Motor Híbrido v8.0** (*Exactitud*, *Macro F1*, *Weighted F1*, casos rescatados, 0 regresiones, top confusiones y **Matriz de Confusión 10 × 10** con código de color accesible WCAG AA/AAA).
- **Aprendizaje Activo Reversible (*Overlay* SQLite):** descubrimiento local *Log-Odds* de nuevos términos con botón **`Aprobar en capa`** (`/analitica/aprendizaje/aprobar/`) y reversión instantánea (`/analitica/aprendizaje/revertir/<id>/`) sin mutar jamás `core/rules/knowledge_base.json`.
- **Dataset académico `.CSV` de 38 columnas** (`/analitica/exportar-csv/`).

### Cuenta opcional multiusuario e Invitado
- **Acceso sin barreras:** la app funciona completa de inmediato como **Invitado** en sesión local aislada.
- Quienes deseen separar su historial y colecciones institucionales o personales disponen de **`/ingresar/`**, **`/registro/`** y **`/salir/`** (`POST`), con migración segura de los datos creados como Invitado al registrarse o iniciar sesión.

---

## Todas las rutas de la aplicación (19 endpoints en `core/urls.py`)

| Método | Ruta | Nombre / Propósito |
| :--- | :--- | :--- |
| `GET` | `/` | `workspace` — Espacio de Trabajo (`?load=`, `?iterate=1`, `?preset=`, `?user_tpl=`). |
| `GET` | `/historial/` | `history` — Historial completo con filtros y trazabilidad de versiones. |
| `GET` | `/favoritos/` | `favorites` — Prompts marcados como favoritos. |
| `POST` | `/historial/favorito/<int:prompt_id>/` | `toggle_favorite` — Alterna favorito (AJAX o formulario). |
| `POST` | `/historial/eliminar/<int:prompt_id>/` | `delete_prompt` — Elimina un prompt respetando `next`. |
| `GET` | `/plantillas/` | `templates_gallery` — 18 plantillas curadas + Mis Plantillas propias. |
| `POST` | `/plantillas/propias/crear/` | `create_user_template` — Crea una plantilla propia del usuario activo. |
| `POST` | `/plantillas/propias/eliminar/<int:template_id>/` | `delete_user_template` — Elimina una plantilla propia. |
| `GET` | `/plantillas/propias/exportar-json/` | `export_user_templates_json` — Descarga `.json` (`promptlab-collection-v1`). |
| `POST` | `/plantillas/propias/importar-json/` | `import_user_templates_json` — Importa `.json` con validación y escaneo PII. |
| `GET` | `/analitica/` | `analytics` — Dashboard SVG, 5-Fold Benchmark, Overlay y Log-Odds. |
| `GET` | `/analitica/exportar-csv/` | `export_csv` — Exporta `promptlab_dataset.csv` UTF-8 BOM (38 columnas). |
| `POST` | `/analitica/aprendizaje/aprobar/` | `approve_learning_rule` — Aprueba término candidato en `ActiveLearningRule`. |
| `POST` | `/analitica/aprendizaje/revertir/<int:rule_id>/` | `toggle_learning_rule` — Activa/revierte una regla de la capa overlay. |
| `POST` | `/api/improve/` | `improve_prompt_api` — Compila prompt, evalúa rúbrica y guarda versión en SQLite. |
| `POST` | `/api/analyze-live/` | `analyze_live_api` — Diagnóstico NLP en vivo sin persistencia. |
| `GET / POST` | `/ingresar/` | `login` — Inicio de sesión opcional (migra sesión de Invitado). |
| `GET / POST` | `/registro/` | `register` — Creación de cuenta local opcional. |
| `POST` | `/salir/` | `logout` — Cierre de sesión seguro con retorno a Workspace Invitado. |

---

## Arquitectura técnica y estructura del proyecto

```text
Proyecto PromptLab/
├── manage.py
├── requirements.txt                       # Django==6.0.3 (0 paquetes externos de ML)
├── README.md
├── PRD.md
├── CHANGELOG.md
├── promptlab/
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
└── core/
    ├── models.py                          # Prompt (versionado vN), ActiveLearningRule, UserTemplate
    ├── views.py                           # Vistas, 18 plantillas curadas, colecciones JSON, Analítica y Auth
    ├── urls.py                            # 19 rutas completas de la plataforma
    ├── services.py                        # Pipeline NLP v7.2, rúbrica v2, PII y puente con overlay/NB
    ├── universal_engine.py                # Motor universal determinístico (21 arquetipos, cálculo, Log-Odds)
    ├── scientific_eval.py                 # Multinomial Naive Bayes en Python puro + Validación 5-Fold + Overlay
    ├── tests.py                           # 83 tests automatizados en 14 suites
    ├── management/
    │   └── commands/
    │       └── evaluate_engine.py         # Comando CLI `./venv/bin/python manage.py evaluate_engine`
    ├── rules/
    │   ├── knowledge_base.json            # Base de conocimiento determinística inmutable
    │   └── benchmark_dataset.json         # Dataset dorado curado de 60 casos (10 clases × 6)
    ├── migrations/                        # Migraciones SQLite 0001–0009
    ├── templates/core/
    │   ├── base.html                      # Layout global, sidebar compacto 1280×720, cuenta y ?v=8.0
    │   ├── workspace.html                 # Espacio de Trabajo inteligente, tokens, privacidad y vN
    │   ├── templates_gallery.html         # 18 plantillas curadas + Mis Plantillas + importar/exportar JSON
    │   ├── history.html                   # Mi Historial, Favoritos y línea de tiempo de versiones
    │   ├── analytics.html                 # 5 gráficos SVG + Benchmark 5-Fold + Matriz 10×10 + Overlay
    │   ├── login.html                     # Inicio de sesión opcional WCAG AA/AAA
    │   └── register.html                  # Registro opcional WCAG AA/AAA
    └── static/
        ├── css/
        │   └── promptlab.css              # Sistema visual unificado --pl-* (Oscuro/Claro WCAG AA/AAA)
        ├── js/
        │   ├── workspace.js               # Detección en vivo, PII client-side, tokens y versionado
        │   ├── templates_gallery.js       # Filtros 18+N, borrado 2 pasos y colección JSON
        │   └── analytics_charts.js        # 5 gráficos SVG interactivos 100 % offline
        └── vendor/                        # Assets locales offline (Bootstrap 5 y Bootstrap Icons)
```

---

## Evaluación Científica Reproducible (`evaluate_engine`)

PromptLab v8.0 incluye un evaluador científico en **Python puro** (`core/scientific_eval.py`) sin `scikit-learn` ni `numpy`, ejecutable desde terminal sobre los **60 casos reales** (`core/rules/benchmark_dataset.json`, 10 clases × 6 ejemplos incluyendo casos `"borde"`):

```bash
./venv/bin/python manage.py evaluate_engine
```

Resultados reales medidos mediante **Validación Cruzada Estratificada 5-Fold (*out-of-fold*, cero *data leakage*)**:

| Métrica | Núcleo Solo Reglas (`v7.2`) | Híbrido `v8.0` (Reglas + Naive Bayes 5-Fold) | Mejora |
| :--- | :---: | :---: | :---: |
| **Exactitud (*Accuracy*)** | **80,0 %** (`48/60`) | **95,0 %** (`57/60`) | **+15,0 pts** |
| **Macro F1** | **83,1 %** | **95,5 %** | **+12,4 pts** |
| **Weighted F1** | **83,1 %** | **95,5 %** | **+12,4 pts** |
| **Casos rescatados / Regresiones** | — | **9/11 rescatados (`81,8 %`)** | **0 regresiones** |
| **Tiempo de ejecución total** | — | **< 200 ms** (~130 ms promedio) | **100 % Python estándar** |

---

## Instalación y ejecución local

Requisitos: **Python 3.10+** (entorno verificado con Django 6.0.3 y SQLite) y **Node.js** opcional para validar sintaxis JS.

1. Clonar el repositorio:
   ```bash
   git clone https://github.com/alanrod10/promptlab.git
   cd promptlab
   ```
2. Crear y activar el entorno virtual:
   ```bash
   python3 -m venv venv
   source venv/bin/activate        # En Windows: venv\Scripts\activate
   ```
3. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```
4. Aplicar migraciones (`0001`–`0009`):
   ```bash
   ./venv/bin/python manage.py migrate
   ```
5. Levantar el servidor local:
   ```bash
   ./venv/bin/python manage.py runserver 8001
   ```
6. Abrir en el navegador:
   - Espacio de Trabajo: `http://127.0.0.1:8001/`
   - Plantillas: `http://127.0.0.1:8001/plantillas/`
   - Mi Historial: `http://127.0.0.1:8001/historial/`
   - Estadísticas y Datos: `http://127.0.0.1:8001/analitica/`

---

## Verificación de calidad y suite de tests (83 tests)

Ejecutar desde la raíz del proyecto:

```bash
node --check core/static/js/workspace.js core/static/js/templates_gallery.js core/static/js/analytics_charts.js
./venv/bin/python manage.py check
./venv/bin/python manage.py makemigrations --check --dry-run
./venv/bin/python manage.py evaluate_engine
./venv/bin/python manage.py test -v 2
```

La suite cuenta con **83 tests en verde** distribuidos en **14 clases** en `core/tests.py`:

- **`PromptLabServicesTests` (4):** sensibilidad de rúbrica, entradas cortas/triviales y combinaciones de niveles y técnicas.
- **`PromptLabViewsAndIntegrationTests` (13):** assets offline, rutas vacías, carga/preset, APIs `/api/improve/` y `/api/analyze-live/`, favoritos/eliminación por POST, CSV de 38 columnas, voseo/clíticos, PII, contradicciones y ausencia de URLs externas.
- **`PromptLabV5EngineTests` (5):** 5 casos dorados reales, linter anti-relleno, fidelidad sin bloques vacíos, caminos sugeridos y etiquetas simples en vistas.
- **`PromptLabV6UniversalEngineTests` (6):** 5 casos dorados del motor universal + inspector, cálculo exacto y minería Log-Odds.
- **`PromptLabV7EngineAndWorkspaceTests` (7):** normalizador de clíticos, límites de entregables, calibración de confianza, señales locales en SQLite, desambiguación/favorito AJAX, modos progresivos y regresión de Ciencia de Datos.
- **`PromptLabV72RegressionTests` (10):** suite dorada v7.2 (esquemas JSON, PII argentino Python/JS, traceback Python, comparativa técnica sin contaminación comercial, entrevistas, planes, minutas, scripts sin librerías externas y persistencia).
- **`PromptLabV721AuditRegressionTests` (6):** casos reales N1–N6 (analogías sin fórmulas, SQL sin falso público cliente, `guion_video`, exclusión de facturas AFIP en PII, pluralización y plan de estudio diario).
- **`PromptLabTemplatesCatalogTests` (3):** vista `/plantillas/` HTTP 200, validación de las 18 plantillas en 6 categorías y carga en Workspace.
- **`PromptLabStatsDashboardTests` (6):** estado vacío, dashboard poblado sin jerga cruda, filtrado por período (`all`/`30d`/`7d`/inválido), período vacío con historial previo, `analytics-chart-data` con 5 contenedores SVG y caso borde de 1 solo prompt.
- **`PromptLabSiteCoherenceTests` (4):** HTTP 200 en todas las pestañas, cache-busting `?v=8.0` sin CDNs externos, cero jerga interna ni modos crudos en la UI y coherencia de `<title>` + `aria-current="page"`.
- **`PromptLabV73WorkspaceSmartFeaturesTests` (4):** chips auto-ocultables con 4° ejemplo institucional/AFIP, Sello de Privacidad verificada en Python/UI, estimador offline de tokens para español y ausencia de nombres de tokenizadores remotos.
- **`PromptLabV73OptionalAuthTests` (5):** modo Invitado completo sin login obligatorio, aislamiento entre sesiones/usuarios, registro/ingreso/salida y migración segura de prompts de Invitado al crear cuenta.
- **`PromptLabV80ScientificAndActiveLearningTests` (5):** validación del dataset dorado de 60 casos sin fuga, Naive Bayes en Python puro (`< 300 ms`, `Macro F1 > 85 %`), no-mutación de `knowledge_base.json`, aprobación/reversión de reglas en capa `ActiveLearningRule` y render de Matriz de Confusión en `/analitica/`.
- **`PromptLabV80VersioningAndCollectionsTests` (5):** versionado `v1 → v2 → v3` con `root_prompt` y aislamiento por usuario, creación/borrado seguro de `UserTemplate`, carga vía `?user_tpl=<id>`, exportación `.JSON` `promptlab-collection-v1` y validación/sanitización PII + AFIP en importación `.JSON`.

---

## Actualización en PythonAnywhere

Para desplegar **PromptLab v8.0** en una instancia ya configurada de **PythonAnywhere**:

1. Abrir una consola Bash en PythonAnywhere dentro del directorio del proyecto y traer los cambios:
   ```bash
   git pull origin master
   ```
2. Aplicar las migraciones nuevas (`0008_activelearningrule` y `0009_prompt_parent_prompt_prompt_root_prompt_and_more`):
   ```bash
   ./venv/bin/python manage.py migrate
   ```
3. Si definiste `STATIC_ROOT` en tu configuración de producción para servir estáticos recolectados, actualizarlos (en configuración local por defecto con `STATIC_URL = 'static/'` sin `STATIC_ROOT`, Django sirve directo desde `core/static/`):
   ```bash
   ./venv/bin/python manage.py collectstatic --noinput
   ```
4. Ir a la pestaña **Web** de PythonAnywhere y pulsar **Reload** para recargar la aplicación WSGI.

---

## Hoja de Ruta v9.0 (Escala Institucional)

1. **Soporte opcional PostgreSQL multi-sede:** manteniendo SQLite como defecto cero-fricción para desarrollo local, aula y pyme.
2. **Roles institucionales:** perfiles diferenciados para *Docente / Coordinador*, *Estudiante / Equipo* y colecciones compartidas de cátedra o área.
3. **Paquetes curriculares firmados:** distribución verificable de colecciones `.JSON` de plantillas y capas de aprendizaje curadas por carrera o organismo.
4. **Evaluación ciega A/B de respuestas reales:** comparación estructurada entre salidas obtenidas con distintos modelos manteniendo trazabilidad de versión de prompt.
5. **Exportación analítica ampliada:** soporte opcional para `.JSONL` y vistas listas para notebooks académicos reproducibles.
