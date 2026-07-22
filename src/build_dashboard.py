"""
Build the self-contained HTML dashboard.

Reads data/coverage_fact.csv + metrics outputs, dictionary-encodes the fact
table into compact parallel arrays, and injects it into
dashboard/index.template.html -> dashboard/index.html (single file, no
external requests).
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
df = pd.read_csv(ROOT / "data" / "coverage_fact.csv")

months = sorted(df["month"].unique().tolist())
customers = sorted(df["customer"].unique().tolist())
states = sorted(df["state"].unique().tolist())
networks = sorted(df["network"].unique().tolist())
dtypes = sorted(df["data_type"].unique().tolist())

idx = {k: {v: i for i, v in enumerate(vals)} for k, vals in
       [("month", months), ("customer", customers), ("state", states),
        ("network", networks), ("data_type", dtypes)]}

fact = {
    "m":  df["month"].map(idx["month"]).tolist(),
    "c":  df["customer"].map(idx["customer"]).tolist(),
    "s":  df["state"].map(idx["state"]).tolist(),
    "n":  df["network"].map(idx["network"]).tolist(),
    "d":  df["data_type"].map(idx["data_type"]).tolist(),
    "q":  df["patients_queried"].tolist(),
    "ma": df["patients_matched"].tolist(),
    "w":  df["patients_with_data"].tolist(),
    "r":  df["records_returned"].tolist(),
    "f":  (df["freshness_days"] * 10).round().astype(int).tolist(),
}

incidents = pd.read_csv(ROOT / "metrics" / "incidents.csv")
top_incidents = (incidents[incidents["severity"] == "high"]
                 .sort_values(["months_affected"], ascending=False)
                 .head(40).fillna("").to_dict(orient="records"))
gaps = pd.read_csv(ROOT / "metrics" / "gaps.csv").round(3).to_dict(orient="records")
investigations = pd.read_csv(ROOT / "data" / "investigations.csv").to_dict(orient="records")

payload = {
    "dims": {"months": months, "customers": customers, "states": states,
             "networks": networks, "dataTypes": dtypes},
    "fact": fact,
    "incidents": top_incidents,
    "gaps": gaps,
    "investigations": investigations,
}

template = (ROOT / "dashboard" / "index.template.html").read_text()
out = template.replace("/*__DATA__*/null", json.dumps(payload, separators=(",", ":")))
(ROOT / "dashboard" / "index.html").write_text(out)
print(f"dashboard/index.html written ({len(out)/1e6:.2f} MB)")
