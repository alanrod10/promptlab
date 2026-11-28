# PromptLab Studio · DS & IA (v8.0.1)

**PromptLab** es una plataforma web desarrollada en Django para diseñar, estructurar, versionar y evaluar *prompts* con una **arquitectura híbrida 100 % offline** (`Motor Universal v7.2` determinístico de Caja Blanca + `Capa Científica Probabilística y Gestión de Prompts v8.0.1`), **cero paquetes externos de ML o APIs**, cero CDNs y base de datos local SQLite por defecto.

Nació como proyecto académico para la **Tecnicatura Superior en Ciencia de Datos e Inteligencia Artificial (IES N° 11)** y combina un pipeline determinístico de Procesamiento de Lenguaje Natural (NLP), un desempate probabilístico liviano en **Python puro** (*Multinomial Naive Bayes* sobre los 21 arquetipos), evaluación científica reproducible mediante **Validación Cruzada Estratificada 5-Fold y CV Repetida 10×5**, capa supervisada reversible (*Human-in-the-Loop*) restringida a administradores, versionado iterativo `v1 → v2 → v3` y portabilidad `.JSON` con escaneo automático de datos personales argentinos.

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
- Editor principal con selector progresivo (`Express`, `Guiado`, `Estudio Pro`), **4 chips de ejemplos rápidos auto-ocultables** (incluyendo control de ventas en Excel, análisis CSV, cálculo de punto de equilibrio y nota oficial con resguardo de PII/facturas AFIP) y atajo `Ctrl + Enter` (límite de entrada de `15.000` caracteres en APIs protegidas con CSRF).
- **Detección en vivo** (`/api/analyze-live/`) mientras escribís: identifica área temática, tipo de tarea, entregable, restricciones negativas, contradicciones e insumos pegados (CSV, listas, código, trazas de error).
- **Protección de privacidad y Sello de Privacidad verificada:** detecta y anonimiza DNI, CUIL/CUIT con o sin guiones (validando Módulo 11 oficial en 11 dígitos), teléfonos y celulares con `15`, correos electrónicos, CBU (22 dígitos) y alias bancarios en forma sincronizada entre Python y JavaScript (`workspace.js`), excluyendo cifras monetarias y comprobantes AFIP (`XXXX-XXXXXXXX`), y protegiendo también campos secundarios (`form_data`, ejemplo de referencia, tema y restricciones) cuando `mask_pii=True` (activo por defecto en `/api/improve/`).
- **Estimación heurística orientativa para español (ChatGPT · Gemini · Claude):** estima en tiempo real el consumo de tokens de manera **100 % offline sin APIs ni tokenizadores externos** mostrando porcentaje orientativo sobre ventanas de `128K`, `1M` y `200K`, acompañado de ayuda pedagógica (*"1 token ≈ ¾ de palabra; un prompt sin relleno consume menos y responde mejor."*) tanto en la salida principal como en el **Comparador Antes vs. Después**.
- **Versionado iterativo (`v1 → v2 → v3`) y guardado como plantilla:** badge de versión `vN`, botón **`Iterar nueva versión`** con banner de nota de cambio opcional, trazabilidad hacia el prompt padre/raíz y modal **`Guardar como plantilla`** para transformar cualquier salida en plantilla propia reutilizable.
- **Asistente Guiado y calidad (0–100):** preguntas contextuales de alto impacto, reglas rápidas en 1 clic, evaluación no circular de 5 criterios y exportación a `.MD` y `.JSON`.

