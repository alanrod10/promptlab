"""
Evaluación Científica NLP + Clasificador Probabilístico Multinomial Naive Bayes
+ Capa Supervisada de Active Learning (Overlay) en Python puro (PromptLab v8.0.1).

100 % biblioteca estándar de Python (sin scikit-learn, numpy ni dependencias externas).
"""

from collections import Counter
import json
import logging
import math
from pathlib import Path
import random
import re
import statistics
import time
from typing import Any, Dict, List, Optional, Tuple
import unicodedata

logger = logging.getLogger(__name__)

BENCHMARK_DATASET_PATH = Path(__file__).resolve().parent / "rules" / "benchmark_dataset.json"
KB_PATH = Path(__file__).resolve().parent / "rules" / "knowledge_base.json"

HYBRID_CONF_THRESHOLD = 0.45
HYBRID_MARGIN_CONF_CEILING = 0.58
HYBRID_MARGIN_THRESHOLD = 0.08
HYBRID_NB_MIN_CONF = 0.55

ALLOWED_SHORT_DOMAIN_TOKENS = {"ia", "ml", "bi", "cv", "tp", "db", "bd", "ui", "ux"}

SPANISH_NB_STOPWORDS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al",
    "a", "en", "con", "por", "para", "sobre", "entre", "hacia", "desde", "y",
    "o", "u", "e", "que", "como", "cual", "este", "esta", "estos", "estas",
    "ese", "esa", "mi", "tu", "su", "mis", "tus", "sus", "me", "te", "se",
    "nos", "lo", "le", "les", "es", "son", "ser", "estan", "muy", "mas",
    "menos", "pero", "si", "no", "sin", "che", "asi", "todo", "toda", "todos",
    "hay", "tengo", "necesito", "quiero", "hace", "hacer", "algo", "alguna",
    "algun", "cuando", "donde",
}

ACTION_LABELS_ES: Dict[str, str] = {
    "depurar_error": "Depurar error",
    "generar_codigo": "Generar código",
    "analizar_datos": "Analizar datos",
    "comparar_evaluar": "Comparar y evaluar",
    "resumir_sintetizar": "Resumir y sintetizar",
    "planificar_pasos": "Planificar pasos",
    "redactar_contenido": "Redactar contenido",
    "explicar_concepto": "Explicar concepto",
    "transformar_formato": "Transformar formato",
    "extraer_informacion": "Extraer información",
    "clasificar_categorizar": "Clasificar y categorizar",
    "traducir_adaptar": "Traducir y adaptar",
    "reescribir_mejorar": "Reescribir y mejorar",
    "auditar_criticar": "Revisar riesgos",
    "simular_practicar": "Simular diálogo",
    "idear_alternativas": "Idear alternativas",
    "calcular_modelar": "Calcular escenarios",
    "razonar_resolver": "Resolver problema lógico",
    "decidir_recomendar": "Evaluar y recomendar",
    "diagnosticar_resolver": "Diagnosticar fallas",
    "consultar_dato": "Consulta directa",
}

ACTION_SHORT_LABELS_ES: Dict[str, str] = {
    "analizar_datos": "Analizar",
    "auditar_criticar": "Auditar",
    "calcular_modelar": "Calcular",
    "clasificar_categorizar": "Clasificar",
    "comparar_evaluar": "Comparar",
    "consultar_dato": "Consultar",
    "decidir_recomendar": "Decidir",
    "depurar_error": "Depurar",
    "diagnosticar_resolver": "Diagnóstico",
    "explicar_concepto": "Explicar",
    "extraer_informacion": "Extraer",
    "generar_codigo": "Código",
    "idear_alternativas": "Idear",
    "planificar_pasos": "Planificar",
    "razonar_resolver": "Razonar",
    "redactar_contenido": "Redactar",
    "reescribir_mejorar": "Pulir",
    "resumir_sintetizar": "Resumir",
    "simular_practicar": "Simular",
    "traducir_adaptar": "Traducir",
    "transformar_formato": "Transformar",
}

_BENCHMARK_CACHE: Dict[str, Any] = {
    "key": None,
    "result": None,
}
_PRODUCTION_NB_CACHE: Dict[str, Any] = {
    "key": None,
    "clf": None,
}
_OVERLAY_RULES_CACHE: Dict[str, Any] = {
    "ts": 0.0,
    "data": None,
}
_OVERLAY_RULES_CACHE_TTL = 10.0


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def normalize_learning_term(raw_term: str) -> str:
    """Normaliza un término o bigrama candidato en minúsculas y sin tildes."""
    cleaned = _strip_accents((raw_term or "").lower())
    tokens = re.findall(r"[a-z0-9_]+", cleaned)
    return " ".join(tokens)[:100]


