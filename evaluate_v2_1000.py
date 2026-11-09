"""Évaluation appariée du routage historique vs intentions V2 sur 1 000 dossiers aléatoires.

Entrées :
- benchmark_1000_random_cases.csv : tirage aléatoire (random_state=42), ancien domaine et vérité terrain.
- LABELS_DIR/labels_*.jsonl : intention V2 brute + confiance par dossier (classification à l'aveugle).

Sorties :
- benchmark_1000_cases_v2.csv, v2_1000_kpi_summary.csv, v2_1000_confusion_matrix.csv,
  v2_1000_remaining_errors.csv, v2_1000_per_domain.csv.
"""

from __future__ import annotations

import json
import sys
from math import comb, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
SAMPLE_PATH = BASE_DIR / "benchmark_1000_random_cases.csv"
LABELS_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE_DIR / "v2_labels"
OUTPUT_PATH = BASE_DIR / "benchmark_1000_cases_v2.csv"
SUMMARY_PATH = BASE_DIR / "v2_1000_kpi_summary.csv"
CONFUSION_PATH = BASE_DIR / "v2_1000_confusion_matrix.csv"
ERRORS_PATH = BASE_DIR / "v2_1000_remaining_errors.csv"
PER_DOMAIN_PATH = BASE_DIR / "v2_1000_per_domain.csv"

REPORTED_BASELINE = 0.1222
MISSING = "Non renseigné"
FALLBACK_DOMAINS = {"Other", "No detection"}
BOOTSTRAP_ITERATIONS = 10_000
SEED = 42

INTENTS = {
    "B2B / Corporate": (0.55, "B2B"),
    "Aftersales B2C": (0.35, "Aftersales"),
    "Marketplace": (0.40, "Marketplace"),
    "Avant-Vente & Conseil Produit": (0.35, "Presales"),
    "Services, Atelier & Location": (0.40, "Services"),
    "Compte Client, Paiement & Loyalty": (0.35, "Other"),
    "Juridique & RGPD": (0.45, "Legal"),
    "Informations Magasin": (0.35, "Other"),
    "Fallback": (0.30, "No detection"),
}


def notebook_error(pred: pd.Series, truth: pd.Series) -> pd.Series:
    """Formule du notebook : fallback et vérité absente ne comptent pas comme erreur."""
    return pred.ne(truth) & truth.ne(MISSING) & ~pred.isin(FALLBACK_DOMAINS)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    p = k / n
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    margin = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, center - margin), min(1.0, center + margin)


def mcnemar_exact(old_bad: pd.Series, new_bad: pd.Series) -> tuple[int, int, float]:
    b = int((old_bad & ~new_bad).sum())  # corrigés par V2
    c = int((~old_bad & new_bad).sum())  # introduits par V2
    n = b + c
    if n == 0:
        return b, c, 1.0
    tail = sum(comb(n, k) for k in range(min(b, c) + 1))
    return b, c, min(1.0, 2 * tail / 2**n)


def paired_bootstrap(old_bad: np.ndarray, new_bad: np.ndarray) -> tuple[float, float]:
    rng = np.random.default_rng(SEED)
    n = len(old_bad)
    idx = rng.integers(0, n, size=(BOOTSTRAP_ITERATIONS, n))
    diffs = new_bad[idx].mean(axis=1) - old_bad[idx].mean(axis=1)
    return float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))


