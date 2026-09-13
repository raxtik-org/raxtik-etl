# Official FDA FAERS Data Structure & Technical Reference Guide

This document contains the official data dictionary, entity relationships, allowed coded values, and technical specifications for the **FDA Adverse Event Reporting System (FAERS)** datasets based on FDA CDER guidelines and ICH E2B(R2/R3) standards.

---

## 1. Overview of the 7 Core FAERS Tables

| Table | File Name Format | Description | Primary Key / Composite Key | Foreign Key (Join to DEMO) |
| :--- | :--- | :--- | :--- | :--- |
| **DEMO** | `DEMO<YY>Q<Q>.txt` | Patient demographics, administrative data, case versioning, and reporting source | `PRIMARYID` | *(Root Table)* |
| **DRUG** | `DRUG<YY>Q<Q>.txt` | Reported drug information (brand name, active ingredient, route, dosage, suspect role) | `PRIMARYID`, `DRUG_SEQ` | `PRIMARYID`, `CASEID` |
| **REAC** | `REAC<YY>Q<Q>.txt` | Adverse events / reactions coded in MedDRA Preferred Terms (`PT`) | `PRIMARYID`, `PT` | `PRIMARYID`, `CASEID` |
| **OUTC** | `OUTC<YY>Q<Q>.txt` | Patient outcomes / Seriousness criteria (Death, Hospitalization, etc.) | `PRIMARYID`, `OUTC_COD` | `PRIMARYID`, `CASEID` |
| **INDI** | `INDI<YY>Q<Q>.txt` | Medical indications for use of the drugs | `PRIMARYID`, `INDI_DRUG_SEQ`, `INDI_PT` | `PRIMARYID` (Links to `DRUG.DRUG_SEQ`) |
| **THER** | `THER<YY>Q<Q>.txt` | Drug therapy start/end dates and durations | `PRIMARYID`, `DSG_DRUG_SEQ` | `PRIMARYID` (Links to `DRUG.DRUG_SEQ`) |
| **RPSR** | `RPSR<YY>Q<Q>.txt` | Report sources (Consumer, Health Professional, Foreign, Literature, Study) | `PRIMARYID`, `RPSR_COD` | `PRIMARYID`, `CASEID` |

---

## 2. Exhaustive Data Dictionaries by Table

### 📋 Table 1: `DEMO` (Demographics & Administrative)

| Field Name | Type | Description | Allowed Values / Code Reference |
| :--- | :--- | :--- | :--- |
| `PRIMARYID` | String | Unique number assigned by FDA to identify a single FAERS report submission. | Numerical string (e.g. `100049281`) |
| `CASEID` | String | Unique number identifying the case across multiple revisions/follow-ups. | Constant across follow-ups of same incident |
| `CASEVERSION` | Integer | Version number of the case (starts at 1; 2+ indicates follow-up). | `1`, `2`, `3`, ... |
| `I_F_COD` | String | Initial report or Follow-up report flag. | `I` = Initial, `F` = Follow-up |
| `EVENT_DT` | String | Date adverse event occurred. | `YYYYMMDD` (may have partial dates e.g. `20240100` or `20240000`) |
| `MFR_DT` | String | Date manufacturer received notification of event. | `YYYYMMDD` |
| `INIT_FDA_DT`| String | Date initial case was received by FDA. | `YYYYMMDD` |
| `FDA_DT` | String | Date this specific report version was received by FDA. | `YYYYMMDD` |
| `MFR_NUM` | String | Manufacturer's proprietary report identifier. | Text (e.g. `US-PFIZER-2024-001`) |
| `MFR_SNDR` | String | Coded name of manufacturer sending report. | Text |
| `AGE` | Double | Numerical age of patient. | Number (e.g. `45`, `6.5`) |
| `AGE_COD` | String | Unit of measurement for `AGE`. | `YR` = Years, `MON` = Months, `WK` = Weeks, `DY` = Days, `HR` = Hours, `DEC` = Decades |
| `AGE_GRP` | String | Patient age group category (Legacy). | `N` = Neonate, `I` = Infant, `C` = Child, `T` = Adolescent, `A` = Adult, `E` = Elderly |
| `SEX` | String | Patient biological sex. | `M` = Male, `F` = Female, `UNK` = Unknown |
| `E_SUB` | String | Electronic submission flag. | `Y` = Yes (E2B electronic format), `N` = No (Paper MedWatch 3500) |
| `WT` | Double | Numerical weight of patient. | Number (e.g. `70.5`) |
| `WT_COD` | String | Unit of measurement for `WT`. | `KG` = Kilograms, `LBS` = Pounds, `GMS` = Grams |
| `REPT_DT` | String | Date report was sent. | `YYYYMMDD` |
| `OCCP_COD` | String | Occupation of initial reporter. | `MD` = Physician, `PH` = Pharmacist, `OT` = Other Health Professional, `LW` = Lawyer, `CN` = Consumer |
| `REPORTER_COUNTRY` | String | Country of origin of the reporter. | ISO Country Code (e.g. `US`, `GB`, `FR`, `DE`) |
| `OCCR_COUNTRY` | String | Country where adverse event occurred. | ISO Country Code |