### 2. Plantillas (`/plantillas/`)
- **Catálogo oficial curado de 18 plantillas multivariadas en 6 categorías** (3 por categoría): *Tecnología y Programación*, *Ciencia de Datos e IA*, *Negocios y Comercio*, *Estudio y Academia*, *Redacción y Comunicación* y *Carrera y Productividad*.
- Guía visual compacta en **3 pasos**, buscador en vivo y filtros instantáneos por categoría y modo 100 % *client-side* (`templates_gallery.js`), placeholders resaltados entre `[corchetes]` y micro-tip didáctico *"Por qué funciona:"*.
- **Sección "Mis Plantillas guardadas (N)" (`UserTemplate`):** creación de plantillas personalizadas con selector de categoría/modo y marcadores `[corchetes]`, confirmación de borrado en 2 pasos sin cuadros nativos bloqueantes, carga directa en Workspace (`/?user_tpl=<id>`) y **portabilidad offline `.JSON`** (`promptlab-collection-v1`, tope `512 KB`, validación estricta, deduplicación por contenido y escaneo automático PII respetando facturas AFIP).

### 3. Mi Historial (`/historial/`) y Favoritos (`/favoritos/`)
- Registro automático en SQLite aislado por cuenta autenticada (o asociado al espacio compartido de demostración en Modo Invitado) con vista dedicada de favoritos (`/favoritos/`).
- Filtros instantáneos por búsqueda de texto, área, estilo de respuesta y modo (`Express`, `Guiado`, `Estudio Pro`).
- **Trazabilidad de versiones (`vN`):** badge de versión, nota de iteración, **línea de tiempo comparativa** (`v1 → v2 → v3`) con variación de puntaje respecto de la versión anterior, botones **`Nueva versión`** (`/?load=<id>&iterate=1`) / **`Cargar`** y promoción automática de nueva raíz si se elimina `v1`.

### 4. Estadísticas y Datos (`/analitica/`)
- Dashboard **100 % offline** con **5 gráficos SVG nativos** en `analytics_charts.js` (cero Chart.js, cero CDNs), tooltips interactivos y actualización instantánea al alternar **Modo Oscuro / Modo Claro** (`themeChanged`).
- **Evaluación Científica del Motor NLP (`60` casos curados de referencia, `10` de `21` arquetipos):** comparativa reproducible entre **Baseline v7.2** y **Híbrido v8.0** (*Exactitud*, *F1 Macro*, *F1 Ponderado*, *Recall*, **IC 95 % de Wilson**, **CV Repetida 10×5**, **Test exacto de McNemar**, cobertura de NB en producción `21/21` arquetipos, similitud máxima Jaccard intra-clase `< 0,35`, **Matriz de Confusión 10 × 10**, recuadro transparente de **Alcance y límites declarados** y **Auditoría caso por caso** desplegable).
- **Capa incremental supervisada (*Human-in-the-Loop*, Overlay SQLite):** descubrimiento local *Log-Odds* de términos recurrentes con aprobación (`/analitica/aprendizaje/aprobar/`) y reversión (`/analitica/aprendizaje/revertir/<id>/`) restringidas exclusivamente a **cuentas administradoras (`is_staff=True`)**, con validación anti-PII y sin mutar jamás `core/rules/knowledge_base.json`.
- **Dataset académico `.CSV` de 38 columnas** (`/analitica/exportar-csv/`) con neutralización contra inyección de fórmulas (`=`, `+`, `-`, `@`).

### Modo Invitado y Cuenta Opcional Privada
- **Modo Invitado:** espacio compartido de demostración (`invitado_demo`, con contraseña inutilizable que impide login directo) pensado para probar la herramienta de inmediato sin fricción. No recibe ni comparte refuerzos aprendidos entre usuarios.
- **Cuenta registrada (`/ingresar/`, `/registro/`, `/salir/`):** espacio privado estrictamente aislado en historial, favoritos, plantillas propias, estadísticas, refuerzos aprendidos por corrección (`user_corrected`) y exportación `.CSV`.

---

## Todas las rutas de la aplicación (19 endpoints en `core/urls.py`)

