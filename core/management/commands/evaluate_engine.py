from django.core.management.base import BaseCommand

from core.scientific_eval import run_scientific_benchmark


class Command(BaseCommand):
    help = (
        "Ejecuta la evaluación científica reproducible (5-Fold estratificada sin fuga de datos) "
        "comparando el Baseline Determinístico (v7.2) vs. la Arquitectura Híbrida (v8.0)."
    )

    def handle(self, *args, **options):
        report = run_scientific_benchmark(force_refresh=True)
        base = report["baseline"]
        hyb = report["hybrid"]

        self.stdout.write("=" * 78)
        self.stdout.write("PROMPTLAB v8.0 — EVALUACIÓN CIENTÍFICA OFFLINE (PYTHON PURO)")
        self.stdout.write("=" * 78)
        self.stdout.write(
            f"Dataset dorado : {report['dataset_size']} casos en español | "
            f"{report['n_classes']} clases | Validación {report['n_folds']}-Fold estratificada"
        )
        self.stdout.write(
            f"Integridad     : Cero fuga de datos = {'SÍ' if report['leakage_free'] else 'NO'} | "
            f"Reglas Overlay activas = {report['overlay_active_count']} | "
            f"Tiempo = {report['elapsed_ms']:.2f} ms"
        )
        self.stdout.write("")
        self.stdout.write(f"{'Métrica':<26} {'Baseline v7.2':>15} {'Híbrido v8.0':>15} {'Diferencia':>14}")
        self.stdout.write("-" * 78)

        rows = [
            ("Exactitud (Accuracy)", base["accuracy"], hyb["accuracy"]),
            ("Precisión Macro", base["macro_precision"], hyb["macro_precision"]),
            ("Exhaustividad (Recall)", base["macro_recall"], hyb["macro_recall"]),
            ("Macro F1", base["macro_f1"], hyb["macro_f1"]),
            ("Weighted F1", base["weighted_f1"], hyb["weighted_f1"]),
        ]
        for label, b_val, h_val in rows:
            diff_pp = (h_val - b_val) * 100.0
            diff_str = f"{diff_pp:+.1f} pp" if abs(diff_pp) >= 0.05 else "0.0 pp"
            self.stdout.write(
                f"{label:<26} {b_val * 100:>14.1f}% {h_val * 100:>14.1f}% {diff_str:>14}"
            )

        self.stdout.write("")
        self.stdout.write("MÉTRICAS POR CLASE (HÍBRIDO v8.0 vs. BASELINE F1)")
        self.stdout.write("-" * 78)
        self.stdout.write(
            f"{'Clase / Tarea':<28} {'Prec.':>8} {'Recall':>8} {'F1 Base':>9} {'F1 Híbr.':>9} {'Soporte':>9}"
        )
        for cls_row in report["per_class"]:
            self.stdout.write(
                f"{cls_row['label'][:28]:<28} "
                f"{cls_row['precision_pct']:>7.1f}% "
                f"{cls_row['recall_pct']:>7.1f}% "
                f"{cls_row['baseline_f1_pct']:>8.1f}% "
                f"{cls_row['f1_pct']:>8.1f}% "
                f"{cls_row['support']:>9d}"
            )

        self.stdout.write("")
        self.stdout.write("RESUMEN DE CASOS Y MATRIZ DE CONFUSIÓN (HÍBRIDO v8.0)")
        self.stdout.write("-" * 78)
        self.stdout.write(
            f"Casos mejorados (rescatados) : {report['improved_count']} | "
            f"Regresiones: {report['regressions_count']}"
        )
        self.stdout.write(
            f"Baja certeza (baseline err.) : {report['low_certainty_rescued']}/"
            f"{report['low_certainty_errors_baseline']} rescatados "
            f"({report['low_certainty_rescued_pct']:.1f}%) | "
            f"Intervenciones NB: {report['nb_interventions']}"
        )
        cm = report["confusion_matrix"]
        self.stdout.write(
            f"Aciertos en diagonal         : {cm['diagonal_sum']}/{cm['total']}"
        )
        self.stdout.write("")
        self.stdout.write(f"Conclusión: {report['verdict_headline']}")
        self.stdout.write(report["verdict_text"])
        self.stdout.write("=" * 78)
