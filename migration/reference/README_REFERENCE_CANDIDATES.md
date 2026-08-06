# Reference Candidate Collection

Inventaris awal berisi 332 kandidat karena filter pencarian sengaja luas.
Paket ini menyaring 14 file yang perlu dibaca sebelum membentuk reference
layer final.

File yang dikumpulkan mencakup:

- empat geography mapping demand/supply;
- output map province canonical;
- metadata dan source registry dashboard;
- GeoJSON/polygon frontend;
- JSON production frontend;
- logika harmonisasi backend dan frontend.

## Penggunaan

Salin dua file berikut ke:

`D:\ECADIN_Project_Clean\migration\reference\`

- `ECADIN_reference_candidate_selection.csv`
- `collect_reference_candidates.ps1`

Lalu jalankan:

```powershell
cd "D:\ECADIN_Project_Clean"

PowerShell -ExecutionPolicy Bypass `
  -File ".\migration\reference\collect_reference_candidates.ps1"
```

Unggah hasil:

`D:\ECADIN_Project_Clean\migration\reference\ECADIN_reference_candidate_files.zip`

Folder proyek lama hanya dibaca. Tidak ada file legacy yang diubah atau dihapus.