| Método | Ruta | Nombre / Propósito |
| :--- | :--- | :--- |
| `GET` | `/` | `workspace` — Espacio de Trabajo (`@ensure_csrf_cookie`; `?load=`, `?iterate=1`, `?preset=`, `?user_tpl=`). |
| `GET` | `/historial/` | `history` — Historial completo con filtros y trazabilidad de versiones. |
| `GET` | `/favoritos/` | `favorites` — Prompts marcados como favoritos. |
| `POST` | `/historial/favorito/<int:prompt_id>/` | `toggle_favorite` — Alterna favorito (AJAX o formulario). |
| `POST` | `/historial/eliminar/<int:prompt_id>/` | `delete_prompt` — Elimina un prompt promoviendo nueva raíz si corresponde. |
| `GET` | `/plantillas/` | `templates_gallery` — 18 plantillas curadas + Mis Plantillas propias. |
| `POST` | `/plantillas/propias/crear/` | `create_user_template` — Crea una plantilla propia del usuario activo. |
| `POST` | `/plantillas/propias/eliminar/<int:template_id>/` | `delete_user_template` — Elimina una plantilla propia. |
| `GET` | `/plantillas/propias/exportar-json/` | `export_user_templates_json` — Descarga `.json` (`promptlab-collection-v1`). |
| `POST` | `/plantillas/propias/importar-json/` | `import_user_templates_json` — Importa `.json` con validación y escaneo PII. |
| `GET` | `/analitica/` | `analytics` — Dashboard SVG, Benchmark 5-Fold/10×5, Auditoría y Overlay. |
| `GET` | `/analitica/exportar-csv/` | `export_csv` — Exporta `promptlab_dataset.csv` UTF-8 BOM (38 columnas seguras). |
| `POST` | `/analitica/aprendizaje/aprobar/` | `approve_learning_rule` — Aprueba término en `ActiveLearningRule` (solo `is_staff`, anti-PII). |
| `POST` | `/analitica/aprendizaje/revertir/<int:rule_id>/` | `toggle_learning_rule` — Activa/revierte una regla de la capa overlay (solo `is_staff`). |
| `POST` | `/api/improve/` | `improve_prompt_api` — Compila prompt, evalúa rúbrica y guarda versión (CSRF real, tope 15.000 chars, `mask_pii=True` por defecto). |
| `POST` | `/api/analyze-live/` | `analyze_live_api` — Diagnóstico NLP en vivo sin persistencia (CSRF real, tope 15.000 chars). |
| `GET / POST` | `/ingresar/` | `login` — Inicio de sesión en cuenta privada. |
| `GET / POST` | `/registro/` | `register` — Creación de cuenta privada (bloquea nombres reservados). |
| `POST` | `/salir/` | `logout` — Cierre de sesión seguro con retorno a Espacio de Trabajo. |

---

## Arquitectura técnica y estructura del proyecto

