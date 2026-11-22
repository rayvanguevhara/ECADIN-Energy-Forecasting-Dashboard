# ADR-001: Pembekuan Snapshot CSV BPS 2011–2024, Bukti Primer Regime Shifts, dan Konvensi Semantik Data

- **Status:** Accepted (Frozen untuk Produksi Batch 1 & Laporan Kerja Praktik)
- **Tanggal Keputusan:** 2026-11-22
- **Konteks Audit:** Temuan `F1-01` s.d. `F1-05`, `F1-09`, dan `F1-12` pada `outputs/reports/phase1_data_processing_review.txt`
- **Artefak Rujukan:** `outputs/reports/data/statistik_listrik_reconciliation.csv`, `outputs/reports/data/statistik_listrik_national_totals.csv`, `data/processed/master/regional_energy_master.csv`, `data/processed/master/data_quality_flags.csv`

---

## 1. Keputusan Resmi: Pembekuan Snapshot CSV BPS 2011–2024 (`F1-12`)

Proyek ECADIN menetapkan bahwa dataset kanonis historis `2011–2024` pada `data/processed/master/regional_energy_master.csv` (`476` baris = `34` provinsi model × `14` tahun) **dibekukan (frozen) secara persis sesuai snapshot file CSV BPS pada `data/raw/bps/`** tanpa penambalan retrospektif otomatis dari publikasi PDF `statistik-listrik-2020-2024.pdf`.

### Landasan Teknis & Statistik Keputusan
1. **Keselarasan Total Target Utama Pasca-2021 (`100% Exact Match`):**
   - `distributed_electricity_gwh` (`2020–2024`): **170 / 170** perbandingan sel regional berstatus `exact_match` terhadap `statistik-listrik-2020-2024.pdf` hal. 60. Seluruh angka jangkar (anchor) peramalan demand `2024` dan histori anomali (`KR` 2020 = `887,60 GWh`) identik 100%.
   - `local_generation_gwh` (`2021–2024`): **136 / 136** perbandingan sel regional berstatus `exact_match` terhadap `statistik-listrik-2020-2024.pdf` hal. 42, termasuk seluruh provinsi pasca-pergeseran rezim 2021 (`LA 5.436,19`, `KT 2.631,62`, `SG 1.181,79`, `BE 2.689,06`, `SR 249,45`) serta agregasi DOB Papua 2023–2024 ke `PA` dan `PB`. Titik jangkar produksi supply tahun `2024` maupun jendela pasca-2021 (`2021–2024`) sudah 100% mutakhir terhadap PDF BPS terbaru.
   - `installed_capacity_mw`: Tidak dipakai sebagai input fitur maupun target pada model produksi forecasting saat ini (`demand_production_drift` & `supply_production_drift_v1`), melainkan sebagai seri pendukung/audit fisik.
2. **Inventaris Lengkap Sel Non-Identik pada Audit PDF `2020–2024` (`510` Sel = `478` `exact_match` + `30` `revision_candidate` + `2` `canonical_missing_pdf_zero`):**
   - **Kelompok A — `22` sel `revision_candidate` pada `installed_capacity_mw` tahun `2021`** (`statistik-listrik-2020-2024.pdf` hal. 31 vs `statistik-listrik-2017-2021.pdf` hal. 28; selisih bersih nasional PDF − Kanonis = **`+6.379,29 MW`**, yakni `72.893,60 MW` vs `66.514,31 MW`):
     - Penggerak utama: `JT` (`+4.763,18 MW`: `13.527,22` vs `8.764,04`), `JB` (`+1.077,72 MW`: `10.156,72` vs `9.079,00`), `KB` (`+177,91 MW`: `987,14` vs `809,23`), `KR` (`+146,05 MW`: `903,48` vs `757,43`), `RI` (`+128,95 MW`: `1.558,81` vs `1.429,86`), `MA` (`+60,00 MW`: `450,74` vs `390,74`), `KT` (`+22,39 MW`: `640,07` vs `617,68`), `ST` (`+13,43 MW`: `663,19` vs `649,76`).
     - Revisi minor (< `10 MW`): `GO` (`-9,20 MW`), `JK` (`-6,50 MW`), `JI` (`+6,50 MW`), `NT` (`+5,00 MW`), `KS` (`-4,93 MW`), `SA` (`-4,23 MW`), `SR` (`+2,77 MW`), `SS` (`+1,03 MW`), `SG` (`+1,00 MW`), `SN` (`-1,00 MW`), `SB` (`-0,50 MW`), `JA` (`-0,33 MW`), `NB` (`+0,25 MW`), `BE` (`-0,20 MW`).
   - **Kelompok B — `7` sel `revision_candidate` pada `local_generation_gwh` tahun `2020`** (`statistik-listrik-2020-2024.pdf` hal. 42; selisih bersih = **`+3.444,94 GWh`**):
     - `SU` (`+2.202,90 GWh`: `22.870,07` vs `20.667,17`), `SB` (`+2.168,48 GWh`: `3.117,40` vs `948,92`), `JK` (`-395,80 GWh`: `15.574,47` vs `15.970,27`), `JI` (`-232,66 GWh`: `57.313,52` vs `57.546,18`), `JT` (`-185,09 GWh`: `41.530,09` vs `41.715,18`), `BT` (`-110,00 GWh`: `44.375,27` vs `44.485,27`), `GO` (`-2,89 GWh`: `93,64` vs `96,53`).
   - **Kelompok C — `1` sel `revision_candidate` pada `installed_capacity_mw` tahun `2022`** (`statistik-listrik-2020-2024.pdf` hal. 31):
     - `PA` (`-0,03 MW`: `531,04` vs `531,07 MW`, perbedaan pembulatan 2 desimal).
   - **Kelompok D — `2` sel `canonical_missing_pdf_zero`** (`YO` tahun `2020`):
     - `local_generation_gwh` `YO 2020` (`""` kanonis vs `0,00 GWh` pada PDF hal. 42) dan `installed_capacity_mw` `YO 2020` (`""` kanonis vs `0,00 MW` pada PDF hal. 31) akibat konvensi `-` (CSV) vs `–` (PDF), lihat Bagian 3.