def _light_stem_spanish(token: str) -> str:
    for clitic in (
        "melo", "mela", "noslo", "nosla", "arme", "irme", "erme",
        "ame", "eme", "ime", "ate", "ete", "ite", "alo", "ala",
    ):
        if len(token) > len(clitic) + 2 and token.endswith(clitic):
            token = token[: -len(clitic)]
            break
    for suffix in (
        "aciones", "iciones", "amiento", "imiento", "ando", "iendo",
        "aron", "ieron", "ado", "ido", "ar", "er", "ir", "es", "s",
    ):
        if len(token) - len(suffix) >= 4 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def tokenize_spanish_unigrams(text: str, stem: bool = True) -> List[str]:
    """Extrae unigramas en español preservando siglas técnicas relevantes de 2 letras."""
    norm = _strip_accents((text or "").lower())
    raw_tokens = re.findall(r"[a-z0-9]+", norm)
    tokens: List[str] = []
    for tok in raw_tokens:
        if tok.isdigit() or tok in SPANISH_NB_STOPWORDS:
            continue
        if len(tok) > 2 or tok in ALLOWED_SHORT_DOMAIN_TOKENS:
            tokens.append(_light_stem_spanish(tok) if stem else tok)
    return tokens


def tokenize_spanish(text: str) -> List[str]:
    """
    Tokenización en español: minúsculas, normalización de tildes, filtrado de
    stopwords básicas, stemming ligero y extracción de unigramas y bigramas.
    """
    unigrams = tokenize_spanish_unigrams(text, stem=True)
    bigrams = [f"{unigrams[i]}_{unigrams[i + 1]}" for i in range(len(unigrams) - 1)]
    return unigrams + bigrams


class MultinomialNaiveBayesClassifier:
    """
    Clasificador probabilístico Multinomial Naive Bayes en Python puro con
    suavizado de Laplace (alpha=1.0) y normalización log-sum-exp.
    """

    def __init__(self, alpha: float = 1.0):
        self.alpha = float(alpha)
        self.classes: List[str] = []
        self.class_log_prior: Dict[str, float] = {}
        self.feature_counts: Dict[str, Counter] = {}
        self.class_totals: Dict[str, int] = {}
        self.vocab: set = set()

    def fit(self, texts: List[str], labels: List[str]) -> "MultinomialNaiveBayesClassifier":
        doc_counts = Counter(labels)
        total_docs = max(len(labels), 1)
        self.classes = sorted(doc_counts.keys())
        self.feature_counts = {c: Counter() for c in self.classes}
        self.class_totals = {c: 0 for c in self.classes}
        self.vocab = set()

        for text, label in zip(texts, labels):
            feats = tokenize_spanish(text)
            self.feature_counts[label].update(feats)
            self.class_totals[label] += len(feats)
            self.vocab.update(feats)

        self.class_log_prior = {
            c: math.log(doc_counts[c] / total_docs)
            for c in self.classes
        }
        return self

    def predict_proba(self, text: str) -> Tuple[str, float, float, Dict[str, float]]:
        if not self.classes:
            return "explicar_concepto", 0.0, 0.0, {}

        feats = tokenize_spanish(text)
        vocab_size = max(len(self.vocab), 1)
        log_scores: Dict[str, float] = {}

        for c in self.classes:
            denom = self.class_totals[c] + self.alpha * vocab_size
            lp = self.class_log_prior[c]
            fc = self.feature_counts[c]
            for feat in feats:
                if feat in self.vocab:
                    lp += math.log((fc[feat] + self.alpha) / denom)
            log_scores[c] = lp

        max_lp = max(log_scores.values())
        exp_sum = sum(math.exp(val - max_lp) for val in log_scores.values())
        log_norm = max_lp + math.log(exp_sum)
        scores = {c: round(math.exp(val - log_norm), 6) for c, val in log_scores.items()}

        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        best_label, best_prob = ranked[0]
        second_prob = ranked[1][1] if len(ranked) > 1 else 0.0
        margin = max(best_prob - second_prob, 0.0)
        return best_label, round(best_prob, 4), round(margin, 4), scores


def invalidate_scientific_cache() -> None:
    """Invalida caché del benchmark, del Naive Bayes de producción y de la capa overlay."""
    _BENCHMARK_CACHE["key"] = None
    _BENCHMARK_CACHE["result"] = None
    _PRODUCTION_NB_CACHE["key"] = None
    _PRODUCTION_NB_CACHE["clf"] = None
    _OVERLAY_RULES_CACHE["ts"] = 0.0
    _OVERLAY_RULES_CACHE["data"] = None