---

### 💊 Table 2: `DRUG` (Drug & Product Information)

| Field Name | Type | Description | Allowed Values / Code Reference |
| :--- | :--- | :--- | :--- |
| `PRIMARYID` | String | Links to `DEMO.PRIMARYID`. | Foreign Key |
| `CASEID` | String | Links to `DEMO.CASEID`. | Foreign Key |
| `DRUG_SEQ` | Integer | Sequence number identifying drug position in report. | `1`, `2`, `3`, ... |
| `ROLE_COD` | String | Suspect role of drug in causing adverse event. | `PS` = Primary Suspect, `SS` = Secondary Suspect, `C` = Concomitant, `I` = Interacting |
| `DRUGNAME` | String | Reported verbatim medicinal product or brand name. | Free text (e.g. `TYLENOL EXTRA STRENGTH`) |
| `PROD_AI` | String | Standardized Active Ingredient name. | Text (e.g. `ACETAMINOPHEN`) |
| `VAL_VBM` | String | Validation status of verbatim drug name against dictionary. | `1` = Validated, `2` = Non-validated |
| `ROUTE` | String | Route of drug administration. | `Oral`, `Intravenous`, `Subcutaneous`, `Topical`, `Intramuscular`, `Infiltration`, `Ophthalmic`, etc. |
| `DOSE_VBM` | String | Verbatim text describing prescribed dose regimen. | Free text (e.g. `500 MG ONCE DAILY AS NEEDED`) |
| `DOSE_AMT` | Double | Numerical dose amount. | Number (e.g. `500`, `10`) |
| `DOSE_UNIT` | String | Measurement unit of dose. | `MG`, `G`, `MCG`, `ML`, `TABLET`, `CAPSULE`, `IU`, etc. |
| `DOSE_FORM` | String | Physical form of drug product. | `TABLET`, `CAPSULE`, `SOLUTION`, `INJECTION`, `CREAM`, `PATCH` |
| `DOSE_FREQ` | String | Frequency of administration. | `QD` = Once daily, `BID` = Twice daily, `TID` = Three times daily, `QID` = 4x daily, `PRN` = As needed, `Q4H` = Every 4 hrs |
| `CUM_DOSE_CHR` | Double | Cumulative dose quantity before reaction. | Number |
| `CUM_DOSE_UNIT`| String | Cumulative dose unit. | `MG`, `G`, etc. |
| `DECHAL` | String | Dechallenge outcome (Did event stop when drug stopped?). | `Y` = Positive Dechallenge, `N` = Negative, `U` = Unknown, `D` = Does not apply |
| `RECHAL` | String | Rechallenge outcome (Did event re-occur when drug restarted?). | `Y` = Positive Rechallenge, `N` = Negative, `U` = Unknown, `D` = Does not apply |
| `LOT_NUM` | String | Manufacturer batch / lot number. | Free text |
| `EXP_DT` | String | Drug product expiration date. | `YYYYMMDD` |
| `NDA_NUM` | String | FDA New Drug Application / BLA / ANDA Number. | Number (e.g. `020489`, `125166`) |

---

### ⚠️ Table 3: `REAC` (Adverse Reactions & MedDRA PTs)

| Field Name | Type | Description | Allowed Values / Code Reference |
| :--- | :--- | :--- | :--- |
| `PRIMARYID` | String | Links to `DEMO.PRIMARYID`. | Foreign Key |
| `CASEID` | String | Links to `DEMO.CASEID`. | Foreign Key |
| `PT` | String | Adverse event term coded in MedDRA Preferred Term (`PT`). | MedDRA PT string (e.g. `Myocardial infarction`, `Nausea`, `Acute kidney injury`) |
| `DRUG_REC_ACT` | String | Action taken with drug as a result of adverse event. | `Drug withdrawn`, `Dose reduced`, `Dose increased`, `Dose not changed`, `Unknown`, `Not applicable` |

