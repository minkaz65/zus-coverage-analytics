"""
Generate a realistic synthetic dataset of clinical data coverage across the
Zus network, modeled on Zus Health's publicly documented architecture:

  - EHR networks:      CommonWell, Carequality (TEFCA ramping in 2026)
  - Pharmacy network:  Surescripts
  - ADT networks:      Bamboo Health, PointClickCare
  - Lab network:       Quest Diagnostics

Grain of the fact table: month x customer x state x network x data_type.
Metrics: patients_queried, patients_matched, patients_with_data,
         records_returned, avg_lookback_months, freshness_days (median lag).

Known real-world dynamics that the generator encodes:
  * Patient match rates on national networks vary ~55-95% by data quality
    of the demographics submitted (customer-dependent) and by network.
  * Geographic coverage is uneven: states with strong HIE participation
    (e.g. IN, NY, MA, CO) outperform low-participation states (e.g. TX rural,
    ID, WY) on record location rates.
  * Data-type completeness differs by network: pharmacy (Surescripts) has
    high med fill coverage but no labs; EHR networks carry conditions/
    encounters/documents; ADT feeds are near-real-time but narrow; Quest
    covers labs only where Quest has market share.
  * Injected incidents (for gap/anomaly detection to find):
      1. Carequality responder outage in the South-Atlantic region,
         Feb 2026 (records_returned collapses ~70% for 1 month).
      2. A customer ("Motive Care") onboards with malformed address data
         starting Nov 2025 -> match rate drops ~25 pts until fixed Mar 2026.
      3. Quest lab feed schema change Apr 2026 -> lab freshness lag spikes
         from ~3 days to ~19 days for 2 months (all customers, all states).
      4. PointClickCare ADT coverage gap in WA/OR (contract lapse)
         Dec 2025 - May 2026: patients_with_data ~0 for ADT in those states.
      5. Slow structural gap: TX/FL rural document coverage persistently
         ~35% below national mean (root cause: low network participation).

Run:  python src/generate_data.py
Outputs: data/coverage_fact.csv, data/customers.csv, data/networks.csv
"""

import numpy as np
import pandas as pd
from pathlib import Path

RNG = np.random.default_rng(42)
OUT = Path(__file__).resolve().parents[1] / "data"
OUT.mkdir(exist_ok=True)

MONTHS = pd.period_range("2025-07", "2026-06", freq="M").astype(str).tolist()

CUSTOMERS = [
    # name, segment, monthly panel size, demographics quality (match modifier)
    ("Elation Direct",   "Primary care EHR",     26000, 1.00),
    ("Oak Grove Health", "Value-based primary",  14000, 0.97),
    ("Motive Care",      "Virtual cardiology",    9000, 0.99),  # incident #2 overrides
    ("Harborview VBC",   "ACO enablement",       19000, 0.94),
    ("Lumen Behavioral", "Tele-behavioral",       7000, 0.90),
    ("Cascade Kidney",   "Nephrology group",      5000, 0.96),
    ("Bluebird Palliativ","Palliative at home",   3500, 0.88),
    ("Northstar Duals",  "D-SNP care mgmt",      12000, 0.92),
]

NETWORKS = {
    # network: (data types carried, base match rate, base data-density)
    "Carequality":     (["conditions", "encounters", "medications", "labs", "documents", "allergies", "immunizations"], 0.86, 0.78),
    "CommonWell":      (["conditions", "encounters", "medications", "labs", "documents", "allergies", "immunizations"], 0.80, 0.70),
    "Surescripts":     (["medications"], 0.93, 0.90),
    "Quest Labs":      (["labs"], 0.88, 0.62),
    "Bamboo Health":   (["adt_events"], 0.84, 0.55),
    "PointClickCare":  (["adt_events"], 0.82, 0.48),
}

DATA_TYPES = ["conditions", "encounters", "medications", "labs",
              "documents", "allergies", "immunizations", "adt_events"]

# State HIE-strength index (0-1): strong HIE states high, weak low.
STATE_STRENGTH = {
    "IN": 0.95, "NY": 0.92, "MA": 0.91, "CO": 0.89, "MD": 0.88, "MI": 0.87,
    "NC": 0.85, "WI": 0.84, "MN": 0.83, "OH": 0.82, "PA": 0.81, "WA": 0.80,
    "OR": 0.79, "CA": 0.78, "AZ": 0.77, "VA": 0.76, "TN": 0.74, "GA": 0.73,
    "IL": 0.72, "NJ": 0.71, "SC": 0.68, "KY": 0.67, "MO": 0.66, "UT": 0.66,
    "FL": 0.62, "AL": 0.60, "LA": 0.58, "OK": 0.57, "NM": 0.56, "TX": 0.55,
    "AR": 0.54, "MS": 0.52, "NV": 0.60, "ID": 0.48, "MT": 0.47, "WY": 0.45,
}
# Quest market share proxy by state (labs coverage modifier)
QUEST_SHARE = {s: 0.55 + 0.35 * RNG.random() for s in STATE_STRENGTH}
QUEST_SHARE.update({"NY": 0.85, "NJ": 0.88, "PA": 0.82, "CA": 0.75, "FL": 0.78,
                    "TX": 0.52, "MN": 0.40, "WI": 0.42, "UT": 0.45})

