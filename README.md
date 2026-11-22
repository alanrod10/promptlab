# PromptLab Studio · DS & IA (v7.2.4)

**PromptLab** es una plataforma web desarrollada en Django para optimizar, estructurar y evaluar *prompts* con un **Motor Universal v7.2 100 % offline** (sin APIs externas, sin CDNs y sin dependencias remotas) e interfaz armonizada **v7.2.4**.

Nació como proyecto académico para la **Tecnicatura Superior en Ciencia de Datos e Inteligencia Artificial (IES N° 11)** y combina un pipeline determinístico de Procesamiento de Lenguaje Natural (NLP) por reglas, evaluación cuantitativa no circular y analítica local en SQLite.

> Ver historial detallado de cambios en [CHANGELOG.md](CHANGELOG.md) y especificaciones de producto en [PRD.md](PRD.md).

---

## Propuesta de valor y los 3 modos de profundidad

PromptLab transforma pedidos cotidianos o incompletos en instrucciones claras y accionables bajo el enfoque **Cero Relleno** (meta de **Datos útiles ≥ 90 %** y **Texto de relleno < 10 %**), adaptándose al nivel de detalle que necesitás mediante **3 modos progresivos**:

| Modo en la interfaz | Cuándo conviene usarlo | Qué entrega |
| :--- | :--- | :--- |
| **Express** | Consultas rápidas y pedidos cotidianos | Prompt breve y directo, listo para copiar sin pasos innecesarios. |
| **Guiado** | Pedidos con contexto que conviene afinar | Prompt estructurado por secciones + **Asistente Guiado** con preguntas rápidas (*Smart Slots*) y barra de puntaje. |
| **Estudio Pro** | Tareas técnicas, análisis de datos o casos críticos | Máximo detalle con **casos borde**, validaciones previas, restricciones negativas, detección editable en vivo, evaluación por 5 criterios y mapa de origen (*De dónde sale cada frase*). |

---

## Las 4 pestañas principales

Todas las rutas reales definidas en `core/urls.py`:

1. **Espacio de Trabajo (`/`)**
   - Editor principal con selector progresivo (`Express`, `Guiado`, `Estudio Pro`) y atajo `Ctrl + Enter`.
   - **Detección en vivo** (`/api/analyze-live/`) mientras escribís: identifica área temática, tipo de tarea, entregable, restricciones negativas, contradicciones e insumos pegados (CSV, listas, código, trazas de error).
   - **Protección de privacidad (PII argentino):** detecta y permite anonimizar DNI/CUIL/CUIT, teléfonos, correos electrónicos, CBU y alias bancarios de forma sincronizada entre Python y JavaScript (`workspace.js`), excluyendo falsos positivos en números de facturas AFIP (`XXXX-XXXXXXXX`).
   - **Asistente Guiado y calidad (0–100):** preguntas contextuales de alto impacto, reglas rápidas en 1 clic, evaluación de *Datos útiles* y *Texto de relleno*, comparador **Antes vs. Después**, favoritos y exportación a `.MD` y `.JSON`.

2. **Plantillas (`/plantillas/`)**
   - Catálogo curado de **18 plantillas multivariadas en 6 categorías** (3 por categoría):
     - *Tecnología y Programación*
     - *Ciencia de Datos e IA*
     - *Negocios y Comercio*
     - *Estudio y Academia*
     - *Redacción y Comunicación*
     - *Carrera y Productividad*
   - Guía visual compacta en **3 pasos**, buscador en vivo y filtros instantáneos por categoría y modo 100 % *client-side* (`templates_gallery.js`).
   - Placeholders resaltados visualmente entre `[corchetes]`, micro-tip didáctico *"Por qué funciona:"*, copia rápida y carga inteligente en el Espacio de Trabajo activando automáticamente el modo recomendado.

3. **Mi Historial (`/historial/`) y Favoritos (`/favoritos/`)**
   - Registro automático en SQLite de cada prompt mejorado, con vista dedicada de favoritos (`/favoritos/`).
   - Filtros instantáneos por búsqueda de texto, área, estilo de respuesta y modo (`Express`, `Guiado`, `Estudio Pro`).
   - Etiquetas en lenguaje natural, badges unificados de modo y calidad (*Excelente*, *Muy bueno*, *Bueno*, *Mejorable*), indicador de *Privacidad protegida* y reutilización en 1 clic en el Espacio de Trabajo (`/?load=<id>`).

