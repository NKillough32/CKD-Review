import os
import numpy as np
import pandas as pd
from datetime import datetime

# ----------------- Helpers -----------------

def _parse_stage(text: str | float | None):
    """
    Return ('1'..'5', 'A'/'B'/None) if 'Stage X[A/B]' found; else None.
    Ignores 'Normal Function'.
    """
    if not isinstance(text, str):
        return None
    t = text.strip().lower()
    if "normal function" in t:
        return None
    # e.g. "Stage 3A", "stage3b", "STAGE 4"
    import re
    m = re.search(r"stage\s*([1-5])\s*([ab])?", t, flags=re.I)
    if not m:
        return None
    num = m.group(1)
    letter = (m.group(2) or "").upper() if m.group(2) else None
    return (num, letter)

def _is_uncoded_emis(emis_code: str | float | None):
    """
    True if EMIS code clearly indicates no structured CKD entry.
    Handles NaN, 'No EMIS', 'EMIS CKD entry missing', etc.
    """
    if not isinstance(emis_code, str):
        return True
    t = emis_code.strip().lower()
    return (
        not t or
        "no emis" in t or
        "ckd entry missing" in t or
        "emis ckd entry missing" in t
    )

def _safe_days_since(dt_series: pd.Series, now: pd.Timestamp) -> pd.Series:
    """Return days since each timestamp, NaN-safe."""
    dt = pd.to_datetime(dt_series, errors="coerce")
    return (now - dt).dt.days

# ----------------- Core analysis -----------------

