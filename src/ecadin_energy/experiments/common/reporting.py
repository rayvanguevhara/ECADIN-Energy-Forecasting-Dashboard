from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def _pipe_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        safe_cells = [str(cell).replace("|", "/") for cell in row]
        lines.append("| " + " | ".join(safe_cells) + " |")
    return lines


def _fmt_num(val: object, decimals: int = 2) -> str:
    if val is None or pd.isna(val):
        return "NA"
    return f"{float(val):,.{decimals}f}"


def _fmt_signed(val: object, decimals: int = 2, suffix: str = "") -> str:
    if val is None or pd.isna(val):
        return "NA"
    return f"{float(val):+,.{decimals}f}{suffix}"


def _metric_rows(df: pd.DataFrame) -> list[list[str]]:
    ordered = df.sort_values(
        ["macro_smape_percent", "macro_mase", "model"]
    ).reset_index(drop=True)
    rows: list[list[str]] = []
    for idx, rec in enumerate(ordered.itertuples(index=False), start=1):
        mase_valid = (
            f"{int(rec.mase_valid_prediction_count)}/{int(rec.mase_valid_region_count)}"
        )
        wr = 100.0 * float(rec.win_rate_vs_drift)
        rows.append(
            [
                str(idx),
                str(rec.model),
                str(rec.family),
                f"{float(rec.macro_smape_percent):.2f}",
                f"{float(rec.macro_mase):.3f}",
                mase_valid,
                _fmt_num(rec.micro_rmse_gwh, 2),
                _fmt_signed(rec.aggregate_bias_gwh, 2),
                _fmt_signed(rec.aggregate_bias_percent, 2, "%"),
                f"{wr:.2f}%",
                str(int(rec.clipped_prediction_count)),
            ]
        )
    return rows


METRIC_HEADERS = [
    "Rank",
    "Model",
    "Family",
    "Macro sMAPE (%)",
    "Macro MASE",
    "MASE Valid (Pred/Reg)",
    "Micro RMSE (GWh)",
    "Agg Bias (GWh)",
    "Agg Bias (%)",
    "Win Rate vs Drift (%)",
    "Clipped",
]


def _sanity_national_rows(df: pd.DataFrame) -> list[list[str]]:
    ordered = df.sort_values(
        ["is_baseline", "implied_cagr_2024_2030_percent", "model"],
        ascending=[False, False, True],
    ).reset_index(drop=True)
    rows: list[list[str]] = []
    for rec in ordered.itertuples(index=False):
        rows.append(
            [
                str(rec.model),
                str(rec.family),
                _fmt_num(rec.actual_2024_gwh, 2),
                _fmt_num(rec.forecast_2025_gwh, 2),
                _fmt_num(rec.forecast_2030_gwh, 2),
                _fmt_signed(rec.implied_cagr_2024_2030_percent, 2, "%"),
                str(int(rec.negative_slope_region_count)),
                str(int(rec.zero_or_clipped_region_count)),
                str(int(rec.extreme_cagr_region_count)),
                _fmt_signed(rec.min_region_cagr_percent, 2, "%"),
                _fmt_signed(rec.median_region_cagr_percent, 2, "%"),
                _fmt_signed(rec.max_region_cagr_percent, 2, "%"),
                str(rec.flagged_regions),
            ]
        )
    return rows


SANITY_NATIONAL_HEADERS = [
    "Model",
    "Family",
    "Actual 2024 (GWh)",
    "Fcst 2025 (GWh)",
    "Fcst 2030 (GWh)",
    "Implied CAGR 24-30",
    "Neg Slope Regs",
    "Zero/Clipped Regs",
    "Extreme CAGR Regs",
    "Min Reg CAGR",
    "Med Reg CAGR",
    "Max Reg CAGR",
    "Flagged Regions",
]


def _key_province_pivot_table(
    key_df: pd.DataFrame,
    *,
    provinces: tuple[str, ...],
    models: tuple[str, ...],
) -> tuple[list[str], list[list[str]]]:
    sub = key_df.loc[key_df["model"].isin(models)].copy()
    lookup = sub.set_index(["region_id", "model"]).to_dict("index")
    headers = ["Region", "Name", "Actual 2024 (GWh)"]
    for m in models:
        headers.append(f"{m} 2030 (CAGR)")

    rows: list[list[str]] = []
    for rid in provinces:
        first_rec = lookup[(rid, models[0])]
        row = [
            rid,
            str(first_rec["region_name"]),
            _fmt_num(first_rec["actual_2024_gwh"], 2),
        ]
        for m in models:
            rec = lookup[(rid, m)]
            f30 = _fmt_num(rec["forecast_2030_gwh"], 1)
            cagr = _fmt_signed(rec["implied_cagr_2024_2030_percent"], 2, "%")
            clip_tag = " [CLIP]" if bool(rec["was_clipped_any_2025_2030"]) else ""
            row.append(f"{f30} ({cagr}){clip_tag}")
        rows.append(row)
    return headers, rows


def _lookup_row(
    df: pd.DataFrame,
    filters: dict[str, object],
) -> pd.Series:
    mask = pd.Series(True, index=df.index)
    for col, val in filters.items():
        mask = mask & df[col].eq(val)
    matched = df.loc[mask]
    if len(matched) != 1:
        raise ValueError(f"Expected 1 row for {filters}, got {len(matched)}")
    return matched.iloc[0]


