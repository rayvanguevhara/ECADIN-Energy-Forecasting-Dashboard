# Ringkasan Final Perbaikan Batch 1 & Rujukan Angka Laporan KP (Tahap 1–4)

- **Proyek**: `ECADIN_Project_Clean` (`ecadin_production_forecasting_v1`, `configs/forecasting/production.json` `schema_version = "1.0"`)
- **Cakupan Data**: Historis `2011–2024` (14 tahun × 34 provinsi harmonisasi = `476` baris/panel) • Proyeksi Produksi `2025–2030` (`204` baris/domain) • Panel Gabungan (`680` baris)
- **Dokumen Sumber Audit**: [`audit_forecasting_pipeline.md`](audit_forecasting_pipeline.md) • [`audit_forecasting_pipeline.pdf`](../outputs/reports/audit_forecasting_pipeline.pdf)

---

## 1. Status Verifikasi Akhir End-to-End

| Pemeriksaan | Hasil Terakhir | Rincian Utama |
| :--- | :--- | :--- |
| `python scripts\ecadin.py forecast validate` | **PASSED (`8/8`)** | `6/6` kontrak frame + `input_hashes_sha256` (`3/3`) + `output_hashes_sha256` (`28/28`, path relatif POSIX) |
| `python scripts\generate_evaluation_diagnostics.py` | **GENERATED (`3` CSV)** | `supply_regime_stratification.csv` (`40` baris), `demand_sensitivity_kr2020.csv` (`32` baris), `data_quality_flag_impact_summary.csv` (`24` baris) di `outputs/reports/analysis/` |
| `python -m pytest tests/unit tests/contracts tests/integration -v` | **69 passed (51.31s)** | Seluruh unit test, kontrak output/dashboard/fixture portabel, & integrasi pipeline produksi/dashboard/full lulus |
| Integritas Input Kanonis & Fixture | **UTUH (0 perubahan)** | `data/processed/master/`, `data/processed/modeling/*`, dan `tests/fixtures/` (`test_portable_fixture_contract.py`) tidak dimodifikasi; `28/28` hash SHA-256 produksi pasca-Tahap 3 tidak tersentuh oleh Tahap 4 |
| Kompatibilitas Dashboard | **AMAN (100%)** | `production_model_id` tetap `demand_production_drift` & `supply_production_drift_v1`; kolom nilai tetap `forecast_gwh`; `test_dashboard_pipeline.py` & `test_dashboard_output_contract.py` lulus |

---

## 2. Rekap Perbaikan Batch 1 (`K-1` s.d. `K-4`, `D-1`, `D-4`, `D-6`, `D-2`)