def analyze_ckd_data(filepath):
    df = pd.read_csv(filepath)

    # Normalise some columns
    now = pd.Timestamp.now()
    # Dates we use for recency
    if "Sample_Date" in df.columns:
        days_since_creat = _safe_days_since(df["Sample_Date"], now)
    else:
        days_since_creat = pd.Series(np.nan, index=df.index)
    if "Sample_Date1" in df.columns:
        days_since_acr = _safe_days_since(df["Sample_Date1"], now)
    else:
        days_since_acr = pd.Series(np.nan, index=df.index)

    # ---------- Staging mismatch / uncoded ----------
    emis_stage_parsed = df.get("EMIS_CKD_Code", pd.Series(index=df.index)).apply(_parse_stage)
    current_stage_parsed = df.get("CKD_Stage", pd.Series(index=df.index)).apply(_parse_stage)

    # staging mismatch only when both sides have a stage
    staging_mismatch_mask = (
        emis_stage_parsed.notna() &
        current_stage_parsed.notna() &
        (emis_stage_parsed != current_stage_parsed)
    )

    # uncoded CKD: EMIS missing but current has a stage
    uncoded_ckd_mask = (
        df.get("EMIS_CKD_Code", pd.Series(index=df.index)).apply(_is_uncoded_emis) &
        current_stage_parsed.notna()
    )

    # ---------- Simple tallies (vectorised) ----------
    bp_not_at_target = (df.get("BP_Flag") == "Above Target").sum()

    anaemia_count = df.get("Anaemia_Classification", pd.Series(index=df.index)).astype(str)\
                        .str.contains("Anaemia", case=False, na=False).sum()

    vitamin_d_deficient = (df.get("Vitamin_D_Flag") == "Deficient").sum()

    high_cv_risk = (df.get("CV_Risk") == "High Risk").sum()

    referral_needed = (df.get("Nephrology_Referral") == "Indicated on the basis of risk calculation").sum()

    # AKI: your pipeline produces strings e.g. "AKI Stage 1 - Review"
    aki_series = df.get("AKI_Flag", pd.Series(index=df.index)).astype(str)
    aki_cases = aki_series.str.startswith("AKI", na=False).sum()
    # Optional: breakdown by stage
    # aki_breakdown = aki_series[aki_series.str.startswith("AKI", na=False)].value_counts().to_dict()

    # Contraindications / dose adjustments
    contra_mask = df.get("contraindicated_prescribed", pd.Series(index=df.index)).notna() & \
                  (df["contraindicated_prescribed"] != "No contraindications")
    dose_adj_mask = df.get("dose_adjustment_prescribed", pd.Series(index=df.index)).notna() & \
                    (df["dose_adjustment_prescribed"] != "No adjustments needed")
    contraindicated_drugs = int(contra_mask.sum())
    dose_adjustment_needed = int(dose_adj_mask.sum())

    # Stage distribution (keep original labels as-is)
    stage_distribution = df.get("CKD_Stage", pd.Series(index=df.index)).value_counts(dropna=False).to_dict()

    # BP classification distribution
    bp_classification = df.get("BP_Classification", pd.Series(index=df.index)).fillna("Unknown")\
                          .astype(str).value_counts().to_dict()

    # Priority distribution
    priority_distribution = df.get("Priority", pd.Series(index=df.index)).fillna("Unknown")\
                              .astype(str).value_counts().to_dict()

    # Gender distribution
    gender_distribution = df.get("Gender", pd.Series(index=df.index)).fillna("Unknown")\
                             .astype(str).value_counts().to_dict()

    # Proteinuria distribution (A1/A2/A3 etc.)
    proteinuria_distribution = df.get("CKD_ACR", pd.Series(index=df.index)).fillna("Unknown")\
                                  .astype(str).value_counts().to_dict()

    # Baseline measures
    acr = pd.to_numeric(df.get("ACR", pd.Series(index=df.index)), errors="coerce")
    albuminuria_tested = int((acr.notna()) & (acr != 0.019)).sum()

    # BP above threshold ≥140/90 (use ≥ per common audit definitions)
    sbp = pd.to_numeric(df.get("Systolic_BP", np.nan), errors="coerce")
    dbp = pd.to_numeric(df.get("Diastolic_BP", np.nan), errors="coerce")
    bp_above_threshold = int(((sbp >= 140) | (dbp >= 90)).sum())

    # Outcome measures
    rapid_egfr_decline = int((df.get("eGFR_Trend", pd.Series(index=df.index)) == "Rapid Decline").sum())
    meds = df.get("Medications", pd.Series(index=df.index)).astype(str)
    ace_arb_mask = meds.str.contains(r"\b(Ramipril|Lisinopril|Losartan|ACEi|ARB)\b", case=False, regex=True, na=False)
    acei_arb_prescribed = int(ace_arb_mask.sum())

    # Process measures
    annual_screening_done = int(
        (days_since_creat <= 365) &
        (days_since_acr <= 365)
    ).sum()

    high_risk = (df.get("Priority") == "High")
    high_risk_reviewed = int((high_risk) & (days_since_creat <= 180)).sum()

    # Balancing measure: hyperkalaemia
    potassium = pd.to_numeric(df.get("Potassium", np.nan), errors="coerce")
    potassium_flag = df.get("Potassium_Flag", pd.Series(index=df.index)).astype(str)
    hyperk_mask = (potassium_flag == "Hyperkalemia") | (potassium > 5.5)
    hyperkalaemia_cases = int(hyperk_mask.sum())

    # Summaries
    age = pd.to_numeric(df.get("Age", np.nan), errors="coerce")
    eGFR = pd.to_numeric(df.get("eGFR", np.nan), errors="coerce")

    stats = {
        "total_patients": int(len(df)),
        "staging_mismatch": int(staging_mismatch_mask.sum()),
        "contraindicated_drugs": contraindicated_drugs,
        "dose_adjustment_needed": dose_adjustment_needed,
        "uncoded_ckd": int(uncoded_ckd_mask.sum()),
        "stage_distribution": stage_distribution,
        "bp_not_at_target": int(bp_not_at_target),
        "anaemia_count": int(anaemia_count),
        "vitamin_d_deficient": int(vitamin_d_deficient),
        "high_cv_risk": int(high_cv_risk),
        "referral_needed": int(referral_needed),
        "aki_cases": int(aki_cases),
        "priority_distribution": priority_distribution,
        "age_stats": {
            "mean": float(age.mean(skipna=True)) if len(age) else np.nan,
            "median": float(age.median(skipna=True)) if len(age) else np.nan,
            "min": float(age.min(skipna=True)) if len(age) else np.nan,
            "max": float(age.max(skipna=True)) if len(age) else np.nan,
        },
        "gender_distribution": gender_distribution,
        "proteinuria_distribution": proteinuria_distribution,
        "bp_classification": bp_classification,
        "egfr_stats": {
            "mean": float(eGFR.mean(skipna=True)) if len(eGFR) else np.nan,
            "median": float(eGFR.median(skipna=True)) if len(eGFR) else np.nan,
            "min": float(eGFR.min(skipna=True)) if len(eGFR) else np.nan,
            "max": float(eGFR.max(skipna=True)) if len(eGFR) else np.nan,
        },
        "baseline_measures": {
            "albuminuria_tested": int(albuminuria_tested),
            "bp_above_threshold": int(bp_above_threshold),
        },
        "outcome_measures": {
            "rapid_egfr_decline": int(rapid_egfr_decline),
            "acei_arb_prescribed": int(acei_arb_prescribed),
        },
        "process_measures": {
            "annual_screening_done": int(annual_screening_done),
            "high_risk_reviewed": int(high_risk_reviewed),
        },
        "balancing_measures": {
            "hyperkalaemia_cases": int(hyperkalaemia_cases),
        },
    }
    return stats