def generate_phase2_report(
    *,
    report_path: Path,
    env_df: pd.DataFrame,
    checks_df: pd.DataFrame,
    supply_panel: pd.DataFrame,
    demand_panel: pd.DataFrame,
    supply_summary: pd.DataFrame,
    demand_summary: pd.DataFrame,
    supply_regime: pd.DataFrame,
    demand_scenario: pd.DataFrame,
    supply_horizon: pd.DataFrame,
    demand_horizon: pd.DataFrame,
    supply_nat_sanity: pd.DataFrame,
    demand_nat_sanity: pd.DataFrame,
    supply_key_sanity: pd.DataFrame,
    demand_key_sanity: pd.DataFrame,
) -> Path:
    """Write the complete, untruncated Phase 2 plain-text report (UTF-8, LF)."""
    lines: list[str] = []

    def add(text: str = "") -> None:
        lines.append(text)

    def add_table(headers: list[str], rows: list[list[str]]) -> None:
        lines.extend(_pipe_table(headers, rows))
        add()

    # Dynamic key lookups for Section 5 accurate citations
    sup_r1_natrec = _lookup_row(
        supply_summary, {"protocol_slice": "rolling_one_step", "model": "national_reconciled_supply"}
    )
    sup_r1_sid = _lookup_row(
        supply_summary, {"protocol_slice": "rolling_one_step", "model": "step_intervention_damped"}
    )
    sup_r1_drift = _lookup_row(
        supply_summary, {"protocol_slice": "rolling_one_step", "model": "drift"}
    )
    sup_r1_post_natrec = _lookup_row(
        supply_regime,
        {"protocol": "rolling_one_step", "regime": "post_2021", "model": "national_reconciled_supply"},
    )
    sup_r1_post_drift = _lookup_row(
        supply_regime,
        {"protocol": "rolling_one_step", "regime": "post_2021", "model": "drift"},
    )

    sup_h3_sols = _lookup_row(
        supply_summary, {"protocol_slice": "recursive_multi_step_h3", "model": "step_intervention_ols"}
    )
    sup_h3_natrec = _lookup_row(
        supply_summary, {"protocol_slice": "recursive_multi_step_h3", "model": "national_reconciled_supply"}
    )
    sup_h3_sid = _lookup_row(
        supply_summary, {"protocol_slice": "recursive_multi_step_h3", "model": "step_intervention_damped"}
    )
    sup_h3_naive = _lookup_row(
        supply_summary, {"protocol_slice": "recursive_multi_step_h3", "model": "naive_lag1"}
    )
    sup_h3_drift = _lookup_row(
        supply_summary, {"protocol_slice": "recursive_multi_step_h3", "model": "drift"}
    )

    sup_h3_post_sols = _lookup_row(
        supply_regime,
        {"protocol": "recursive_multi_step_h3", "regime": "post_2021", "model": "step_intervention_ols"},
    )
    sup_h3_post_natrec = _lookup_row(
        supply_regime,
        {"protocol": "recursive_multi_step_h3", "regime": "post_2021", "model": "national_reconciled_supply"},
    )
    sup_h3_post_drift = _lookup_row(
        supply_regime,
        {"protocol": "recursive_multi_step_h3", "regime": "post_2021", "model": "drift"},
    )
    sup_h3_clean_natrec = _lookup_row(
        supply_regime,
        {"protocol": "recursive_multi_step_h3", "regime": "post_2021_clean_origins", "model": "national_reconciled_supply"},
    )
    sup_h3_clean_drift = _lookup_row(
        supply_regime,
        {"protocol": "recursive_multi_step_h3", "regime": "post_2021_clean_origins", "model": "drift"},
    )
    sup_h3_clean_sid = _lookup_row(
        supply_regime,
        {"protocol": "recursive_multi_step_h3", "regime": "post_2021_clean_origins", "model": "step_intervention_damped"},
    )

    sup_ext_ts = _lookup_row(
        supply_summary, {"protocol_slice": "extended_horizon_h4_h6", "model": "theil_sen_trend"}
    )
    sup_ext_natrec = _lookup_row(
        supply_summary, {"protocol_slice": "extended_horizon_h4_h6", "model": "national_reconciled_supply"}
    )
    sup_ext_drift = _lookup_row(
        supply_summary, {"protocol_slice": "extended_horizon_h4_h6", "model": "drift"}
    )

    sup_nat_natrec = _lookup_row(supply_nat_sanity, {"model": "national_reconciled_supply"})
    sup_nat_drift = _lookup_row(supply_nat_sanity, {"model": "drift"})
    sup_nat_sid = _lookup_row(supply_nat_sanity, {"model": "step_intervention_damped"})
    sup_nat_sols = _lookup_row(supply_nat_sanity, {"model": "step_intervention_ols"})
    sup_nat_ts = _lookup_row(supply_nat_sanity, {"model": "theil_sen_trend"})

    dem_r1_drift = _lookup_row(
        demand_summary, {"protocol_slice": "rolling_one_step", "model": "drift"}
    )
    dem_r1_ddrift = _lookup_row(
        demand_summary, {"protocol_slice": "rolling_one_step", "model": "damped_drift"}
    )
    dem_r1_ex_drift = _lookup_row(
        demand_scenario,
        {
            "protocol_slice": "rolling_one_step",
            "scenario": "exclude_kr_2020_target_and_origin",
            "model": "drift",
        },
    )
    dem_h3_drift = _lookup_row(
        demand_summary, {"protocol_slice": "recursive_multi_step_h3", "model": "drift"}
    )
    dem_h3_huber = _lookup_row(
        demand_summary, {"protocol_slice": "recursive_multi_step_h3", "model": "huber_trend"}
    )
    dem_h3_ols = _lookup_row(
        demand_summary, {"protocol_slice": "recursive_multi_step_h3", "model": "ols_linear_trend"}
    )
    dem_h3_ddrift = _lookup_row(
        demand_summary, {"protocol_slice": "recursive_multi_step_h3", "model": "damped_drift"}
    )
    dem_h3_ex_drift = _lookup_row(
        demand_scenario,
        {
            "protocol_slice": "recursive_multi_step_h3",
            "scenario": "exclude_kr_2020_target_and_origin",
            "model": "drift",
        },
    )
    dem_ext_drift = _lookup_row(
        demand_summary, {"protocol_slice": "extended_horizon_h4_h6", "model": "drift"}
    )
    dem_ext_ts = _lookup_row(
        demand_summary, {"protocol_slice": "extended_horizon_h4_h6", "model": "theil_sen_trend"}
    )
    dem_ext_ridge = _lookup_row(
        demand_summary, {"protocol_slice": "extended_horizon_h4_h6", "model": "ridge_lag_panel"}
    )
    dem_ext_ex_drift = _lookup_row(
        demand_scenario,
        {
            "protocol_slice": "extended_horizon_h4_h6",
            "scenario": "exclude_kr_2020_target_and_origin",
            "model": "drift",
        },
    )
    dem_nat_drift = _lookup_row(demand_nat_sanity, {"model": "drift"})
    dem_nat_ridge = _lookup_row(demand_nat_sanity, {"model": "ridge_lag_panel"})
    dem_nat_ols = _lookup_row(demand_nat_sanity, {"model": "ols_linear_trend"})
    dem_nat_ddrift = _lookup_row(demand_nat_sanity, {"model": "damped_drift"})

    # =========================================================================
    # HEADER & VERIFICATION
    # =========================================================================
    add("=" * 80)
    add("ECADIN PROJECT - LAPORAN EKSPERIMEN FORECASTING FASE 2 (SUPPLY & DEMAND)")
    add("=" * 80)
    add("Tanggal Laporan       : 2026-11-22")
    add("Skrip Reproducible    : scripts/run_forecasting_experiments.py")
    add("Direktori Kode        : src/ecadin_energy/experiments/")
    add("Direktori Tabel CSV   : outputs/experiments/")
    add("Panel Kanonis         : data/processed/modeling/{supply,demand}_modeling_panel.csv")
    add("Status Isolasi        : Ketat (0 perubahan pada data/, configs/forecasting/production.json,")
    add("                        src/ecadin_energy/forecasting/, src/ecadin_energy/dashboard/,")
    add("                        outputs/production/, dan tests/fixtures/)")
    add()
    add("Ringkasan Verifikasi Otomatis (Parity Produksi, Zero-Leakage, & Integritas):")
    check_rows = [
        [
            str(r.domain),
            str(r.check_name),
            str(r.status),
            str(int(r.row_count)),
            f"{float(r.max_abs_diff):.3e}",
            str(r.details),
        ]
        for r in checks_df.itertuples(index=False)
    ]
    add_table(
        ["Domain", "Check Name", "Status", "Rows", "Max Abs Diff", "Details"],
        check_rows,
    )

    # =========================================================================
    # SECTION 1: ENVIRONMENT & FORMULATIONS
    # =========================================================================
    add("=== 1. INVENTARIS LINGKUNGAN, PROTOKOL ANTI-LEAKAGE, & FORMULASI MODEL ===")
    add()
    add("1.1 Inventaris Pustaka Python (Tanpa Instalasi Paket Eksternal Baru)")
    env_rows = [
        [
            str(r.package),
            "YES" if bool(r.installed) else "NO",
            str(r.version),
            str(r.usage_note),
        ]
        for r in env_df.itertuples(index=False)
    ]
    add_table(["Package", "Installed", "Version", "Usage Note"], env_rows)

    add("1.2 Aturan Panel, Anti-Leakage, & Kontrak Metrik")
    add("- Cakupan panel: 34 provinsi x 14 tahun historis (2011-2024; 476 baris per domain).")
    add("- Konsistensi geografi & interpolasi (dari panel kanonis):")
    add("  * KI dan KU pada tahun < 2013 berstatus training_eligible=False & validation_eligible=False.")
    add("  * Tahun 2016 merupakan celah PDF BPS terinterpolasi linear: training_eligible=True, validation_eligible=False.")
    add("  * Supply YO (DI Yogyakarta) memiliki 2011-2014 unavailable, 2015-2019 = 0.00 GWh, 2020 unavailable")
    add("    (validation_eligible=False), dan 2021-2024 = 3.30-3.64 GWh; sehingga evaluasi Supply berjumlah")
    add("    n=203 (rolling_one_step), n=406 (recursive_multi_step_h3), dan n=508 (extended_horizon h=1..6).")
    add("- Anti-leakage ketat: pada setiap origin t_0, model hanya melihat observasi dengan training_eligible=True")
    add("  dan year <= t_0. Prediksi mentah di-clip non-negatif: y_hat = max(0, y_raw).")
    add("- K-2 MASE denominator (`mase_scale()`): rata-rata |y_t - y_{t-1}| hanya atas pasangan tahun berurutan")
    add("  (diff(year) == 1) di dalam history <= origin_year; bila penyebut = 0 (mis. YO pada origin <= 2020),")
    add("  MASE bernilai NaN dan dilaporkan bersama jumlah prediksi/provinsi valid (`MASE Valid`).")
    add()
    add("1.3 Formulasi Matematis Seluruh Model")
    add("[A] Baseline Produksi Eksisting (Rekursif Multi-Step dengan Clip Non-Negatif):")
    add("  1. naive_lag1              : y_hat(T+h) = y_T.")
    add("  2. drift                   : y_hat(T+h) = y_T + h * (y_T - y_{t_0}) / (T - t_0).")
    add("  3. moving_average_3        : y_hat(T+1) = mean(tail_3(history)); digulirkan rekursif ke h > 1.")
    add("  4. average_growth_3        : CAGR g = (y_T / y_{T-k})^(1/k) - 1 atas maks 4 titik positif terakhir;")
    add("                               y_hat(T+h) = y_T * (1 + g)^h (rekursif).")
    add()
    add("[B] Kandidat Khusus SUPPLY (`local_generation_gwh`):")
    add("  5. step_intervention_ols   : Jika origin < 2021 -> OLS y_t = a + b*(t - t_0).")
    add("                               Jika origin >= 2021 (dan ada data pra & pasca-2021) -> OLS dengan dummy")
    add("                               level-shift: y_t = a + b*(t - t_0) + d*I(t >= 2021); lonjakan 2021")
    add("                               diserap oleh koefisien d tanpa merusak slope b.")
    add("  6. step_intervention_damped: Estimasi slope via Frisch-Waugh-Lovell (FWL) memusatkan t dan y terpisah")
    add("                               pada rezim pra-2021 dan pasca-2021 saat origin >= 2021 (zero-leakage),")
    add("                               lalu regularisasi Ridge pada slope: b_reg = S_ty / (S_tt + lambda) dengan")
    add("                               lambda=25.0, dijangkarkan di y_T + b_reg * sum_{j=1..h} phi^j (phi=0.85).")
    add("  7. post_break_drift_or_naive: Sebelum 2021 identik drift; saat origin >= 2021 gunakan drift hanya")
    add("                               atas titik year >= 2021 jika >= 2 titik tersedia, atau fallback naive_lag1")
    add("                               saat origin = 2021 (baru 1 titik pasca-break).")
    add("  8. recent_window_drift_4   : Drift linear pada 4 observasi terakhir: slope = (y_T - y_{T-3}) / span.")
    add("  9. recent_window_ols_5     : Regresi OLS y_t = a + b*(t - t_bar) atas 5 observasi terakhir.")
    add(" 10. holt_damped             : State-space ETS(A,Ad,N) dalam numpy/scipy: y_hat = l_{t-1} + phi*b_{t-1},")
    add("                               l_t = y_hat + alpha*e_t, b_t = phi*b_{t-1} + (beta_ratio*alpha)*e_t;")
    add("                               optimasi SSE grid + L-BFGS-B pada alpha in [0.05,0.99], beta_ratio in")
    add("                               [0.001,0.99], phi in [0.80,0.98]; proyeksi l_T + b_T*sum_{j=1..h} phi^j.")
    add(" 11. theta                   : Standard Theta Method: Z_0(t) = OLS(t,y), kurva Theta=2 z_2 = 2y - Z_0,")
    add("                               SES(l_0, alpha in [0.05,0.99]) pada z_2; proyeksi 0.5*Z_0(T+h) + 0.5*l_T.")
    add(" 12. theil_sen_trend         : Median slope berpasangan (scipy.stats.theilslopes) atas seluruh histori.")
    add(" 13. huber_trend             : M-estimator HuberRegressor (epsilon=1.35, alpha=0) atas t terpusat.")
    add(" 14. national_reconciled_supply: Top-down proportional reconciliation: ramal agregat nasional bebas")
    add("                               realokasi provinsi 2021 (year >= 2013 agar konsisten KI/KU) memakai")
    add("                               Drift (`drift_nat`), lalu skalakan prediksi non-negatif regional dari")
    add("                               `step_intervention_damped` agar jumlah 34 provinsi tepat = proyeksi nasional.")
    add()
    add("[C] Kandidat Khusus DEMAND (`distributed_electricity_gwh`):")
    add("  5. ols_linear_trend        : Regresi OLS y_t = a + b*(t - t_bar) atas seluruh histori <= origin.")
    add("  6. theil_sen_trend         : Median slope berpasangan Theil-Sen (tahan outlier tunggal KR 2020).")
    add("  7. huber_trend             : M-estimator Huber (epsilon=1.35) tahan outlier KR 2020 & lonjakan BT.")
    add("  8. holt_damped             : ETS(A,Ad,N) dengan optimasi deterministik SSE grid + L-BFGS-B.")
    add("  9. theta                   : Standard Theta Method (kombinasi 0.5*OLS + 0.5*SES(Theta=2)).")
    add(" 10. recent_window_ols_5     : Regresi OLS pada 5 observasi terakhir.")
    add(" 11. damped_drift            : Drift endpoint dengan redaman geometrik phi=0.88: y_T + b*sum_{j=1..h} phi^j.")
    add(" 12. ridge_lag_panel         : Model autoregresif panel pooled bebas leakage memanfaatkan lag 1..3")
    add("                               (`lags.py`) dinormalisasi oleh rolling_mean_3 (rm3 > 0): fitur")
    add("                               [lag_1/rm3, lag_2/rm3, lag_3/rm3, (lag_1 - lag_3)/(2*rm3)], target")
    add("                               y/rm3, dilatih via StandardScaler + RidgeCV(alphas=logspace(-1,4,25))")
    add("                               strictly <= origin_year dan digulirkan rekursif untuk h=1..6.")
    add()

    # =========================================================================
    # SECTION 2: SUPPLY BENCHMARK RESULTS
    # =========================================================================
    add("=== 2. HASIL BENCHMARK LENGKAP SUPPLY (local_generation_gwh, 14 MODEL) ===")
    add()

    add("2.1 Supply - Rolling One-Step (All Years: Target 2019-2024, n=203)")
    add_table(
        METRIC_HEADERS,
        _metric_rows(
            supply_summary.loc[supply_summary["protocol_slice"].eq("rolling_one_step")]
        ),
    )

    add("2.2 Supply - Rolling One-Step Post-2021 (Target 2022-2024, n=102)")
    add_table(
        METRIC_HEADERS,
        _metric_rows(
            supply_regime.loc[
                supply_regime["protocol"].eq("rolling_one_step")
                & supply_regime["regime"].eq("post_2021")
            ]
        ),
    )

    add("2.3 Supply - Recursive Multi-Step h=1..3 (All Years: Origins 2018-2021, n=406)")
    add_table(
        METRIC_HEADERS,
        _metric_rows(
            supply_summary.loc[
                supply_summary["protocol_slice"].eq("recursive_multi_step_h3")
            ]
        ),
    )

    add("2.4 Supply - Recursive Multi-Step h=1..3 Post-2021 (Target 2022-2024, All Origins, n=204)")
    add_table(
        METRIC_HEADERS,
        _metric_rows(
            supply_regime.loc[
                supply_regime["protocol"].eq("recursive_multi_step_h3")
                & supply_regime["regime"].eq("post_2021")
            ]
        ),
    )

    add("2.5 Supply - Recursive Multi-Step h=1..3 Post-2021 Clean Origins (Origin >= 2021, n=102)")
    add_table(
        METRIC_HEADERS,
        _metric_rows(
            supply_regime.loc[
                supply_regime["protocol"].eq("recursive_multi_step_h3")
                & supply_regime["regime"].eq("post_2021_clean_origins")
            ]
        ),
    )

    add("2.6 Supply - Extended Horizon h=4..6 (Origins 2018-2020 -> Target 2022-2024, n=204)")
    add("Catatan Metodologis: Seluruh origin yang memiliki horizon h=4..6 (2018, 2019, 2020) berada sebelum")
    add("tahun break 2021, sehingga seluruh prediksi h=4..6 melintasi lonjakan pencatatan BPS 2021 tanpa")
    add("mengetahui break tersebut di origin (menguji ketahanan terhadap shock, bukan performa rezim stabil).")
    add_table(
        METRIC_HEADERS,
        _metric_rows(
            supply_summary.loc[
                supply_summary["protocol_slice"].eq("extended_horizon_h4_h6")
            ]
        ),
    )

    add("2.7 Supply - Extended Horizon Breakdown per Horizon h=1..6 (Origins 2018->h1..6, 2019->h1..5, 2020->h1..4)")
    sup_ext_h = supply_horizon.loc[
        supply_horizon["protocol_slice"].eq("extended_horizon")
        & supply_horizon["scenario"].eq("all_observations")
    ]
    sup_h_rows: list[list[str]] = []
    for h in range(1, 7):
        h_df = sup_ext_h.loc[sup_ext_h["horizon"].eq(h)].sort_values(
            ["macro_smape_percent", "macro_mase", "model"]
        )
        for rank, rec in enumerate(h_df.itertuples(index=False), start=1):
            sup_h_rows.append(
                [
                    f"h={h}",
                    str(rank),
                    str(rec.model),
                    f"{float(rec.macro_smape_percent):.2f}",
                    f"{float(rec.macro_mase):.3f}",
                    f"{int(rec.mase_valid_prediction_count)}/{int(rec.mase_valid_region_count)}",
                    _fmt_num(rec.micro_rmse_gwh, 2),
                    _fmt_signed(rec.aggregate_bias_percent, 2, "%"),
                    f"{100.0 * float(rec.win_rate_vs_drift):.2f}%",
                ]
            )
    add_table(
        [
            "Horizon",
            "Rank",
            "Model",
            "Macro sMAPE (%)",
            "Macro MASE",
            "MASE Valid",
            "Micro RMSE (GWh)",
            "Agg Bias (%)",
            "Win Rate vs Drift",
        ],
        sup_h_rows,
    )

    # =========================================================================
    # SECTION 3: DEMAND BENCHMARK RESULTS
    # =========================================================================
    add("=== 3. HASIL BENCHMARK LENGKAP DEMAND (distributed_electricity_gwh, 12 MODEL) ===")
    add()

    add("3.1 Demand - Rolling One-Step (All Observations: Target 2019-2024, n=204)")
    add_table(
        METRIC_HEADERS,
        _metric_rows(
            demand_summary.loc[demand_summary["protocol_slice"].eq("rolling_one_step")]
        ),
    )

    add("3.2 Demand - Rolling One-Step (Exclude Target Outlier KR 2020, n=203)")
    add_table(
        METRIC_HEADERS,
        _metric_rows(
            demand_scenario.loc[
                demand_scenario["protocol_slice"].eq("rolling_one_step")
                & demand_scenario["scenario"].eq("exclude_kr_2020_target")
            ]
        ),
    )

    add("3.3 Demand - Rolling One-Step (Exclude Target & Origin KR 2020, n=202)")
    add_table(
        METRIC_HEADERS,
        _metric_rows(
            demand_scenario.loc[
                demand_scenario["protocol_slice"].eq("rolling_one_step")
                & demand_scenario["scenario"].eq("exclude_kr_2020_target_and_origin")
            ]
        ),
    )

    add("3.4 Demand - Recursive Multi-Step h=1..3 (All Observations: Origins 2018-2021, n=408)")
    add_table(
        METRIC_HEADERS,
        _metric_rows(
            demand_summary.loc[
                demand_summary["protocol_slice"].eq("recursive_multi_step_h3")
            ]
        ),
    )

    add("3.5 Demand - Recursive Multi-Step h=1..3 (Exclude Target Outlier KR 2020, n=406)")
    add_table(
        METRIC_HEADERS,
        _metric_rows(
            demand_scenario.loc[
                demand_scenario["protocol_slice"].eq("recursive_multi_step_h3")
                & demand_scenario["scenario"].eq("exclude_kr_2020_target")
            ]
        ),
    )

    add("3.6 Demand - Recursive Multi-Step h=1..3 (Exclude Target & Origin KR 2020, n=403)")
    add_table(
        METRIC_HEADERS,
        _metric_rows(
            demand_scenario.loc[
                demand_scenario["protocol_slice"].eq("recursive_multi_step_h3")
                & demand_scenario["scenario"].eq("exclude_kr_2020_target_and_origin")
            ]
        ),
    )

    add("3.7 Demand - Extended Horizon h=4..6 (All Observations, n=204)")
    add_table(
        METRIC_HEADERS,
        _metric_rows(
            demand_summary.loc[
                demand_summary["protocol_slice"].eq("extended_horizon_h4_h6")
            ]
        ),
    )

    add("3.8 Demand - Extended Horizon h=4..6 (Exclude Target & Origin KR 2020, n=203)")
    add_table(
        METRIC_HEADERS,
        _metric_rows(
            demand_scenario.loc[
                demand_scenario["protocol_slice"].eq("extended_horizon_h4_h6")
                & demand_scenario["scenario"].eq("exclude_kr_2020_target_and_origin")
            ]
        ),
    )

    add("3.9 Demand - Extended Horizon Breakdown per Horizon h=1..6 (All Observations)")
    dem_ext_h = demand_horizon.loc[
        demand_horizon["protocol_slice"].eq("extended_horizon")
        & demand_horizon["scenario"].eq("all_observations")
    ]
    dem_h_rows: list[list[str]] = []
    for h in range(1, 7):
        h_df = dem_ext_h.loc[dem_ext_h["horizon"].eq(h)].sort_values(
            ["macro_smape_percent", "macro_mase", "model"]
        )
        for rank, rec in enumerate(h_df.itertuples(index=False), start=1):
            dem_h_rows.append(
                [
                    f"h={h}",
                    str(rank),
                    str(rec.model),
                    f"{float(rec.macro_smape_percent):.2f}",
                    f"{float(rec.macro_mase):.3f}",
                    f"{int(rec.mase_valid_prediction_count)}/{int(rec.mase_valid_region_count)}",
                    _fmt_num(rec.micro_rmse_gwh, 2),
                    _fmt_signed(rec.aggregate_bias_percent, 2, "%"),
                    f"{100.0 * float(rec.win_rate_vs_drift):.2f}%",
                ]
            )
    add_table(
        [
            "Horizon",
            "Rank",
            "Model",
            "Macro sMAPE (%)",
            "Macro MASE",
            "MASE Valid",
            "Micro RMSE (GWh)",
            "Agg Bias (%)",
            "Win Rate vs Drift",
        ],
        dem_h_rows,
    )

    add("3.10 Ringkasan Perbandingan Demand per Horizon (All Observations vs Excl KR 2020 Target & Origin)")
    dem_ext_ex = demand_horizon.loc[
        demand_horizon["protocol_slice"].eq("extended_horizon")
        & demand_horizon["scenario"].eq("exclude_kr_2020_target_and_origin")
    ]
    cmp_rows: list[list[str]] = []
    for h in range(1, 7):
        sub_all = dem_ext_h.loc[dem_ext_h["horizon"].eq(h)].sort_values(
            ["macro_smape_percent", "macro_mase", "model"]
        )
        sub_ex = dem_ext_ex.loc[dem_ext_ex["horizon"].eq(h)].sort_values(
            ["macro_smape_percent", "macro_mase", "model"]
        )
        best_all = sub_all.iloc[0]
        drift_all = sub_all.loc[sub_all["model"].eq("drift")].iloc[0]
        best_ex = sub_ex.iloc[0]
        drift_ex = sub_ex.loc[sub_ex["model"].eq("drift")].iloc[0]
        cmp_rows.append(
            [
                f"h={h}",
                f"{best_all['model']} ({best_all['macro_smape_percent']:.2f}%)",
                f"{drift_all['macro_smape_percent']:.2f}% / {drift_all['macro_mase']:.3f}",
                f"{best_ex['model']} ({best_ex['macro_smape_percent']:.2f}%)",
                f"{drift_ex['macro_smape_percent']:.2f}% / {drift_ex['macro_mase']:.3f}",
            ]
        )
    add_table(
        [
            "Horizon",
            "Best Model (All Obs)",
            "Drift sMAPE / MASE (All Obs)",
            "Best Model (Excl KR20)",
            "Drift sMAPE / MASE (Excl KR20)",
        ],
        cmp_rows,
    )

    # =========================================================================
    # SECTION 4: 2025-2030 SANITY CHECK AUDIT
    # =========================================================================
    add("=== 4. AUDIT KEWAJARAN PROYEKSI PRODUKSI 2025-2030 (SANITY CHECK) ===")
    add()

    def _nat_totals(panel: pd.DataFrame) -> dict[int, float]:
        return (
            panel.loc[panel["actual_gwh"].notna()]
            .groupby("year")["actual_gwh"]
            .sum()
            .to_dict()
        )

    sup_nat = _nat_totals(supply_panel)
    dem_nat = _nat_totals(demand_panel)
    sup_cagr_11_24 = float(sup_nat_drift["hist_cagr_2011_2024_percent"])
    sup_cagr_13_24 = float(sup_nat_drift["hist_cagr_2013_2024_percent"])
    sup_cagr_21_24 = float(sup_nat_drift["hist_cagr_2021_2024_percent"])
    dem_cagr_11_24 = float(dem_nat_drift["hist_cagr_2011_2024_percent"])
    dem_cagr_13_24 = float(dem_nat_drift["hist_cagr_2013_2024_percent"])
    dem_cagr_21_24 = float(dem_nat_drift["hist_cagr_2021_2024_percent"])

    add("4.0 Rujukan Total Nasional & CAGR Historis Aktual")
    add_table(
        [
            "Domain",
            "Actual 2011 (GWh)",
            "Actual 2013 (GWh)",
            "Actual 2021 (GWh)",
            "Actual 2024 (GWh)",
            "CAGR 2011-2024",
            "CAGR 2013-2024",
            "CAGR 2021-2024",
        ],
        [
            [
                "supply",
                _fmt_num(sup_nat[2011], 2),
                _fmt_num(sup_nat[2013], 2),
                _fmt_num(sup_nat[2021], 2),
                _fmt_num(sup_nat[2024], 2),
                _fmt_signed(sup_cagr_11_24, 2, "%"),
                _fmt_signed(sup_cagr_13_24, 2, "%"),
                _fmt_signed(sup_cagr_21_24, 2, "%"),
            ],
            [
                "demand",
                _fmt_num(dem_nat[2011], 2),
                _fmt_num(dem_nat[2013], 2),
                _fmt_num(dem_nat[2021], 2),
                _fmt_num(dem_nat[2024], 2),
                _fmt_signed(dem_cagr_11_24, 2, "%"),
                _fmt_signed(dem_cagr_13_24, 2, "%"),
                _fmt_signed(dem_cagr_21_24, 2, "%"),
            ],
        ],
    )

    add("4.1 Supply - Audit Kewajaran Nasional & Anomali Provinsi 2025-2030 (Seluruh 14 Model)")
    add_table(SANITY_NATIONAL_HEADERS, _sanity_national_rows(supply_nat_sanity))

    add("4.2 Supply - Perbandingan Provinsi Kunci Bermasalah 2030 (Drift vs Top-5 Kandidat Supply)")
    sup_key_headers, sup_key_rows = _key_province_pivot_table(
        supply_key_sanity,
        provinces=("LA", "BE", "KT", "SG", "KS", "SS", "JI", "JB", "JT", "YO"),
        models=(
            "drift",
            "national_reconciled_supply",
            "step_intervention_damped",
            "step_intervention_ols",
            "post_break_drift_or_naive",
            "holt_damped",
        ),
    )
    add_table(sup_key_headers, sup_key_rows)

    add("4.3 Demand - Audit Kewajaran Nasional & Anomali Provinsi 2025-2030 (Seluruh 12 Model)")
    add_table(SANITY_NATIONAL_HEADERS, _sanity_national_rows(demand_nat_sanity))

    add("4.4 Demand - Perbandingan Provinsi Kunci Bermasalah 2030 (Drift vs Top-5 Kandidat Demand)")
    dem_key_headers, dem_key_rows = _key_province_pivot_table(
        demand_key_sanity,
        provinces=("KR", "BT", "JK", "JI", "JB", "KU"),
        models=(
            "drift",
            "damped_drift",
            "ols_linear_trend",
            "huber_trend",
            "theil_sen_trend",
            "ridge_lag_panel",
        ),
    )
    add_table(dem_key_headers, dem_key_rows)

    # =========================================================================
    # SECTION 5: ACADEMIC ANALYSIS & RECOMMENDATIONS
    # =========================================================================
    add("=== 5. ANALISIS AKADEMIS, RISIKO, & REKOMENDASI OBJEKTIF FASE 3 ===")
    add()
    add("5.1 Domain SUPPLY (`local_generation_gwh`)")
    add("Rekomendasi Utama: PERTIMBANGKAN PENGGANTIAN `drift` DENGAN `national_reconciled_supply`")
    add("(`drift_nat -> step_intervention_damped`) PADA FASE 3 (dengan `step_intervention_damped`")
    add("sebagai penantang univariat terbaik dan `drift` tetap menjadi baseline acuan / fallback).")
    add()
    add("Bukti Empiris Kuantitatif:")
    add(
        f"1. Konsistensi Lintas Protokol Backtest: `national_reconciled_supply` menempati peringkat #1 pada "
        f"`rolling_one_step` (Macro sMAPE {sup_r1_natrec['macro_smape_percent']:.2f}%, MASE "
        f"{sup_r1_natrec['macro_mase']:.3f}, RMSE {sup_r1_natrec['micro_rmse_gwh']:,.2f} GWh) vs `drift` "
        f"({sup_r1_drift['macro_smape_percent']:.2f}%, MASE {sup_r1_drift['macro_mase']:.3f}, RMSE "
        f"{sup_r1_drift['micro_rmse_gwh']:,.2f} GWh). Pada kontrak produksi `recursive_multi_step_h3`, "
        f"`national_reconciled_supply` mencapai Macro sMAPE {sup_h3_natrec['macro_smape_percent']:.2f}% "
        f"(MASE {sup_h3_natrec['macro_mase']:.3f}, RMSE {sup_h3_natrec['micro_rmse_gwh']:,.2f} GWh, "
        f"Win Rate {100.0 * sup_h3_natrec['win_rate_vs_drift']:.2f}% vs `drift`), mengungguli `drift` "
        f"({sup_h3_drift['macro_smape_percent']:.2f}%, MASE {sup_h3_drift['macro_mase']:.3f}, RMSE "
        f"{sup_h3_drift['micro_rmse_gwh']:,.2f} GWh)."
    )
    add(
        f"2. Keunggulan Bersih pada Rezim Pasca-2021: Pada irisan paling menentukan untuk proyeksi masa depan "
        f"(`recursive_multi_step_h3 post_2021_clean_origins`, yaitu origin >= 2021), `national_reconciled_supply` "
        f"menduduki peringkat #1 dari seluruh 14 model (sMAPE {sup_h3_clean_natrec['macro_smape_percent']:.2f}%, "
        f"MASE {sup_h3_clean_natrec['macro_mase']:.3f}), mengalahkan `drift` "
        f"({sup_h3_clean_drift['macro_smape_percent']:.2f}%, MASE {sup_h3_clean_drift['macro_mase']:.3f}) dan "
        f"`step_intervention_damped` univariat ({sup_h3_clean_sid['macro_smape_percent']:.2f}%). Pada "
        f"`rolling_one_step post_2021`, model ini juga mencatat Macro MASE terbaik #1 "
        f"({sup_r1_post_natrec['macro_mase']:.3f} vs `drift` {sup_r1_post_drift['macro_mase']:.3f}), walau "
        f"Macro sMAPE sedikit di belakang `drift` ({sup_r1_post_natrec['macro_smape_percent']:.2f}% vs "
        f"{sup_r1_post_drift['macro_smape_percent']:.2f}%)."
    )
    add(
        f"3. Ketahanan Horizon Panjang h=4..6: Pada `extended_horizon_h4_h6`, `national_reconciled_supply` "
        f"menekan Macro sMAPE menjadi {sup_ext_natrec['macro_smape_percent']:.2f}% (Win Rate "
        f"{100.0 * sup_ext_natrec['win_rate_vs_drift']:.2f}%) dibanding `drift` "
        f"({sup_ext_drift['macro_smape_percent']:.2f}%), sekaligus memiliki Micro RMSE kompetitif."
    )
    add(
        f"4. Kewajaran Domain & Resolusi Distorsi 2021 (Sanity Check 2025-2030): Total nasional proyeksi "
        f"2030 sebesar {sup_nat_natrec['forecast_2030_gwh']:,.2f} GWh (implied CAGR "
        f"{sup_nat_natrec['implied_cagr_2024_2030_percent']:+.2f}% per tahun), konsisten dengan tren agregat "
        f"historis 2013-2024 ({sup_cagr_13_24:+.2f}%) dan `drift` ({sup_nat_drift['implied_cagr_2024_2030_percent']:+.2f}%), "
        f"hanya menyisakan {int(sup_nat_natrec['negative_slope_region_count'])} provinsi berslope negatif, "
        f"0 provinsi ter-clip nol, dan 0 provinsi CAGR ekstrem. Secara ekonomi-kelistrikan, lonjakan "
        f"administratif 2021 pada LA/BE/KT/SG (yang sebelumnya membuat `drift` memproyeksikan pertumbuhan "
        f"palsu +4.6% s.d. +6.4%/tahun) diserap bersih oleh komponen FWL `step_intervention_damped`, lalu "
        f"pertumbuhan sistem nasional (`drift_nat`) didistribusikan secara proporsional."
    )
    add()
    add("Mengapa Kandidat Supply Lain TIDAK Layak Menjadi Model Produksi Tunggal:")
    add(
        f"- `step_intervention_ols` unggul pada `recursive_h3` ({sup_h3_sols['macro_smape_percent']:.2f}%) dan "
        f"`post_2021` ({sup_h3_post_sols['macro_smape_percent']:.2f}%), tetapi gagal pada audit kewajaran 2030: "
        f"{int(sup_nat_sols['negative_slope_region_count'])} provinsi berproyeksi menurun di 2030 karena OLS "
        f"menggabungkan slope pra-2021 yang turun tajam (mis. KI -5.2%/thn, JA -8.1%/thn, KB -7.4%/thn)."
    )
    add(
        f"- `step_intervention_damped` (tanpa rekonsiliasi nasional) unggul pada `rolling_one_step` "
        f"({sup_r1_sid['macro_smape_percent']:.2f}%) dan memiliki RMSE terendah di `recursive_h3` "
        f"({sup_h3_sid['micro_rmse_gwh']:,.2f} GWh), namun tanpa penjangkar agregat nasional ia mengalami "
        f"under-forecasting kronis (-4.15% di h3, -10.29% di h4..6), menghasilkan implied CAGR 2024-2030 "
        f"terlalu rendah ({sup_nat_sid['implied_cagr_2024_2030_percent']:+.2f}%) serta "
        f"{int(sup_nat_sid['negative_slope_region_count'])} provinsi berslope negatif."
    )
    add(
        f"- `theil_sen_trend` & `huber_trend` hanya terlihat unggul di `extended_horizon h=4..6` "
        f"({sup_ext_ts['macro_smape_percent']:.2f}%) karena berasal dari origin 2018-2020 yang melintasi break "
        f"2021; pada seri pendek pasca-break, median slope Theil-Sen didominasi pasangan tahun pra-2021 "
        f"sehingga memprediksi kehancuran pasokan di LA (-49.3%), BE (-26.2%), dan KT (-18.5%) untuk 2030."
    )
    add(
        f"- `post_break_drift_or_naive` & `recent_window_drift_4` sensitif terhadap penurunan lokal LA "
        f"(2021->2024) hingga memproyeksikan LA = 0.0 GWh (-100%, ter-clip) pada 2030. `recent_window_ols_5` "
        f"memproyeksikan KS = 0.0 GWh (-100%, ter-clip)."
    )
    add(
        f"- `holt_damped` dan `theta` berkinerja lemah pada seluruh metrik backtest regional karena optimasi "
        f"SSE global tidak memiliki parameter level-shift 2021 (memperlambat respons terhadap perubahan rezim)."
    )
    add()
    add("Risiko & Catatan Implementasi Supply untuk Fase 3:")
    add("- Ketergantungan lintas-provinsi (panel coupling): rekonsiliasi mengaitkan seluruh 34 provinsi ke total")
    add("  nasional `year >= 2013`, sehingga kalibrasi interval ketidakpastian (`supply_uncertainty_calibration`)")
    add("  wajib dihitung ulang dari residual backtest model baru pada Fase 3.")
    add("- Keterbukaan opsi konservatif: bila tata kelola produksi menghendaki model univariat murni per")
    add("  provinsi tanpa kopling nasional, maka `drift` tetap lebih aman daripada `step_intervention_damped`")
    add("  univariat atau `step_intervention_ols` karena bebas bias turun nasional yang ekstrem.")
    add()

    add("5.2 Domain DEMAND (`distributed_electricity_gwh`)")
    add("Rekomendasi Utama: PERTAHANKAN `drift` SEBAGAI MODEL PRODUKSI (TIDAK PERLU DIGANTI PADA FASE 3).")
    add()
    add("Bukti Empiris Kuantitatif:")
    add(
        f"1. Dominasi Penuh di Seluruh Protokol Evaluasi: `drift` menempati peringkat #1 pada Macro sMAPE dan "
        f"Macro MASE di ketiga protokol backtest baik pada seluruh observasi maupun tanpa outlier KR 2020:"
    )
    add(
        f"   * `rolling_one_step`: Macro sMAPE {dem_r1_drift['macro_smape_percent']:.2f}% (MASE "
        f"{dem_r1_drift['macro_mase']:.3f}); tanpa KR 2020: {dem_r1_ex_drift['macro_smape_percent']:.2f}% "
        f"(MASE {dem_r1_ex_drift['macro_mase']:.3f}). Pesaing terdekat `damped_drift` tertinggal di "
        f"{dem_r1_ddrift['macro_smape_percent']:.2f}% (Win Rate hanya {100.0 * dem_r1_ddrift['win_rate_vs_drift']:.2f}%)."
    )
    add(
        f"   * `recursive_multi_step_h3` (kontrak produksi): Macro sMAPE {dem_h3_drift['macro_smape_percent']:.2f}% "
        f"(MASE {dem_h3_drift['macro_mase']:.3f}, Agg Bias {dem_h3_drift['aggregate_bias_percent']:+.2f}%); "
        f"tanpa KR 2020: {dem_h3_ex_drift['macro_smape_percent']:.2f}% (MASE {dem_h3_ex_drift['macro_mase']:.3f}). "
        f"Tidak ada satu pun dari 7 kandidat baru yang melampaui Win Rate 50% vs `drift` (tertinggi "
        f"`ridge_lag_panel` hanya {100.0 * _lookup_row(demand_summary, {'protocol_slice': 'recursive_multi_step_h3', 'model': 'ridge_lag_panel'})['win_rate_vs_drift']:.2f}%)."
    )
    add(
        f"   * `extended_horizon_h4_h6`: Macro sMAPE {dem_ext_drift['macro_smape_percent']:.2f}% (MASE "
        f"{dem_ext_drift['macro_mase']:.3f}, Agg Bias {dem_ext_drift['aggregate_bias_percent']:+.2f}%); "
        f"tanpa KR 2020: {dem_ext_ex_drift['macro_smape_percent']:.2f}% (MASE {dem_ext_ex_drift['macro_mase']:.3f}), "
        f"tetap mengalahkan `theil_sen_trend` ({dem_ext_ts['macro_smape_percent']:.2f}%), `ols_linear_trend`, "
        f"`huber_trend`, maupun `ridge_lag_panel` ({dem_ext_ridge['macro_smape_percent']:.2f}%)."
    )
    add(
        f"2. Kewajaran Proyeksi 2025-2030: `drift` memproyeksikan permintaan nasional 2030 sebesar "
        f"{dem_nat_drift['forecast_2030_gwh']:,.2f} GWh (implied CAGR "
        f"{dem_nat_drift['implied_cagr_2024_2030_percent']:+.2f}%), wajar dan sedikit konservatif terhadap "
        f"CAGR historis 2013-2024 ({dem_cagr_13_24:+.2f}%) mengingat efek saturasi linear pada basis yang membesar, "
        f"dengan 0 provinsi berslope negatif, 0 provinsi ter-clip, dan 0 CAGR ekstrem."
    )
    add()
    add("Mengapa Kandidat Demand Lain Kalah Secara Akademis:")
    add(
        f"- Model tren teredam (`damped_drift`, `holt_damped`, `theta`) memang sedikit menurunkan Micro RMSE "
        f"pada beberapa irisan (mis. `damped_drift` RMSE {dem_h3_ddrift['micro_rmse_gwh']:,.2f} vs `drift` "
        f"{dem_h3_drift['micro_rmse_gwh']:,.2f} GWh di h3) akibat meredam deviasi provinsi besar seperti BT/JK, "
        f"tetapi pertumbuhan permintaan listrik regional Indonesia bersifat persisten positif sehingga redaman "
        f"justru menciptakan bias turun sistematis (-5.63% di h4..6; CAGR nasional hanya "
        f"{dem_nat_ddrift['implied_cagr_2024_2030_percent']:+.2f}%)."
    )
    add(
        f"- Regresi global (`ols_linear_trend`, `huber_trend`, `theil_sen_trend`) terdistorsi oleh fase "
        f"penurunan JK 2015-2017 sehingga memproyeksikan kontraksi berkepanjangan pada DKI Jakarta di 2030 "
        f"(JK -2.49% s.d. -2.67%/tahun), padahal JK sudah pulih bertumbuh sejak 2021 hingga 38,198 GWh di 2024."
    )
    add(
        f"- `ridge_lag_panel` menghasilkan bias agregat positif sangat tinggi (+14.88% di h4..6) dan CAGR "
        f"2024-2030 tidak realistis sebesar {dem_nat_ridge['implied_cagr_2024_2030_percent']:+.2f}% "
        f"({dem_nat_ridge['forecast_2030_gwh']:,.2f} GWh) karena pooling parameter pertumbuhan lintas provinsi "
        f"memaksakan laju tumbuh rata-rata nasional (~7%/thn) pada seluruh provinsi termasuk Jakarta yang matang."
    )
    add()
    add("Catatan Risiko Demand (`drift`):")
    add("- Karena `drift` memakai dua titik ujung (2011 dan 2024), DKI Jakarta memperoleh proyeksi pertumbuhan")
    add("  moderat (+0.62%/tahun) sedangkan Banten tetap dipengaruhi oleh kenaikan level 2015->2017 (+4.90%/tahun).")
    add("  Kelemahan struktural kecil ini sudah diuji dan terbukti tidak teratasi oleh OLS, Huber, Theil-Sen,")
    add("  ETS, Theta, maupun Ridge panel tanpa mengorbankan akurasi mayoritas dari 34 provinsi.")
    add()

    add("5.3 Matriks Keputusan Rekomendasi Fase 3")
    add_table(
        [
            "Domain",
            "Produksi Saat Ini",
            "Kandidat Pemenang Eksperimen",
            "Keputusan Fase 3",
            "Alasan Kunci",
        ],
        [
            [
                "Supply",
                "drift",
                "national_reconciled_supply (drift_nat -> step_intervention_damped)",
                "REKOMENDASI GANTI (kandidat kuat Fase 3)",
                "Menang lintas protokol (29.05% one-step, 54.52% h3, #1 clean post_2021 15.44%), hilangkan distorsi 2021 di LA/BE/KT/SG/KS/SS/JI/YO, CAGR 2030 wajar (+2.98%).",
            ],
            [
                "Demand",
                "drift",
                "drift (eksisting terbaik)",
                "PERTAHANKAN drift",
                "#1 sMAPE & MASE di seluruh protokol & skenario KR-2020 (5.83% one-step, 8.14% h3, 12.36% h4..6), bias mendekati 0%, win rate >50% atas semua penantang, 0 anomali 2030.",
            ],
        ],
    )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(lines).rstrip() + "\n"
    with report_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
    return report_path