| Kode | Prioritas | File Terkait | Masalah Awal | Perbaikan yang Diterapkan |
| :---: | :---: | :--- | :--- | :--- |
| **`K-1`** | `[Kritis]` | `src/ecadin_energy/forecasting/strategies/recursive.py` | `run_recursive_for_model()` melompati `predict_next()` & *append* ke `recursive_history` ketika target masa depan tidak valid (`YO` supply 2020). | `model.predict_next()` → `clip_nonnegative()` → *append* ke `recursive_history` selalu dijalankan pada `horizon = 1..max_horizon`; kelayakan target hanya menyaring pencatatan baris evaluasi (`2.448` demand / `2.436` supply tetap utuh). |
| **`K-2`** | `[Kritis]` | `src/ecadin_energy/forecasting/evaluation/metrics.py`, `evaluation/aggregation.py`, `tests/unit/test_metrics.py` | `mase_scale()` menghitung `abs(diff(values))` tanpa mengecek `diff(year) == 1` (gap `2019→2021` pada `YO` supply dianggap 1 tahun), serta jumlah kasus MASE valid belum dilaporkan. | `mase_scale()` memfilter pasangan tahun konsekutif (`np.diff(years) == 1`), mengembalikan `NaN` eksplisit untuk seri konstan/nol (`scale <= 0`), dan menambahkan `mase_valid_prediction_count` & `mase_valid_region_count` pada agregasi metrik. |
| **`K-3`** | `[Kritis]` | `src/ecadin_energy/forecasting/production/supply.py`, `tests/unit/test_supply_calibration.py` | Bucket `small` tercemar *structural break* 2021 & *bucket migration* (`q95(h=6)=61.01x`, `YO` 2030 = `1.007x`), `national/all` merilis `q95` dari `n=4`, serta interval simetris dengan faktor $\sqrt{h/3}$. | Seleksi residual konsisten rezim & bucket (`~crosses_structural_break & origin_size_bucket == target_size_bucket`), kuantil log-error asimetris ($\log((y+10)/(\hat{y}+10))$, `LOG_SHIFT_GWH=10.0`), penskalaan varians slope Drift $\sqrt{\frac{h(1+h/T)}{h_0(1+h_0/T)}}$ (`T=13`), dan supresi `q95 = NaN` (`insufficient_sample_size`) pada `national/all` (`n = 4 < 10`). |
| **`K-4`** | `[Kritis]` | `src/ecadin_energy/forecasting/production/validation.py`, `tests/unit/test_production_validation.py` | `validate_production_frames()` meng-hardcode `2448`, `2436`, dan `historical_missing == 9`. | Diganti perhitungan dinamis `_expected_backtest_rows()` dari panel `validation_eligible` + `ProductionConfig` dan `_expected_historical_missing()` dari *outer merge* panel historis. |
| **`D-1`** | `[Disarankan]` | `src/ecadin_energy/forecasting/configuration.py`, `data/panels.py`, `tests/unit/test_forecasting_panels.py` | Interpolasi 2016 pra-split aman hanya selama `origins >= 2018`, belum ada *guard* jika konfigurasi diubah. | Menambahkan `validate_interpolation_origin_guard()` (`min(origins) > max(interpolate_years) + 1`) di `validate_production_config()` dan pembangun panel. |
| **`D-4`** | `[Disarankan]` | `src/ecadin_energy/forecasting/evaluation/challenger.py`, `backtesting/runner.py`, `pipeline/production.py` | *Win rate* agregat menumpuk bobot berulang pada `2021` (3×) dan mencampur rezim pra vs pasca-2021. | Menambahkan `win_rate_by_horizon()` dan `win_rate_by_regime()` (`all_years`, `pre_2022`, `post_2021`, `post_2021_origins`), menghasilkan 4 CSV baru tanpa mengubah kontrak lama. |
| **`D-6`** | `[Disarankan]` | `configs/forecasting/production.json`, `pipeline/production.py`, `pipeline/validation.py`, `production/{artifacts,demand,supply,accounting,validation}.py` | `_model_summary()` hardcode `"drift"`/`"Drift"`, `supply_forecast.csv` urut `["year","modeling_order"]`, mismatch `output_value_column` & `model_version`, JSON simpan `D:\...`, dan SHA-256 belum diverifikasi validator. | Config-driven `_model_summary()` (menjaga ID `demand_production_drift` & `supply_production_drift_v1`), sinkronisasi `output_value_column = "forecast_gwh"` dan `model_version`, sort `supply_forecast.csv` menjadi `["modeling_order","year"]`, `relative_posix_path()` (`project_root: "."`), serta verifikasi SHA-256 `3/3` input & `28/28` output di `validate_written_outputs()`. |
| **`D-2`** | `[Disarankan]` | `scripts/generate_evaluation_diagnostics.py`, `outputs/reports/analysis/*.csv` | `data_quality_flags.csv` belum terintegrasi dalam pelaporan evaluasi terstratifikasi. | Membuat skrip diagnostik *read-only* yang menerbitkan 3 tabel analisis untuk Laporan KP tanpa mengubah hash produksi maupun data historis kanonis. |

*(Catatan: Temuan `D-3` terkait riset challenger lanjutan di `experiments/`, `D-5` terkait catatan interpretasi/YoY, serta `O-1`/`O-2` dibahas terpisah sesuai batasan Batch 1; catatan metodologis `D-5` disiapkan pada Bagian 6 di bawah.)*

---

## 3. Tabel Angka Metrik Final Backtesting (`outputs/production/metrics/`)

### 3.1 Ringkasan Performa Model Demand & Supply (`demand_metrics_summary.csv` & `supply_metrics_summary.csv`)

Pada evaluasi **Demand**, model produksi **`drift`** (`demand_production_drift`) unggul di seluruh metrik pada kedua protokol. Pada evaluasi **Supply**, `naive_lag1` unggul tipis pada agregat keseluruhan (`macro_smape_percent` & `micro_rmse_gwh`) terutama akibat guncangan tahun 2021, tetapi **`drift`** (`supply_production_drift_v1`) memiliki *aggregate bias* mendekati nol dan menang mutlak pasca-2021 (lihat Bagian 5.1).

