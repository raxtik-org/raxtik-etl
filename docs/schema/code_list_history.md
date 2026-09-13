# FAERS/AEMS Coded Values & Code-List History Reference

> **Status**: 🟡 **Phase 0 Substantially Complete — Evidence Lock Pending**  
> *Note*: Code lists documented below reflect FDA CDER / ICH guidelines. The platform preserves the raw reported code and attaches the applicable canonical label based on verified schema signatures.

---

## 1. Drug Role Codes (`ROLE_COD` / `role_code`)

| Reported Code | Canonical Label | Definition / Clinical Meaning |
| :--- | :--- | :--- |
| `PS` | `Primary Suspect` | The primary suspect drug identified by reporter as causing adverse event |
| `SS` | `Secondary Suspect` | Secondary suspect drug also suspected of contributing |
| `C` | `Concomitant` | Concomitant drug taken concurrently by patient |
| `I` | `Interacting` | Drug suspected of causing a drug-drug interaction |

*Legacy Note: In early AERS data (pre-2012), numerical codes were occasionally observed in raw submissions: `1`=PS, `2`=SS, `3`=C, `4`=I. The source adapter preserves the raw reported code and resolves the canonical code/label.*

---

## 2. Patient Outcome / Seriousness Codes (`OUTC_COD` / `outcome_code`)

| Reported Code | Canonical Label | ICH E2B Seriousness Category |
| :--- | :--- | :--- |
| `DE` | `Death` | Results in death |
| `LT` | `Life-Threatening` | Life-threatening adverse event |
| `HO` | `Hospitalization` | Initial or prolonged inpatient hospitalization |
| `DS` | `Disability` | Disability or significant/permanent incapacity |
| `CA` | `Congenital Anomaly` | Congenital anomaly or birth defect |
| `RI` | `Required Intervention` | Required intervention to prevent permanent harm |
| `OT` | `Other Serious` | Other medically important serious condition |

---

## 3. Patient Sex (`SEX` / `GNDR_COD` / `reported_sex_code`)

| Reported Code | Canonical Label | Notes |
| :--- | :--- | :--- |
| `M` | `Male` | |
| `F` | `Female` | |
| `UNK` | `Unknown` | Gender not specified or unknown |
| `NS` | `Not Specified` | Observed in certain legacy records |

---

## 4. Age Units (`AGE_COD` / `reported_age_code`) & Normalization Multipliers

| Reported Code | Unit | Conversion to `standard_age_years` |
| :--- | :--- | :--- |
| `YR` | Years | $\text{age} \times 1.0$ |
| `DEC`| Decades | $\text{age} \times 10.0$ |
| `MON`| Months | $\text{age} / 12.0$ |
| `WK` | Weeks | $\text{age} / 52.1429$ |
| `DY` | Days | $\text{age} / 365.25$ |
| `HR` | Hours | $\text{age} / 8766.0$ |

---

## 5. Weight Units (`WT_COD` / `reported_weight_code`) & Normalization Multipliers

| Reported Code | Unit | Conversion to `standard_weight_kg` |
| :--- | :--- | :--- |
| `KG` | Kilograms | $\text{wt} \times 1.0$ |
| `LBS`| Pounds | $\text{wt} \times 0.45359237$ |
| `GMS`| Grams | $\text{wt} / 1000.0$ |

---

## 6. Reporter Occupation (`OCCP_COD` / `reporter_occupation_code`)

| Reported Code | Canonical Label | Category |
| :--- | :--- | :--- |
| `MD` | `Physician` | Healthcare Professional |
| `PH` | `Pharmacist` | Healthcare Professional |
| `OT` | `Other Health Professional` | Healthcare Professional (Nurse, Dentist, etc.) |
| `LW` | `Lawyer` | Legal Representative |
| `CN` | `Consumer` | Patient, Family Member, or Consumer |

---

## 7. Report Sources (`RPSR_COD` / `report_source_code`)

| Reported Code | Canonical Label | Description |
| :--- | :--- | :--- |
| `FGN` | `Foreign` | Foreign regulatory agency / international report |
| `SDY` | `Study` | Clinical trial or post-marketing surveillance study |
| `LIT` | `Literature` | Published scientific journal or literature |
| `HP` | `Health Professional` | Voluntary report from physician or pharmacist |
| `CSM` | `Consumer` | Voluntary report from consumer or patient |
| `CR` | `Company Representative` | Report submitted via company field rep |
| `UF` | `User Facility` | User facility (hospital, clinic, nursing home) |

---

## 8. Dechallenge / Rechallenge Codes (`DECHAL` / `RECHAL`)

| Reported Code | Canonical Label | Description |
| :--- | :--- | :--- |
| `Y` | `Positive` | Event abated when drug discontinued (or recurred on rechallenge) |
| `N` | `Negative` | Event did not abate when drug discontinued (or did not recur) |
| `U` | `Unknown` | Unknown / Unreported |
| `D` | `Does Not Apply` | Dose was not changed or drug was continued |
