"""Comprehensive Exploratory Data Analysis (EDA) on real FDA FAERS data."""

from pathlib import Path

import duckdb
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()
EDA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "eda_sample"


def run_eda():
    json_files = list(EDA_DIR.glob("*.json"))
    if not json_files:
        console.print(
            "[red]No JSON sample files found in data/raw/eda_sample/. Run fetch_eda_sample.py first.[/red]"
        )
        return

    sample_path = json_files[0]
    console.print(
        Panel(
            f"[bold cyan]FAERS Real Dataset EDA: {sample_path.name}[/bold cyan]\nFile Size: {sample_path.stat().st_size / (1024 * 1024):.2f} MB",
            style="blue",
        )
    )

    con = duckdb.connect()

    # Query nested JSON directly with DuckDB with increased maximum_object_size
    con.execute(f"""
        CREATE OR REPLACE TABLE raw_events AS
        SELECT unnest(results) AS event
        FROM read_json_auto('{sample_path.as_posix()}', maximum_object_size=500000000);
    """)

    total_reports = con.execute("SELECT COUNT(*) FROM raw_events").fetchone()[0]
    console.print(
        f"[bold green]✓ Total Patient Safety Reports in partition:[/bold green] {total_reports:,}"
    )

    # 1. Demographics Profiling
    stats = con.execute("""
        SELECT
            COUNT(*) AS total_cases,
            COUNT(CASE WHEN event.patient.patientonsetage IS NULL THEN 1 END) AS missing_age,
            COUNT(CASE WHEN event.patient.patientsex IS NULL THEN 1 END) AS missing_sex,
            COUNT(CASE WHEN event.seriousnessdeath = '1' THEN 1 END) AS deaths,
            COUNT(CASE WHEN event.seriousnesshospitalization = '1' THEN 1 END) AS hospitalizations,
            COUNT(CASE WHEN event.seriousnesslifethreatening = '1' THEN 1 END) AS life_threat
        FROM raw_events
    """).fetchone()

    total_cases, missing_age, missing_sex, deaths, hospitalizations, life_threat = stats

    console.print("\n[bold yellow]1. Demographics & Seriousness Breakdown[/bold yellow]")
    demo_table = Table(title="Demographics Summary", style="cyan")
    demo_table.add_column("Metric", style="bold white")
    demo_table.add_column("Value", style="green")

    demo_table.add_row("Total Reports in Partition", f"{total_cases:,}")
    demo_table.add_row(
        "Missing Age Rate", f"{missing_age / total_cases * 100:.1f}% ({missing_age:,})"
    )
    demo_table.add_row(
        "Missing Sex Rate", f"{missing_sex / total_cases * 100:.1f}% ({missing_sex:,})"
    )
    demo_table.add_row("Death Outcome Cases", f"{deaths / total_cases * 100:.1f}% ({deaths:,})")
    demo_table.add_row(
        "Hospitalization Cases",
        f"{hospitalizations / total_cases * 100:.1f}% ({hospitalizations:,})",
    )
    demo_table.add_row(
        "Life-Threatening Cases", f"{life_threat / total_cases * 100:.1f}% ({life_threat:,})"
    )
    console.print(demo_table)

    # 2. Top 15 Most Frequently Reported Drugs
    console.print("\n[bold yellow]2. Top 15 Reported Drugs[/bold yellow]")
    top_drugs = con.execute("""
        SELECT
            UPPER(TRIM(drug.medicinalproduct)) AS drug_name,
            COUNT(*) AS report_count,
            COUNT(DISTINCT event.safetyreportid) AS unique_cases
        FROM raw_events,
        LATERAL (SELECT unnest(event.patient.drug) AS drug)
        WHERE drug.medicinalproduct IS NOT NULL
        GROUP BY drug_name
        ORDER BY report_count DESC
        LIMIT 15;
    """).fetchall()

    drug_table = Table(title="Top 15 Reported Drugs", style="magenta")
    drug_table.add_column("Drug Product Name", style="bold white")
    drug_table.add_column("Total Drug Entries", justify="right", style="green")
    drug_table.add_column("Unique Patient Cases", justify="right", style="cyan")
    for r in top_drugs:
        drug_table.add_row(str(r[0]), f"{r[1]:,}", f"{r[2]:,}")
    console.print(drug_table)

    # 3. Top 15 Adverse Reactions (MedDRA Preferred Terms)
    console.print("\n[bold yellow]3. Top 15 Adverse Reactions (MedDRA PTs)[/bold yellow]")
    top_reactions = con.execute("""
        SELECT
            UPPER(TRIM(reac.reactionmeddrapt)) AS reaction_pt,
            COUNT(*) AS frequency,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM raw_events), 2) AS pct_of_all_reports
        FROM raw_events,
        LATERAL (SELECT unnest(event.patient.reaction) AS reac)
        WHERE reac.reactionmeddrapt IS NOT NULL
        GROUP BY reaction_pt
        ORDER BY frequency DESC
        LIMIT 15;
    """).fetchall()

    reac_table = Table(title="Top 15 Adverse Reactions (MedDRA PTs)", style="red")
    reac_table.add_column("MedDRA Preferred Term (PT)", style="bold white")
    reac_table.add_column("Occurrence Count", justify="right", style="green")
    reac_table.add_column("% of Total Cases", justify="right", style="yellow")
    for r in top_reactions:
        reac_table.add_row(str(r[0]), f"{r[1]:,}", f"{r[2]}%")
    console.print(reac_table)

    # 4. Top Indications
    console.print("\n[bold yellow]4. Top 10 Reported Indications / Diagnoses[/bold yellow]")
    top_indications = con.execute("""
        SELECT
            UPPER(TRIM(drug.drugindication)) AS indication_pt,
            COUNT(*) AS count
        FROM raw_events,
        LATERAL (SELECT unnest(event.patient.drug) AS drug)
        WHERE drug.drugindication IS NOT NULL AND TRIM(drug.drugindication) != ''
        GROUP BY indication_pt
        ORDER BY count DESC
        LIMIT 10;
    """).fetchall()

    indi_table = Table(title="Top 10 Reported Indications", style="green")
    indi_table.add_column("Indication (Diagnosis)", style="bold white")
    indi_table.add_column("Reported Cases", justify="right", style="green")
    for r in top_indications:
        indi_table.add_row(str(r[0]), f"{r[1]:,}")
    console.print(indi_table)

    con.close()
    console.print("\n[bold green]🎉 EDA Completed Successfully![/bold green]")


if __name__ == "__main__":
    run_eda()
