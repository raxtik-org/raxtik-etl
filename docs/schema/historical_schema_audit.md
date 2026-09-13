# FDA FAERS/AEMS Historical Schema Audit & Evolution Guide (2004 – 2026+)

> **Phase 0 Status**: 🟡 **Documentation Verified — Physical Header Verification Pending**  
> *Documentation verification confirms major milestone boundaries (2004Q1, 2012Q4, 2014Q3, 2026Q1/March 11). Individual column existence below reflects official FDA "Summary of Changes" publications.*

---

## 1. Dual Historical Timelines

### Timeline A: FDA Operational / System Migrations
* **Pre-Sept 10, 2012**: **Legacy AERS** (Adverse Event Reporting System) backend.
* **Sept 10, 2012 – March 10, 2026**: **FAERS** (FDA Adverse Event Reporting System) backend.
* **March 11, 2026 – Present**: **AEMS** (FDA Adverse Event Monitoring System) backend.

### Timeline B: Downloadable Quarterly Extract Schema Signatures (QDE)

```text
┌──────────────────────────┬──────────────────────────┬──────────────────────────┬──────────────────────────┐
│  Signature S1 (AERS)     │  Signature S2 (FAERS-1)  │  Signature S3 (FAERS-2)  │  Signature S4 (AEMS)     │
│  (2004 Q1 – 2012 Q3)     │  (2012 Q4 – 2014 Q2)     │  (2014 Q3 – 2025 Q4)     │  (2026 Q1 – Present)     │
├──────────────────────────┼──────────────────────────┼──────────────────────────┼──────────────────────────┤
│ • Primary Key: ISR       │ • Primary Key: PRIMARYID │ • Added PROD_AI in DRUG  │ • AEMS operational era   │
│ • Case Key: CASE         │ • Case Key: CASEID       │ • Added DRUG_REC_ACT     │ • Extract distributions  │
│ • Follow-up: FOLL_SEQ    │ • Added CASEVERSION      │ • Added AGE_GRP in DEMO  │   continue               │
│ • Sex column: GNDR_COD   │ • Sex column: GNDR_COD   │ • Header changed:        │ • Header signatures      │
│ • PROD_AI: ABSENT        │ • PROD_AI: ABSENT        │   GNDR_COD → SEX         │   verified dynamically   │
│ • Delimiter: $           │ • Delimiter: $           │ • Added AUTH_NUM, LIT_REF│   via resolver           │
└──────────────────────────┴──────────────────────────┴──────────────────────────┴──────────────────────────┘
```

---

## 2. Table-by-Table Verified Historical Analysis

### 📋 Table 1: Demographics (`DEMO`)

| Signature / Era | Columns in Extract File | Verified Mapping & Evolution Semantics |
| :--- | :--- | :--- |
| **Signature S1 (2004Q1–2012Q3)** | `ISR$CASE$I_F_COD$FOLL_SEQ$IMAGE$EVENT_DT$MFR_DT$FDA_DT$MFR_NUM$MFR_SNDR$AGE$AGE_COD$GNDR_COD$E_SUB$WT$WT_COD$REPT_DT$OCCP_COD$DEATH_DT$TO_MFR$CONFID` | • `ISR`: Submission primary key (Category H).<br>• `CASE`: Case identifier.<br>• `FOLL_SEQ`: Contributes to legacy follow-up/version semantics; does not overwrite `fda_case_version`.<br>• `GNDR_COD`: Reported sex code.<br>• `AGE_GRP`: `NOT_PRESENT_IN_SOURCE`.<br>• `2005Q3`: Documented addition point for reporting metadata.<br>• Unmapped fields (`IMAGE`, `CONFID`, `DEATH_DT`, `TO_MFR`) explicitly cataloged in `_schema_registry`. |
| **Signature S2 (2012Q4–2014Q2)** | `PRIMARYID$CASEID$CASEVERSION$I_F_COD$EVENT_DT$MFR_DT$INIT_FDA_DT$FDA_DT$MFR_NUM$MFR_SNDR$AGE$AGE_COD$GNDR_COD$E_SUB$WT$WT_COD$REPT_DT$OCCP_COD$REPT_COD$REL_RPT$FOLL_SEQ` | • `PRIMARYID`, `CASEID`, and `CASEVERSION` introduced.<br>• `INIT_FDA_DT` introduced.<br>• Sex header remains `GNDR_COD` (verified via 2014Q3 change notice).<br>• `AGE_GRP`: `NOT_PRESENT_IN_SOURCE`. |
| **Signature S3 (2014Q3–2025Q4)** | `PRIMARYID$CASEID$CASEVERSION$I_F_COD$EVENT_DT$MFR_DT$INIT_FDA_DT$FDA_DT$MFR_NUM$MFR_SNDR$AGE$AGE_COD$AGE_GRP$SEX$E_SUB$WT$WT_COD$REPT_DT$OCCP_COD$AUTH_NUM$LIT_REF$REPORTER_COUNTRY$OCCR_COUNTRY` | • **2014Q3 Expansion**: Added `AGE_GRP`, `AUTH_NUM`, `LIT_REF`.<br>• **Header change**: `GNDR_COD` modified to `SEX`.<br>• Added `REPORTER_COUNTRY` and `OCCR_COUNTRY`. |
| **Signature S4 (2026Q1+)** | *Subject to physical archive signature check* | • AEMS quarterly extract distributions continue. |

---

### 💊 Table 2: Drug Product Information (`DRUG`)

