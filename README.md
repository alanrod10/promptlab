# ✨ PromptLab Studio | DS & IA

**PromptLab** es un motor compilador determinístico de *prompts* 100% offline, desarrollado como proyecto de tesis para la Tecnicatura Superior en Ciencia de Datos e Inteligencia Artificial (IES N° 11). 

A diferencia de los generadores basados en plantillas, PromptLab utiliza un pipeline de Procesamiento de Lenguaje Natural (NLP) por reglas para diseccionar, estructurar y potenciar las instrucciones del usuario con cero dependencia de APIs externas o LLMs de terceros.

## 🚀 Características Principales

*   **Motor Universal (21 Arquetipos):** Clasifica la intención del usuario mediante un modelo híbrido (Reglas + TF-IDF) abordando desde *Data Science* hasta tareas de "cola larga" (auditorías, cálculos comerciales, simulaciones interactivas).
*   **100% Offline y Seguro:** Toda la lógica, detección de entidades y enmascaramiento de Datos Personales Sensibles (PII) ocurre localmente en Python. Interfaz construida con assets locales (Bootstrap 5, Chart.js).
*   **Filtro Anti-Relleno (Noise Ratio < 10%):** Garantiza que más del 90% de las líneas del prompt generado sean instrucciones operativas, anclas del usuario o criterios de éxito verificables.
*   **Inspector Estructural de Insumos:** Detecta y procesa automáticamente *payloads* pegados por el usuario (tablas CSV, JSON, logs de errores, cláusulas legales) extrayendo metadatos clave para inyectarlos en las instrucciones.
*   **Analítica de Datos Avanzada:** Registra telemetría en SQLite y exporta un dataset de 38 variables (Rúbrica v2, densidad informativa, confianza, factor de corrección del usuario) ideal para ingesta en Pandas o Scikit-Learn.

## ⚙️ Arquitectura Técnica

*   **Backend:** Python 3.10+, Django, SQLite.
*   **Motor NLP (`universal_engine.py`):** Etiquetado POS heurístico, análisis de roles semánticos, cálculo determinístico exacto (`Decimal`/`Fraction`) y minería estadística offline (Log-Odds).
*   **Frontend:** Vanilla JS, Tema Claro/Oscuro persistente por variables CSS, *Active Learning* vía chips editables en vivo.

## 💻 Instalación y Ejecución Local

1. Clonar el repositorio:
   `git clone https://github.com/alanrod10/promptlab.git`
2. Crear y activar entorno virtual:
   `python -m venv venv`
   `source venv/bin/activate` (En Windows: `venv\Scripts\activate`)
3. Instalar dependencias:
   `pip install -r requirements.txt`
4. Ejecutar el servidor:
   `python manage.py runserver 8001`
5. Abrir en el navegador: `http://127.0.0.1:8001/`