---

### 🏥 Table 4: `OUTC` (Patient Outcomes & Seriousness)

| Field Name | Type | Description | Allowed Values / Code Reference |
| :--- | :--- | :--- | :--- |
| `PRIMARYID` | String | Links to `DEMO.PRIMARYID`. | Foreign Key |
| `CASEID` | String | Links to `DEMO.CASEID`. | Foreign Key |
| `OUTC_COD` | String | Coded patient outcome / FDA seriousness criteria. | **`DE`** = Death<br>**`LT`** = Life-Threatening<br>**`HO`** = Hospitalization (Initial or Prolonged)<br>**`DS`** = Disability or Permanent Impairment<br>**`CA`** = Congenital Anomaly / Birth Defect<br>**`RI`** = Required Intervention to Prevent Permanent Harm<br>**`OT`** = Other Serious (Important Medical Event) |

---

### 🎯 Table 5: `INDI` (Indications for Use)

| Field Name | Type | Description | Allowed Values / Code Reference |
| :--- | :--- | :--- | :--- |
| `PRIMARYID` | String | Links to `DEMO.PRIMARYID`. | Foreign Key |
| `CASEID` | String | Links to `DEMO.CASEID`. | Foreign Key |
| `INDI_DRUG_SEQ`| Integer | Sequence number linking to `DRUG.DRUG_SEQ`. | `1`, `2`, `3`, ... |
| `INDI_PT` | String | Disease condition / indication for which drug was prescribed (MedDRA PT). | MedDRA PT (e.g. `Type 2 diabetes mellitus`, `Hypertension`, `Rheumatoid arthritis`) |

---

### ⏱️ Table 6: `THER` (Therapy Dates & Durations)

| Field Name | Type | Description | Allowed Values / Code Reference |
| :--- | :--- | :--- | :--- |
| `PRIMARYID` | String | Links to `DEMO.PRIMARYID`. | Foreign Key |
| `CASEID` | String | Links to `DEMO.CASEID`. | Foreign Key |
| `DSG_DRUG_SEQ` | Integer | Sequence number linking to `DRUG.DRUG_SEQ`. | `1`, `2`, `3`, ... |
| `START_DT` | String | Date drug therapy was initiated. | `YYYYMMDD` |
| `END_DT` | String | Date drug therapy was discontinued. | `YYYYMMDD` |
| `DUR` | Double | Duration of treatment. | Number (e.g. `14`, `3`) |
| `DUR_COD` | String | Duration unit. | `YR` = Years, `MON` = Months, `WK` = Weeks, `DY` = Days, `HR` = Hours |

---

### 📰 Table 7: `RPSR` (Report Sources)

| Field Name | Type | Description | Allowed Values / Code Reference |
| :--- | :--- | :--- | :--- |
| `PRIMARYID` | String | Links to `DEMO.PRIMARYID`. | Foreign Key |
| `CASEID` | String | Links to `DEMO.CASEID`. | Foreign Key |
| `RPSR_COD` | String | Source category of the adverse event report. | `FGN` = Foreign report<br>`SDY` = Clinical Study<br>`LIT` = Literature Publication<br>`HP` = Health Professional<br>`CSM` = Consumer / Patient<br>`CR` = Company Representative<br>`UF` = User Facility (Hospital/Clinic) |

---

## 3. Historical Schema Evolutions & Gotchas

1. **Pre-2012 Q4 (Legacy AERS)**:
   - Primary key was `ISR` (Individual Safety Report Number) instead of `PRIMARYID`.
   - `CASE` number was used instead of `CASEID`.
   - `CASEVERSION` was not tracked explicitly (each follow-up had a new `ISR`).
2. **2012 Q4 – 2014 Q3 (Transition Era)**:
   - Modern column names introduced (`PRIMARYID`, `CASEID`, `CASEVERSION`), but date formatting and ASCII encodings had frequent corruption issues.
3. **2014 Q4 – Present (Modern Standardized FAERS)**:
   - Fully standardized 7-table ASCII format delimited by `$`.
