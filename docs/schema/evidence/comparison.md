# Phase 0 Empirical Schema Fingerprint Comparison Report

> **Generated at**: 2026-09-13 10:55:37Z

## 1. Verified Release Signatures & Fingerprints

| Release | Signature ID | Release Signature Hash (SHA-256) | Archive Size (MB) | Verified Archive SHA-256 |
| :--- | :--- | :--- | :--- | :--- |
| **2004Q1** | `S1` | `2202d728e518b7a0...` | 7.23 MB | `649ed8ec2b30b5e5...` |
| **2012Q4** | `S2` | `1c04438534eb727e...` | 27.22 MB | `20562c821eebd248...` |
| **2014Q3** | `S3` | `7a3f39867658e5c1...` | 27.92 MB | `8b8b79a7381103f5...` |
| **2024Q1** | `S3` | `7a3f39867658e5c1...` | 64.32 MB | `12a086c473666c2c...` |
| **2026Q1** | `S3` | `7a3f39867658e5c1...` | 61.11 MB | `ed36733361701ed5...` |
| **2026Q2** | `S3` | `7a3f39867658e5c1...` | 60.29 MB | `90213500721ecaf9...` |

---

## 2. Table-by-Table Column Evolution

### 📋 Table: `DEMO`

| # | S1 (2004Q1) | S2 (2012Q4) | S3 (2014Q3) |
| :--- | :--- | :--- | :--- |
| 1 | `ISR` | `primaryid` | `primaryid` |
| 2 | `CASE` | `caseid` | `caseid` |
| 3 | `I_F_COD` | `caseversion` | `caseversion` |
| 4 | `FOLL_SEQ` | `i_f_code` | `i_f_code` |
| 5 | `IMAGE` | `event_dt` | `event_dt` |
| 6 | `EVENT_DT` | `mfr_dt` | `mfr_dt` |
| 7 | `MFR_DT` | `init_fda_dt` | `init_fda_dt` |
| 8 | `FDA_DT` | `fda_dt` | `fda_dt` |
| 9 | `REPT_COD` | `rept_cod` | `rept_cod` |
| 10 | `MFR_NUM` | `mfr_num` | `auth_num` |
| 11 | `MFR_SNDR` | `mfr_sndr` | `mfr_num` |
| 12 | `AGE` | `age` | `mfr_sndr` |
| 13 | `AGE_COD` | `age_cod` | `lit_ref` |
| 14 | `GNDR_COD` | `gndr_cod` | `age` |
| 15 | `E_SUB` | `e_sub` | `age_cod` |
| 16 | `WT` | `wt` | `age_grp` |
| 17 | `WT_COD` | `wt_cod` | `sex` |
| 18 | `REPT_DT` | `rept_dt` | `e_sub` |
| 19 | `OCCP_COD` | `to_mfr` | `wt` |
| 20 | `DEATH_DT` | `occp_cod` | `wt_cod` |
| 21 | `TO_MFR` | `reporter_country` | `rept_dt` |
| 22 | `CONFID` | `occr_country` | `to_mfr` |
| 23 | — | — | `occp_cod` |
| 24 | — | — | `reporter_country` |
| 25 | — | — | `occr_country` |

### 📋 Table: `DRUG`

| # | S1 (2004Q1) | S2 (2012Q4) | S3 (2014Q3) |
| :--- | :--- | :--- | :--- |
| 1 | `ISR` | `primaryid` | `primaryid` |
| 2 | `DRUG_SEQ` | `caseid` | `caseid` |
| 3 | `ROLE_COD` | `drug_seq` | `drug_seq` |
| 4 | `DRUGNAME` | `role_cod` | `role_cod` |
| 5 | `VAL_VBM` | `drugname` | `drugname` |
| 6 | `ROUTE` | `val_vbm` | `prod_ai` |
| 7 | `DOSE_VBM` | `route` | `val_vbm` |
| 8 | `DECHAL` | `dose_vbm` | `route` |
| 9 | `RECHAL` | `cum_dose_chr` | `dose_vbm` |
| 10 | `LOT_NUM` | `cum_dose_unit` | `cum_dose_chr` |
| 11 | `EXP_DT` | `dechal` | `cum_dose_unit` |
| 12 | `NDA_NUM` | `rechal` | `dechal` |
| 13 | — | `lot_nbr` | `rechal` |
| 14 | — | `exp_dt` | `lot_num` |
| 15 | — | `nda_num` | `exp_dt` |
| 16 | — | `dose_amt` | `nda_num` |
| 17 | — | `dose_unit` | `dose_amt` |
| 18 | — | `dose_form` | `dose_unit` |
| 19 | — | `dose_freq` | `dose_form` |
| 20 | — | — | `dose_freq` |

### 📋 Table: `REAC`

| # | S1 (2004Q1) | S2 (2012Q4) | S3 (2014Q3) |
| :--- | :--- | :--- | :--- |
| 1 | `ISR` | `primaryid` | `primaryid` |
| 2 | `PT` | `caseid` | `caseid` |
| 3 | — | `pt` | `pt` |
| 4 | — | — | `drug_rec_act` |

### 📋 Table: `OUTC`

| # | S1 (2004Q1) | S2 (2012Q4) | S3 (2014Q3) |
| :--- | :--- | :--- | :--- |
| 1 | `ISR` | `primaryid` | `primaryid` |
| 2 | `OUTC_COD` | `caseid` | `caseid` |
| 3 | — | `outc_code` | `outc_cod` |

### 📋 Table: `RPSR`

| # | S1 (2004Q1) | S2 (2012Q4) | S3 (2014Q3) |
| :--- | :--- | :--- | :--- |
| 1 | `ISR` | `primaryid` | `primaryid` |
| 2 | `RPSR_COD` | `caseid` | `caseid` |
| 3 | — | `rpsr_cod` | `rpsr_cod` |

### 📋 Table: `THER`

| # | S1 (2004Q1) | S2 (2012Q4) | S3 (2014Q3) |
| :--- | :--- | :--- | :--- |
| 1 | `ISR` | `primaryid` | `primaryid` |
| 2 | `DRUG_SEQ` | `caseid` | `caseid` |
| 3 | `START_DT` | `dsg_drug_seq` | `dsg_drug_seq` |
| 4 | `END_DT` | `start_dt` | `start_dt` |
| 5 | `DUR` | `end_dt` | `end_dt` |
| 6 | `DUR_COD` | `dur` | `dur` |
| 7 | — | `dur_cod` | `dur_cod` |

### 📋 Table: `INDI`

| # | S1 (2004Q1) | S2 (2012Q4) | S3 (2014Q3) |
| :--- | :--- | :--- | :--- |
| 1 | `ISR` | `primaryid` | `primaryid` |
| 2 | `DRUG_SEQ` | `caseid` | `caseid` |
| 3 | `INDI_PT` | `indi_drug_seq` | `indi_drug_seq` |
| 4 | — | `indi_pt` | `indi_pt` |