4. **Estadísticas y Datos (`/analitica/`)**
   - Dashboard interactivo **100 % offline** construido con **5 gráficos SVG nativos** en `analytics_charts.js` (cero Chart.js, cero CDNs), tooltips interactivos con soporte de teclado y actualización instantánea al alternar **Modo Oscuro / Modo Claro** (`themeChanged`):
     1. **Barras horizontales con eje numérico:** *¿Sobre qué temas consultás más?*
     2. **Dona interactiva con conmutador:** *¿Qué estilos y modos elegís más?* (*Estilos de respuesta* vs. *Modos de profundidad*).
     3. **Líneas con área sombreada:** *Evolución: Antes vs. Después* (últimos 10 prompts en orden cronológico, con soporte para el caso borde de 1 solo registro).
     4. **Barras verticales agrupadas (técnica/modo):** *¿Cuánto mejoran los prompts según la técnica elegida?* (con conmutador *Por técnica* / *Por modo*).
     5. **Barras verticales agrupadas por tarea:** *¿Cuánto mejoran los prompts según la tarea?*
   - **Barra segmentada 100 %** de distribución de calidad + 4 KPIs explicados en lenguaje claro + tarjeta **"Tu resumen rápido"** + filtro de período (`?periodo=all|30d|7d`) + consejos deterministas (*"Qué podés aprovechar mejor"*) + tabla de últimos 5 prompts evaluados.
   - Bloque de **Descubrimiento de Nuevos Temas (Bucle de Aprendizaje Offline)** mediante minería estadística *Log-Odds* y **Descarga de Dataset `.CSV` de 38 columnas** (`/analitica/exportar-csv/`).

### Endpoints auxiliares y API local

| Ruta | Propósito |
| :--- | :--- |
| `POST /api/analyze-live/` | Diagnóstico NLP en vivo sin persistir en base de datos. |
| `POST /api/improve/` | Compilación del prompt mejorado, evaluación de rúbrica y guardado en SQLite. |
| `POST /historial/favorito/<id>/` | Alterna el estado de favorito (soporta AJAX y formulario). |
| `POST /historial/eliminar/<id>/` | Elimina un registro del historial respetando la vista de origen (`next`). |
| `GET /analitica/exportar-csv/` | Exporta `promptlab_dataset.csv` en UTF-8 (BOM) con 38 columnas estructuradas. |

---

## Arquitectura técnica y estructura del proyecto

```text
Proyecto PromptLab/
├── manage.py
├── requirements.txt
├── README.md
├── PRD.md
├── CHANGELOG.md
├── promptlab/
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
└── core/
    ├── models.py                      # Modelo Prompt (telemetría NLP, rúbrica y privacidad)
    ├── views.py                       # Vistas, catálogo de 18 plantillas, agregaciones y APIs
    ├── urls.py                        # Rutas de las 4 pestañas, favoritos, CSV y API local
    ├── services.py                    # Pipeline NLP v7.2, rúbrica v2 no circular y PII
    ├── universal_engine.py            # Motor universal (21 arquetipos, inspector, cálculo y Log-Odds)
    ├── tests.py                       # 64 tests automatizados (10 suites)
    ├── rules/
    │   └── knowledge_base.json        # Base de conocimiento determinística 100 % offline
    ├── migrations/                    # Migraciones estables de SQLite (0001–0007)
    ├── templates/core/
    │   ├── base.html                  # Layout global, sidebar SVG, toggle de tema y cache-busting
    │   ├── workspace.html             # Espacio de Trabajo (3 modos progresivos)
    │   ├── templates_gallery.html     # Catálogo didáctico de 18 plantillas
    │   ├── history.html               # Mi Historial y Favoritos
    │   └── analytics.html             # Dashboard Estadísticas y Datos (5 gráficos SVG)
    └── static/
        ├── css/
        │   └── promptlab.css          # Sistema visual unificado con tokens --pl-* (Oscuro/Claro)
        ├── js/
        │   ├── workspace.js           # Interacción en vivo, PII client-side y carga de plantillas
        │   ├── templates_gallery.js   # Búsqueda, filtros dinámicos y sessionStorage
        │   └── analytics_charts.js    # 5 gráficos SVG interactivos 100 % offline
        └── vendor/                    # Assets locales offline (Bootstrap 5 y Bootstrap Icons)
```

### Principios de diseño e ingeniería