3. **Kebijakan Tata Kelola Pemutakhiran Masa Depan (Batch 2):**
   - Nilai master historis tidak boleh diubah secara parsial (*ad-hoc patching*) pada tabel kanonis. Jika revisi retrospektif `local_generation_gwh 2020` dan `installed_capacity_mw 2021` hendak diadopsi pada siklus berikutnya (Batch 2), pembaruan wajib dilakukan di folder `data/raw/bps/` berversi baru, diikuti eksekusi penuh `ecadin data build` -> `ecadin forecast build` -> `ecadin dashboard build` -> pembaruan hash SHA-256 kontrak.

---

## 2. Bukti Primer 5 Fakta Sumber BPS & Regime Shifts (`F1-01` s.d. `F1-05`)

Seluruh nilai mentah di `data/raw/bps/` diverifikasi 100% cocok (`0` kesalahan parsing `Decimal`, `0` kesalahan konversi satuan, `0` pergeseran baris/kolom). Anomali ekstrem antar-tahun adalah fakta sumber resmi BPS yang terbukti secara dokumenter:

### `F1-01` — Pergeseran Rezim Supply 2021 (`16` Provinsi Flag YoY + `SR` Zero-Base Jump)
1. **Catatan Kaki Publikasi BPS Pra-2021:** Dalam `statistik-listrik-2015-2020.pdf` hal. 24 (*Penjelasan Teknis*), hal. 28 (*Tabel Kapasitas Terpasang*), dan hal. 39 (*Tabel Tenaga Listrik yang Dibangkitkan*), BPS secara eksplisit mencantumkan keterangan:
   > *"Pembangkit PLN UIKL Kalimantan tercatat di Provinsi Kalimantan Selatan, PLN UIKL Sulawesi tercatat di Provinsi Sulawesi Selatan, PLN UIP Sumbagut tercatat di Provinsi Sumatera Utara, PLN UIK Sumbagsel tercatat di Provinsi Sumatera Selatan."*
   (Catatan kaki tersebut masih tersalin di `2017-2021.pdf` hal. 24 & `2018-2022.pdf` hal. 21, kemudian dihapus pada `2020-2024.pdf` hal. 26–27.)
2. **Perubahan Kuesioner Resmi STPL BPS Tahun 2021:**
   - `statistik-listrik-2015-2020.pdf` hal. 91 (*Blok III.301 Tahun 2020*): kolom lokasi pembangkit hanya mencatat **`Kab/Kota`**, dan kolom *Status Kepemilikan Pembangkit* hanya memuat **`1. Milik Sendiri  2. Sewa`**.
   - `statistik-listrik-2017-2021.pdf` hal. 92 (*Blok IV.401 Tahun 2021*): kolom `(3)` diperbarui menjadi **`Prov/Kab/Kota`**, dan kode kepemilikan ditambah menjadi **`1. Milik Sendiri  2. Sewa  3. IPP`**.
