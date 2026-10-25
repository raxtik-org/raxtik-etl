# raxtik-etl Documentation

**`raxtik-etl`** is a high-performance canonical pharmacovigilance data engine and packaging toolkit powered by DuckDB and Polars.

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
changelog
```

---

## 🌟 Core Features

- **Decoupled Architecture**: Source-agnostic canonical data engine separated from source-specific connectors (`raxtik-source-faers`).
- **Canonical Schemas**: 7 normalized entities (`demo`, `drug`, `reac`, `outc`, `indi`, `ther`, `rpsr`) preserving original verbatim values.
- **Dual Presentation Packaging**: Produces self-describing standalone DuckDB databases and ZSTD-compressed Apache Parquet directories.
- **Deterministic Case Deduplication**: Resolves multi-version follow-up submissions across quarters while retaining raw historical submissions.
- **Zero-Copy Python Client**: Query cases, suspect drugs, and reactions directly as Polars DataFrames using `Dataset`.
- **Hugging Face Hub Streaming**: Zero-auth public downloads of precompiled packages directly to user cache.

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