def load_labels() -> pd.DataFrame:
    rows = []
    for path in sorted(LABELS_DIR.glob("labels_*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    labels = pd.DataFrame(rows)
    labels["_Case_ID"] = labels["_Case_ID"].astype(str)
    labels = labels.drop_duplicates("_Case_ID", keep="last")
    unknown = set(labels["raw_intent"]) - set(INTENTS)
    if unknown:
        raise ValueError(f"Intentions inconnues : {unknown}")
    labels["confidence"] = labels["confidence"].astype(float)
    if not labels["confidence"].between(0, 1).all():
        raise ValueError("Confiance hors [0, 1].")
    return labels


def comparison_row(name: str, old_bad: pd.Series, new_bad: pd.Series) -> dict:
    n = len(old_bad)
    k_old, k_new = int(old_bad.sum()), int(new_bad.sum())
    lo_old, hi_old = wilson(k_old, n)
    lo_new, hi_new = wilson(k_new, n)
    b, c, p = mcnemar_exact(old_bad, new_bad)
    lo_d, hi_d = paired_bootstrap(old_bad.to_numpy(bool).astype(float), new_bad.to_numpy(bool).astype(float))
    return {
        "Métrique": name,
        "Dossiers": n,
        "Erreurs ancien": k_old,
        "Taux ancien": k_old / n,
        "IC95 ancien": f"[{lo_old:.2%} ; {hi_old:.2%}]",
        "Erreurs V2": k_new,
        "Taux V2": k_new / n,
        "IC95 V2": f"[{lo_new:.2%} ; {hi_new:.2%}]",
        "Écart V2 - ancien (pts)": (k_new - k_old) / n * 100,
        "IC95 bootstrap écart (pts)": f"[{lo_d * 100:+.2f} ; {hi_d * 100:+.2f}]",
        "Corrigés par V2": b,
        "Introduits par V2": c,
        "McNemar p exact": p,
    }


def main() -> None:
    sample = pd.read_csv(SAMPLE_PATH, dtype={"_Case_ID": str})
    labels = load_labels()
    data = sample.merge(labels, on="_Case_ID", how="left", validate="one_to_one")
    missing = data["raw_intent"].isna().sum()
    if missing:
        raise ValueError(f"{missing} dossiers sans prédiction V2.")
    if len(data) != 1000 or data["_Case_ID"].nunique() != 1000:
        raise ValueError("Le benchmark doit contenir 1 000 dossiers uniques.")

    data["V2_Raw_Intent"] = data["raw_intent"]
    data["V2_Confidence"] = data["confidence"].round(2)
    data["V2_Threshold"] = data["raw_intent"].map(lambda i: INTENTS[i][0])
    below = data["V2_Confidence"] < data["V2_Threshold"]
    data["V2_Intent"] = np.where(below, "Fallback", data["raw_intent"])
    data["V2_Domain"] = data["V2_Intent"].map(lambda i: INTENTS[i][1])
    data["Reasoning"] = data["reason"]

    truth = data["True_Domain"]
    known = truth.ne(MISSING)
    data["Old_Error"] = notebook_error(data["Old_Domain"], truth)
    data["Is_V2_Error"] = notebook_error(data["V2_Domain"], truth)
    data["Old_Exact_Miss"] = known & data["Old_Domain"].ne(truth)
    data["Exact_Mismatch"] = known & data["V2_Domain"].ne(truth)

    out_cols = [
        "_Case_ID", "Clean_Subject", "Old_Domain", "True_Domain", "V2_Raw_Intent", "V2_Intent",
        "V2_Confidence", "V2_Threshold", "V2_Domain", "Old_Error", "Is_V2_Error",
        "Old_Exact_Miss", "Exact_Mismatch", "Reasoning",
    ]
    data[out_cols].to_csv(OUTPUT_PATH, index=False)

    # 1) KPI notebook (dénominateur = 1 000) ; 2) KPI strict : accord exact sur vérité connue.
    rows = [
        comparison_row("Erreur formule notebook (fallback non compté)", data["Old_Error"], data["Is_V2_Error"]),
        comparison_row(
            "Désaccord strict avec équipe finale (vérité connue)",
            data.loc[known, "Old_Exact_Miss"], data.loc[known, "Exact_Mismatch"],
        ),
    ]
    summary = pd.DataFrame(rows)
    old_fb = int(data["Old_Domain"].isin(FALLBACK_DOMAINS).sum())
    new_fb = int(data["V2_Domain"].isin(FALLBACK_DOMAINS).sum())
    new_nd = int(data["V2_Domain"].eq("No detection").sum())
    below_n = int(below.sum())
    summary.to_csv(SUMMARY_PATH, index=False)

    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 20)
    print("=== Comparaison appariée sur 1 000 dossiers aléatoires ===")
    show = summary.copy()
    for col in ("Taux ancien", "Taux V2"):
        show[col] = show[col].map(lambda v: f"{v:.2%}")
    show["Écart V2 - ancien (pts)"] = show["Écart V2 - ancien (pts)"].map(lambda v: f"{v:+.2f}")
    show["McNemar p exact"] = show["McNemar p exact"].map(lambda v: f"{v:.4g}")
    print(show.T.to_string(header=False))
    print(f"\nRéférence notebook (9 197 dossiers) : {REPORTED_BASELINE:.2%}")
    print(f"Fallback (Other + No detection) : ancien {old_fb} ({old_fb / 10:.1f} %) | V2 {new_fb} ({new_fb / 10:.1f} %)")
    print(f"  dont V2 No detection : {new_nd} ; bascules sous seuil : {below_n}")
    print(f"Vérité non renseignée : {int((~known).sum())} dossiers")

    print("\n=== Anomalies ciblées présentes dans le tirage aléatoire ===")
    specs = [
        ("Faux positifs B2B -> Aftersales", "B2B", "Aftersales"),
        ("Fuites Aftersales -> Marketplace", "Aftersales", "Marketplace"),
        ("Faux positifs Legal -> Aftersales", "Legal", "Aftersales"),
    ]
    for label, old, true in specs:
        cohort = data.loc[data["Old_Domain"].eq(old) & truth.eq(true)]
        fixed = int(cohort["V2_Domain"].eq(true).sum())
        rate = f"{fixed / len(cohort):.1%}" if len(cohort) else "N/D"
        print(f"{label:<36} {fixed}/{len(cohort)} corrigés ({rate})")

    print("\n=== Exactitude par vraie équipe (vérité connue) ===")
    per = data.loc[known].groupby("True_Domain").agg(
        Dossiers=("_Case_ID", "count"),
        Exact_Ancien=("Old_Exact_Miss", lambda s: 1 - s.mean()),
        Exact_V2=("Exact_Mismatch", lambda s: 1 - s.mean()),
    ).sort_values("Dossiers", ascending=False)
    per.to_csv(PER_DOMAIN_PATH)
    print(per.assign(
        Exact_Ancien=per["Exact_Ancien"].map("{:.1%}".format),
        Exact_V2=per["Exact_V2"].map("{:.1%}".format),
    ).to_string())

    confusion = pd.crosstab(data["V2_Domain"], truth, margins=True, margins_name="Total")
    confusion.to_csv(CONFUSION_PATH)
    print("\n=== Matrice de confusion V2_Domain (lignes) x True_Domain (colonnes) ===")
    print(confusion.to_string())

    errors = data.loc[data["Exact_Mismatch"], [
        "_Case_ID", "Clean_Subject", "Old_Domain", "True_Domain", "V2_Intent",
        "V2_Confidence", "V2_Domain", "Is_V2_Error", "Reasoning",
    ]]
    errors.to_csv(ERRORS_PATH, index=False)
    flows = errors.groupby(["V2_Domain", "True_Domain"]).size().sort_values(ascending=False)
    print(f"\n=== Écarts exacts V2 restants : {len(errors)} (détail : {ERRORS_PATH.name}) ===")
    print(flows.head(12).to_string())


if __name__ == "__main__":
    main()