# ----------------- Reporting (unchanged API) -----------------

def print_results(stats):
    print("\n=== CKD Patient Analysis Results ===")
    total = max(stats['total_patients'], 1)  # avoid div/0 in formatting

    def pct(x): return f"{(x/total*100):.1f}%"

    print(f"Total number of patients: {total}")

    print("\nStaging Discrepancies:")
    print(f"Number of patients with EMIS staging mismatch: {stats['staging_mismatch']} ({pct(stats['staging_mismatch'])})")
    print(f"Number of patients with uncoded CKD: {stats['uncoded_ckd']} ({pct(stats['uncoded_ckd'])})")

    print("\nCKD Stage Distribution:")
    for stage, count in sorted(stats['stage_distribution'].items(), key=lambda x: str(x[0])):
        print(f"{stage}: {count} patients ({pct(count)})")

    print("\nClinical Indicators:")
    print(f"Patients with BP above target: {stats['bp_not_at_target']} ({pct(stats['bp_not_at_target'])})")
    print(f"Patients with Anaemia: {stats['anaemia_count']} ({pct(stats['anaemia_count'])})")
    print(f"Patients with Vitamin D deficiency: {stats['vitamin_d_deficient']} ({pct(stats['vitamin_d_deficient'])})")
    print(f"Patients with high CV risk: {stats['high_cv_risk']} ({pct(stats['high_cv_risk'])})")
    print(f"Patients needing nephrology referral: {stats['referral_needed']} ({pct(stats['referral_needed'])})")
    print(f"Patients with AKI: {stats['aki_cases']} ({pct(stats['aki_cases'])})")

    print("\nMedication Issues:")
    print(f"Patients on contraindicated medications: {stats['contraindicated_drugs']} ({pct(stats['contraindicated_drugs'])})")
    print(f"Patients requiring medication dose adjustments: {stats['dose_adjustment_needed']} ({pct(stats['dose_adjustment_needed'])})")

    print("\nAge Statistics:")
    print(f"Mean age: {stats['age_stats']['mean']:.1f}")
    print(f"Median age: {stats['age_stats']['median']:.1f}")
    print(f"Age range: {stats['age_stats']['min']:.0f} - {stats['age_stats']['max']:.0f}")

    print("\neGFR Statistics:")
    print(f"Mean eGFR: {stats['egfr_stats']['mean']:.1f}")
    print(f"Median eGFR: {stats['egfr_stats']['median']:.1f}")
    print(f"eGFR range: {stats['egfr_stats']['min']:.0f} - {stats['egfr_stats']['max']:.0f}")

    print("\nGender Distribution:")
    for gender, count in stats['gender_distribution'].items():
        print(f"{gender}: {count} patients ({pct(count)})")

    print("\nProteinuria Distribution:")
    for category, count in sorted(stats['proteinuria_distribution'].items(), key=lambda x: str(x[0])):
        print(f"{category}: {count} patients ({pct(count)})")

    print("\nBP Classification:")
    for bp_class, count in sorted(stats['bp_classification'].items(), key=lambda x: str(x[0])):
        print(f"{bp_class}: {count} patients ({pct(count)})")

    print("\nPriority Distribution:")
    for priority, count in sorted(stats['priority_distribution'].items(), key=lambda x: str(x[0])):
        print(f"{priority}: {count} patients ({pct(count)})")

    print("\nQuality Measures:")

    print("\nBaseline Measures:")
    print(f"Patients with albuminuria testing: {stats['baseline_measures']['albuminuria_tested']} ({pct(stats['baseline_measures']['albuminuria_tested'])})")
    print(f"Patients with BP ≥140/90 mmHg: {stats['baseline_measures']['bp_above_threshold']} ({pct(stats['baseline_measures']['bp_above_threshold'])})")

    print("\nOutcome Measures:")
    print(f"Patients with rapid eGFR decline: {stats['outcome_measures']['rapid_egfr_decline']} ({pct(stats['outcome_measures']['rapid_egfr_decline'])})")
    print(f"Patients on ACEi/ARB therapy: {stats['outcome_measures']['acei_arb_prescribed']} ({pct(stats['outcome_measures']['acei_arb_prescribed'])})")

    print("\nProcess Measures:")
    print(f"Patients with annual screening (creatinine & ACR within 12 months): {stats['process_measures']['annual_screening_done']} ({pct(stats['process_measures']['annual_screening_done'])})")
    print(f"High-risk patients reviewed ≤6 months: {stats['process_measures']['high_risk_reviewed']} ({pct(stats['process_measures']['high_risk_reviewed'])})")

    print("\nBalancing Measures:")
    print(f"Patients with hyperkalaemia: {stats['balancing_measures']['hyperkalaemia_cases']} ({pct(stats['balancing_measures']['hyperkalaemia_cases'])})")

