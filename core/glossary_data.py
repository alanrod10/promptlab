"""Catálogo curado y 100 % offline del Glosario IA de PromptLab."""

GLOSSARY_CATEGORIES = [
    "Lo básico para empezar",
    "Cómo pedir mejor",
    "Límites y cuidados",
    "Cómo funciona por dentro",
]

GLOSSARY_CATALOG = [
    # 1. Lo básico para empezar (5)
    {
        "slug": "token",
        "term": "Token",
        "tagline": "La unidad mínima que leen las IA",
        "category": "Lo básico para empezar",
        "level": "Inicial",
        "plain_definition": (
            "Es el pedacito de texto con el que trabaja un modelo de lenguaje: puede ser una palabra corta, "
            "una sílaba o un signo de puntuación. En español, 1 token equivale aproximadamente a ¾ de palabra."
        ),
        "analogy": (
            "Es como pagar un mensaje por bloques de sílabas: las palabras largas se parten en dos o tres "
            "fichas, y cada espacio o coma también suma."
        ),
        "example": (
            "La frase 'Hola, mundo' suele dividirse en 3 o 4 tokens ('Hola', ',', ' mun', 'do'). "
            "Un prompt sin relleno gasta menos tokens y deja lugar para una mejor respuesta."
        ),
        "in_promptlab": (
            "En el Espacio de Trabajo estimamos cuántos tokens consume tu prompt en ChatGPT, Gemini y Claude "
            "100 % offline antes de copiarlo."
        ),
        "related_url_name": "workspace",
    },
    {
        "slug": "ventana-de-contexto",
        "term": "Ventana de contexto (Context Window)",
        "tagline": "La memoria de corto plazo del chat",
        "category": "Lo básico para empezar",
        "level": "Inicial",
        "plain_definition": (
            "Es la cantidad máxima de tokens que la IA puede tener presentes al mismo tiempo entre tu pedido, "
            "los archivos que pegás y su propia respuesta. Si se llena, empieza a olvidar el principio de la charla."
        ),
        "analogy": (
            "Es como el tamaño de un escritorio: cuanto más grande sea, más apuntes podés tener abiertos a la vez "
            "sin que se caigan del borde."
        ),
        "example": (
            "Si pegás un apunte enorme de 120.000 tokens en un chat con límite de 128K, casi no queda espacio "
            "para que la IA redacte un resumen detallado."
        ),
        "in_promptlab": (
            "La tarjeta de consumo del Espacio de Trabajo te muestra qué porcentaje de la ventana (128K, 1M o 200K) "
            "ocupa tu prompt mejorado."
        ),
        "related_url_name": "workspace",
    },
    {
        "slug": "prompt",
        "term": "Prompt (Instrucción o pedido)",
        "tagline": "El pedido concreto que le hacés",
        "category": "Lo básico para empezar",
        "level": "Inicial",
        "plain_definition": (
            "Es el texto que le escribís a la inteligencia artificial para indicarle qué necesitás, con qué datos "
            "contás y cómo querés el resultado. Cuanto más claro es el prompt, más útil sale la respuesta."
        ),
        "analogy": (
            "Es como darle indicaciones a alguien que te ayuda por primera vez: si le decís 'haceme una nota', "
            "adivina; si le decís tema, tono y largo, acierta de una."
        ),
        "example": (
            "En vez de 'resumime esto', un buen prompt pide: 'Resumí este apunte en 5 puntos clave para estudiar "
            "un parcial, sin inventar datos que no estén en el texto'."
        ),
        "in_promptlab": (
            "Todo el Espacio de Trabajo transforma tu idea inicial en un prompt ordenado por secciones con rol, "
            "objetivo, formato y criterio de éxito."
        ),
        "related_url_name": "workspace",
    },
    {
        "slug": "llm",
        "term": "LLM / Modelo de Lenguaje",
        "tagline": "El cerebro estadístico detrás del chat",
        "category": "Lo básico para empezar",
        "level": "Inicial",
        "plain_definition": (
            "Son las siglas en inglés de Gran Modelo de Lenguaje: un sistema entrenado con enormes cantidades de "
            "texto para predecir y generar respuestas coherentes en lenguaje humano."
        ),
        "analogy": (
            "Es como un lector incansable que leyó millones de libros y artículos, y aprendió cómo continúan las "
            "ideas según el contexto que le das."
        ),
        "example": (
            "ChatGPT, Gemini y Claude son chats impulsados por distintos LLM que responden al mismo tipo de "
            "instrucciones claras y bien delimitadas."
        ),
        "in_promptlab": (
            "PromptLab prepara tus instrucciones 100 % offline para que funcionen mejor en cualquier LLM externo "
            "cuando copiás el resultado."
        ),
        "related_url_name": "workspace",
    },
    {
        "slug": "rol-o-system-prompt",
        "term": "Rol o System Prompt",
        "tagline": "El perfil experto que orienta respuestas",
        "category": "Lo básico para empezar",
        "level": "Inicial",
        "plain_definition": (
            "Es la indicación inicial que define desde qué oficio, criterio o nivel de detalle debe responder la IA. "
            "Fija las reglas de juego antes de abordar el pedido principal."
        ),
        "analogy": (
            "Es como pedirle consejo sobre un contrato a un abogado en lugar de preguntarle a un amigo al azar: "
            "el sombrero que se pone cambia el enfoque y el vocabulario."
        ),
        "example": (
            "'Actuá como docente de estadística que explica con ejemplos cotidianos y evita fórmulas técnicas' "
            "orienta toda la explicación desde la primera línea."
        ),
        "in_promptlab": (
            "Según tu pedido, el motor asigna automáticamente el bloque '# Rol' en los modos Guiado y Estudio Pro "
            "para encuadrar la respuesta."
        ),
        "related_url_name": "workspace",
    },
    # 2. Cómo pedir mejor (6)
    {
        "slug": "zero-shot",
        "term": "Zero-Shot / Pedido directo",
        "tagline": "Pedir una tarea sin mostrar ejemplos",
        "category": "Cómo pedir mejor",
        "level": "Inicial",
        "plain_definition": (
            "Consiste en darle a la IA la instrucción directa sin incluir casos de muestra previos. "
            "Funciona muy bien para tareas claras, resúmenes rápidos o preguntas cotidianas."
        ),
        "analogy": (
            "Es como pedirle a un cocinero conocido que prepare un plato clásico solo nombrándolo, sin tener que "
            "mostrarle una foto paso a paso."
        ),
        "example": (
            "'Escribime un mensaje cordial para pedirle a un proveedor 15 días más de plazo en una factura por "
            "falta de cobro, sin sonar desesperado'."
        ),
        "in_promptlab": (
            "El modo Express y la técnica Estándar generan prompts directos y livianos ideales para pedidos "
            "cotidianos sin ejemplos adicionales."
        ),
        "related_url_name": "workspace",
    },
    {
        "slug": "few-shot",
        "term": "Few-Shot / Con ejemplos",
        "tagline": "Enseñar el formato con muestras reales",
        "category": "Cómo pedir mejor",
        "level": "Intermedio",
        "plain_definition": (
            "Es incluir uno o más ejemplos concretos de 'Entrada → Salida' dentro del prompt para que la IA "
            "imite exactamente el estilo, tono o estructura que buscás."
        ),
        "analogy": (
            "Es como mostrarle dos planillas ya llenas a alguien nuevo antes de darle la tercera para que "
            "copie el criterio sin dudar."
        ),
        "example": (
            "'Entrada: venta anulada por error → Motivo: Corrección administrativa. Entrada: cliente sin saldo → "
            "Motivo: Rechazo de pago. Ahora clasificá: ...'"
        ),
        "in_promptlab": (
            "En Estudio Pro podés cargar tu propio caso en el campo 'Ejemplo Few-Shot' o elegir la técnica "
            "'Con Ejemplos Prácticos'."
        ),
        "related_url_name": "workspace",
    },
    {
        "slug": "chain-of-thought",
        "term": "Paso a paso / Chain-of-Thought",
        "tagline": "Dividir problemas complejos en etapas lógicas",
        "category": "Cómo pedir mejor",
        "level": "Intermedio",
        "plain_definition": (
            "Es pedirle al modelo que desarrolle su razonamiento en pasos ordenados antes de dar la conclusión final. "
            "Reduce errores en cuentas, lógica, código y diagnósticos."
        ),
        "analogy": (
            "Es como pedirle a alguien que muestre las cuentas intermedias en una hoja en lugar de tirar un "
            "resultado de memoria."
        ),
        "example": (
            "'Antes de dar la consulta SQL final, listá qué tablas se unen, qué columna las vincula y qué filtro "
            "se aplica en cada paso'."
        ),
        "in_promptlab": (
            "Podés activar la técnica 'Paso a Paso' en Estudio Pro para sumar instrucciones de desglose secuencial "
            "y verificación previa."
        ),
        "related_url_name": "workspace",
    },
    {
        "slug": "iteracion",
        "term": "Iteración y versionado",
        "tagline": "Mejorar tu pedido versión tras versión",
        "category": "Cómo pedir mejor",
        "level": "Inicial",
        "plain_definition": (
            "Es refinar un prompt en rondas sucesivas: probás una primera versión, detectás qué faltó y ajustás "
            "contexto, tono o restricciones guardando cada avance."
        ),
        "analogy": (
            "Es como corregir un borrador de carta: la primera versión ordena la idea y la segunda pule los "
            "detalles para que no quede nada suelto."
        ),
        "example": (
            "Pasar de v1 en Express ('Explicar SQL JOIN') a v2 en Guiado sumando ejemplos de tablas y a v3 "
            "agregando casos borde."
        ),
        "in_promptlab": (
            "Desde el botón 'Iterar nueva versión' y en Mi Historial podés encadenar versiones v1 → v2 → v3 con "
            "notas de cambio y evolución de puntaje."
        ),
        "related_url_name": "history",
    },
    {
        "slug": "delimitadores",
        "term": "Delimitadores de datos",
        "tagline": "Fronteras claras entre orden e insumo",
        "category": "Cómo pedir mejor",
        "level": "Inicial",
        "plain_definition": (
            "Son marcas visuales (como etiquetas, comillas triples o bloques separados) que le indican a la IA "
            "dónde empieza y termina el texto o código que tiene que procesar."
        ),
        "analogy": (
            "Es como poner un recuadro o un clip alrededor de un documento adjunto para que no se mezcle con "
            "tu nota de instrucciones."
        ),
        "example": (
            "Encerrar un CSV o un correo largo entre etiquetas <datos_entrada> ... </datos_entrada> evita que "
            "el modelo confunda frases del texto con órdenes nuevas."
        ),
        "in_promptlab": (
            "Cuando pegás código, tablas, CSV o mensajes largos, PromptLab envuelve automáticamente tu material "
            "en bloques <datos_entrada> limpios."
        ),
        "related_url_name": "workspace",
    },
    {
        "slug": "marcadores-completar",
        "term": "Marcadores [COMPLETAR]",
        "tagline": "Huecos visibles para tus datos reales",
        "category": "Cómo pedir mejor",
        "level": "Inicial",
        "plain_definition": (
            "Son espacios resaltados entre corchetes que indican exactamente qué dato real tenés que escribir vos "
            "antes de enviar el prompt a una IA externa, evitando que invente cifras."
        ),
        "analogy": (
            "Son como las líneas punteadas de un formulario: te muestran de un vistazo qué casillero falta "
            "llenar con tu nombre, fecha o monto."
        ),
        "example": (
            "'Redactar nota dirigida a [nombre del organismo] por el expediente [número de trámite] del día "
            "[fecha]' deja claro qué falta personalizar."
        ),
        "in_promptlab": (
            "Las 18 Plantillas curadas destacan tus huecos entre [corchetes] y el Espacio de Trabajo te avisa si "
            "quedaron datos pendientes por llenar."
        ),
        "related_url_name": "templates_gallery",
    },
    # 3. Límites y cuidados (4)
    {
        "slug": "alucinacion",
        "term": "Alucinación (Hallucination)",
        "tagline": "Cuando la IA inventa con seguridad",
        "category": "Límites y cuidados",
        "level": "Inicial",
        "plain_definition": (
            "Ocurre cuando un modelo de lenguaje fabrica datos, citas, leyes, cifras o nombres que suenan "
            "convincentes, pero no son reales ni estaban en el material que le pasaste."
        ),
        "analogy": (
            "Es como alguien que no recuerda una fecha en un examen y, en vez de decir 'no sé', improvisa una "
            "historia muy segura para llenar el silencio."
        ),
        "example": (
            "Pedir un resumen de un apunte sin restricciones y que la IA agregue definiciones o artículos "
            "legales que nunca aparecían en tu texto original."
        ),
        "in_promptlab": (
            "PromptLab incorpora cláusulas de fidelidad y la técnica 'Con Control de Calidad' para exigir que la "
            "IA no invente datos fuera de tu insumo."
        ),
        "related_url_name": "workspace",
    },
    {
        "slug": "datos-sensibles-pii",
        "term": "Datos sensibles / PII",
        "tagline": "Información privada que conviene resguardar siempre",
        "category": "Límites y cuidados",
        "level": "Inicial",
        "plain_definition": (
            "PII significa Información Personal Identificable: datos como DNI, CUIL/CUIT, teléfonos, correos "
            "electrónicos, CBU o alias bancarios que identifican a una persona real."
        ),
        "analogy": (
            "Es como tapar con marcador negro el DNI y el teléfono de una factura antes de mostrarla como "
            "ejemplo en una clase o subirla a internet."
        ),
        "example": (
            "Antes de pedirle a una IA que redacte una nota oficial, conviene cambiar '27-34567890-4' por "
            "'[DNI_CUIL_OCULTO]' y dejar intactos los números de comprobante."
        ),
        "in_promptlab": (
            "PromptLab detecta y anonimiza automáticamente PII argentino en vivo (respetando montos y facturas "
            "AFIP) y muestra el Sello de Privacidad verificada."
        ),
        "related_url_name": "workspace",
    },
    {
        "slug": "sesgo",
        "term": "Sesgo / Bias",
        "tagline": "Inclinaciones heredadas de textos de entrenamiento",
        "category": "Límites y cuidados",
        "level": "Intermedio",
        "plain_definition": (
            "Es la tendencia de un modelo a repetir estereotipos, suposiciones culturales o preferencias de los "
            "textos con los que fue entrenado, especialmente si el pedido es ambiguo."
        ),
        "analogy": (
            "Es como pedir opiniones preguntando solo en un barrio: aunque la respuesta parezca general, refleja "
            "las costumbres de ese grupo."
        ),
        "example": (
            "Si pedís 'evaluar dos candidatos' sin criterios objetivos, la IA puede favorecer estilos de redacción "
            "o suponer datos que no evaluaste."
        ),
        "in_promptlab": (
            "Las Plantillas curadas y los criterios de evaluación piden pautas explícitas y restricciones claras "
            "para reducir suposiciones implícitas."
        ),
        "related_url_name": "templates_gallery",
    },
    {
        "slug": "temperatura",
        "term": "Temperatura y creatividad (Temperature)",
        "tagline": "El dial entre precisión y variedad",
        "category": "Límites y cuidados",
        "level": "Intermedio",
        "plain_definition": (
            "Es un parámetro de los modelos de lenguaje que controla qué tan predecibles o variadas son las "
            "palabras elegidas: baja para datos y código; más alta para lluvia de ideas."
        ),
        "analogy": (
            "Es como cocinar siguiendo la receta al gramo (temperatura baja) frente a improvisar con nuevos "
            "condimentos (temperatura alta)."
        ),
        "example": (
            "Para extraer fechas de una factura conviene respuesta exacta y sobria; para crear nombres de "
            "emprendimiento conviene mayor variedad creativa."
        ),
        "in_promptlab": (
            "Aunque la temperatura se ajusta en el chat externo, los modos Express, Guiado y Estudio Pro adaptan "
            "el nivel de precisión y control según tu tarea."
        ),
        "related_url_name": "workspace",
    },
    # 4. Cómo funciona por dentro (3)
    {
        "slug": "nlp",
        "term": "Procesamiento de Lenguaje Natural / NLP",
        "tagline": "Cómo las computadoras analizan nuestro idioma",
        "category": "Cómo funciona por dentro",
        "level": "Intermedio",
        "plain_definition": (
            "Es la rama de la Ciencia de Datos e IA dedicada a que un programa entienda, normalice y clasifique "
            "texto humano escrito en lenguaje cotidiano, con modismos y sinónimos."
        ),
        "analogy": (
            "Es como tener un traductor rápido que lee tu mensaje coloquial, identifica qué verbo pedís, qué "
            "tema tratás y arma una ficha ordenada."
        ),
        "example": (
            "Reconocer que 'armame un script' y 'necesito programar un código' apuntan a la misma tarea, aun "
            "cuando usen voseo argentino o palabras distintas."
        ),
        "in_promptlab": (
            "El motor híbrido local combina reglas transparentes en español con un clasificador probabilístico "
            "Naive Bayes para detectar dominio, acción y entregable en vivo."
        ),
        "related_url_name": "workspace",
    },
    {
        "slug": "validacion-cruzada",
        "term": "Validación cruzada 5-Fold",
        "tagline": "Examen justo en cinco rondas independientes",
        "category": "Cómo funciona por dentro",
        "level": "Intermedio",
        "plain_definition": (
            "Es una técnica estadística para evaluar modelos dividiendo los datos en 5 grupos iguales: en cada "
            "ronda se entrena con 4 grupos y se evalúa con el grupo restante sin verlo antes."
        ),
        "analogy": (
            "Es como evaluar a un estudiante con cinco exámenes distintos sobre temas que no practicó de memoria "
            "la noche anterior, promediando todas las notas."
        ),
        "example": (
            "Sobre 60 casos curados de prueba, en cada vuelta 48 ejemplos sirven de referencia y 12 se evalúan "
            "a ciegas hasta cubrir los 60."
        ),
        "in_promptlab": (
            "En Estadísticas y Datos podés consultar el Benchmark 5-Fold Offline y la validación repetida 10×5 "
            "que comparan el motor base frente al híbrido."
        ),
        "related_url_name": "analytics",
    },
    {
        "slug": "matriz-confusion-f1",
        "term": "Matriz de confusión y F1-Score",
        "tagline": "El mapa exacto de aciertos y confusiones",
        "category": "Cómo funciona por dentro",
        "level": "Intermedio",
        "plain_definition": (
            "La matriz de confusión es una tabla que cruza lo esperado contra lo predicho por el sistema; el "
            "F1-Score resume en un único número el equilibrio entre precisión y aciertos encontrados."
        ),
        "analogy": (
            "Es como una tabla de tiro al blanco donde la diagonal muestra los aciertos perfectos y las casillas "
            "de afuera muestran qué objetivo se confundió con otro."
        ),
        "example": (
            "Permite ver si un pedido de 'analizar datos' se clasificó bien o se confundió con 'generar código', "
            "y medir la mejora real tras el desempate."
        ),
        "in_promptlab": (
            "En la sección científica de Estadísticas y Datos podés desplegar la Matriz de Confusión 10 × 10, "
            "las métricas por clase y la auditoría caso por caso."
        ),
        "related_url_name": "analytics",
    },
]