| Domain | Protokol (`N` / `MASE Valid`) | Model | Macro sMAPE (%) | Macro MASE | Valid Region MASE | Micro RMSE (GWh) | Agg. Bias (%) |
| :--- | :--- | :--- | ---: | ---: | :---: | ---: | ---: |
| **Demand** | `rolling_one_step` (`204` / `204`) | **`drift` [Produksi]** | **5.83** | **0.894** | 34 / 34 | **856.92** | **-0.27%** |
| Demand | `rolling_one_step` (`204` / `204`) | `average_growth_3` | 7.09 | 1.055 | 34 / 34 | 1,207.05 | +0.41% |
| Demand | `rolling_one_step` (`204` / `204`) | `naive_lag1` | 8.93 | 1.423 | 34 / 34 | 906.28 | -4.16% |
| Demand | `rolling_one_step` (`204` / `204`) | `moving_average_3` | 14.30 | 2.259 | 34 / 34 | 1,259.03 | -7.95% |
| **Demand** | `recursive_multi_step` (`408` / `408`) | **`drift` [Produksi]** | **8.14** | **1.256** | 34 / 34 | **1,329.67** | **-0.04%** |
| Demand | `recursive_multi_step` (`408` / `408`) | `average_growth_3` | 11.42 | 1.766 | 34 / 34 | 2,547.18 | +0.67% |
| Demand | `recursive_multi_step` (`408` / `408`) | `naive_lag1` | 14.61 | 2.367 | 34 / 34 | 1,433.20 | -7.81% |
| Demand | `recursive_multi_step` (`408` / `408`) | `moving_average_3` | 17.81 | 2.883 | 34 / 34 | 1,511.93 | -9.90% |
| **Supply** | `rolling_one_step` (`203` / `200`) | `naive_lag1` | **29.35** | **4.756** | 34 / 34 | **2,056.84** | -3.75% |
| Supply | `rolling_one_step` (`203` / `200`) | **`drift` [Produksi]** | 29.51 | 4.935 | 34 / 34 | 2,065.43 | **-0.10%** |
| Supply | `rolling_one_step` (`203` / `200`) | `average_growth_3` | 40.64 | 6.844 | 34 / 34 | 4,257.15 | +9.03% |
| Supply | `rolling_one_step` (`203` / `200`) | `moving_average_3` | 40.85 | 5.948 | 34 / 34 | 2,808.87 | -7.27% |
| **Supply** | `recursive_multi_step` (`406` / `396`) | `naive_lag1` | **54.83** | **12.353** | 33 / 34 | **3,669.13** | -7.99% |
| Supply | `recursive_multi_step` (`406` / `396`) | **`drift` [Produksi]** | 56.24 | 12.383 | 33 / 34 | 3,731.86 | **-0.82%** |
| Supply | `recursive_multi_step` (`406` / `396`) | `moving_average_3` | 61.12 | 12.770 | 33 / 34 | 3,838.44 | -9.89% |
| Supply | `recursive_multi_step` (`406` / `396`) | `average_growth_3` | 68.49 | 39.395 | 33 / 34 | 219,751.87 | +148.22% |

> **Catatan K-2 (`mase_valid_prediction_count`)**: Pada **Supply**, `DI Yogyakarta (YO)` memiliki histori konstan `0.0 GWh` pada `2015–2019` dan observasi hilang pada `2020`. Dengan aturan `K-2` (`diff(year) == 1` & penolakan skala nol), seluruh origin `2018–2021` pada `recursive_multi_step` tidak memiliki pasangan konsekutif non-nol yang valid sehingga `YO` berkontribusi `0/10` kasus MASE (`mase = NaN`; total valid `396/406` prediksi dan `33/34` region). Pada `rolling_one_step`, hanya `3` fold `YO` (`2019, 2021, 2022`) yang berskala nol sehingga total valid menjadi `200/203` prediksi (`34/34` region karena `YO` valid di `2023–2024`).

### 3.2 Win Rate Challenger vs Reference `drift` per Horizon & Rezim (D-4)

Nilai `< 50%` berarti *challenger* lebih jarang mengalahkan `drift` (model referensi produksi lebih unggul pada mayoritas pasangan observasi).

#### A. Per Horizon (`*_win_rate_by_horizon_vs_drift.csv`)

| Domain | Protokol | Horizon (`N`) | `naive_lag1` (W/T/L → WR) | `moving_average_3` (W/T/L → WR) | `average_growth_3` (W/T/L → WR) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Demand** | `rolling_one_step` | `h=1` (`204`) | 34/0/170 → **16.7%** | 27/0/177 → **13.2%** | 93/0/111 → **45.6%** |
| **Demand** | `recursive_multi_step` | `h=1` (`136`) | 29/0/107 → **21.3%** | 25/0/111 → **18.4%** | 49/0/87 → **36.0%** |
| Demand | `recursive_multi_step` | `h=2` (`136`) | 19/0/117 → **14.0%** | 20/0/116 → **14.7%** | 49/0/87 → **36.0%** |
| Demand | `recursive_multi_step` | `h=3` (`136`) | 18/0/118 → **13.2%** | 20/0/116 → **14.7%** | 48/0/88 → **35.3%** |
| **Supply** | `rolling_one_step` | `h=1` (`203`) | 81/3/119 → **40.6%** | 72/2/129 → **36.0%** | 68/2/133 → **34.0%** |
| **Supply** | `recursive_multi_step` | `h=1` (`135`) | 61/3/71 → **46.3%** | 53/2/80 → **40.0%** | 51/2/82 → **38.5%** |
| Supply | `recursive_multi_step` | `h=2` (`135`) | 66/3/66 → **50.0%** | 65/2/68 → **48.9%** | 51/2/82 → **38.5%** |
| Supply | `recursive_multi_step` | `h=3` (`136`) | 64/4/68 → **48.5%** | 65/3/68 → **48.9%** | 40/3/93 → **30.5%** |

