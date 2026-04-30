# Arctal Technical Assessment: Bond Data Quality Analysis

## Objective

Assess data quality in `bond_data.xlsx` across four sheets:
- `issuances`
- `cat_allocations`
- `impacts`
- `geo_allocations`

The goal is to identify high-value issues, explain business impact, and prioritize remediation.

## Method

I used `script.py` to run:
- Cross-table reconciliations (`issuances` vs category/geography allocations)
- Key integrity checks (`bond_id` completeness, uniqueness, orphan detection)
- Statistical sanity checks (FX dispersion, impact outlier behavior)
- Completeness/coverage checks (missing dates and missing child records)

The script exports both a summary and detailed evidence files.

## Prioritized Findings

### P1 - Allocation totals do not reconcile

**Category mismatch**
- `30` bonds where `sum(cat_allocations.post_allocation_USD)` does not equal `issuances.total_USD_allocated` (USD 1 tolerance).
- Largest observed gap: `bond_id=10760` (`France`), about `USD 18.1M`.

**Geography mismatch**
- `31` bonds where `sum(geo_allocations.allocation_USD)` does not equal `issuances.total_USD_allocated`.
- Largest observed gap: `bond_id=10608` (`France`), about `USD 337.7M`.

**Why this matters**
- This is a core financial integrity issue and can materially distort external reporting.

---

### P2 - Impact quality concerns (duplication, outliers, missing/invalid values)

- `50` duplicate rows by (`bond_id`, `impact_metric`)
- `47` top-5% outliers in `impact_per_million_USD`
- `34` missing `impact_per_million_USD`
- `2` negative impact values

**Why this matters**
- Likely unit mismatches or duplicate reporting; can over/understate impact reporting.

---

### P2 - FX consistency flags

- High implicit FX variability in a few currencies (e.g., HKD, GBP, USD under defined threshold rules).

**Why this matters**
- Suggests possible stale/mixed conversion dates or inconsistent currency treatment.

---

### P3 - Coverage/completeness gaps

- `5` issuance bonds without impact records
- `1` issuance bond without geography records
- `2` missing maturity dates

**Why this matters**
- Could be valid timing gaps, but should be explicitly tracked to avoid misleading completeness.

## What Looks Strong

- No missing `bond_id` in any sheet
- No duplicate `bond_id` in `issuances`
- No orphan child `bond_id` values (all child keys map to an issuance)

## Deliverables in This Repo

- `script.py`: main audit script
- `findings_summary.csv`: prioritized issue summary
- `findings_category_mismatches.csv`
- `findings_geo_mismatches.csv`
- `findings_fx_stats.csv`
- `findings_impact_duplicates.csv`
- `findings_impact_outliers_top5pct.csv`
- `findings_impact_negative_values.csv`
- `bond_data.xlsx`: source data provided for assessment

## How to Run

```bash
/usr/local/bin/python3 script.py
```

This regenerates all `findings_*.csv` files.

## Suggested Remediation Plan

1. Enforce per-bond reconciliation checks in ingestion (category and geography totals).
2. Add impact metric data contracts (unit dictionary, valid ranges, duplicate handling).
3. Define FX conversion policy (reference date/source) and validate tolerance bands.
4. Add explicit completeness flags for lagging impact/geography disclosures.
