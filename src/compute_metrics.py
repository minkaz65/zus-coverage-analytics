"""
Compute coverage metrics and detect gaps/anomalies from data/coverage_fact.csv.

Metrics
  match_rate        = patients_matched / patients_queried
  hit_rate          = patients_with_data / patients_matched   (data density)
  coverage_rate     = patients_with_data / patients_queried   (end-to-end)
  records_per_hit   = records_returned / patients_with_data

Anomaly detection (two complementary methods)
  1. Time-series z-score per (network, data_type) national series:
     robust z on month-over-month values; |z| >= 2.5 flags a spike/drop.
  2. Cross-sectional gap detection: any (state, data_type) whose latest-
     quarter coverage_rate sits more than 40% below the national mean for
     that data_type is flagged as a structural coverage gap.
  3. Freshness SLO breaches: median freshness_days > SLO for the data type.

Outputs (metrics/):
  monthly_summary.csv      national KPIs per month
  by_dimension.csv         coverage by month x each dimension (long format)
  anomalies.csv            flagged anomalies with method + severity
  gaps.csv                 structural coverage gaps (latest quarter)
  dashboard_data.json      everything the HTML dashboard needs
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
df = pd.read_csv(ROOT / "data" / "coverage_fact.csv")
OUT = ROOT / "metrics"
OUT.mkdir(exist_ok=True)

FRESHNESS_SLO = {"adt_events": 1, "medications": 5, "labs": 7, "conditions": 21,
                 "encounters": 21, "documents": 30, "allergies": 30, "immunizations": 45}

def rates(g):
    q = g["patients_queried"].sum()
    m = g["patients_matched"].sum()
    w = g["patients_with_data"].sum()
    r = g["records_returned"].sum()
    return pd.Series({
        "patients_queried": q, "patients_matched": m,
        "patients_with_data": w, "records_returned": r,
        "match_rate": m / q if q else np.nan,
        "hit_rate": w / m if m else np.nan,
        "coverage_rate": w / q if q else np.nan,
        "records_per_hit": r / w if w else np.nan,
        "median_freshness_days": g["freshness_days"].median(),
    })

# ---------- summaries ----------
monthly = df.groupby("month").apply(rates, include_groups=False).reset_index()
monthly.to_csv(OUT / "monthly_summary.csv", index=False)

dims = {}
for dim in ["state", "network", "data_type", "customer"]:
    d = df.groupby(["month", dim]).apply(rates, include_groups=False).reset_index()
    d = d.rename(columns={dim: "value"})
    d["dimension"] = dim
    dims[dim] = d
by_dim = pd.concat(dims.values(), ignore_index=True)
by_dim.to_csv(OUT / "by_dimension.csv", index=False)

# ---------- 1. time-series anomalies ----------
anoms = []
for keys, dim in [ (["network"], "network"),
                   (["network", "data_type"], "network+data_type"),
                   (["customer"], "customer"),
                   (["state", "network"], "state+network") ]:
    ser = df.groupby(keys + ["month"]).apply(rates, include_groups=False).reset_index()
    for name, g in ser.groupby(keys):
        g = g.sort_values("month")
        for metric in ["coverage_rate", "match_rate", "median_freshness_days"]:
            v = g[metric].to_numpy(dtype=float)
            if len(v) < 6:
                continue
            med, mad = np.median(v), np.median(np.abs(v - np.median(v)))
            if mad == 0:
                continue
            z = 0.6745 * (v - med) / mad
            for i, zi in enumerate(z):
                if abs(zi) >= 2.5:
                    label = name if isinstance(name, str) else " / ".join(name)
                    anoms.append({
                        "month": g["month"].iloc[i], "scope": dim, "entity": label,
                        "metric": metric, "value": round(float(v[i]), 3),
                        "baseline_median": round(float(med), 3),
                        "robust_z": round(float(zi), 2),
                        "direction": "spike" if zi > 0 else "drop",
                        "severity": "high" if abs(zi) >= 4 else "medium",
                        "method": "robust_zscore",
                    })
anom_df = pd.DataFrame(anoms).sort_values(["severity", "robust_z"],
                                          ascending=[True, True])

# ---------- 1b. level-shift detection ----------
# Robust z-scores miss long-lived regressions (the shifted months drag the
# median with them). Compare each series' trailing 6-month mean to its
# leading 6-month mean; flag relative drops > 30%.
ls_ser = df.groupby(["state", "network", "month"]).apply(rates, include_groups=False).reset_index()
for (state, net), g in ls_ser.groupby(["state", "network"]):
    g = g.sort_values("month")
    if len(g) < 12:
        continue
    head, tail = g["coverage_rate"].iloc[:6].mean(), g["coverage_rate"].iloc[6:].mean()
    if head > 0.02 and (tail / head - 1) < -0.30:
        anoms.append({
            "month": g["month"].iloc[-1], "scope": "state+network",
            "entity": f"{state} / {net}", "metric": "coverage_rate",
            "value": round(float(tail), 3), "baseline_median": round(float(head), 3),
            "robust_z": np.nan, "direction": "drop",
            "severity": "high" if (tail / head - 1) < -0.60 else "medium",
            "method": "level_shift",
        })

# ---------- 2. structural gaps (latest quarter) ----------
last3 = sorted(df["month"].unique())[-3:]
recent = df[df["month"].isin(last3)]
nat = recent.groupby("data_type").apply(rates, include_groups=False)["coverage_rate"]
sd = recent.groupby(["state", "data_type"]).apply(rates, include_groups=False).reset_index()
sd["national_coverage"] = sd["data_type"].map(nat)
sd["gap_pct_vs_national"] = (sd["coverage_rate"] / sd["national_coverage"] - 1) * 100
gaps = sd[(sd["gap_pct_vs_national"] < -40) & (sd["patients_queried"] > 3000)].copy()
gaps["severity"] = np.where(gaps["gap_pct_vs_national"] < -70, "high", "medium")
gaps = gaps.sort_values("gap_pct_vs_national")
gaps.round(3).to_csv(OUT / "gaps.csv", index=False)

# ---------- 3. freshness SLO breaches ----------
fresh = df.groupby(["month", "network", "data_type"])["freshness_days"].median().reset_index()
fresh["slo_days"] = fresh["data_type"].map(FRESHNESS_SLO)
breach = fresh[fresh["freshness_days"] > fresh["slo_days"]].copy()
for _, b in breach.iterrows():
    anoms.append({
        "month": b["month"], "scope": "network+data_type",
        "entity": f'{b["network"]} / {b["data_type"]}',
        "metric": "median_freshness_days", "value": round(b["freshness_days"], 1),
        "baseline_median": b["slo_days"], "robust_z": np.nan,
        "direction": "spike",
        "severity": "high" if b["freshness_days"] > 2 * b["slo_days"] else "medium",
        "method": "slo_breach",
    })
anom_df = pd.DataFrame(anoms)
anom_df.to_csv(OUT / "anomalies.csv", index=False)

# ---------- consolidate raw flags into incidents ----------
# Consecutive monthly flags on the same (scope, entity, metric, direction)
# are one incident with a start and end month.
inc_rows = []
mi = {m: i for i, m in enumerate(sorted(df["month"].unique()))}
for (scope, entity, metric, direction), g in anom_df.groupby(
        ["scope", "entity", "metric", "direction"]):
    g = g.sort_values("month")
    idxs = [mi[m] for m in g["month"]]
    start = prev = idxs[0]
    chunk = [g.iloc[0]]
    def flush(chunk, start, end):
        worst = max(chunk, key=lambda r: abs(r["robust_z"]) if pd.notna(r["robust_z"]) else 99)
        inv_m = sorted(df["month"].unique())
        inc_rows.append({
            "scope": scope, "entity": entity, "metric": metric,
            "direction": direction, "start_month": inv_m[start],
            "end_month": inv_m[end], "months_affected": end - start + 1,
            "worst_value": worst["value"], "baseline": worst["baseline_median"],
            "peak_robust_z": worst["robust_z"],
            "severity": "high" if any(c["severity"] == "high" for c in chunk) else "medium",
            "method": worst["method"],
        })
    for i, (idx, (_, row)) in enumerate(zip(idxs[1:], list(g.iterrows())[1:]), 1):
        if idx == prev + 1:
            chunk.append(row); prev = idx
        else:
            flush(chunk, start, prev); start = prev = idx; chunk = [row]
    flush(chunk, start, prev)
incidents = pd.DataFrame(inc_rows).sort_values(
    ["severity", "months_affected"], ascending=[True, False])
incidents.to_csv(OUT / "incidents.csv", index=False)

# ---------- dashboard JSON ----------
inv_path = ROOT / "data" / "investigations.csv"
investigations = (pd.read_csv(inv_path).to_dict(orient="records")
                  if inv_path.exists() else [])

payload = {
    "investigations": investigations,
    "months": sorted(df["month"].unique().tolist()),
    "monthly": monthly.round(4).to_dict(orient="records"),
    "by_dimension": by_dim.round(4).to_dict(orient="records"),
    "state_latest": sd.round(4).to_dict(orient="records"),
    "gaps": gaps.round(3).to_dict(orient="records"),
    "anomalies": anom_df.fillna("").to_dict(orient="records"),
    "incidents": incidents.fillna("").to_dict(orient="records"),
    "freshness_slo": FRESHNESS_SLO,
}
(OUT / "dashboard_data.json").write_text(json.dumps(payload))
print(f"anomalies: {len(anom_df)}, gaps: {len(gaps)}")
print(anom_df.groupby(['method','severity']).size())
