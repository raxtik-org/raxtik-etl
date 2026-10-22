# raxtik-etl Documentation

**`raxtik-etl`** is an enterprise-grade pharmacovigilance data engine, canonical schema platform, and reproducible pipeline for FDA FAERS and AEMS adverse event safety databases.

---

```{toctree}
:maxdepth: 2
:caption: Getting Started

quickstart
cli_reference
```

```{toctree}
:maxdepth: 2
:caption: Architecture & Design

architecture
deduplication
```

```{toctree}
:maxdepth: 2
:caption: Guides & Schema Specifications

guides/2004q1_usage_guide
fda_faers_official_data_dictionary
schema/historical_schema_audit
schema/code_list_history
schema/evidence/comparison
```

```{toctree}
:maxdepth: 2
:caption: API Reference

api
```

```{toctree}
:maxdepth: 2
:caption: Community & Contributing

contributing
contributors
```

---

## 🌟 Core Features

- **Decoupled Architecture**: Source-agnostic canonical data engine separated from source-specific connectors (`raxtik-source-faers`).
- **Signature Detection (S1 → S2 → S3)**: Fail-closed schema evolution tracking legacy ASCII (2004–2012), migration era (2012–2014), and modern FAERS/AEMS (2014–present).
- **Dual Presentation Packaging**: Produces self-describing standalone SQLite, DuckDB, and zero-copy Apache Parquet formats.
- **Cross-Quarter Case Deduplication Engine**: Deterministic longitudinal case resolution resolving follow-up submissions across quarters and years while preserving raw physical provenance.
- **Zero-Copy Python SDK**: Query canonical cases, suspect drugs, reactions, and outcomes directly as Polars DataFrames.
- **Hugging Face Hub Remote Distribution**: Instant public streaming download of precompiled packages without requiring local compilation or API tokens.

---

## 🚀 Quick Installation

Requires Python >= 3.11.

```bash
# Core package
pip install raxtik-etl

# With developer & Hugging Face upload tooling
pip install "raxtik-etl[dev]"

# With documentation tooling
pip install "raxtik-etl[docs]"
```

---

## 📄 License

- **Source Code**: GNU Affero General Public License v3 or later ([AGPL-3.0-or-later](https://www.gnu.org/licenses/agpl-3.0.html)).
- **Raw FDA Data**: United States Federal Government Work / Public Domain ([17 U.S.C. § 105](https://www.law.cornell.edu/uscode/text/17/105)).
- **Derived Safety Packages**: Open Data Commons Attribution License ([ODC-By 1.0](https://opendatacommons.org/licenses/by/1-0/)).
