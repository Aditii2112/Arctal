import pandas as pd

WORKBOOK_PATH = "bond_data.xlsx"
ROUNDING_TOLERANCE_USD = 1.0


def load_data():
    """Load all assessment tables from the workbook."""
    return {
        "issuances": pd.read_excel(WORKBOOK_PATH, sheet_name="issuances"),
        "cat_allocations": pd.read_excel(WORKBOOK_PATH, sheet_name="cat_allocations"),
        "impacts": pd.read_excel(WORKBOOK_PATH, sheet_name="impacts"),
        "geo_allocations": pd.read_excel(WORKBOOK_PATH, sheet_name="geo_allocations"),
    }


def add_finding(summary_rows, priority, check, issue, count, notes):
    summary_rows.append(
        {
            "priority": priority,
            "check": check,
            "issue": issue,
            "count": int(count),
            "notes": notes,
        }
    )


def pick_first_existing_column(df, candidates):
    """Return first matching column name from candidates, else None."""
    for col in candidates:
        if col in df.columns:
            return col
    return None


def run_audit():
    data = load_data()
    issuances = data["issuances"].copy()
    cat_allocations = data["cat_allocations"].copy()
    impacts = data["impacts"].copy()
    geo_allocations = data["geo_allocations"].copy()

    findings = []
    detail_outputs = {}

    print("\n--- ARCTAL DATA QUALITY AUDIT START ---")

    # 1) Key integrity checks
    missing_bond_id = {
        "issuances": issuances["bond_id"].isna().sum(),
        "cat_allocations": cat_allocations["bond_id"].isna().sum(),
        "impacts": impacts["bond_id"].isna().sum(),
        "geo_allocations": geo_allocations["bond_id"].isna().sum(),
    }
    add_finding(
        findings,
        "P1",
        "Primary key completeness",
        "Missing bond_id values",
        sum(missing_bond_id.values()),
        f"Breakdown: {missing_bond_id}",
    )

    duplicate_issuance_ids = issuances["bond_id"].duplicated().sum()
    add_finding(
        findings,
        "P1",
        "Primary key uniqueness",
        "Duplicate bond_id in issuances",
        duplicate_issuance_ids,
        "Bond-level table should contain one row per bond_id.",
    )

    issuance_keys = set(issuances["bond_id"].dropna())
    for table_name, df in [("cat_allocations", cat_allocations), ("impacts", impacts), ("geo_allocations", geo_allocations)]:
        child_keys = set(df["bond_id"].dropna())
        orphan_count = len(child_keys - issuance_keys)
        add_finding(
            findings,
            "P1",
            "Referential integrity",
            f"Orphan bond_id in {table_name}",
            orphan_count,
            "Child table should not contain bond_id absent from issuances.",
        )

    # 2) Category allocation reconciliation
    cat_sums = (
        cat_allocations.groupby("bond_id", as_index=False)["post_allocation_USD"]
        .sum()
        .rename(columns={"post_allocation_USD": "category_sum_USD"})
    )
    cat_check = issuances[["bond_id", "issuer_name", "total_USD_allocated"]].merge(
        cat_sums, on="bond_id", how="left"
    )
    cat_check["difference_USD"] = cat_check["total_USD_allocated"] - cat_check["category_sum_USD"]
    cat_mismatches = cat_check[cat_check["difference_USD"].abs() > ROUNDING_TOLERANCE_USD].copy()
    cat_mismatches = cat_mismatches.sort_values("difference_USD", key=lambda s: s.abs(), ascending=False)
    detail_outputs["category_mismatches"] = cat_mismatches

    add_finding(
        findings,
        "P1",
        "Allocation reconciliation",
        "Category allocations do not match issuance total",
        len(cat_mismatches),
        "Sum(cat_allocations.post_allocation_USD) should equal issuances.total_USD_allocated per bond.",
    )

    # 3) Geographic allocation reconciliation
    geo_sums = (
        geo_allocations.groupby("bond_id", as_index=False)["allocation_USD"]
        .sum()
        .rename(columns={"allocation_USD": "geo_sum_USD"})
    )
    geo_check = issuances[["bond_id", "issuer_name", "total_USD_allocated"]].merge(
        geo_sums, on="bond_id", how="left"
    )
    geo_check["difference_USD"] = geo_check["total_USD_allocated"] - geo_check["geo_sum_USD"]
    geo_mismatches = geo_check[geo_check["difference_USD"].abs() > ROUNDING_TOLERANCE_USD].copy()
    geo_mismatches = geo_mismatches.sort_values("difference_USD", key=lambda s: s.abs(), ascending=False)
    detail_outputs["geo_mismatches"] = geo_mismatches

    add_finding(
        findings,
        "P1",
        "Allocation reconciliation",
        "Geographic allocations do not match issuance total",
        len(geo_mismatches),
        "Sum(geo_allocations.allocation_USD) should equal issuances.total_USD_allocated per bond.",
    )

    # 4) Coverage checks for missing child records
    missing_impact = len(issuance_keys - set(impacts["bond_id"].dropna()))
    missing_geo = len(issuance_keys - set(geo_allocations["bond_id"].dropna()))
    add_finding(
        findings,
        "P3",
        "Coverage",
        "Issuance bonds without impact records",
        missing_impact,
        "Could be normal for new bonds, but should be explicitly tracked.",
    )
    add_finding(
        findings,
        "P3",
        "Coverage",
        "Issuance bonds without geographic allocation records",
        missing_geo,
        "Could indicate delayed or incomplete reporting.",
    )

    # 5) Date completeness and chronology (schema tolerant)
    issue_col = pick_first_existing_column(issuances, ["issuance_date", "issue_date", "placement_date"])
    maturity_col = pick_first_existing_column(issuances, ["maturity_date"])
    if issue_col is not None and maturity_col is not None:
        issuances[issue_col] = pd.to_datetime(issuances[issue_col], errors="coerce")
        issuances[maturity_col] = pd.to_datetime(issuances[maturity_col], errors="coerce")
        missing_maturity = issuances[maturity_col].isna().sum()
        bad_chronology = (
            (issuances[maturity_col] < issuances[issue_col])
            & issuances[maturity_col].notna()
            & issuances[issue_col].notna()
        ).sum()
        add_finding(
            findings,
            "P2",
            "Date quality",
            "Missing maturity_date",
            missing_maturity,
            "Maturity dates are required for tenor and duration analysis.",
        )
        add_finding(
            findings,
            "P1",
            "Date quality",
            f"{maturity_col} earlier than {issue_col}",
            bad_chronology,
            "Chronological violation indicates source data error.",
        )
    else:
        add_finding(
            findings,
            "P2",
            "Date quality",
            "Date chronology check skipped",
            0,
            "Required columns not found in issuances table.",
        )

    # 6) FX consistency checks
    issuances["implicit_fx"] = issuances["bond_USD_amount"] / issuances["bond_amount"]
    fx_stats = issuances.groupby("bond_currency")["implicit_fx"].agg(["count", "median", "std"]).reset_index()
    fx_stats = fx_stats.sort_values("std", ascending=False)
    detail_outputs["fx_stats"] = fx_stats
    high_fx_variability = fx_stats[(fx_stats["count"] >= 3) & (fx_stats["std"] > 0.02)]
    add_finding(
        findings,
        "P2",
        "FX sanity",
        "Currencies with high implicit FX variability (std > 0.02, count >= 3)",
        len(high_fx_variability),
        "Potential stale rates, mixed valuation dates, or amount inconsistencies.",
    )

    # 7) Impact consistency checks
    impact_dupes = impacts[impacts.duplicated(subset=["bond_id", "impact_metric"], keep=False)].copy()
    impact_outliers = impacts[
        impacts["impact_per_million_USD"] > impacts["impact_per_million_USD"].quantile(0.95)
    ].copy()
    impact_negative = impacts[
        (impacts["impact_value"] < 0) | (impacts["impact_per_million_USD"] < 0)
    ].copy()
    impact_missing_rate = impacts["impact_per_million_USD"].isna().sum()

    detail_outputs["impact_duplicates"] = impact_dupes
    detail_outputs["impact_outliers_top5pct"] = impact_outliers
    detail_outputs["impact_negative_values"] = impact_negative

    add_finding(
        findings,
        "P2",
        "Impact quality",
        "Duplicate (bond_id, impact_metric) rows",
        len(impact_dupes),
        "May inflate metrics if data is aggregated without de-duplication.",
    )
    add_finding(
        findings,
        "P2",
        "Impact quality",
        "Top 5% impact_per_million_USD outliers",
        len(impact_outliers),
        "Outliers may indicate unit mismatch or denominator issues.",
    )
    add_finding(
        findings,
        "P2",
        "Impact quality",
        "Negative impact values",
        len(impact_negative),
        "Negative values are usually invalid depending on metric definition.",
    )
    add_finding(
        findings,
        "P2",
        "Impact quality",
        "Missing impact_per_million_USD",
        impact_missing_rate,
        "Missing normalized rates reduce comparability across bonds.",
    )

    # Build and export findings
    summary_df = pd.DataFrame(findings)
    priority_order = {"P1": 1, "P2": 2, "P3": 3}
    summary_df["priority_rank"] = summary_df["priority"].map(priority_order)
    summary_df = summary_df.sort_values(["priority_rank", "count"], ascending=[True, False]).drop(
        columns=["priority_rank"]
    )

    summary_df.to_csv("findings_summary.csv", index=False)
    for name, df in detail_outputs.items():
        df.to_csv(f"findings_{name}.csv", index=False)

    # Console output for interview walkthrough
    print("\nTop findings by priority:")
    for _, row in summary_df.iterrows():
        print(f"- [{row['priority']}] {row['issue']}: {row['count']}")

    print("\nExported files:")
    print("- findings_summary.csv")
    for name in detail_outputs:
        print(f"- findings_{name}.csv")

    print("\n--- ARCTAL DATA QUALITY AUDIT END ---\n")


if __name__ == "__main__":
    run_audit()