def save_results(stats, output_path):
    total = max(stats['total_patients'], 1)
    def pct(x): return f"{(x/total*100):.1f}%"
    with open(output_path, "w") as f:
        f.write("=== CKD Patient Analysis Results ===\n")
        f.write(f"Total number of patients: {total}\n\n")

        f.write("Staging Discrepancies:\n")
        f.write(f"Number of patients with EMIS staging mismatch: {stats['staging_mismatch']} ({pct(stats['staging_mismatch'])})\n")
        f.write(f"Number of patients with uncoded CKD: {stats['uncoded_ckd']} ({pct(stats['uncoded_ckd'])})\n\n")

        f.write("Clinical Indicators:\n")
        f.write(f"Patients with BP above target: {stats['bp_not_at_target']} ({pct(stats['bp_not_at_target'])})\n")
        f.write(f"Patients with Anaemia: {stats['anaemia_count']} ({pct(stats['anaemia_count'])})\n")
        f.write(f"Patients with Vitamin D deficiency: {stats['vitamin_d_deficient']} ({pct(stats['vitamin_d_deficient'])})\n")
        f.write(f"Patients with high CV risk: {stats['high_cv_risk']} ({pct(stats['high_cv_risk'])})\n")
        f.write(f"Patients needing nephrology referral: {stats['referral_needed']} ({pct(stats['referral_needed'])})\n")
        f.write(f"Patients with AKI: {stats['aki_cases']} ({pct(stats['aki_cases'])})\n\n")

        f.write("Medication Issues:\n")
        f.write(f"Patients on contraindicated medications: {stats['contraindicated_drugs']} ({pct(stats['contraindicated_drugs'])})\n")
        f.write(f"Patients requiring medication dose adjustments: {stats['dose_adjustment_needed']} ({pct(stats['dose_adjustment_needed'])})\n\n")

        f.write("Age Statistics:\n")
        f.write(f"Mean age: {stats['age_stats']['mean']:.1f}\n")
        f.write(f"Median age: {stats['age_stats']['median']:.1f}\n")
        f.write(f"Age range: {stats['age_stats']['min']:.0f} - {stats['age_stats']['max']:.0f}\n\n")

        f.write("eGFR Statistics:\n")
        f.write(f"Mean eGFR: {stats['egfr_stats']['mean']:.1f}\n")
        f.write(f"Median eGFR: {stats['egfr_stats']['median']:.1f}\n")
        f.write(f"eGFR range: {stats['egfr_stats']['min']:.0f} - {stats['egfr_stats']['max']:.0f}\n\n")

        f.write("Gender Distribution:\n")
        for gender, count in stats['gender_distribution'].items():
            f.write(f"{gender}: {count} patients ({pct(count)})\n")
        f.write("\nProteinuria Distribution:\n")
        for category, count in sorted(stats['proteinuria_distribution'].items(), key=lambda x: str(x[0])):
            f.write(f"{category}: {count} patients ({pct(count)})\n")
        f.write("\nBP Classification:\n")
        for bp_class, count in sorted(stats['bp_classification'].items(), key=lambda x: str(x[0])):
            f.write(f"{bp_class}: {count} patients ({pct(count)})\n")
        f.write("\nPriority Distribution:\n")
        for priority, count in sorted(stats['priority_distribution'].items(), key=lambda x: str(x[0])):
            f.write(f"{priority}: {count} patients ({pct(count)})\n")

        f.write("\nBaseline Measures:\n")
        f.write(f"Patients with albuminuria testing: {stats['baseline_measures']['albuminuria_tested']} ({pct(stats['baseline_measures']['albuminuria_tested'])})\n")
        f.write(f"Patients with BP ≥140/90 mmHg: {stats['baseline_measures']['bp_above_threshold']} ({pct(stats['baseline_measures']['bp_above_threshold'])})\n\n")

        f.write("Outcome Measures:\n")
        f.write(f"Patients with rapid eGFR decline: {stats['outcome_measures']['rapid_egfr_decline']} ({pct(stats['outcome_measures']['rapid_egfr_decline'])})\n")
        f.write(f"Patients on ACEi/ARB therapy: {stats['outcome_measures']['acei_arb_prescribed']} ({pct(stats['outcome_measures']['acei_arb_prescribed'])})\n\n")

        f.write("Process Measures:\n")
        f.write(f"Patients with annual screening (creatinine & ACR within 12 months): {stats['process_measures']['annual_screening_done']} ({pct(stats['process_measures']['annual_screening_done'])})\n")
        f.write(f"High-risk patients reviewed ≤6 months: {stats['process_measures']['high_risk_reviewed']} ({pct(stats['process_measures']['high_risk_reviewed'])})\n\n")

        f.write("Balancing Measures:\n")
        f.write(f"Patients with hyperkalaemia: {stats['balancing_measures']['hyperkalaemia_cases']} ({pct(stats['balancing_measures']['hyperkalaemia_cases'])})\n")
# ----------------- CLI block (unchanged from your version) -----------------
if __name__ == "__main__":
    current_date = datetime.now().strftime("%Y-%m-%d")
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    folder = os.path.join(base_path, "Patient_Summaries", current_date)
    filepath = os.path.join(folder, f"data_check_{current_date}.csv")
    output_path = os.path.join(folder, f"analysis_results_{current_date}.txt")

    if not os.path.exists(filepath):
        print(f"Error: File not found at {filepath}")
        raise SystemExit(1)

    results = analyze_ckd_data(filepath)
    save_results(results, output_path)
    print(f"Analysis results saved to: {output_path}")
    print_results(results)