| Signature / Era | Columns in Extract File | Verified Mapping & Evolution Semantics |
| :--- | :--- | :--- |
| **Signature S1 (2004Q1–2012Q3)** | `ISR$DRUG_SEQ$ROLE_COD$DRUGNAME$VAL_VBM$ROUTE$DOSE_VBM$CUM_DOSE_CHR$CUM_DOSE_UNIT$DECHAL$RECHAL$LOT_NUM$EXP_DT$NDA_NUM` | • `ISR` links to DEMO.<br>• `PROD_AI`: `NOT_PRESENT_IN_SOURCE`.<br>• `DOSE_AMT`, `DOSE_UNIT`, `DOSE_FORM`, `DOSE_FREQ`: `NOT_PRESENT_IN_SOURCE` (dosage text in `DOSE_VBM`). |
| **Signature S2 (2012Q4–2014Q2)** | `PRIMARYID$CASEID$DRUG_SEQ$ROLE_COD$DRUGNAME$VAL_VBM$ROUTE$DOSE_VBM$DOSE_AMT$DOSE_UNIT$DOSE_FORM$DOSE_FREQ$CUM_DOSE_CHR$CUM_DOSE_UNIT$DECHAL$RECHAL$LOT_NUM$EXP_DT$NDA_NUM` | • `PRIMARYID` and `CASEID` link to DEMO.<br>• **Critical Correction**: `PROD_AI` is `NOT_PRESENT_IN_SOURCE` (Introduced later in 2014Q3).<br>• Parsed dose fields verified as `value_origin = FDA_REPORTED`. |
| **Signature S3 (2014Q3–2025Q4)** | `PRIMARYID$CASEID$DRUG_SEQ$ROLE_COD$DRUGNAME$PROD_AI$VAL_VBM$ROUTE$DOSE_VBM$DOSE_AMT$DOSE_UNIT$DOSE_FORM$DOSE_FREQ$CUM_DOSE_CHR$CUM_DOSE_UNIT$DECHAL$RECHAL$LOT_NUM$EXP_DT$NDA_NUM` | • **2014Q3 Expansion**: `PROD_AI` introduced by FDA.<br>• `ROLE_COD` preserves verbatim code. |
| **Signature S4 (2026Q1+)** | *Subject to physical archive signature check* | • AEMS era extracts. |

---

### ⚠️ Table 3: Adverse Reactions (`REAC`)

| Signature / Era | Columns in Extract File | Verified Mapping & Evolution Semantics |
| :--- | :--- | :--- |
| **Signature S1 (2004Q1–2012Q3)** | `ISR$PT` | • `ISR` links to DEMO.<br>• `DRUG_REC_ACT`: `NOT_PRESENT_IN_SOURCE`. |
| **Signature S2 (2012Q4–2014Q2)** | `PRIMARYID$CASEID$PT` | • Added `CASEID`.<br>• `DRUG_REC_ACT`: `NOT_PRESENT_IN_SOURCE`. |
| **Signature S3 (2014Q3–2025Q4)** | `PRIMARYID$CASEID$PT$DRUG_REC_ACT` | • **2014Q3 Expansion**: `DRUG_REC_ACT` introduced. |
| **Signature S4 (2026Q1+)** | *Subject to physical archive signature check* | • AEMS era extracts. |

---

### 🏥 Tables 4–7: Outcomes, Indications, Therapy, and Report Sources

* **`OUTC`**: `ISR$OUTC_COD` (S1) $\rightarrow$ `PRIMARYID$CASEID$OUTC_COD` (S2–S4).
* **`INDI`**: `ISR$DRUG_SEQ$INDI_PT` (S1) $\rightarrow$ `PRIMARYID$CASEID$INDI_DRUG_SEQ$INDI_PT` (S2–S4).
* **`THER`**: `ISR$DRUG_SEQ$START_DT$END_DT$DUR$DUR_COD` (S1) $\rightarrow$ `PRIMARYID$CASEID$DSG_DRUG_SEQ$START_DT$END_DT$DUR$DUR_COD` (S2–S4).
* **`RPSR`**: `ISR$RPSR_COD` (S1) $\rightarrow$ `PRIMARYID$CASEID$RPSR_COD` (S2–S4).

---

## 3. Transformation & Evolution Categories (8-Category Formal System)

* **Category A (Identical)**: Same field name, type, and semantic meaning across eras.
* **Category B (Renamed / Alias)**: Same semantic concept, but FDA renamed column (e.g., `GNDR_COD` $\rightarrow$ `SEX`).
* **Category C (Added Later)**: Field introduced in a documented QDE expansion (e.g., `PROD_AI` in 2014Q3). Mapped as `NOT_PRESENT_IN_SOURCE` for earlier signatures.
* **Category D (Deprecated / Unmapped)**: Field present in early source files but unmapped into canonical entity (e.g., `IMAGE`, `CONFID`). Recorded explicitly in `_schema_registry`.
* **Category E (Code-Set Evolution)**: Field exists across eras, but allowed coded values evolved or were formatted differently.
* **Category F (Semantic Split)**: Field unbundled into granular sub-fields in newer extracts (e.g., `DOSE_VBM` $\rightarrow$ `DOSE_AMT` + `DOSE_UNIT` + `DOSE_FREQ`).
* **Category G (Derived / Standardized)**: Raxtik-derived standard columns (e.g., `standard_age_years`, `canonical_case_version`).
* **Category H (Structural Relationship / Key Semantics Change)**: Identifier or foreign-key relationship shift (e.g. `ISR` $\rightarrow$ `PRIMARYID` + `CASEID` + `CASEVERSION`).
