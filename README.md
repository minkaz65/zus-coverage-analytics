# Zus Network — Clinical Data Coverage Analytics

Metrics, anomaly detection, and an interactive dashboard tracking clinical data
coverage across the Zus aggregation network — **by geography, network partner,
data type, and customer** — plus root-cause investigations for every detected
gap and anomaly.

> **Data is synthetic.** Zus Health's real coverage numbers are not public. The
> dataset is generated to match Zus's publicly documented architecture
> ([docs.zushealth.com](https://docs.zushealth.com/docs/intro-to-zus)): EHR data
> via CommonWell & Carequality, pharmacy via Surescripts, ADT via Bamboo Health
> & PointClickCare, labs via Quest Diagnostics — with realistic match rates,
> state-level HIE participation effects, and five injected incidents for the
> detectors to find. No real patient or customer data anywhere.

## Quick start

```bash
pip install -r requirements.txt
python src/generate_data.py      # -> data/coverage_fact.csv (13.5K rows)
python src/compute_metrics.py    # -> metrics/*.csv, dashboard_data.json
python src/build_dashboard.py    # -> dashboard/index.html
open dashboard/index.html        # single self-contained file, no server needed
```

## What's here

| Path | What it is |
|---|---|
| `dashboard/index.html` | Self-contained interactive dashboard — KPI tiles, coverage & freshness trends by network, data-type and customer breakdowns, a state × data-type coverage heatmap, investigations panel, and a full data-table view. Filters (period, customer, state, network, data type) scope everything. Light & dark mode. |
| `src/generate_data.py` | Synthetic data generator (documented assumptions + injected incidents) |
| `src/compute_metrics.py` | Metrics + three detector families: robust z-score (spikes), level-shift (sustained regressions), SLO rules (freshness) |
| `src/build_dashboard.py` | Compacts the fact table and injects it into the dashboard template |
| `data/coverage_fact.csv` | Fact table: month × customer × state × network × data type |
| `data/investigations.csv` | Root-cause log for the five major findings |
| `metrics/` | Monthly summaries, per-dimension rollups, anomalies, consolidated incidents, structural gaps |
| `reports/findings_report.md` | Stakeholder-facing findings: what broke, why, who was affected, what changed |

## Core metrics

- **Match rate** = patients matched ÷ patients queried — demographics quality + record location
- **Hit rate** = patients with data ÷ patients matched — data density given a match
- **Coverage rate** = patients with data ÷ patients queried — what a customer actually experiences
- **Freshness** = days from clinical event to data availability, against per-data-type SLOs

## Detection design (the interesting part)

Three detector families run in parallel because each misses what the others catch:

1. **Robust z-score** (median/MAD, |z| ≥ 2.5) on monthly series at four scopes —
   network, network × data type, customer, state × network. Catches spikes and
   short outages (e.g., a one-month regional responder outage at |z| ≈ 10).
2. **Level-shift** (trailing vs. leading 6-month mean, −30% threshold). Catches
   sustained regressions that *move the median itself* and therefore evade
   z-scores — exactly how a 6-month regional ADT feed loss slipped past detector #1.
3. **SLO rules** on freshness — latency incidents are invisible in volume metrics.

Consecutive monthly flags are consolidated into incidents with start/end,
peak deviation, and severity. Root causes are documented per incident in
`data/investigations.csv` and surfaced in the dashboard.

## Findings summary

See [`reports/findings_report.md`](reports/findings_report.md). Headlines: a
customer-side demographics regression that presented as a *cross-network* match
drop; a one-month Carequality responder outage in the South-Atlantic; a Quest
schema change that breached the lab freshness SLO for two months; a six-month
PointClickCare contract lapse in WA/OR that blended-network dashboards masked;
and a persistent structural document-coverage gap in the Gulf states that is a
network-strategy issue, not an engineering one.
