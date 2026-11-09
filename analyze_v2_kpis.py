"""Analyse locale des KPI du benchmark manuel de 100 dossiers.

Exécuter depuis ce dossier avec :
    python3 analyze_v2_kpis.py

Le lot stratifié de 100 cas n'est pas une estimation représentative de toute la
population. Le taux de précision générale est calculé sur B_Random seulement.
"""

from __future__ import annotations

from math import comb, sqrt
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
INPUT_PATH = BASE_DIR / "benchmark_100_cases.csv"
SUMMARY_PATH = BASE_DIR / "v2_kpi_summary.csv"
CONFUSION_PATH = BASE_DIR / "v2_confusion_matrix_random.csv"
ERRORS_PATH = BASE_DIR / "v2_remaining_errors.csv"
REPORTED_BASELINE = 0.1222
FALLBACK_DOMAINS = {"Other", "No detection"}
MISSING_DOMAIN = "Non renseigné"


def notebook_error(predicted: pd.Series, truth: pd.Series) -> pd.Series:
    """Reproduit la formule d'erreur de domaine du notebook."""
    return (
        predicted.ne(truth)
        & truth.ne(MISSING_DOMAIN)
        & ~predicted.isin(FALLBACK_DOMAINS)
    )


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total == 0:
        return float("nan"), float("nan")
    rate = successes / total
    denominator = 1 + z**2 / total
    center = (rate + z**2 / (2 * total)) / denominator
    margin = z * sqrt(
        rate * (1 - rate) / total + z**2 / (4 * total**2)
    ) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def exact_mcnemar_p_value(old_errors: pd.Series, new_errors: pd.Series) -> float:
    """Test binomial exact sur les paires discordantes, sans dépendance SciPy."""
    old_errors = old_errors.astype(bool)
    new_errors = new_errors.astype(bool)
    corrected = int((old_errors & ~new_errors).sum())
    introduced = int((~old_errors & new_errors).sum())
    discordant = corrected + introduced
    if discordant == 0:
        return 1.0
    tail = sum(comb(discordant, k) for k in range(min(corrected, introduced) + 1))
    return min(1.0, 2 * tail / (2**discordant))


def rate(series: pd.Series) -> float:
    return float(series.mean()) if len(series) else float("nan")


def fmt_rate(value: float) -> str:
    return "N/D" if pd.isna(value) else f"{value:.2%}"


