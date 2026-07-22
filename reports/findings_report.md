# Clinical Data Coverage — Findings Report

**Period:** July 2025 – June 2026 · **Prepared for:** customers and internal stakeholders
**Data:** synthetic demonstration dataset modeled on the Zus network architecture (CommonWell, Carequality, Surescripts, Quest Diagnostics, Bamboo Health, PointClickCare)

## Executive summary

Network-wide, end-to-end coverage (patients with data returned ÷ patients queried) finished the period at **55.8%**, up from 52.1% a year earlier, driven mostly by Carequality density improvements as TEFCA connectivity ramps. Match rate ended at **78.8%**. Five notable events shaped the year: one customer-side data-quality regression, one regional network outage, one lab-feed latency incident, one six-month regional ADT feed loss, and one persistent structural gap in Gulf-state document coverage. Four of the five are resolved; the structural gap is a network-strategy item, not an engineering fix.

The key operational lesson of the period: **no single detector catches everything.** The z-score detector missed a six-month regional outage precisely because the outage was long enough to move the baseline; a level-shift detector now covers that class. Conversely, correlated drops across all six networks at once are a signature of a *customer-side* demographics problem, not a network problem — decomposition by customer is the first triage step for any cross-network anomaly.

## How to read the metrics

| Metric | Definition | What it tells you |
|---|---|---|
| Match rate | patients matched ÷ patients queried | Quality of demographics + network record location |
| Hit rate | patients with data ÷ patients matched | Data density where a match exists |
| Coverage rate | patients with data ÷ patients queried | End-to-end: what a customer actually experiences |
| Freshness | days from clinical event to availability | Whether data arrives in time to act on |

Coverage is examined on four axes — geography (state), network partner, data type, and customer — because each axis isolates a different root-cause family: geography → network participation; network → partner/feed health; data type → source-system mix; customer → demographics quality and panel geography.

## Findings

### 1. Match-rate drop across all networks (Nov 2025 – Feb 2026) — resolved

National match rate fell ~2.5 points, with drops appearing **simultaneously on all six networks**. Because a genuine network problem is never synchronized across independent partners, triage went straight to decomposition by customer: the entire drop was concentrated in **Motive Care**, which onboarded in November with address lines concatenated into a single field by their EHR export. Their panel matched ~25 points below expectation on every network. A parser fix in their intake pipeline (March) restored match rates within one cycle.

**Customer communication:** Motive Care received a weekly coverage readout during remediation showing match rate vs. cohort benchmark, so the improvement was visible to them as it landed.

### 2. Carequality coverage collapse, South-Atlantic states (Feb 2026) — resolved

Coverage rate for MD/VA/NC/SC/GA/FL on Carequality dropped 40–60% for one month (peak |z| ≈ 10). `records_returned` collapsed ~70% while `patients_queried` was flat — the signature of a **responder outage**, not a demand change. A major regional implementer confirmed a data-center migration took their responders offline. Backfill queries recovered the history in March; per-implementer responder health monitoring was added so the next one is caught in days, not at month-end.

### 3. Quest lab freshness SLO breach (Apr – May 2026) — resolved

Median lab freshness jumped from ~3 days to ~19 days against a 7-day SLO — volume unaffected, latency only, which pointed at our ingest rather than the feed. Quest had changed result-feed schema (new OBX segments); non-conforming messages were quarantined for manual review. Parser updated late May; a schema-drift canary now sits on all inbound lab feeds. **Impact concentrated in lab-dependent customers** (e.g., nephrology eGFR monitoring), who were notified with expected-recovery dates.

### 4. ADT coverage loss in WA/OR via PointClickCare (Dec 2025 – May 2026) — resolved

A regional contract lapse silently removed Pacific-Northwest facilities from the PointClickCare feed; coverage fell ~95% in WA/OR for six months. Two detection lessons:

- The **z-score detector missed it** — six affected months out of twelve dragged the series median down with them. The level-shift detector (trailing vs. leading 6-month mean) now catches sustained regressions.
- **Blended ADT dashboards masked it** — Bamboo Health kept blended ADT coverage looking tolerable. Coverage views now break out per-partner series so one partner can't hide another's gap.

WA/OR-concentrated customers (Harborview VBC, Cascade Kidney) bore nearly all the impact through degraded readmission-outreach workflows.

### 5. Structural document gap: TX, OK, MS (+FL, AR) — open

Document coverage in these states runs persistently **40–45% below the national mean** — not an incident but a structural feature of low rural provider participation in nationwide EHR networks. This is a network-strategy problem: prioritize regional HIE partnerships in the Gulf states and track the TEFCA QHIN ramp quarterly. Meanwhile it is an **expectations problem** with customers: Gulf-state-heavy panels (Oak Grove, Bluebird) should see this called out during onboarding and in their standing coverage reports rather than discovering it anecdotally.

## Recommendations

1. **Run three detector families in parallel** — robust z-score for spikes, level-shift for sustained regressions, SLO rules for latency. Each catches a class the others miss.
2. **Triage cross-network correlated drops as customer-side first.** Independent networks don't fail in unison; demographics do.
3. **Never publish only blended coverage.** Per-partner breakouts are what make a partner-level gap visible.
4. **Watch volume and latency separately.** Incident 3 was invisible in volume metrics.
5. **Separate incidents from structural gaps in customer communication.** Incidents get status updates and recovery dates; structural gaps get expectation-setting and a strategy roadmap.

## Appendix — artifacts

- `dashboard/index.html` — interactive dashboard (filters: period, customer, state, network, data type)
- `metrics/incidents.csv` — all consolidated detector flags
- `metrics/gaps.csv` — structural gaps, latest quarter
- `data/investigations.csv` — root-cause log (source for the dashboard's investigations panel)