3. **Realokasi Zero-Sum Dominan Antarprovinsi (`2020 -> 2021`):** Total nasional `local_generation_gwh` hanya tumbuh wajar **`+7,70%`** (`275.599,80 -> 296.811,94 GWh`), dan `installed_capacity_mw` nasional hanya naik **`+1,96%`** (`65.235,80 -> 66.514,31 MW`). Namun di level provinsi, provinsi yang melonjak menyumbang `+50.231,02 GWh` (`+10.225,83 MW`), nyaris diimbangi penurunan `-29.022,20 GWh` (`-8.948,10 MW`) tepat pada provinsi kantor induk UIKL/UIK/UIP (`KS`, `SS`, `SU`, `SN`, `ST`, `JB`, `JI`).
4. **Verifikasi Silang Independen Terhadap Statistik Ketenagalistrikan ESDM (`2020–2021`, Tabel 4):**

| Provinsi | BPS Cap 2020 (MW) | BPS Cap 2021 (MW) | ESDM Tabel 4 2020 (MW) | ESDM Tabel 4 2021 (MW) | Interpretasi Cross-Check |
| :--- | ---: | ---: | ---: | ---: | :--- |
| Lampung (`LA`) | `237,96` | `1.087,92` | `1.106,97` | `1.107,13` | Pembangkit fisik ~1.107 MW sudah ada sejak 2020; BPS 2021 konvergen ke lokasi fisik |
| Bengkulu (`BE`) | `60,38` | `529,89` | `558,15` | `580,88` | Kapasitas fisik 2020 sudah ~558 MW; BPS 2021 pulih dari pencatatan UIK Sumbagsel |
| Kalimantan Tengah (`KT`) | `169,60` | `617,68` | `761,39` | `1.165,37` | Fisik 2020 sudah ~4,5× angka BPS 2020 akibat konsentrasi UIKL Kalimantan di `KS` |
| Sulawesi Tenggara (`SG`) | `131,89` | `405,70` | `602,60` | `649,91` | BPS 2021 mengejar pencatatan kapasitas fisik dan pembangkit IPP |
| Sulawesi Barat (`SR`) | `62,77` | `57,40` | `76,44` | `76,61` | Kapasitas terpasang stabil ~60 MW saat pencatatan pembangkitan bergeser `0 -> 249,45 GWh` |
| Kalimantan Selatan (`KS`) | `3.524,98` | `675,89` | `897,30` | `897,39` | BPS 2020 tercatat ~3,9× kapasitas fisik karena UIKL Kalimantan, lalu turun di 2021 |
| Sumatera Selatan (`SS`) | `4.345,22` | `2.286,43` | `2.273,84` | `2.372,45` | BPS 2020 ~1,9× fisik karena UIK Sumbagsel, lalu tepat cocok dengan ESDM di 2021 |
| Sulawesi Selatan (`SN`) | `3.020,37` | `1.874,20` | `2.339,28` | `2.440,10` | BPS 2020 melampaui kapasitas fisik karena UIKL Sulawesi, lalu turun mendekati ESDM di 2021 |

5. **Implikasi Modeling:** Rezim pra-2021 vs pasca-2021 distratifikasi eksplisit dalam diagnostik (`scripts/generate_evaluation_diagnostics.py` -> `supply_regime_stratification.csv`) dan kalibrasi ketidakpastian pasca-break (`src/ecadin_energy/forecasting/production/supply.py`).

### `F1-02` — Kontraksi Anomali Demand `KR` Tahun `2020` (`887,60 GWh`, `-73,48%`)
- Nilai `887,60 GWh` pada CSV mentah `distributed_electricity` 2020 baris `KEP. RIAU` identik 100% dengan publikasi PDF `statistik-listrik-2020-2024.pdf` hal. 60.
- **Bukti Silang Statistik Ketenagalistrikan ESDM:** Pada edisi ESDM `2020` (`ccf8b-8f7e7-20211110-statistik-2020-rev03.pdf`, Tabel 25 hal. 84–85), `UIW Riau & Kepri` terjual `5.854,65 GWh`, tepat sama dengan `RI (4.967,05) + KR (887,60) = 5.854,65 GWh`, sementara **`PT PLN Batam`** (`2.443,27 GWh`) dicatat pada baris terpisah dan tidak digabungkan ke Provinsi `KR` pada publikasi BPS 2020. Sebaliknya pada ESDM `2021` (`c4764-6e4c6-statistik-2021-rev-2-.pdf`, Tabel 24 hal. 88–89), `UIW Riau & Kepri (7.021,16) + PT PLN Batam (2.565,79) = 9.586,95 GWh` tepat sama dengan `RI (6.108,32) + KR (3.478,63) = 9.586,95 GWh`.