#### B. Per Rezim (`*_win_rate_by_regime_vs_drift.csv`)

| Domain | Protokol | Rezim (`Target`, `N`) | `naive_lag1` Win Rate | `moving_average_3` Win Rate | `average_growth_3` Win Rate |
| :--- | :--- | :--- | :---: | :---: | :---: |
| **Demand** | `rolling_one_step` | `all_years` (`2019–2024`, `204`) | 16.7% | 13.2% | 45.6% |
| Demand | `rolling_one_step` | `pre_2022` (`2019–2021`, `102`) | 24.5% | 21.6% | 37.3% |
| Demand | `rolling_one_step` | `post_2021` / `post_2021_origins` (`2022–2024`, `102`) | **8.8%** | **4.9%** | **53.9%** *(55 vs 47)* |
| **Demand** | `recursive_multi_step` | `all_years` (`2019–2024`, `408`) | 16.2% | 15.9% | 35.8% |
| Demand | `recursive_multi_step` | `pre_2022` (`2019–2021`, `204`) | 23.0% | 22.5% | 41.2% |
| Demand | `recursive_multi_step` | `post_2021` (`2022–2024`, `204`) | 9.3% | 9.3% | 30.4% |
| Demand | `recursive_multi_step` | `post_2021_origins` (`2022–2024`, `102`) | **5.9%** | **6.9%** | **41.2%** |
| **Supply** | `rolling_one_step` | `all_years` (`2019–2024`, `203`) | 40.6% | 36.0% | 34.0% |
| Supply | `rolling_one_step` | `pre_2022` (`2019–2021`, `101`) | 49.0% | 46.5% | 41.6% |
| Supply | `rolling_one_step` | `post_2021` / `post_2021_origins` (`2022–2024`, `102`) | **32.4%** | **25.5%** | **26.5%** |
| **Supply** | `recursive_multi_step` | `all_years` (`2019–2024`, `406`) | 48.3% | 45.9% | 35.8% |
| Supply | `recursive_multi_step` | `pre_2022` (`2019–2021`, `202`) | 49.3% | 49.5% | 41.6% |
| Supply | `recursive_multi_step` | `post_2021` (`2022–2024`, `204`) | 47.3% | 42.4% | 30.1% |
| Supply | `recursive_multi_step` | `post_2021_origins` (`2022–2024`, `102`) | **38.2%** | **20.6%** | **22.5%** |

---

## 4. Ringkasan Kalibrasi Ketidakpastian Supply — K-3 (`outputs/production/forecasts/`)

Kalibrasi K-3 di [`supply.py`](../src/ecadin_energy/forecasting/production/supply.py) menggunakan residual *recursive drift* yang **konsisten rezim & bucket** (`~crosses_structural_break & origin_size_bucket == target_size_bucket`), kuantil empiris *log-error* asimetris dengan pergeseran `LOG_SHIFT_GWH = 10.0`, serta ekstrapolasi horizon `h = 4..6` berbasis varians slope Drift $\sqrt{\frac{h(1+h/T)}{h_0(1+h_0/T)}}$ ($h_0 = 3, T = 13$). Untuk skala `national/all` yang hanya memiliki `n = 4` observasi per horizon, **`q95` disupresi menjadi `NaN`** (`q95_status = insufficient_sample_size`).

### 4.1 Parameter Kalibrasi `supply_uncertainty_calibration.csv` (`h = 1..6`)