```text
Proyecto PromptLab/
├── manage.py
├── requirements.txt                       # Django==6.1.3, asgiref==3.13.0, sqlparse==0.6.1 (+ tzdata en Windows)
├── README.md
├── PRD.md
├── CHANGELOG.md
├── promptlab/
│   ├── settings.py                        # Perfil seguro por variables de entorno, STATIC_ROOT y LOGGING
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
└── core/
    ├── models.py                          # Prompt (versionado vN), ActiveLearningRule, UserTemplate
    ├── views.py                           # Vistas, 18 plantillas curadas, colecciones JSON, Analítica, CSRF y Auth
    ├── urls.py                            # 19 rutas completas de la plataforma
    ├── services.py                        # Pipeline NLP v7.2, rúbrica v2, PII Módulo 11, caché por usuario y puente híbrido
    ├── universal_engine.py                # Motor universal determinístico (21 arquetipos, cálculo, Log-Odds)
    ├── scientific_eval.py                 # Multinomial NB 21 clases, CV 5-Fold/10×5, Wilson, McNemar, Jaccard y Overlay
    ├── tests.py                           # 90 tests automatizados en 15 suites
    ├── management/
    │   └── commands/
    │       └── evaluate_engine.py         # Comando CLI `./venv/bin/python manage.py evaluate_engine`
    ├── rules/
    │   ├── knowledge_base.json            # Base de conocimiento determinística inmutable
    │   └── benchmark_dataset.json         # Conjunto curado de 60 casos de referencia (10 clases × 6, Jaccard < 0.35)
    ├── migrations/                        # Migraciones SQLite 0001–0009
    ├── templates/core/
    │   ├── base.html                      # Layout global, sidebar v8.0, invitado compartido, cuenta y ?v=8.0
    │   ├── workspace.html                 # Espacio de Trabajo inteligente, tokens orientativos, privacidad y vN
    │   ├── templates_gallery.html         # 18 plantillas curadas + Mis Plantillas + importar/exportar JSON
    │   ├── history.html                   # Mi Historial, Favoritos, línea de tiempo y copia resiliente
    │   ├── analytics.html                 # 5 gráficos SVG + Benchmark 5-Fold/10×5 + Auditoría casos + Overlay staff
    │   ├── login.html                     # Inicio de sesión opcional WCAG AA
    │   └── register.html                  # Registro opcional WCAG AA
    └── static/
        ├── css/
        │   └── promptlab.css              # Sistema visual unificado --pl-* (Oscuro/Claro WCAG AA)
        ├── js/
        │   ├── workspace.js               # Detección en vivo, CSRF, PII Módulo 11 client-side, tokens y versionado
        │   ├── templates_gallery.js       # Filtros 18+N, borrado 2 pasos y colección JSON
        │   └── analytics_charts.js        # 5 gráficos SVG interactivos 100 % offline
        └── vendor/                        # Assets locales offline (Bootstrap 5 y Bootstrap Icons)
```

---

## Evaluación Científica Reproducible (`evaluate_engine`)

PromptLab v8.0.1 incluye un evaluador científico en **Python puro** (`core/scientific_eval.py`) sin `scikit-learn` ni `numpy`, completamente aislado de SQLite y de la capa Overlay, ejecutable desde terminal sobre **60 casos curados de referencia** (`core/rules/benchmark_dataset.json`, `10` de los `21` arquetipos × 6 ejemplos = 4 `normal` + 2 `borde` sin pares espejo; similitud Jaccard máxima intra-clase = **`0,278`** `< 0,35`), mientras que en producción el clasificador auxiliar Multinomial Naive Bayes cubre los **`21/21`** arquetipos (`126` prototipos + `60` casos):

```bash
./venv/bin/python manage.py evaluate_engine
```

Resultados reales medidos (*Naive Bayes out-of-fold* en 5-Fold balanceado `12×5`, corrida principal semilla `42`):

| Métrica | Baseline `v7.2` (Solo Reglas) | Híbrido `v8.0` (Reglas + Naive Bayes *out-of-fold*) | Diferencia |
| :--- | :---: | :---: | :---: |
| **Exactitud (*Accuracy*)** | **86,7 %** (`IC 95 % Wilson: [75,8 %; 93,1 %]`) | **93,3 %** (`IC 95 % Wilson: [84,1 %; 97,4 %]`) | **+6,6 pp** |
| **Precisión Macro** | **94,8 %** | **95,7 %** | **+0,9 pp** |
| **Exhaustividad (*Recall*)** | **86,7 %** | **93,3 %** | **+6,6 pp** |
| **Macro F1** | **89,8 %** | **94,2 %** | **+4,4 pp** |
| **Weighted F1** | **89,8 %** | **94,2 %** | **+4,4 pp** |
| **CV Repetida (10 × 5-Fold)** | — | **Exactitud `91,8 % ± 0,9 pp`** (`90,0 %–93,3 %`) · **Macro F1 `93,0 % ± 0,7 pp`** | — |
| **Rescatados / Regresiones** | `8` errores totales (`5` de baja certeza) | **4/8 errores totales (`50,0 %`)** · **4/5 baja certeza (`80,0 %`)** | **0 regresiones** (`56/60` diagonal) |
| **Test exacto de McNemar** | — | `p = 0,1250` (`4` rescates vs. `0` regresiones; 9 intervenciones NB) | Alcance honesto sobre 60 casos |