### `F1-03` — Pergeseran Batas `BT`/`JK` Demand & `JT`/`BT`/`JB`/`JK` Supply (`2015 -> 2017`)
- Pada `distributed_electricity`, `BT` melonjak `+13.982,43 GWh` sementara `JK` turun `-9.685,47 GWh` (`2015 -> 2017`) akibat reklasifikasi wilayah pelanggan PLN Distribusi Banten vs PLN Disjaya/Tangerang (`JK+BT` gabungan tumbuh normal `+8,61%` dalam 2 tahun).
- Pada `local_generation` & `installed_capacity`, `statistik-listrik-2012-2017.pdf` hal. 38 dan hal. 49 mencantumkan catatan kaki eksplisit `*)` pada `JK, JB, JT, BT`: **`*) 2017, Penyesuaian data lokasi pembangkit`** (hal. 38) dan **`*) 2017, Penyesuaian PT PJB`** (hal. 49).

### `F1-04` — Ketiadaan Publikasi Data Tahun `2016`
- Pada `statistik-listrik-2012-2017.pdf` hal. 38, 49, dan 67, kolom tabel resmi BPS melompat langsung dari `2015` ke `2017` (`2012 | 2013 | 2014 | 2015 | 2017`). Ketiadaan `2016` adalah kekosongan publikasi resmi BPS, sehingga wajib dipertahankan sebagai missing eksplisit (`missing_source_year`) tanpa interpolasi di master layer.

### `F1-05` — Kesalahan Ketik Baris Total `INDONESIA` di CSV Mentah BPS
- Ditemukan 4 selisih total nasional melebihi toleransi `0,10`: `local_generation` `2013` (`22206.93` vs jumlah provinsi `222206.92`, kurang digit `'2'`), `local_generation` `2014` (`-10,08 GWh`), `installed_capacity` `2013` (`-9,00 MW`), dan `installed_capacity` `2017` (`-1.270,42 MW`). Kebijakan cleaner untuk menghitung total nasional dari penjumlahan baris provinsi (`canonical_uses_sum_of_reported_province_values`) terbukti tepat dan dipertahankan.

---

## 3. Konvensi Semantik Tanda `-` (CSV) vs `–` (PDF) vs `...` (`F1-09`)

1. **Legenda Resmi Publikasi PDF BPS** (`statistik-listrik-2017-2021.pdf` hal. 15; `statistik-listrik-2020-2024.pdf` hal. 20):
   - Tanda **`–`** berarti *"Data dapat diabaikan / Tidak ada atau nol"* (`Decimal("0")`).
   - Tanda **`...`** (elipsis) berarti *"Data tidak tersedia / Belum tersedia"* (`missing`).
2. **Perbedaan di File CSV Web BPS vs Audit PDF:**
   - Pada ekspor CSV BPS (`data/raw/bps/{distributed_electricity,local_generation,installed_capacity}/`), BPS menggunakan tanda hubung ASCII `"-"` baik untuk entitas belum terbentuk (`KU` 2011–2012, 4 DOB Papua 2011–2022) maupun entri bernilai nol (`YO` `local_generation` 2011–2014 & 2020; `YO` `installed_capacity` 2017–2020), dan sesekali menulis `"0"` eksplisit (`YO` `local_generation` 2015, 2017–2019; `SR` 2020).
   - Di modul audit PDF (`src/ecadin_energy/data_processing/audit/statistik_listrik_bps.py`), parser menjaga semantik legenda PDF (`"..."`/`"…"` -> `None`, `"-"`/`"–"`/`"−"` -> `Decimal("0")`), sehingga pada tahun `2020` menghasilkan `2` sel `canonical_missing_pdf_zero` untuk `YO`.
   - Di modul cleaner (`src/ecadin_energy/data_processing/cleaning/annual_province_series.py`), konstanta `MISSING_VALUE_MARKERS = {"", "-", "–", "—", "...", "…"}` **sengaja mempertahankan perlakuan `"-"` -> missing eksplisit (`""`)** agar kontrak sel kosong pada master kanonis (`36` demand, `39` local generation, `38` installed capacity) tidak berubah retrospektif, sambil menambahkan dukungan standar BPS `"..."` / `"…"` untuk parser seri tambahan (mis. data penduduk DOB Papua 2023).
   - Selain itu, pada cleaner (`local_generation.py`, `installed_capacity.py`, `distributed_electricity.py`), lonjakan dari basis `"0.00"` seperti `SR 2021` (`0.00 -> 249.45 GWh`) kini ditandai secara eksplisit melalui flag `large_zero_base_jump` di `data_quality_flags.csv`.