def get_active_overlay_rules(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """
    Lee las reglas activas de la capa overlay (`ActiveLearningRule`) desde SQLite
    con caché en memoria de TTL 10 s (invalidada por `invalidate_scientific_cache()`).
    """
    try:
        from django.apps import apps
        if not apps.ready:
            return []

        now = time.monotonic()
        if (
            not force_refresh
            and _OVERLAY_RULES_CACHE["data"] is not None
            and (now - _OVERLAY_RULES_CACHE["ts"]) < _OVERLAY_RULES_CACHE_TTL
        ):
            return _OVERLAY_RULES_CACHE["data"]

        from .models import ActiveLearningRule

        qs = ActiveLearningRule.objects.filter(is_active=True).order_by("id")
        rules = [
            {
                "id": r.id,
                "term": normalize_learning_term(r.term),
                "raw_term": r.term,
                "target_action": r.target_action,
                "target_category": r.target_category or "",
                "source_z_score": float(r.source_z_score or 0.0),
            }
            for r in qs
            if r.term and r.target_action
        ]
        _OVERLAY_RULES_CACHE["ts"] = now
        _OVERLAY_RULES_CACHE["data"] = rules
        return rules
    except Exception as exc:
        logger.warning("No se pudo leer ActiveLearningRule de SQLite: %s", exc)
        return []


def match_overlay_rules(
    raw_text: str,
    normalized_text: str,
    overlay_rules: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[Dict[str, float], Dict[str, float], List[Dict[str, Any]]]:
    """
    Evalúa reglas activas de Active Learning (overlay) sobre el texto del pedido
    sin mutar knowledge_base.json. Devuelve boosts por acción, por dominio y trazas.
    """
    rules = get_active_overlay_rules() if overlay_rules is None else overlay_rules
    if not rules:
        return {}, {}, []

    raw_norm = _strip_accents((raw_text or "").lower())
    raw_norm_clean = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9_]+", " ", raw_norm)).strip()
    norm_clean = re.sub(r"\s+", " ", (normalized_text or "").lower()).strip()

    action_boosts: Dict[str, float] = {}
    domain_boosts: Dict[str, float] = {}
    traces: List[Dict[str, Any]] = []

    for rule in rules:
        term = normalize_learning_term(rule.get("term", ""))
        target_action = (rule.get("target_action") or "").strip()
        target_category = (rule.get("target_category") or "").strip()
        if not term or not target_action:
            continue

        pattern = rf"(?<![a-z0-9_]){re.escape(term)}(?![a-z0-9_])"
        matched = bool(re.search(pattern, raw_norm_clean) or re.search(pattern, norm_clean))
        if not matched:
            continue

        step_boost = 0.44 if " " in term else 0.38
        action_boosts[target_action] = round(
            min(action_boosts.get(target_action, 0.0) + step_boost, 0.52),
            4,
        )
        if target_category and target_category != "Otro / General":
            domain_boosts[target_category] = round(
                min(domain_boosts.get(target_category, 0.0) + 0.35, 0.45),
                4,
            )

        display_term = rule.get("raw_term") or term
        traces.append({
            "stage": "active_learning_overlay",
            "term": display_term,
            "target_action": target_action,
            "target_category": target_category,
            "rule": f"Capa Active Learning v8.0: término '{display_term}' → acción '{target_action}'",
        })

    return action_boosts, domain_boosts, traces


def load_benchmark_dataset(dataset_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = dataset_path or BENCHMARK_DATASET_PATH
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError("benchmark_dataset.json debe ser una lista de casos.")
    return data


def _load_kb_actions_prototypes() -> Tuple[List[str], List[str], int]:
    if not KB_PATH.exists():
        return [], [], 0
    with open(KB_PATH, "r", encoding="utf-8") as fh:
        kb = json.load(fh)
    actions = kb.get("actions", {})
    texts: List[str] = []
    labels: List[str] = []
    for act_key, cfg in actions.items():
        for proto in cfg.get("prototypes", []):
            if isinstance(proto, str) and proto.strip():
                texts.append(proto.strip())
                labels.append(act_key)
    return texts, labels, len(actions)


def get_production_nb_classifier() -> MultinomialNaiveBayesClassifier:
    """
    Entrena (y cachea en memoria) el clasificador Naive Bayes auxiliar de producción
    combinando los 126 prototipos de las 21 acciones de `knowledge_base.json` con los
    60 casos de `benchmark_dataset.json`, sin inyectar reglas de SQLite.
    """
    bm_mtime = BENCHMARK_DATASET_PATH.stat().st_mtime if BENCHMARK_DATASET_PATH.exists() else 0.0
    kb_mtime = KB_PATH.stat().st_mtime if KB_PATH.exists() else 0.0
    cache_key = (bm_mtime, kb_mtime)

    if _PRODUCTION_NB_CACHE["key"] == cache_key and _PRODUCTION_NB_CACHE["clf"] is not None:
        return _PRODUCTION_NB_CACHE["clf"]

    texts, labels, _ = _load_kb_actions_prototypes()
    if BENCHMARK_DATASET_PATH.exists():
        for case in load_benchmark_dataset():
            texts.append(case["text"])
            labels.append(case["expected_action"])

    clf = MultinomialNaiveBayesClassifier(alpha=1.0).fit(texts, labels)
    _PRODUCTION_NB_CACHE["key"] = cache_key
    _PRODUCTION_NB_CACHE["clf"] = clf
    return clf


def is_low_certainty_decision(
    det_confidence: float,
    det_margin: float,
    word_count: Optional[int] = None,
    is_trivial: bool = False,
    conf_threshold: float = HYBRID_CONF_THRESHOLD,
    margin_conf_ceiling: float = HYBRID_MARGIN_CONF_CEILING,
    margin_threshold: float = HYBRID_MARGIN_THRESHOLD,
) -> bool:
    """Regla única de gating para habilitar desempate probabilístico en baja certeza."""
    is_short_trivial = is_trivial or (word_count is not None and word_count < 3)
    if is_short_trivial:
        return False
    return (
        det_confidence < conf_threshold
        or (det_confidence < margin_conf_ceiling and det_margin < margin_threshold)
    )


def classify_hybrid_action(
    text: str,
    det_action: str,
    det_confidence: float,
    det_margin: float,
    nb_classifier: Optional[MultinomialNaiveBayesClassifier] = None,
    conf_threshold: float = HYBRID_CONF_THRESHOLD,
    margin_threshold: float = HYBRID_MARGIN_THRESHOLD,
    nb_min_conf: float = HYBRID_NB_MIN_CONF,
    word_count: Optional[int] = None,
    is_trivial: bool = False,
) -> Dict[str, Any]:
    """
    Arquitectura híbrida condicionada a evidencia:
    - El motor determinístico es el carril principal de Caja Blanca.
    - Naive Bayes interviene ÚNICAMENTE en baja certeza o margen estrecho
      cuando supera el umbral verificado `nb_min_conf`.
    """
    is_low_certainty = is_low_certainty_decision(
        det_confidence=det_confidence,
        det_margin=det_margin,
        word_count=word_count,
        is_trivial=is_trivial,
        conf_threshold=conf_threshold,
        margin_threshold=margin_threshold,
    )

    if not is_low_certainty:
        return {
            "final_action": det_action,
            "final_confidence": det_confidence,
            "used_nb": False,
            "is_low_certainty": False,
            "nb_action": None,
            "nb_confidence": 0.0,
            "nb_margin": 0.0,
        }

    clf = nb_classifier or get_production_nb_classifier()
    nb_label, nb_conf, nb_margin, _ = clf.predict_proba(text)

    if nb_conf >= nb_min_conf:
        calibrated_conf = round(max(det_confidence, min(0.84, 0.50 + 0.35 * nb_conf)), 3)
        return {
            "final_action": nb_label,
            "final_confidence": calibrated_conf,
            "used_nb": True,
            "is_low_certainty": True,
            "nb_action": nb_label,
            "nb_confidence": nb_conf,
            "nb_margin": nb_margin,
        }

    return {
        "final_action": det_action,
        "final_confidence": det_confidence,
        "used_nb": False,
        "is_low_certainty": True,
        "nb_action": nb_label,
        "nb_confidence": nb_conf,
        "nb_margin": nb_margin,
    }


def build_stratified_folds(
    cases: List[Dict[str, Any]],
    n_splits: int = 5,
    seed: int = 42,
) -> List[List[int]]:
    """
    Construye particiones estratificadas balanceadas (12 casos por fold sobre 60)
    barajando cada clase con semilla fija y rotando el desplazamiento por clase.
    """
    by_class: Dict[str, List[int]] = {}
    for idx, case in enumerate(cases):
        by_class.setdefault(case["expected_action"], []).append(idx)

    rng = random.Random(seed)
    folds: List[List[int]] = [[] for _ in range(n_splits)]
    for cls_idx, cls_name in enumerate(sorted(by_class.keys())):
        items = list(by_class[cls_name])
        rng.shuffle(items)
        for offset, idx in enumerate(items):
            folds[(cls_idx + offset) % n_splits].append(idx)
    for fold in folds:
        fold.sort()
    return folds


def wilson_ci_95(successes: int, total: int) -> Tuple[float, float]:
    """Intervalo de confianza del 95 % de Wilson en porcentaje (z = 1.959964)."""
    if total <= 0:
        return 0.0, 0.0
    z = 1.959964
    p = successes / total
    z2 = z * z
    denom = 1.0 + z2 / total
    center = (p + z2 / (2.0 * total)) / denom
    half = (z * math.sqrt((p * (1.0 - p) + z2 / (4.0 * total)) / total)) / denom
    low = max(0.0, (center - half) * 100.0)
    high = min(100.0, (center + half) * 100.0)
    return round(low, 1), round(high, 1)


def mcnemar_exact_p_value(b_rescued: int, c_regressions: int) -> float:
    """
    Test exacto de McNemar (prueba binomial bilateral sobre pares discordantes b y c).
    """
    n = b_rescued + c_regressions
    if n <= 0:
        return 1.0
    k = min(b_rescued, c_regressions)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return round(min(1.0, 2.0 * tail), 4)


def compute_max_intra_class_jaccard(cases: List[Dict[str, Any]]) -> float:
    """Calcula la similitud Jaccard máxima de unigramas sin stopwords dentro de cada clase."""
    by_class: Dict[str, List[set]] = {}
    for case in cases:
        tokens = set(tokenize_spanish_unigrams(case.get("text", ""), stem=False))
        by_class.setdefault(case["expected_action"], []).append(tokens)

    max_jaccard = 0.0
    for token_sets in by_class.values():
        for i in range(len(token_sets)):
            for j in range(i + 1, len(token_sets)):
                union = token_sets[i] | token_sets[j]
                if not union:
                    continue
                jacc = len(token_sets[i] & token_sets[j]) / len(union)
                if jacc > max_jaccard:
                    max_jaccard = jacc
    return round(max_jaccard, 3)


def _compute_classification_metrics(
    y_true: List[str],
    y_pred: List[str],
    classes: List[str],
) -> Dict[str, Any]:
    total = max(len(y_true), 1)
    idx_map = {cls_name: i for i, cls_name in enumerate(classes)}
    k = len(classes)
    matrix = [[0 for _ in range(k)] for _ in range(k)]

    for t_lbl, p_lbl in zip(y_true, y_pred):
        if t_lbl in idx_map and p_lbl in idx_map:
            matrix[idx_map[t_lbl]][idx_map[p_lbl]] += 1

    diagonal_sum = sum(matrix[i][i] for i in range(k))
    correct_count = sum(1 for t_lbl, p_lbl in zip(y_true, y_pred) if t_lbl == p_lbl)
    accuracy = correct_count / total
    ci_low_pct, ci_high_pct = wilson_ci_95(correct_count, len(y_true))

    per_class: List[Dict[str, Any]] = []
    precisions: List[float] = []
    recalls: List[float] = []
    f1s: List[float] = []
    supports: List[int] = []

    for cls_name in classes:
        tp = sum(1 for t_lbl, p_lbl in zip(y_true, y_pred) if t_lbl == cls_name and p_lbl == cls_name)
        fp = sum(1 for t_lbl, p_lbl in zip(y_true, y_pred) if t_lbl != cls_name and p_lbl == cls_name)
        fn = sum(1 for t_lbl, p_lbl in zip(y_true, y_pred) if t_lbl == cls_name and p_lbl != cls_name)
        support = tp + fn

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2.0 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

        precisions.append(prec)
        recalls.append(rec)
        f1s.append(f1)
        supports.append(support)

        per_class.append({
            "class_key": cls_name,
            "label": ACTION_LABELS_ES.get(cls_name, cls_name.replace("_", " ").capitalize()),
            "short_label": ACTION_SHORT_LABELS_ES.get(cls_name, cls_name[:10]),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "precision_pct": round(prec * 100.0, 1),
            "recall_pct": round(rec * 100.0, 1),
            "f1_pct": round(f1 * 100.0, 1),
            "support": support,
        })

    macro_precision = statistics.fmean(precisions) if precisions else 0.0
    macro_recall = statistics.fmean(recalls) if recalls else 0.0
    macro_f1 = statistics.fmean(f1s) if f1s else 0.0
    total_support = max(sum(supports), 1)
    weighted_f1 = sum(f * s for f, s in zip(f1s, supports)) / total_support

    return {
        "accuracy": round(accuracy, 4),
        "macro_precision": round(macro_precision, 4),
        "macro_recall": round(macro_recall, 4),
        "macro_f1": round(macro_f1, 4),
        "weighted_f1": round(weighted_f1, 4),
        "accuracy_pct": round(accuracy * 100.0, 1),
        "macro_precision_pct": round(macro_precision * 100.0, 1),
        "macro_recall_pct": round(macro_recall * 100.0, 1),
        "macro_f1_pct": round(macro_f1 * 100.0, 1),
        "weighted_f1_pct": round(weighted_f1 * 100.0, 1),
        "accuracy_ci_low_pct": ci_low_pct,
        "accuracy_ci_high_pct": ci_high_pct,
        "per_class": per_class,
        "confusion_matrix": {
            "classes": classes,
            "labels": [ACTION_LABELS_ES.get(c, c) for c in classes],
            "short_labels": [ACTION_SHORT_LABELS_ES.get(c, c[:10]) for c in classes],
            "matrix": matrix,
            "diagonal_sum": diagonal_sum,
            "total": len(y_true),
        },
    }


def _format_pp_diff(diff_pp: float) -> Tuple[str, str]:
    rounded = round(diff_pp, 1)
    if rounded > 0:
        return f"+{rounded:.1f}".replace(".", ",") + " pp", "positive"
    if rounded < 0:
        return f"{rounded:.1f}".replace(".", ",") + " pp", "negative"
    return "= 0,0 pp", "neutral"


def _heat_class(val: int, is_diag: bool, row_total: int) -> str:
    if val == 0:
        return "pl-cm-cell--zero"
    ratio = val / max(row_total, 1)
    if is_diag:
        return "pl-cm-cell--diag-high" if ratio >= 0.75 else "pl-cm-cell--diag-mid"
    return "pl-cm-cell--err-high" if val >= 2 else "pl-cm-cell--err-low"


def _truncate_excerpt(text: str, max_len: int = 86) -> str:
    clean = " ".join((text or "").split())
    if len(clean) <= max_len:
        return clean
    return clean[: max_len - 1].rstrip() + "…"


def run_scientific_benchmark(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Ejecuta evaluación reproducible sobre `benchmark_dataset.json`:
    - Baseline determinístico (v7.2) aislado de SQLite y de la capa Overlay.
    - Validación cruzada estratificada 5-Fold balanceada (12×5) + CV repetida 10×5.
    - NB entrenado únicamente out-of-fold sobre los 4 folds de entrenamiento.
    - Estadística en Python puro: IC 95 % de Wilson, McNemar exacto, Jaccard intra-clase
      y auditoría caso por caso.
    """
    overlay_rules = get_active_overlay_rules()
    bm_mtime = BENCHMARK_DATASET_PATH.stat().st_mtime if BENCHMARK_DATASET_PATH.exists() else 0.0
    kb_mtime = KB_PATH.stat().st_mtime if KB_PATH.exists() else 0.0
    cache_key = (bm_mtime, kb_mtime)

    if not force_refresh and _BENCHMARK_CACHE["key"] == cache_key and _BENCHMARK_CACHE["result"] is not None:
        cached_res = dict(_BENCHMARK_CACHE["result"])
        cached_res["overlay_active_count"] = len(overlay_rules)
        return cached_res

    from .services import parse_request

    t0 = time.perf_counter()
    cases = load_benchmark_dataset()
    n_cases = len(cases)
    expected_classes = sorted({c["expected_action"] for c in cases})
    y_true = [c["expected_action"] for c in cases]
    max_intra_class_jaccard = compute_max_intra_class_jaccard(cases)

    # 1. Ejecutar el baseline determinístico 1 sola vez, completamente aislado de SQLite/overlay
    det_cache: List[Tuple[str, float, float, int, str]] = []
    baseline_preds: List[str] = []
    low_certainty_flags: List[bool] = []

    for case in cases:
        det_req = parse_request(
            case["text"],
            enable_overlay=False,
            enable_hybrid=False,
            enable_learned_boosts=False,
            overlay_rules=[],
            classify_only=True,
        )
        det_cache.append((
            det_req.action,
            det_req.confidence,
            det_req.margin,
            det_req.word_count,
            det_req.instruction_text or det_req.raw_text,
        ))
        baseline_preds.append(det_req.action)
        low_certainty_flags.append(
            is_low_certainty_decision(
                det_confidence=det_req.confidence,
                det_margin=det_req.margin,
                word_count=det_req.word_count,
                is_trivial=False,
            )
        )

    # 2. Validación Cruzada 5-Fold principal (seed=42) + Repeated 10x5 CV (seeds 42..51)
    hybrid_preds: List[str] = [""] * n_cases
    hybrid_nb_used: List[bool] = [False] * n_cases
    hybrid_nb_confs: List[float] = [0.0] * n_cases
    case_folds: List[int] = [0] * n_cases
    nb_interventions = 0
    nb_out_of_fold = True

    rep_accuracies: List[float] = []
    rep_macro_f1s: List[float] = []

    for seed in range(42, 52):
        folds = build_stratified_folds(cases, n_splits=5, seed=seed)
        seed_preds: List[str] = [""] * n_cases

        for fold_num, fold_test_idx in enumerate(folds, start=1):
            test_set = set(fold_test_idx)
            train_idx = [i for i in range(n_cases) if i not in test_set]
            if seed == 42 and (set(train_idx) & test_set):
                nb_out_of_fold = False

            train_texts = [cases[i]["text"] for i in train_idx]
            train_labels = [cases[i]["expected_action"] for i in train_idx]
            fold_nb = MultinomialNaiveBayesClassifier(alpha=1.0).fit(train_texts, train_labels)

            for idx in fold_test_idx:
                det_act, det_conf, det_marg, wc, txt = det_cache[idx]
                hyb_out = classify_hybrid_action(
                    text=txt,
                    det_action=det_act,
                    det_confidence=det_conf,
                    det_margin=det_marg,
                    nb_classifier=fold_nb,
                    word_count=wc,
                    is_trivial=False,
                )
                seed_preds[idx] = hyb_out["final_action"]
                if seed == 42:
                    hybrid_preds[idx] = hyb_out["final_action"]
                    hybrid_nb_used[idx] = bool(hyb_out["used_nb"])
                    hybrid_nb_confs[idx] = float(hyb_out.get("nb_confidence") or 0.0)
                    case_folds[idx] = fold_num
                    if hyb_out["used_nb"]:
                        nb_interventions += 1

        seed_metrics = _compute_classification_metrics(y_true, seed_preds, expected_classes)
        rep_accuracies.append(seed_metrics["accuracy_pct"])
        rep_macro_f1s.append(seed_metrics["macro_f1_pct"])

    repeated_cv = {
        "n_repeats": 10,
        "n_splits": 5,
        "accuracy_mean_pct": round(statistics.fmean(rep_accuracies), 1),
        "accuracy_std_pct": round(statistics.stdev(rep_accuracies), 1) if len(rep_accuracies) > 1 else 0.0,
        "accuracy_min_pct": round(min(rep_accuracies), 1),
        "accuracy_max_pct": round(max(rep_accuracies), 1),
        "macro_f1_mean_pct": round(statistics.fmean(rep_macro_f1s), 1),
        "macro_f1_std_pct": round(statistics.stdev(rep_macro_f1s), 1) if len(rep_macro_f1s) > 1 else 0.0,
    }

    extra_pred_classes = sorted({p for p in baseline_preds + hybrid_preds if p not in expected_classes})
    matrix_classes = expected_classes + extra_pred_classes

    base_raw = _compute_classification_metrics(y_true, baseline_preds, expected_classes)
    hyb_raw = _compute_classification_metrics(y_true, hybrid_preds, expected_classes)
    hyb_matrix_full = _compute_classification_metrics(y_true, hybrid_preds, matrix_classes)["confusion_matrix"]
    base_matrix_full = _compute_classification_metrics(y_true, baseline_preds, matrix_classes)["confusion_matrix"]

    improved_count = sum(
        1 for i in range(n_cases)
        if baseline_preds[i] != y_true[i] and hybrid_preds[i] == y_true[i]
    )
    regressions_count = sum(
        1 for i in range(n_cases)
        if baseline_preds[i] == y_true[i] and hybrid_preds[i] != y_true[i]
    )
    baseline_errors_total = sum(1 for i in range(n_cases) if baseline_preds[i] != y_true[i])
    total_errors_rescued_pct = (
        round((improved_count / baseline_errors_total) * 100.0, 1)
        if baseline_errors_total > 0
        else 0.0
    )

    low_certainty_count = sum(1 for f in low_certainty_flags if f)
    low_certainty_errors_baseline = sum(
        1 for i in range(n_cases)
        if low_certainty_flags[i] and baseline_preds[i] != y_true[i]
    )
    low_certainty_rescued = sum(
        1 for i in range(n_cases)
        if low_certainty_flags[i] and baseline_preds[i] != y_true[i] and hybrid_preds[i] == y_true[i]
    )
    low_certainty_rescued_pct = (
        round((low_certainty_rescued / low_certainty_errors_baseline) * 100.0, 1)
        if low_certainty_errors_baseline > 0
        else 0.0
    )

    mcnemar_p = mcnemar_exact_p_value(improved_count, regressions_count)
    mcnemar_p_display = "< 0.001" if mcnemar_p < 0.001 else f"{mcnemar_p:.4f}"

    # 3. Auditoría caso por caso
    outcome_rank = {
        "regresion": 0,
        "rescatado": 1,
        "error_persistente": 2,
        "acierto": 3,
    }
    case_audit: List[Dict[str, Any]] = []
    for i, case in enumerate(cases):
        base_ok = baseline_preds[i] == y_true[i]
        hyb_ok = hybrid_preds[i] == y_true[i]
        if not base_ok and hyb_ok:
            outcome = "rescatado"
            outcome_label = "Rescatado"
        elif base_ok and not hyb_ok:
            outcome = "regresion"
            outcome_label = "Regresión"
        elif not base_ok and not hyb_ok:
            outcome = "error_persistente"
            outcome_label = "Error persistente"
        else:
            outcome = "acierto"
            outcome_label = "Acierto directo"

        case_audit.append({
            "id": case["id"],
            "text": case["text"],
            "text_excerpt": _truncate_excerpt(case["text"], 88),
            "difficulty": case.get("difficulty", "normal"),
            "fold": case_folds[i],
            "expected_action": y_true[i],
            "expected_label": ACTION_LABELS_ES.get(y_true[i], y_true[i]),
            "baseline_action": baseline_preds[i],
            "baseline_label": ACTION_LABELS_ES.get(baseline_preds[i], baseline_preds[i]),
            "baseline_conf_pct": int(round(det_cache[i][1] * 100)),
            "hybrid_action": hybrid_preds[i],
            "hybrid_label": ACTION_LABELS_ES.get(hybrid_preds[i], hybrid_preds[i]),
            "nb_used": hybrid_nb_used[i],
            "nb_conf_pct": int(round(hybrid_nb_confs[i] * 100)) if hybrid_nb_confs[i] else 0,
            "outcome": outcome,
            "outcome_label": outcome_label,
        })

    case_audit.sort(key=lambda row: (outcome_rank.get(row["outcome"], 9), row["id"]))
    notable_cases = [row for row in case_audit if row["outcome"] != "acierto"]
    direct_hits_count = sum(1 for row in case_audit if row["outcome"] == "acierto")
    direct_hits_pct = round((direct_hits_count / max(n_cases, 1)) * 100.0, 1)

    base_by_cls = {row["class_key"]: row for row in base_raw["per_class"]}
    per_class_enriched: List[Dict[str, Any]] = []
    for row in hyb_raw["per_class"]:
        b_row = base_by_cls.get(row["class_key"], {})
        b_f1_pct = b_row.get("f1_pct", 0.0)
        diff_txt, diff_tone = _format_pp_diff(row["f1_pct"] - b_f1_pct)
        per_class_enriched.append({
            **row,
            "baseline_f1": b_row.get("f1", 0.0),
            "baseline_f1_pct": b_f1_pct,
            "f1_diff_text": diff_txt,
            "f1_diff_tone": diff_tone,
        })

    cm_rows: List[Dict[str, Any]] = []
    cm_matrix = hyb_matrix_full["matrix"]
    for r_idx, cls_key in enumerate(matrix_classes):
        if cls_key not in expected_classes and sum(cm_matrix[r_idx]) == 0:
            continue
        row_vals = cm_matrix[r_idx]
        row_sum = sum(row_vals)
        cells = [
            {
                "value": val,
                "is_diag": (r_idx == c_idx),
                "heat_class": _heat_class(val, r_idx == c_idx, row_sum),
                "col_label": ACTION_LABELS_ES.get(matrix_classes[c_idx], matrix_classes[c_idx]),
            }
            for c_idx, val in enumerate(row_vals)
            if matrix_classes[c_idx] in expected_classes or any(cm_matrix[rr][c_idx] > 0 for rr in range(len(matrix_classes)))
        ]
        cm_rows.append({
            "class_key": cls_key,
            "label": ACTION_LABELS_ES.get(cls_key, cls_key),
            "short_label": ACTION_SHORT_LABELS_ES.get(cls_key, cls_key[:10]),
            "cells": cells,
            "support": row_sum,
        })

    visible_cols = [
        {
            "class_key": matrix_classes[c_idx],
            "label": ACTION_LABELS_ES.get(matrix_classes[c_idx], matrix_classes[c_idx]),
            "short_label": ACTION_SHORT_LABELS_ES.get(matrix_classes[c_idx], matrix_classes[c_idx][:10]),
        }
        for c_idx in range(len(matrix_classes))
        if matrix_classes[c_idx] in expected_classes or any(cm_matrix[rr][c_idx] > 0 for rr in range(len(matrix_classes)))
    ]

    acc_diff, acc_tone = _format_pp_diff(hyb_raw["accuracy_pct"] - base_raw["accuracy_pct"])
    mf1_diff, mf1_tone = _format_pp_diff(hyb_raw["macro_f1_pct"] - base_raw["macro_f1_pct"])
    wf1_diff, wf1_tone = _format_pp_diff(hyb_raw["weighted_f1_pct"] - base_raw["weighted_f1_pct"])
    mrec_diff, mrec_tone = _format_pp_diff(hyb_raw["macro_recall_pct"] - base_raw["macro_recall_pct"])

    comparison_cards = [
        {
            "title": "Exactitud (Accuracy)",
            "baseline_pct": base_raw["accuracy_pct"],
            "hybrid_pct": hyb_raw["accuracy_pct"],
            "diff_text": acc_diff,
            "diff_tone": acc_tone,
        },
        {
            "title": "F1 Macro",
            "baseline_pct": base_raw["macro_f1_pct"],
            "hybrid_pct": hyb_raw["macro_f1_pct"],
            "diff_text": mf1_diff,
            "diff_tone": mf1_tone,
        },
        {
            "title": "F1 Ponderado",
            "baseline_pct": base_raw["weighted_f1_pct"],
            "hybrid_pct": hyb_raw["weighted_f1_pct"],
            "diff_text": wf1_diff,
            "diff_tone": wf1_tone,
        },
        {
            "title": "Exhaustividad (Recall)",
            "baseline_pct": base_raw["macro_recall_pct"],
            "hybrid_pct": hyb_raw["macro_recall_pct"],
            "diff_text": mrec_diff,
            "diff_tone": mrec_tone,
        },
    ]

    _, _, kb_actions_total = _load_kb_actions_prototypes()
    production_nb_classes = kb_actions_total or len(ACTION_LABELS_ES)
    coverage_actions = f"{len(expected_classes)}/{production_nb_classes}"

    if hyb_raw["macro_f1"] > base_raw["macro_f1"] and regressions_count == 0:
        verdict_tone = "success"
        verdict_headline = "El enfoque híbrido supera al motor determinístico sin regresiones"
        verdict_text = (
            f"Sobre {n_cases} casos curados ({coverage_actions} arquetipos) en 5-Fold balanceado (12x5) con Naive Bayes "
            f"out-of-fold, rescató {improved_count} de {baseline_errors_total} errores totales del baseline "
            f"({total_errors_rescued_pct:.1f}%) y {low_certainty_rescued}/{low_certainty_errors_baseline} de baja certeza "
            f"({low_certainty_rescued_pct:.1f}%), con 0 regresiones (McNemar p = {mcnemar_p_display})."
        )
    elif hyb_raw["macro_f1"] >= base_raw["macro_f1"]:
        verdict_tone = "info"
        verdict_headline = "El enfoque híbrido iguala o mejora el F1 Macro del baseline"
        verdict_text = (
            f"Sobre {n_cases} casos en 5-Fold balanceado, rescató {improved_count} de {baseline_errors_total} errores "
            f"con {regressions_count} regresión(es) (McNemar p = {mcnemar_p_display})."
        )
    else:
        verdict_tone = "warning"
        verdict_headline = "El baseline determinístico mantuvo mejor balance en esta corrida"
        verdict_text = (
            f"El híbrido rescató {improved_count} caso(s) pero presentó {regressions_count} regresión(es); "
            "conviene ajustar los umbrales de intervención."
        )

    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    result = {
        "dataset_size": n_cases,
        "n_folds": 5,
        "n_classes": len(expected_classes),
        "coverage_actions": coverage_actions,
        "production_nb_classes": production_nb_classes,
        "nb_out_of_fold": nb_out_of_fold,
        "rules_held_out": False,
        "max_intra_class_jaccard": max_intra_class_jaccard,
        "elapsed_ms": elapsed_ms,
        "overlay_active_count": len(overlay_rules),
        "baseline": base_raw,
        "hybrid": hyb_raw,
        "repeated_cv": repeated_cv,
        "mcnemar_p_value": mcnemar_p,
        "mcnemar_p_display": mcnemar_p_display,
        "baseline_confusion_matrix": base_matrix_full,
        "confusion_matrix": hyb_matrix_full,
        "confusion_table": {
            "columns": visible_cols,
            "rows": cm_rows,
            "diagonal_sum": hyb_matrix_full["diagonal_sum"],
            "total": hyb_matrix_full["total"],
        },
        "per_class": per_class_enriched,
        "comparison_cards": comparison_cards,
        "improved_count": improved_count,
        "regressions_count": regressions_count,
        "baseline_errors_total": baseline_errors_total,
        "total_errors_rescued_pct": total_errors_rescued_pct,
        "low_certainty_count": low_certainty_count,
        "low_certainty_errors_baseline": low_certainty_errors_baseline,
        "low_certainty_rescued": low_certainty_rescued,
        "low_certainty_rescued_pct": low_certainty_rescued_pct,
        "nb_interventions": nb_interventions,
        "case_audit": case_audit,
        "notable_cases": notable_cases,
        "direct_hits_count": direct_hits_count,
        "direct_hits_pct": direct_hits_pct,
        "verdict_tone": verdict_tone,
        "verdict_headline": verdict_headline,
        "verdict_text": verdict_text,
    }

    _BENCHMARK_CACHE["key"] = cache_key
    _BENCHMARK_CACHE["result"] = result
    return result