**Alcance y límites declarados:** el desempate probabilístico *Multinomial Naive Bayes* se evalúa estrictamente *out-of-fold* sobre `benchmark_dataset.json` sin acceso a SQLite ni reglas overlay; las reglas determinísticas base (`v7.2`) fueron diseñadas con conocimiento del dominio de los 10 arquetipos evaluados y aún no cuentan con una muestra externa independiente curada por terceros.

---

## Instalación y ejecución local

Requisitos: **Python 3.10+** (entorno verificado con **Python 3.14.4**, **`Django==6.1.3`** y SQLite) y **Node.js** opcional para validar sintaxis JS.

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

## Verificación de calidad y suite de tests (90 tests)

Ejecutar desde la raíz del proyecto:

```bash
for f in core/static/js/*.js; do node --check "$f" && echo "OK: $f"; done
./venv/bin/python manage.py check
./venv/bin/python manage.py makemigrations --check --dry-run
./venv/bin/python manage.py evaluate_engine
./venv/bin/python manage.py test -v 2
```

La suite cuenta con **90 tests en verde** distribuidos en **15 clases** en `core/tests.py`:

- **`PromptLabServicesTests` (4):** sensibilidad de rúbrica, entradas cortas/triviales y combinaciones de niveles y técnicas.
- **`PromptLabViewsAndIntegrationTests` (13):** assets offline, rutas vacías, carga/preset, APIs `/api/improve/` y `/api/analyze-live/`, favoritos/eliminación por POST, CSV de 38 columnas, voseo/clíticos, PII, contradicciones y ausencia de URLs externas.
- **`PromptLabV5EngineTests` (5):** 5 casos dorados reales, linter anti-relleno, fidelidad sin bloques vacíos, caminos sugeridos y etiquetas simples en vistas.
- **`PromptLabV6UniversalEngineTests` (6):** 5 casos dorados del motor universal + inspector, cálculo exacto y minería Log-Odds.
- **`PromptLabV7EngineAndWorkspaceTests` (7):** normalizador de clíticos, límites de entregables, calibración de confianza, refuerzos aprendidos por usuario en SQLite, desambiguación/favorito AJAX, modos progresivos y regresión de Ciencia de Datos.
- **`PromptLabV72RegressionTests` (10):** suite dorada v7.2 (esquemas JSON, PII argentino Python/JS, traceback Python, comparativa técnica sin contaminación comercial, entrevistas, planes, minutas, scripts sin librerías externas y persistencia).
- **`PromptLabV721AuditRegressionTests` (6):** casos reales N1–N6 (analogías sin fórmulas, SQL sin falso público cliente, `guion_video`, exclusión de facturas AFIP en PII, pluralización y plan de estudio diario).
- **`PromptLabTemplatesCatalogTests` (3):** vista `/plantillas/` HTTP 200, validación de las 18 plantillas en 6 categorías y carga en Workspace.
- **`PromptLabStatsDashboardTests` (6):** estado vacío, dashboard poblado sin jerga cruda, filtrado por período (`all`/`30d`/`7d`/inválido), período vacío con historial previo, `analytics-chart-data` con 5 contenedores SVG y caso borde de 1 solo prompt.
- **`PromptLabSiteCoherenceTests` (4):** HTTP 200 en todas las pestañas, cache-busting `?v=8.0` sin CDNs externos, cero jerga interna ni modos crudos en la UI y coherencia de `<title>`, etiqueta `Motor Híbrido v8.0 • 100% Offline` y `aria-current="page"`.
- **`PromptLabV73WorkspaceSmartFeaturesTests` (4):** chips auto-ocultables con 4° ejemplo institucional/AFIP, Sello de Privacidad verificada en Python/UI, estimador heurístico offline de tokens para español y ausencia de nombres internos en la interfaz.
- **`PromptLabV73OptionalAuthTests` (5):** modo invitado operativo sin login obligatorio, registro/ingreso/salida, rechazo de `next` externo y aislamiento estricto por usuario en historial, favoritos, analítica, borrado y CSV.
- **`PromptLabV80ScientificAndActiveLearningTests` (6):** validación del dataset curado de 60 casos, 5 folds balanceados (12×5), Jaccard `< 0,35`, NB `21/21`, CV 10×5 / Wilson / McNemar / invariancia frente a SQLite (`elapsed_ms < 2000.0`, `regressions_count == 0`, `hybrid["macro_f1"] >= baseline["macro_f1"]`), comando `evaluate_engine`, aislamiento estricto de refuerzos aprendidos por usuario/invitado, aprobación/reversión de capa Overlay (`is_staff`) sin mutar `knowledge_base.json` y render auditable en `/analitica/`.
- **`PromptLabV80VersioningAndCollectionsTests` (5):** versionado `v1 → v2 → v3` con `root_prompt` y aislamiento por usuario, creación/borrado seguro de `UserTemplate`, carga vía `?user_tpl=<id>`, exportación `.JSON` `promptlab-collection-v1` y validación/sanitización PII + AFIP en importación `.JSON`.
- **`PromptLabV801SecurityAndAuditFixesTests` (6):** candado `is_staff` + rechazo anti-PII en capa Overlay, usuario centinela `invitado_demo` con clave inutilizable y sin fallback al primer usuario, CSRF estricto (`403` sin token) + tope `15.000` caracteres, PII endurecido (exclusión monetaria, CUIT 11 dígitos Módulo 11, alias en prosa, celular con `15`, protección secundaria en `user_example`/`form_data` y fix de `Desglose de nota formal`), neutralización de fórmulas en `.CSV` y promoción atómica de nueva raíz al borrar `v1`.