SOUTH_ATLANTIC = {"MD", "VA", "NC", "SC", "GA", "FL"}

# Customer geographic footprints (weights over states)
def make_footprint(k):
    states = RNG.choice(list(STATE_STRENGTH), size=k, replace=False)
    w = RNG.dirichlet(np.ones(k) * 2.0)
    return dict(zip(states, w))

FOOTPRINTS = {
    "Elation Direct":    make_footprint(20),
    "Oak Grove Health":  {"TX": 0.30, "FL": 0.25, "GA": 0.15, "AL": 0.10, "LA": 0.10, "MS": 0.10},
    "Motive Care":       make_footprint(14),
    "Harborview VBC":    {"WA": 0.35, "OR": 0.25, "CA": 0.20, "ID": 0.10, "CO": 0.10},
    "Lumen Behavioral":  make_footprint(10),
    "Cascade Kidney":    {"WA": 0.45, "OR": 0.30, "CA": 0.25},
    "Bluebird Palliativ": {"FL": 0.40, "AZ": 0.25, "TX": 0.20, "NV": 0.15},
    "Northstar Duals":   {"NY": 0.30, "NJ": 0.20, "PA": 0.20, "OH": 0.15, "MI": 0.15},
}

def month_index(m):  # 0..11
    return MONTHS.index(m)

rows = []
for cust, seg, panel, demo_q in CUSTOMERS:
    fp = FOOTPRINTS[cust]
    for m in MONTHS:
        mi = month_index(m)
        # panels grow slowly; Motive Care launches Nov 2025
        if cust == "Motive Care" and mi < month_index("2025-11"):
            continue
        growth = 1.0 + 0.015 * mi + RNG.normal(0, 0.01)
        for state, w in fp.items():
            q = max(1, int(panel * w * growth))
            strength = STATE_STRENGTH[state]
            for net, (types, base_match, base_density) in NETWORKS.items():
                # --- match rate ---
                match = base_match * demo_q * (0.85 + 0.18 * strength)
                # Incident 2: Motive Care malformed addresses Nov25-Feb26
                if cust == "Motive Care" and month_index("2025-11") <= mi <= month_index("2026-02"):
                    match *= 0.68
                match = float(np.clip(match + RNG.normal(0, 0.015), 0.30, 0.97))
                matched = int(q * match)

                for dt in types:
                    density = base_density * (0.55 + 0.55 * strength)
                    if net == "Quest Labs":
                        density = base_density * QUEST_SHARE[state]
                    # structural gap: rural-heavy TX/FL documents thin on EHR nets
                    if dt == "documents" and state in {"TX", "FL", "OK", "AR", "MS"}:
                        density *= 0.62
                    # TEFCA ramp helps Carequality density slightly through the year
                    if net == "Carequality":
                        density *= (1.0 + 0.012 * mi)
                    # Incident 4: PCC ADT gap WA/OR Dec25-May26
                    if (net == "PointClickCare" and state in {"WA", "OR"}
                            and month_index("2025-12") <= mi <= month_index("2026-05")):
                        density *= 0.03
                    # Incident 1: Carequality South-Atlantic outage Feb 2026
                    outage = (net == "Carequality" and state in SOUTH_ATLANTIC
                              and m == "2026-02")
                    density = float(np.clip(density + RNG.normal(0, 0.02), 0.01, 0.98))
                    with_data = int(matched * density)

                    rec_per = {"conditions": 6.2, "encounters": 9.5, "medications": 11.0,
                               "labs": 14.0, "documents": 4.1, "allergies": 1.6,
                               "immunizations": 2.4, "adt_events": 1.9}[dt]
                    records = int(with_data * rec_per * RNG.uniform(0.85, 1.15))
                    if outage:
                        records = int(records * 0.30)
                        with_data = int(with_data * 0.55)

                    # freshness (days from event to availability)
                    base_fresh = {"adt_events": 0.2, "medications": 2.5, "labs": 3.0,
                                  "conditions": 12.0, "encounters": 10.0, "documents": 15.0,
                                  "allergies": 14.0, "immunizations": 20.0}[dt]
                    fresh = base_fresh * RNG.uniform(0.8, 1.3)
                    # Incident 3: Quest schema change Apr-May 2026
                    if net == "Quest Labs" and m in ("2026-04", "2026-05"):
                        fresh = RNG.uniform(16, 22)

                    rows.append({
                        "month": m, "customer": cust, "segment": seg, "state": state,
                        "network": net, "data_type": dt,
                        "patients_queried": q, "patients_matched": matched,
                        "patients_with_data": with_data, "records_returned": records,
                        "freshness_days": round(fresh, 1),
                        "avg_lookback_months": round(RNG.uniform(18, 60), 0),
                    })

df = pd.DataFrame(rows)
df.to_csv(OUT / "coverage_fact.csv", index=False)

pd.DataFrame(
    [{"customer": c, "segment": s, "monthly_panel": p, "demographics_quality": d}
     for c, s, p, d in CUSTOMERS]
).to_csv(OUT / "customers.csv", index=False)

pd.DataFrame(
    [{"network": n, "data_types": "|".join(t), "base_match_rate": m, "base_density": dns}
     for n, (t, m, dns) in NETWORKS.items()]
).to_csv(OUT / "networks.csv", index=False)

print(f"coverage_fact.csv rows: {len(df):,}")
print(df.head())
