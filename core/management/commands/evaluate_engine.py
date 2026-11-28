from django.core.management.base import BaseCommand, CommandError

from core.scientific_eval import run_scientific_benchmark


class Command(BaseCommand):
    help = (
        "Ejecuta la evaluación científica reproducible (5-Fold balanceada + CV repetida 10x5) "
        "comparando el Baseline Determinístico (v7.2) vs. la Arquitectura Híbrida (v8.0.1)."
    )

    def handle(self, *args, **options):
        try:
            report = run_scientific_benchmark(force_refresh=True)
        except Exception as exc:
            raise CommandError(f"Error al ejecutar la evaluación científica: {exc}") from exc

        base = report["baseline"]
        hyb = report["hybrid"]
        rep = report["repeated_cv"]

        self.stdout.write("=" * 78)
        self.stdout.write("PROMPTLAB v8.0.1 — EVALUACIÓN CIENTÍFICA OFFLINE (PYTHON PURO)")
        self.stdout.write("=" * 78)
        self.stdout.write(
            f"Dataset curado : {report['dataset_size']} casos en español | "
            f"Cobertura: {report['coverage_actions']} arquetipos | "
            f"NB producción: {report['production_nb_classes']}/21"
        )
        self.stdout.write(
            f"Integridad     : NB out-of-fold = {'SÍ' if report['nb_out_of_fold'] else 'NO'} | "
            f"Reglas base hold-out externo = NO | "
            f"Jaccard máx. = {report['max_intra_class_jaccard']:.3f}"
        )
        self.stdout.write(
            f"Entorno        : Aislado de SQLite y Overlay (activas en DB: {report['overlay_active_count']}) | "
            f"Tiempo = {report['elapsed_ms']:.2f} ms"
        )
        self.stdout.write("")
        self.stdout.write(f"{'Métrica':<26} {'Baseline v7.2':>15} {'Híbrido v8.0':>15} {'Diferencia':>14}")
        self.stdout.write("-" * 78)

        rows = [
            ("Exactitud (Accuracy)", base["accuracy_pct"], hyb["accuracy_pct"]),
            ("Precisión Macro", base["macro_precision_pct"], hyb["macro_precision_pct"]),
            ("Exhaustividad (Recall)", base["macro_recall_pct"], hyb["macro_recall_pct"]),
            ("Macro F1", base["macro_f1_pct"], hyb["macro_f1_pct"]),
            ("Weighted F1", base["weighted_f1_pct"], hyb["weighted_f1_pct"]),
        ]
        for label, b_pct, h_pct in rows:
            diff_pp = round(h_pct - b_pct, 1)
            diff_str = f"{diff_pp:+.1f} pp" if abs(diff_pp) >= 0.05 else "0.0 pp"
            self.stdout.write(
                f"{label:<26} {b_pct:>14.1f}% {h_pct:>14.1f}% {diff_str:>14}"
            )

        self.stdout.write("")
        self.stdout.write("RIGOR ESTADÍSTICO (PYTHON PURO)")
        self.stdout.write("-" * 78)
        self.stdout.write(
            f"IC 95 % Wilson (Accuracy) : Baseline [{base['accuracy_ci_low_pct']:.1f}%; {base['accuracy_ci_high_pct']:.1f}%] | "
            f"Híbrido [{hyb['accuracy_ci_low_pct']:.1f}%; {hyb['accuracy_ci_high_pct']:.1f}%]"
        )
        self.stdout.write(
            f"CV Repetida {rep['n_repeats']}x{rep['n_splits']}        : "
            f"Exactitud = {rep['accuracy_mean_pct']:.1f}% ± {rep['accuracy_std_pct']:.1f} pp "
            f"(rango {rep['accuracy_min_pct']:.1f}%–{rep['accuracy_max_pct']:.1f}%) | "
            f"Macro F1 = {rep['macro_f1_mean_pct']:.1f}% ± {rep['macro_f1_std_pct']:.1f} pp"
        )
        self.stdout.write(
            f"Test exacto de McNemar    : p = {report['mcnemar_p_display']} "
            f"(rescates = {report['improved_count']}, regresiones = {report['regressions_count']})"
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
            f"Rescatados / errores totales : {report['improved_count']}/{report['baseline_errors_total']} "
            f"({report['total_errors_rescued_pct']:.1f}%) | Regresiones: {report['regressions_count']}"
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