| Scope / Bucket | Horizon | `n` | `q80_lower_log` | `q80_upper_log` | `q95_lower_log` | `q95_upper_log` | Cov. 80 / 95 | `q95_status` |
| :--- | :---: | :---: | ---: | ---: | ---: | ---: | :---: | :--- |
| **`national` / `all`** | `1` | 4 | 0.0468 | 0.0396 | `NaN` | `NaN` | 0.500 / `NaN` | `insufficient_sample_size` (`n=4 < 10`) |
| `national` / `all` | `2` | 4 | 0.0639 | 0.0636 | `NaN` | `NaN` | 0.500 / `NaN` | `insufficient_sample_size` |
| `national` / `all` | `3` | 4 | 0.0639 | 0.0636 | `NaN` | `NaN` | 0.750 / `NaN` | `insufficient_sample_size` |
| `national` / `all` | `4`–`6` | 0 | 0.0760–0.0984 | 0.0756–0.0979 | `NaN` | `NaN` | `NaN` / `NaN` | `insufficient_sample_size` *(anchor n=4)* |
| **`regional` / `small`** | `1` | 20 | 0.3472 | 0.4149 | 1.0298 | 0.5724 | 0.800 / 0.900 | `sufficient` |
| `regional` / `small` | `2` | 13 | 0.4994 | 0.4861 | 1.4631 | 0.9952 | 0.692 / 0.846 | `sufficient` |
| `regional` / `small` | `3` | 7 | 0.4994 | 0.4861 | 1.4631 | 0.9952 | 0.857 / 1.000 | `limited_sample_stabilized` |
| `regional` / `small` | `4`–`6` | 0 | 0.5944–0.7696 | 0.5786–0.7491 | 1.7414–**2.2548** | 1.1846–**1.5337** | — | `extrapolated_from_horizon_3` |
| **`regional` / `medium`** | `1` | 38 | 0.2340 | 0.1054 | 0.3446 | 0.1758 | 0.789 / 0.947 | `sufficient` |
| `regional` / `medium` | `2` | 29 | 0.3279 | 0.2058 | 0.5715 | 0.2447 | 0.793 / 0.931 | `sufficient` |
| `regional` / `medium` | `3` | 19 | 0.3279 | 0.2457 | 0.6526 | 0.3932 | 0.842 / 0.895 | `sufficient` |
| `regional` / `medium` | `4`–`6` | 0 | 0.3902–0.5053 | 0.2925–0.3787 | 0.7767–**1.0057** | 0.4680–**0.6060** | — | `extrapolated_from_horizon_3` |
| **`regional` / `large`** | `1` | 21 | 0.1240 | 0.0324 | 0.1999 | 0.1989 | 0.810 / 0.905 | `sufficient` |
| `regional` / `large` | `2` | 14 | 0.2182 | 0.1309 | 0.2942 | 0.2545 | 0.714 / 0.857 | `sufficient` |
| `regional` / `large` | `3` | 7 | 0.2182 | 0.3168 | 0.2942 | 0.3368 | 0.714 / 0.857 | `limited_sample_stabilized` |
| `regional` / `large` | `4`–`6` | 0 | 0.2597–0.3362 | 0.3771–0.4883 | 0.3502–**0.4535** | 0.4008–**0.5190** | — | `extrapolated_from_horizon_3` |

*(Nilai `q80_absolute_scaled_error` & `q95_absolute_scaled_error` pada `small` h=6 turun dari `11.265 / 61.011` sebelum K-3 menjadi `0.754 / 2.190` pasca K-3.)*

### 4.2 Sampel Interval Prediksi Supply Tahun 2030 (`h = 6`, `supply_forecast.csv`)

| Region (`Bucket`) | Point 2030 (GWh) | Lower 80 (GWh) | Upper 80 (GWh) | Lower 95 (GWh) | Upper 95 (GWh) | Rasio `upper95 / point` (vs Sebelum K-3) |
| :--- | ---: | ---: | ---: | ---: | ---: | :---: |
| `YO` — DI Yogyakarta (`small`) | 6.07 | 0.00 | 23.98 | 0.00 | **64.48** | **10.63×** *(turun dari `1.007×` / 6.107 GWh)* |
| `SR` — Sulawesi Barat (`small`) | 291.33 | 129.57 | 627.36 | 21.61 | **1,386.80** | **4.76×** *(turun dari `43.4×`)* |
| `PB` — Papua Barat (`small`) | 996.76 | 456.31 | 2,119.47 | 95.61 | **4,656.83** | **4.67×** *(turun dari `49.3×`)* |
| `MU` — Maluku Utara (`small`) | 1,084.24 | 496.83 | 2,304.52 | 104.79 | **5,062.36** | **4.67×** *(turun dari `45.5×`)* |
| `KU` — Kalimantan Utara (`small`) | 1,093.54 | 501.13 | 2,324.18 | 105.76 | **5,105.46** | **4.67×** *(turun dari `43.7×`)* |
| `MA` — Maluku (`small`) | 1,107.45 | 507.58 | 2,353.61 | 107.22 | **5,169.95** | **4.67×** *(turun dari `50.9×`)* |
| `GO` — Gorontalo (`small`) | 1,291.45 | 592.80 | 2,742.81 | 126.52 | **6,022.89** | **4.66×** *(turun dari `46.5×`)* |
| `AC` — Aceh (`medium`) | 5,400.86 | 3,254.63 | 7,891.92 | 1,969.20 | **9,908.74** | **1.83×** |
| `LA` — Lampung (`medium`) | 3,748.96 | 2,257.96 | 5,479.53 | 1,364.97 | **6,880.63** | **1.84×** |
| `JB` — Jawa Barat (`large`) | 57,440.37 | 41,037.10 | 93,607.12 | 36,495.26 | **96,527.18** | **1.68×** |
| `JI` — Jawa Timur (`large`) | 44,657.22 | 31,903.80 | 72,776.58 | 28,372.56 | **75,046.91** | **1.68×** |

---

## 5. Ringkasan Hasil 3 Tabel Analisis Diagnostik D-2 (`outputs/reports/analysis/`)

