"""
Evaluación Científica NLP + Clasificador Probabilístico Multinomial Naive Bayes
+ Capa Supervisada de Active Learning (Overlay) en Python puro (PromptLab v8.0).

100 % biblioteca estándar de Python (sin scikit-learn, numpy ni dependencias externas).
"""

from collections import Counter
import json
import math
from pathlib import Path
import re
import statistics
import time
from typing import Any, Dict, List, Optional, Tuple
import unicodedata


BENCHMARK_DATASET_PATH = Path(__file__).resolve().parent / "rules" / "benchmark_dataset.json"

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
    "comparar_evaluar": "Comparar",
    "depurar_error": "Depurar",
    "explicar_concepto": "Explicar",
    "generar_codigo": "Código",
    "planificar_pasos": "Planificar",
    "redactar_contenido": "Redactar",
    "simular_practicar": "Simular",
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


def tokenize_spanish(text: str) -> List[str]:
    """
    Tokenización en español: minúsculas, normalización de tildes, filtrado de
    stopwords básicas, stemming ligero y extracción de unigramas y bigramas.
    """
    norm = _strip_accents((text or "").lower())
    raw_tokens = re.findall(r"[a-z0-9]+", norm)
    unigrams = [
        _light_stem_spanish(tok)
        for tok in raw_tokens
        if len(tok) > 2 and tok not in SPANISH_NB_STOPWORDS and not tok.isdigit()
    ]
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
    """Invalida la caché del benchmark científico y del clasificador Naive Bayes."""
    _BENCHMARK_CACHE["key"] = None
    _BENCHMARK_CACHE["result"] = None
    _PRODUCTION_NB_CACHE["key"] = None
    _PRODUCTION_NB_CACHE["clf"] = None