---

## Actualización en PythonAnywhere

Para desplegar **PromptLab v8.0.1** en **PythonAnywhere**:

1. Configurar variables de entorno de producción en el WSGI / consola (al menos `DJANGO_SECRET_KEY`; cuando `PYTHONANYWHERE_DOMAIN` está presente, `DEBUG` pasa automáticamente a `False` con cookies seguras y `X_FRAME_OPTIONS = 'DENY'`).
2. Abrir una consola Bash dentro del directorio del proyecto y traer los cambios:
   ```bash
   git pull origin master
   pip install -r requirements.txt
   ```
3. Aplicar las migraciones nuevas (`0008_activelearningrule` y `0009_prompt_parent_prompt_prompt_root_prompt_and_more`):
   ```bash
   ./venv/bin/python manage.py migrate
   ```
4. Recolectar archivos estáticos en `STATIC_ROOT` (`staticfiles/`):
   ```bash
   ./venv/bin/python manage.py collectstatic --noinput
   ```
5. Ir a la pestaña **Web** de PythonAnywhere y pulsar **Reload** para recargar la aplicación WSGI.

---

## Hoja de Ruta v9.0 (Escala Institucional)

1. **Soporte opcional PostgreSQL multi-sede:** manteniendo SQLite como defecto cero-fricción para desarrollo local, aula y pyme.
2. **Roles institucionales:** perfiles diferenciados para *Docente / Coordinador*, *Estudiante / Equipo* y colecciones compartidas de cátedra o área.
3. **Evaluación externa (*hold-out* independiente) y cobertura 21/21 del benchmark:** corpus externo etiquetado por terceros que cubra los 21 arquetipos del motor.
4. **Paquetes curriculares firmados:** distribución verificable de colecciones `.JSON` de plantillas y capas de aprendizaje curadas por carrera o organismo.
5. **Evaluación ciega A/B y exportación ampliada:** comparación de respuestas reales y exportación opcional `.JSONL`.
