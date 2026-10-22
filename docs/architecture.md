# System Architecture

`raxtik-etl` provides a decoupled, reproducible architecture separating canonical schemas and case resolution from source-specific extraction.

---

## 1. Decoupled Pipeline Design

```text
Physical FDA Archives (ASCII / XML / JSON)
                   │
                   ▼
       [raxtik-source-faers]
   Source Adapter & Signature Detection
         (S1 / S2 / S3 Eras)
                   │
                   ▼
            [raxtik-etl]
     Canonical Schema Normalization
  (demo, drug, reac, outc, indi, ther, rpsr)
                   │
                   ├─────────────────────────────┐
                   ▼                             ▼
       [Single-Quarter Packages]       [Longitudinal Merger]
        (faers_YYYYQX.duckdb)         (faers_YYYY_YYYY_merged)
```

---

## 2. The 7 Canonical Entities

The canonical layer establishes a frozen contract across FDA format changes:

1. **`demo`**: Primary adverse event submission report. Stores age, sex, dates, reporter country, and provenance.
2. **`drug`**: Medicinal products reported for the event. Contains verbatim reported name, structural clean name, role (`PS`, `SS`, `C`, `I`), and dosage.
3. **`reac`**: Adverse reactions mapped to MedDRA Preferred Terms (PT).
4. **`outc`**: Patient clinical outcomes (`DE` death, `HO` hospitalization, `LT` life-threatening, `DS` disability, `CA` congenital anomaly, `RI` intervention required, `OT` other).
5. **`indi`**: Reported indications for drug therapy.
6. **`ther`**: Therapy duration, start date, and end date.
7. **`rpsr`**: Report sources (physician, pharmacist, consumer, distributor).

---

## 3. Schema Evolution Signatures

| Signature | File Era | Date Range | Primary ID | Case ID | Version Source |
|---|---|---|---|---|---|
| **`S1`** | Legacy AERS ASCII | 2004Q1 – 2012Q3 | `ISR` | `CASE` | Derived (`FOLL_SEQ`) |
| **`S2`** | Migration FAERS | 2012Q4 – 2014Q2 | `PRIMARYID` | `CASEID` | Reported (`CASEVERSION`) |
| **`S3`** | Modern FAERS/AEMS | 2014Q3 – Present | `PRIMARYID` | `CASEID` | Reported (`CASEVERSION`) |

All three signatures are normalized into the exact same canonical database schema, enabling uniform longitudinal analysis across decades.