Dihasilkan secara *read-only* oleh [`scripts/generate_evaluation_diagnostics.py`](../scripts/generate_evaluation_diagnostics.py).

### 5.1 Stratifikasi Rezim Supply (`supply_regime_stratification.csv`)

Memisahkan performa 4 model sebelum guncangan (`2019–2020`), tepat saat guncangan (`2021`), dan pasca-guncangan (`2022–2024`), memperlihatkan bahwa ketidakunggulan tipis `drift` secara agregat keseluruhan **murni disebabkan oleh *structural break* tahun 2021** (serta kontaminasi *origin* pra-2021 pada *recursive multi-step*). Setelah tahun 2021, **`drift` menjadi model paling akurat secara konsisten**:

| Protokol | Rezim (`Target`, `N` / `MASE Valid`) | `drift` sMAPE / MASE / RMSE / Bias | `naive_lag1` sMAPE / MASE / RMSE / Bias | Pemenang sMAPE |
| :--- | :--- | :---: | :---: | :---: |
| `rolling_one_step` | Pra-2021 (`2019–2020`, `67` / `66`) | 29.23% / **1.527** / 1,205.69 / +4.10% | **27.16%** / 1.529 / **776.99** / -0.13% | `naive_lag1` |
| `rolling_one_step` | Tahun Guncangan (`2021`, `34` / `33`) | 88.45% / 22.510 / 3,460.91 / **-3.93%** | 86.84% / 22.393 / 3,293.01 / -7.15% | `moving_average_3` (`77.88%`) |
| `rolling_one_step` | **Pasca-2021 (`2022–2024`, `102` / `101`)** | **9.61% / 1.283 / 1,882.19 / -1.32%** | 11.23% / **1.203** / 2,099.64 / -4.76% | **`drift`** *(unggul `-1.62 pp`)* |
| `recursive_multi_step` | Pra-2021 (`2019–2020`, `100` / `99`) | 36.39% / 2.050 / 1,622.47 / +5.59% | **33.00% / 2.001 / 882.85 / -0.17%** | `naive_lag1` |
| `recursive_multi_step` | Tahun Guncangan (`2021`, `102` / `99`) | 81.44% / 22.526 / 3,742.38 / **+1.04%** | 80.32% / 22.466 / 3,030.45 / -6.69% | `moving_average_3` (`75.58%`) |
| `recursive_multi_step` | Pasca-2021 semua origin (`2022–2024`, `204` / `198`) | 52.32% / 12.478 / **4,407.25** / **-4.38%** | **51.81% / 12.473** / 4,671.10 / -11.90% | `naive_lag1` *(origin 2019–2020 terbawa)* |
| `recursive_multi_step` | **Pasca-2021 `origin >= 2021` (`2022–2024`, `102` / `99`)** | **15.80% / 1.628 / 3,301.19 / -3.48%** | 17.42% / 1.791 / 3,929.31 / -10.00% | **`drift`** *(unggul `-1.61 pp`; MA3 43.83%; AG3 55.75%)* |

*(Catatan: Pada `recursive_multi_step`, `average_growth_3` meledak ekstrem pasca-2021 menjadi Micro RMSE `309,949.79 GWh` pada semua origin dan `438,295.27 GWh` / Bias `+535.25%` pada `origin >= 2021` karena memproyeksikan tingkat pertumbuhan CAGR 2021 secara majemuk.)*

### 5.2 Sensitivitas Outlier Demand Kepulauan Riau (`KR`) 2020 (`demand_sensitivity_kr2020.csv`)

Pada tahun 2020, distribusi listrik Kepulauan Riau (`KR`) turun drastis satu tahun sebesar **`-73.48%`** (`3.346,31 -> 887,60 -> 3.478,63 GWh`). Tabel di bawah menunjukkan dampak observasi outlier tunggal tersebut terhadap performa **`drift`**:

| Protokol | Skenario (`N` prediksi) | Macro sMAPE (%) | Delta sMAPE (`pp`) | Macro MASE | Delta MASE | Micro RMSE (GWh) | Delta RMSE |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| `rolling_one_step` | `all_observations` (34 prov, `204`) | 5.83% | — | 0.894 | — | 856.92 | — |
| `rolling_one_step` | `exclude_kr_2020_target` (`203`, `-1` baris) | 5.40% | **-0.44 pp** | 0.825 | -0.068 | 839.03 | -17.89 |
| `rolling_one_step` | `exclude_kr_2020_target_and_origin` (`202`, `-2` baris) | **4.68%** | **-1.16 pp** *(≈ -19.8% rel.)* | **0.791** | **-0.102** | **819.11** | **-37.81** |
| `rolling_one_step` | `exclude_kr_all_years` (33 prov, `198`, `-6` baris) | 4.64% | -1.19 pp | 0.795 | -0.098 | 826.70 | -30.23 |
| `recursive_multi_step` | `all_observations` (34 prov, `408`) | 8.14% | — | 1.256 | — | 1,329.67 | — |
| `recursive_multi_step` | `exclude_kr_2020_target` (`406`, `-2` baris) | 7.80% | **-0.34 pp** | 1.190 | -0.066 | 1,321.28 | -8.40 |
| `recursive_multi_step` | `exclude_kr_2020_target_and_origin` (`403`, `-5` baris) | **6.60%** | **-1.53 pp** *(≈ -18.9% rel.)* | **1.129** | **-0.126** | **1,296.28** | **-33.40** |
| `recursive_multi_step` | `exclude_kr_all_years` (33 prov, `396`, `-12` baris) | 6.58% | -1.55 pp | 1.139 | -0.117 | 1,306.81 | -22.87 |