def main() -> None:
    if not INPUT_PATH.is_file():
        raise FileNotFoundError(
            f"Fichier introuvable : {INPUT_PATH}. "
            "Génère d'abord benchmark_100_cases.csv."
        )

    data = pd.read_csv(INPUT_PATH, dtype={"_Case_ID": str})
    required = {
        "_Case_ID",
        "Evaluation_Group",
        "Old_Domain",
        "True_Domain",
        "V2_Intent",
        "V2_Domain",
    }
    missing = required - set(data.columns)
    if missing:
        raise KeyError(f"Colonnes manquantes dans le benchmark : {sorted(missing)}")
    if data["_Case_ID"].duplicated().any():
        raise ValueError("Le benchmark contient des _Case_ID dupliqués.")

    data["Old_Domain"] = data["Old_Domain"].fillna(MISSING_DOMAIN)
    data["True_Domain"] = data["True_Domain"].fillna(MISSING_DOMAIN)
    data["V2_Domain"] = data["V2_Domain"].fillna("No detection")
    data["Old_Error"] = notebook_error(data["Old_Domain"], data["True_Domain"])
    data["Is_V2_Error"] = notebook_error(data["V2_Domain"], data["True_Domain"])
    data["Exact_Mismatch"] = (
        data["True_Domain"].ne(MISSING_DOMAIN)
        & data["V2_Domain"].ne(data["True_Domain"])
    )
    data["V2_Fallback"] = data["V2_Domain"].isin(FALLBACK_DOMAINS)

    expected_groups = {"A_B2B", "A_Marketplace", "A_Legal", "B_Random"}
    actual_groups = set(data["Evaluation_Group"].dropna().unique())
    if actual_groups != expected_groups:
        raise ValueError(
            f"Groupes attendus {sorted(expected_groups)}, "
            f"groupes trouvés {sorted(actual_groups)}."
        )
    counts = data["Evaluation_Group"].value_counts().to_dict()
    expected_counts = {
        "A_B2B": 20,
        "A_Marketplace": 20,
        "A_Legal": 10,
        "B_Random": 50,
    }
    if counts != expected_counts:
        raise ValueError(f"Tailles d'échantillons incorrectes : {counts}")

    rows = []
    for group_name in ("A_B2B", "A_Marketplace", "A_Legal", "B_Random"):
        group = data.loc[data["Evaluation_Group"].eq(group_name)]
        rows.append({
            "Périmètre": group_name,
            "Dossiers": len(group),
            "Erreur ancien domaine": fmt_rate(rate(group["Old_Error"])),
            "Erreur V2": fmt_rate(rate(group["Is_V2_Error"])),
            "Fallback V2 (Other + No detection)": int(group["V2_Fallback"].sum()),
            "Part fallback V2": fmt_rate(rate(group["V2_Fallback"])),
            "Écart ancien - V2 (points)": (
                f"{(rate(group['Old_Error']) - rate(group['Is_V2_Error'])) * 100:+.2f}"
                if len(group) else "N/D"
            ),
        })

    risk = data.loc[data["Evaluation_Group"].ne("B_Random")]
    all_rows = {
        "Périmètre": "100 cas stratifiés (descriptif, non représentatif)",
        "Dossiers": len(data),
        "Erreur ancien domaine": fmt_rate(rate(data["Old_Error"])),
        "Erreur V2": fmt_rate(rate(data["Is_V2_Error"])),
        "Fallback V2 (Other + No detection)": int(data["V2_Fallback"].sum()),
        "Part fallback V2": fmt_rate(rate(data["V2_Fallback"])),
        "Écart ancien - V2 (points)": (
            f"{(rate(data['Old_Error']) - rate(data['Is_V2_Error'])) * 100:+.2f}"
        ),
    }
    rows.insert(0, all_rows)

    random_sample = data.loc[data["Evaluation_Group"].eq("B_Random")].copy()
    old_random = rate(random_sample["Old_Error"])
    v2_random = rate(random_sample["Is_V2_Error"])
    low, high = wilson_interval(
        int(random_sample["Is_V2_Error"].sum()), len(random_sample)
    )
    corrected = int(
        (random_sample["Old_Error"] & ~random_sample["Is_V2_Error"]).sum()
    )
    newly_introduced = int(
        (~random_sample["Old_Error"] & random_sample["Is_V2_Error"]).sum()
    )
    comparison = {
        "Périmètre": "Comparaison appariée B_Random",
        "Dossiers": len(random_sample),
        "Erreur ancien domaine": fmt_rate(old_random),
        "Erreur V2": fmt_rate(v2_random),
        "Fallback V2 (Other + No detection)": int(random_sample["V2_Fallback"].sum()),
        "Part fallback V2": fmt_rate(rate(random_sample["V2_Fallback"])),
        "Écart ancien - V2 (points)": f"{(old_random - v2_random) * 100:+.2f}",
    }
    rows.insert(1, comparison)

    summary = pd.DataFrame(rows)
    summary.to_csv(SUMMARY_PATH, index=False)
    print("KPI par cohorte (erreurs calculées avec la formule du notebook)")
    print(summary.to_string(index=False))
    print(
        f"\nRéférence notebook, population complète : {REPORTED_BASELINE:.2%}. "
        f"Ancien taux observé sur les mêmes 50 cas aléatoires : {old_random:.2%}."
    )
    print(
        "B_Random : IC 95 % de Wilson du taux V2 "
        f"[{low:.2%}, {high:.2%}] ; "
        f"erreurs anciennes corrigées={corrected}, "
        f"erreurs nouvelles introduites={newly_introduced}, "
        f"McNemar exact p={exact_mcnemar_p_value(random_sample['Old_Error'], random_sample['Is_V2_Error']):.4f}."
    )
    print(
        "Attention : les 50 cas ciblés sont volontairement suréchantillonnés. "
        "Ne pas utiliser le taux des 100 cas comme estimation de la population."
    )

    correction_specs = [
        ("B2B faux positifs vers Aftersales", "A_B2B", "B2B", "Aftersales"),
        ("Fuites Aftersales vers Marketplace", "A_Marketplace", "Aftersales", "Marketplace"),
        ("Faux positifs Legal vers Aftersales", "A_Legal", "Legal", "Aftersales"),
    ]
    correction_rows = []
    for label, group_name, old_domain, true_domain in correction_specs:
        cohort = data.loc[
            data["Evaluation_Group"].eq(group_name)
            & data["Old_Domain"].eq(old_domain)
            & data["True_Domain"].eq(true_domain)
        ]
        corrected_count = int(cohort["V2_Domain"].eq(true_domain).sum())
        correction_rows.append({
            "Cohorte ciblée": label,
            "Dossiers": len(cohort),
            "Corrigés vers la vérité terrain": corrected_count,
            "Taux de correction": fmt_rate(
                corrected_count / len(cohort) if len(cohort) else float("nan")
            ),
        })
    correction_table = pd.DataFrame(correction_rows)
    print("\nCorrection des anomalies ciblées")
    print(correction_table.to_string(index=False))

    confusion = pd.crosstab(
        random_sample["V2_Domain"],
        random_sample["True_Domain"],
        dropna=False,
    )
    confusion.to_csv(CONFUSION_PATH)
    print(f"\nMatrice de confusion B_Random enregistrée : {CONFUSION_PATH.name}")

    remaining = data.loc[
        data["True_Domain"].ne(MISSING_DOMAIN) & data["Exact_Mismatch"]
    ].copy()
    remaining.to_csv(ERRORS_PATH, index=False)
    print(
        f"Écarts exacts V2 vs vérité terrain : {len(remaining)} "
        f"(enregistrés dans {ERRORS_PATH.name})."
    )


if __name__ == "__main__":
    main()