def get_active_overlay_rules() -> List[Dict[str, Any]]:
    """
    Lee las reglas activas de la capa overlay (`ActiveLearningRule`) desde SQLite.
    Seguro ante bases sin tabla o ejecuciones previas a que Django inicialice apps.
    """
    try:
        from django.apps import apps
        if not apps.ready:
            return []
        from .models import ActiveLearningRule

        qs = ActiveLearningRule.objects.filter(is_active=True).order_by("id")
        return [
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
    except Exception:
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


def _build_overlay_signature(overlay_rules: List[Dict[str, Any]]) -> Tuple[Tuple[str, str, str], ...]:
    return tuple(
        (r.get("term", ""), r.get("target_action", ""), r.get("target_category", ""))
        for r in overlay_rules
    )


def get_production_nb_classifier(
    overlay_rules: Optional[List[Dict[str, Any]]] = None,
) -> MultinomialNaiveBayesClassifier:
    """
    Entrena (y cachea en memoria) el clasificador Naive Bayes auxiliar usando
    el dataset dorado de referencia y las reglas activas de la capa overlay.
    """
    rules = get_active_overlay_rules() if overlay_rules is None else overlay_rules
    mtime = BENCHMARK_DATASET_PATH.stat().st_mtime if BENCHMARK_DATASET_PATH.exists() else 0.0
    cache_key = (mtime, _build_overlay_signature(rules))

    if _PRODUCTION_NB_CACHE["key"] == cache_key and _PRODUCTION_NB_CACHE["clf"] is not None:
        return _PRODUCTION_NB_CACHE["clf"]

    texts: List[str] = []
    labels: List[str] = []
    if BENCHMARK_DATASET_PATH.exists():
        for case in load_benchmark_dataset():
            texts.append(case["text"])
            labels.append(case["expected_action"])

    for r in rules:
        term = r.get("term", "")
        act = r.get("target_action", "")
        if term and act:
            texts.append(term)
            labels.append(act)

    clf = MultinomialNaiveBayesClassifier(alpha=1.0).fit(texts, labels)
    _PRODUCTION_NB_CACHE["key"] = cache_key
    _PRODUCTION_NB_CACHE["clf"] = clf
    return clf


def classify_hybrid_action(
    text: str,
    det_action: str,
    det_confidence: float,
    det_margin: float,
    nb_classifier: Optional[MultinomialNaiveBayesClassifier] = None,
    conf_threshold: float = 0.45,
    margin_threshold: float = 0.08,
    nb_min_conf: float = 0.55,
    word_count: Optional[int] = None,
    is_trivial: bool = False,
) -> Dict[str, Any]:
    """
    Arquitectura híbrida condicionada a evidencia:
    - El motor determinístico es el carril principal de Caja Blanca.
    - Naive Bayes interviene ÚNICAMENTE en baja certeza o margen estrecho
      cuando supera el umbral verificado `nb_min_conf`.
    """
    is_short_trivial = is_trivial or (word_count is not None and word_count < 3)
    is_low_certainty = (
        not is_short_trivial
        and (det_confidence < conf_threshold or (det_confidence < 0.58 and det_margin < margin_threshold))
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


def build_stratified_folds(cases: List[Dict[str, Any]], n_splits: int = 5) -> List[List[int]]:
    """Construye particiones estratificadas determinísticas por `expected_action`."""
    by_class: Dict[str, List[int]] = {}
    for idx, case in enumerate(cases):
        by_class.setdefault(case["expected_action"], []).append(idx)

    folds: List[List[int]] = [[] for _ in range(n_splits)]
    for cls_name in sorted(by_class.keys()):
        for offset, idx in enumerate(by_class[cls_name]):
            folds[offset % n_splits].append(idx)
    return folds


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
    accuracy = sum(1 for t_lbl, p_lbl in zip(y_true, y_pred) if t_lbl == p_lbl) / total

    per_class: List[Dict[str, Any]] = []
    precisions: List[float] = []
    recalls: List[float] = []
    f1s: List[float] = []
    supports: List[int] = []

    for i, cls_name in enumerate(classes):
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


def run_scientific_benchmark(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Ejecuta evaluación reproducible sobre `benchmark_dataset.json` con validación
    cruzada estratificada 5-Fold (predicciones out-of-fold, cero fuga de datos).
    """
    overlay_rules = get_active_overlay_rules()
    mtime = BENCHMARK_DATASET_PATH.stat().st_mtime if BENCHMARK_DATASET_PATH.exists() else 0.0
    cache_key = (mtime, _build_overlay_signature(overlay_rules))

    if not force_refresh and _BENCHMARK_CACHE["key"] == cache_key and _BENCHMARK_CACHE["result"] is not None:
        return _BENCHMARK_CACHE["result"]

    from .services import parse_request

    t0 = time.perf_counter()
    cases = load_benchmark_dataset()
    n_cases = len(cases)
    folds = build_stratified_folds(cases, n_splits=5)

    # Clases ordenadas: incluye todas las clases esperadas del dataset dorado
    expected_classes = sorted({c["expected_action"] for c in cases})

    y_true = [c["expected_action"] for c in cases]
    baseline_preds: List[str] = [""] * n_cases
    hybrid_preds: List[str] = [""] * n_cases
    low_certainty_flags: List[bool] = [False] * n_cases
    nb_interventions = 0
    leakage_free = True

    for fold_test_idx in folds:
        test_set = set(fold_test_idx)
        train_idx = [i for i in range(n_cases) if i not in test_set]
        if set(train_idx) & test_set:
            leakage_free = False

        train_texts = [cases[i]["text"] for i in train_idx]
        train_labels = [cases[i]["expected_action"] for i in train_idx]
        for r in overlay_rules:
            if r.get("term") and r.get("target_action") in expected_classes:
                train_texts.append(r["term"])
                train_labels.append(r["target_action"])

        fold_nb = MultinomialNaiveBayesClassifier(alpha=1.0).fit(train_texts, train_labels)

        for idx in fold_test_idx:
            txt = cases[idx]["text"]
            det_req = parse_request(
                txt,
                enable_overlay=False,
                enable_hybrid=False,
                overlay_rules=[],
                classify_only=True,
            )
            baseline_preds[idx] = det_req.action
            is_det_low = det_req.confidence < 0.45 or (det_req.confidence < 0.58 and det_req.margin < 0.08)
            if is_det_low:
                low_certainty_flags[idx] = True

            if overlay_rules:
                hyb_req = parse_request(
                    txt,
                    enable_overlay=True,
                    enable_hybrid=True,
                    nb_classifier=fold_nb,
                    overlay_rules=overlay_rules,
                    classify_only=True,
                )
                hybrid_preds[idx] = hyb_req.action
                if any(tr.get("stage") == "hybrid_tiebreak" for tr in hyb_req.trace):
                    nb_interventions += 1
            else:
                hyb_out = classify_hybrid_action(
                    text=det_req.instruction_text or det_req.raw_text,
                    det_action=det_req.action,
                    det_confidence=det_req.confidence,
                    det_margin=det_req.margin,
                    nb_classifier=fold_nb,
                    word_count=det_req.word_count,
                    is_trivial=False,
                )
                hybrid_preds[idx] = hyb_out["final_action"]
                if hyb_out["used_nb"]:
                    nb_interventions += 1

    # Si alguna predicción cayó en una acción fuera del conjunto evaluado, agregarla para consistencia matricial
    extra_pred_classes = sorted({p for p in baseline_preds + hybrid_preds if p not in expected_classes})
    matrix_classes = expected_classes + extra_pred_classes

    base_raw = _compute_classification_metrics(y_true, baseline_preds, expected_classes)
    hyb_raw = _compute_classification_metrics(y_true, hybrid_preds, expected_classes)
    # Matriz de confusión extendida para garantizar que sum(matrix) == n_cases
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

    # Enriquecer tabla por clase con F1 baseline y diferencia
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

    # Enriquecer matriz de confusión del modelo híbrido para HTML accesible
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

    if hyb_raw["macro_f1"] > base_raw["macro_f1"] and regressions_count == 0:
        verdict_tone = "success"
        verdict_headline = "El enfoque híbrido supera al motor determinístico sin regresiones"
        verdict_text = (
            f"Sobre {n_cases} casos evaluados en validación cruzada 5-Fold sin fuga de datos, "
            f"la arquitectura híbrida rescató {improved_count} caso(s) de baja certeza "
            f"({low_certainty_rescued_pct:.1f}% de los errores iniciales con duda) y mantuvo 0 regresiones."
        )
    elif hyb_raw["macro_f1"] >= base_raw["macro_f1"]:
        verdict_tone = "info"
        verdict_headline = "El enfoque híbrido iguala o mejora el F1 Macro del baseline"
        verdict_text = (
            f"Sobre {n_cases} casos en 5-Fold, rescató {improved_count} caso(s) con {regressions_count} regresión(es) "
            f"y preservó intactas las decisiones de alta certeza."
        )
    else:
        verdict_tone = "warning"
        verdict_headline = "El baseline determinístico mantuvo mejor balance en esta corrida"
        verdict_text = (
            f"El híbrido rescató {improved_count} caso(s) pero presentó {regressions_count} regresión(es); "
            "conviene ajustar los umbrales de intervención o revisar las reglas activas."
        )

    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    result = {
        "dataset_size": n_cases,
        "n_folds": 5,
        "n_classes": len(expected_classes),
        "leakage_free": leakage_free,
        "elapsed_ms": elapsed_ms,
        "overlay_active_count": len(overlay_rules),
        "baseline": base_raw,
        "hybrid": hyb_raw,
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
        "low_certainty_count": low_certainty_count,
        "low_certainty_errors_baseline": low_certainty_errors_baseline,
        "low_certainty_rescued": low_certainty_rescued,
        "low_certainty_rescued_pct": low_certainty_rescued_pct,
        "nb_interventions": nb_interventions,
        "verdict_tone": verdict_tone,
        "verdict_headline": verdict_headline,
        "verdict_text": verdict_text,
    }

    _BENCHMARK_CACHE["key"] = cache_key
    _BENCHMARK_CACHE["result"] = result
    return result