Di seluruh skenario sensitivitas tersebut, peringkat model **tidak berubah**: **`drift`** tetap peringkat ke-1 diikuti `average_growth_3`, `naive_lag1`, dan `moving_average_3`. Hanya menghapus target & origin 2020 milik `KR` (`2` dari `204` baris one-step; `5` dari `408` baris recursive) sudah menurunkan Macro sMAPE nasional sekitar **19% relatif**.

### 5.3 Dampak Flag `data_quality_flags.csv` (`data_quality_flag_impact_summary.csv`)

1. **Structural Break Supply Tahun 2021 (`17` provinsi terdampak: `16` ter-flag + `SR` lonjakan dari nol)**:
   - **16 provinsi** ditandai `large_consecutive_yoy_change` (`>= +75%` dan `>= 100 GWh`):
     `LA` Lampung (`41.55 -> 5,436.19 GWh`, **+12,983.5%**), `KT` Kalimantan Tengah (`49.85 -> 2,631.62`, **+5,179.1%**), `SG` Sulawesi Tenggara (`25.73 -> 1,181.79`, **+4,493.0%**), `BE` Bengkulu (`158.67 -> 2,689.06`, **+1,594.8%**), `KB` Kalimantan Barat (`234.34 -> 3,416.64`, **+1,358.0%**), `JA` Jambi (`85.54 -> 730.00`, **+753.4%**), `AC` Aceh (`421.51 -> 3,001.78`, **+612.2%**), `RI` Riau (`716.38 -> 5,028.96`, **+602.0%**), `GO` Gorontalo (`96.53 -> 579.41`, **+500.2%**), `SB` Sumatera Barat (`948.92 -> 4,396.18`, **+363.3%**), `MU` Maluku Utara (`126.03 -> 377.04`, **+199.2%**), `SA` Sulawesi Utara (`908.75 -> 2,380.58`, **+162.0%**), `PA` Papua (`522.52 -> 1,360.61`, **+160.4%**), `KU` Kalimantan Utara (`261.92 -> 619.17`, **+136.4%**), `KI` Kalimantan Timur (`1,944.98 -> 3,908.24`, **+100.9%**), dan `BB` Bangka Belitung (`830.12 -> 1,498.09`, **+80.5%**).
   - **11 dari 16 provinsi** tersebut (`LA`, `KT`, `SG`, `BE`, `JA`, `AC`, `RI`, `GO`, `SB`, `SA`, `KI`) juga mengalami flag `large_consecutive_yoy_change` secara bersamaan pada **`installed_capacity_mw` tahun 2021** (`+129.9%` hingga `+777.6%`), memperkuat indikasi perubahan cakupan pencatatan statistik BPS pada tahun 2021.
   - **1 provinsi tambahan (`SR` — Sulawesi Barat)** melonjak dari **`0.00 -> 249.45 GWh`** pada tahun yang sama (`drift` one-step sMAPE `200.00%`, recursive `173.84%`); tidak masuk aturan flag persentase YoY karena basis pembagi 2020 bernilai nol, namun didokumentasikan eksplisit dalam tabel dampak.
   - Error one-step `drift` pada 17 provinsi tersebut di tahun 2021 berkisar antara **`54.65%` (`BB`) hingga `200.00%` (`KT`, `SG`, `SR`)**.

2. **Anomali Demand YoY (`7` baris flag `large_consecutive_yoy_change`)**:
   - **`KR` 2020 (`-73.48%`)**: `3,346.31 -> 887.60 GWh` (`drift` one-step `119.33%`, recursive `116.97%`), diikuti pantulan **`KR` 2021 (`+291.91%`)**: `887.60 -> 3,478.63 GWh` (`drift` one-step `128.06%`, recursive `45.22%`).
   - Flag lainnya (semuanya mencerminkan ekspansi jaringan/konsumsi yang relatif persisten sehingga dipertahankan): `MU` 2018 (`+69.32%`), `JA` 2019 (`+58.49%`), `MU` 2023 (`+51.49%`, disertai flag kapasitas `+90.73%`), `KU` 2019 (`+44.31%`), dan `KU` 2023 (`+36.92%`).

