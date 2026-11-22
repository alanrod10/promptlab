# Changelog — PromptLab

Todas las mejoras relevantes de **PromptLab** se documentan en este archivo.

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