- **100 % Offline:** cero llamadas a APIs externas, cero fuentes remotas y cero CDNs (`test_offline_templates_have_no_external_urls` y `PromptLabSiteCoherenceTests` validan este invariante).
- **Sistema visual unificado (`?v=7.2.4`):** tokens CSS `--pl-*` en `promptlab.css` con soporte completo para **Modo Oscuro** (por defecto) y **Modo Claro**, encabezados `.pl-page-header`, badges de modo `.pl-mode-badge--*`, estados vacíos `.pl-empty-state` y cache-busting unificado en `?v=7.2.4`.
- **Contrato de lenguaje consistente:** toda la interfaz utiliza **voseo argentino claro y accesible** sin jerga interna expuesta, mientras que los prompts generados por el motor para pegar en otras IAs conservan **español neutro estándar**.
- **Dataset académico de 38 columnas (`promptlab_dataset.csv`):** incluye `id`, fecha, `engine_version`, categoría, acción y entregable detectados, sub-intención, nivel y técnica, puntajes inicial/aporte/final/ganancia, confianza y margen de intención, conteos de entidades/restricciones/slots, densidad informativa, cobertura de datos útiles y ruido, tipo de insumo, roles resueltos, ratio verificable, banderas de criterio de éxito/corrección/PII/favorito, métricas de longitud/expansión y textos original y mejorado.

---

## Instalación y ejecución local

Requisitos: **Python 3.10+** (entorno probado con Django 6.1.3 y SQLite) y **Node.js** opcional para validar sintaxis JS.

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
4. Aplicar migraciones (en instalaciones limpias):
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

## Verificación de calidad y suite de tests (64 tests)

Ejecutar desde la raíz del proyecto:

```bash
node --check core/static/js/workspace.js core/static/js/templates_gallery.js core/static/js/analytics_charts.js
./venv/bin/python manage.py check
./venv/bin/python manage.py makemigrations --check --dry-run
./venv/bin/python manage.py test -v 2
```

La suite actual cuenta con **64 tests en verde** distribuidos en 10 clases en `core/tests.py`:

- **`PromptLabServicesTests` (4):** sensibilidad de rúbrica, entradas cortas/triviales y combinaciones de niveles y técnicas.
- **`PromptLabViewsAndIntegrationTests` (13):** assets offline, rutas vacías, carga/preset, APIs `/api/improve/` y `/api/analyze-live/`, favoritos/eliminación por POST, CSV de 38 columnas, voseo/clíticos, PII, contradicciones y ausencia de URLs externas.
- **`PromptLabV5EngineTests` (5):** 5 casos dorados reales, linter anti-relleno, fidelidad sin bloques vacíos, caminos sugeridos y etiquetas simples en vistas.
- **`PromptLabV6UniversalEngineTests` (6):** 5 casos dorados del motor universal (precios a JSON, auditoría de cláusula, simulación WhatsApp, punto de equilibrio, ideación) + inspector, cálculo exacto y minería Log-Odds.
- **`PromptLabV7EngineAndWorkspaceTests` (7):** normalizador de clíticos, límites de entregables, calibración de confianza, *active learning* en SQLite, desambiguación/favorito AJAX, modos progresivos y regresión conceptual de Ciencia de Datos.
- **`PromptLabV72RegressionTests` (10):** suite dorada v7.2 (esquemas JSON, PII argentino Python/JS, traceback Python, comparativa técnica sin contaminación comercial, entrevistas, planes, minutas, scripts sin librerías externas y persistencia v7.2).
- **`PromptLabV721AuditRegressionTests` (6):** casos de auditoría real N1–N6 (analogías sin fórmulas, SQL sin falso público cliente, `guion_video`, exclusión de facturas AFIP en PII, pluralización/cache-busting y plan de estudio diario).
- **`PromptLabTemplatesCatalogTests` (3):** vista `/plantillas/` HTTP 200, validación de las 18 plantillas en 6 categorías con placeholders `[...]` y ejecución completa a través del motor + carga en Workspace.
- **`PromptLabStatsDashboardTests` (6):** estado vacío, dashboard poblado sin jerga cruda, filtrado real por período (`all`/`30d`/`7d`/inválido), período vacío con historial previo, payload JSON `analytics-chart-data` con 5 contenedores SVG y caso borde de 1 solo prompt.
- **`PromptLabSiteCoherenceTests` (4):** HTTP 200 en todas las pestañas (vacías y pobladas), cache-busting `?v=7.2.4` sin CDNs externos, cero jerga interna ni modos crudos en la UI y coherencia de `<title>` + `aria-current="page"`.

---

## Actualización en PythonAnywhere

Para desplegar cambios nuevos en una instancia ya configurada de **PythonAnywhere**:

1. Abrir una consola Bash en PythonAnywhere dentro del directorio del proyecto y traer los cambios:
   ```bash
   git pull origin master
   ```
2. Ejecutar migraciones **únicamente si el despliegue incluye archivos nuevos** en `core/migrations/`:
   ```bash
   ./venv/bin/python manage.py migrate
   ```
3. Si utilizás `collectstatic` en tu configuración de archivos estáticos, actualizar los estáticos:
   ```bash
   ./venv/bin/python manage.py collectstatic --noinput
   ```
4. Ir a la pestaña **Web** de PythonAnywhere y pulsar **Reload** para recargar la aplicación WSGI.