---

## 6. Catatan Metodologis D-5 Siap Kutip untuk Laporan Kerja Praktik

Bagian ini merangkum dua penjelasan metodologis penting dari audit `D-5` agar konsisten antara kode/kontrak dashboard dan narasi Bab 3–Bab 4 Laporan KP (tanpa mengubah kode/kontrak frontend yang sudah final).

### 6.1 Pembedaan `gap_category` Internal vs Makna Non-Adequacy (`accounting.py` vs `region_detail.py`)

- **Fakta implementasi**: Pada output peramalan (`accounting_difference.csv` & `regional_energy_history_forecast.csv`), selisih dihitung sebagai `accounting_difference_gwh = supply_gwh - demand_gwh` dengan disclaimer tegas bahwa *interregional electricity flows are omitted, so it must not be interpreted as shortage, surplus, or adequacy*. Namun di lapisan dashboard (`region_detail.py` & `configs/dashboard/production.json`), rasio persentase `difference_to_demand_percent` tetap dipetakan ke kode kategori internal `"surplus_tinggi"` (`>= +20%`), `"surplus_moderat"` (`+5% s.d. < +20%`), `"relatif_seimbang"` (`>-5% s.d. < +5%`), `"defisit_moderat"` (`>-20% s.d. <= -5%`), dan `"defisit_tinggi"` (`<= -20%`).
- **Teks siap kutip**:
  > *"Metrik selisih energi dalam sistem ini didefinisikan secara ketat sebagai **selisih akuntansi lokal** (*accounting difference*), yakni produksi listrik pembangkit lokal (`local_generation_gwh`) dikurangi listrik yang didistribusikan (`distributed_electricity_gwh`) di provinsi tersebut. Label kategorisasi internal pada antarmuka analitik (`surplus_tinggi` hingga `defisit_tinggi`) hanya berfungsi sebagai penanda posisi pembangkitan lokal terhadap distribusi provinsi guna menjaga kompatibilitas kontrak data, dan **tidak boleh diinterpretasikan sebagai indikator surplus fisik, defisit pasokan, ataupun kecukupan sistem (*adequacy*)**, karena arus transfer listrik lintas-provinsi dalam sistem interkoneksi grid regional tidak dimodelkan dalam dataset BPS."*

### 6.2 Distorsi Pertumbuhan YoY Nasional (`dashboard_national_timeseries.csv` — `partial_overlap`)

- **Fakta observasi aktual**: Pada `dashboard_national_timeseries.csv`, agregasi nasional hanya menjumlahkan provinsi dengan pasangan demand–supply lengkap pada tahun terkait (`complete_regions`), sehingga tahun historis memiliki perubahan cakupan wilayah:
  - `2011–2012`: `31/34` provinsi (`partial_overlap`, tanpa `KI`, `KU`, `YO`) → YoY `2012`: Demand `+9.87%`, Supply `+8.45%`
  - `2013–2014`: `33/34` provinsi (`partial_overlap`, masuk `KI` & `KU`; `YO` masih kosong) → YoY `2013`: Demand `+9.62%`, Supply `+10.35%`
  - `2015–2019`: `34/34` provinsi (`complete`, tahun `2016` memakai target demand & supply terinterpolasi linear) → YoY `2015`: Demand `+3.88%`, Supply `+0.73%`
  - `2020`: `33/34` provinsi (`partial_overlap`, `YO` supply hilang sehingga `YO` dikeluarkan dari pasangan nasional 2020) → YoY `2020`: Demand `-3.74%`, Supply `-1.69%`
  - `2021–2024`: `34/34` provinsi (`complete`, `YO` kembali masuk sekaligus terjadi ekspansi cakupan 2021) → YoY `2021`: Demand `+8.07%`, Supply `+7.70%`
  - `2025–2030`: `34/34` provinsi (`complete`, seluruhnya proyeksi)
- **Teks siap kutip**:
  > *"Rangkaian agregat nasional disusun dari penjumlahan provinsi yang memiliki pasangan data demand dan supply lengkap pada setiap tahun (`complete_regions`). Akibatnya, indikator pertumbuhan tahunan nasional (`demand_growth_yoy_percent` dan `supply_growth_yoy_percent`) pada tahun berstatus `partial_overlap` atau transisi cakupan — khususnya **2013** (masuknya `KI` dan `KU`), **2015** (mulai lengkapnya `YO`), **2020** (keluarnya `YO` akibat kekosongan data pembangkitan 2020), dan **2021** (kembalinya `YO` beserta pergeseran rezim pencatatan pembangkitan lokal) — mencerminkan gabungan antara pertumbuhan energi riil dan perubahan komposisi provinsi terhitung, sehingga interpretasi tren nasional murni perlu merujuk pada periode cakupan penuh (`complete`)."*
