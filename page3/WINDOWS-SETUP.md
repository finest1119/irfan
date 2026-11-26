# Setup laptop Windows: senarai langkah (Everyday Decoded / Page 3)

Untuk: Irfan. Disediakan 24 Nov 2026 oleh session Page 3. Laptop ED: **Asus ROG Strix G513QC** (Ryzen 7 5800H, 16 GB RAM, RTX 3050 Laptop 4 GB VRAM, ~322 GB kosong, Windows 11 Home).
Laptop Page 2 (Self-Made Engineer) ikut langkah yang sama; cuma `.env` dia lain.

Cara guna: Irfan buat **Bahagian A** (pasang program). Lepas Claude Code dah jalan di laptop tu,
**Bahagian B dan C dibuat oleh Claude**: Irfan cuma taip arahan yang diberi dalam kotak.
Tanda ☐ → ☑ bila siap.

---

## A. Pasang program (Irfan, lebih kurang 1 jam)

☐ **1. Update Windows + driver NVIDIA**
   - Settings → Windows Update → install semua, restart.
   - Pasang **NVIDIA App** (nvidia.com), kemudian pilih driver **Studio** (bukan Game Ready) dan install.

☐ **1b. Pastikan Blender guna GPU NVIDIA (laptop ni ada 2 GPU: AMD dalam CPU + RTX 3050)**
   - Buka **Armoury Crate** → GPU Mode → pilih **Ultimate** (atau Standard; jangan Eco).
   - Settings → System → Display → **Graphics** → tambah `blender.exe` → Options → **High performance (NVIDIA)**.

☐ **2. Setting kuasa (supaya laptop tak tidur masa render)**
   - Settings → System → Power: **Screen off / Sleep = Never** (bila plugged in).
   - Control Panel → Power Options → "Choose what closing the lid does" → **Do nothing** (plugged in).
   - Charger sentiasa dicucuk. Letak laptop atas permukaan keras (atau cooling pad); jangan atas tilam.

☐ **3. Git**: git-scm.com → Download for Windows → install (tekan Next sahaja).

☐ **4. Python 3.12** (sama dengan laptop SME): python.org → Downloads → Python **3.12** (versi 3.12.x terkini) (Windows installer 64-bit).
   - ⚠️ Di skrin pertama installer, **tandakan "Add python.exe to PATH"**.

☐ **5. Blender 5.3.0** (mesti sama versi dengan Mac): blender.org → Download → "Previous versions" kalau
   perlu → **5.3.0 Windows Installer** → install di tempat default
   (`C:\Program Files\Blender Foundation\Blender 5.3\`).

☐ **6. ffmpeg**: buka **PowerShell**, taip:
   ```
   winget install Gyan.FFmpeg
   ```
   Tutup dan buka semula PowerShell, kemudian taip `ffmpeg -version`. Kalau keluar tulisan versi, dah OK.

☐ **7. Node.js** (untuk Codex CLI): nodejs.org → **LTS** → install.

☐ **8. Codex CLI** (untuk jana gambar): dalam PowerShell taip:
   ```
   npm install -g @openai/codex
   codex
   ```
   Login guna akaun ChatGPT yang sama macam di Mac. Lepas login, tutup.

☐ **9. Claude Code**: pasang **Claude desktop app** (claude.ai/download), login akaun yang sama (Max),
   kemudian buka tab **Code**.

---

## B. Ambil kod dari GitHub (Irfan + Claude, 10 minit)

☐ **10. Login GitHub**: dalam PowerShell:
   ```
   winget install GitHub.cli
   gh auth login
   ```
   Pilih GitHub.com → HTTPS → Login with a web browser, kemudian ikut kod yang keluar.

☐ **11. Clone repo** (folder yang sama untuk semua kerja):
   ```
   cd $HOME\Documents
   git clone https://github.com/finest1119/irfan.git
   cd irfan
   git checkout claude/optimistic-hawking-lkruq9
   ```
   (Nama branch ni ialah branch semasa di Mac pada 24 Nov 2026. Kalau chief tukar branch, guna yang dia beri.)

☐ **12. Buka folder `Documents\irfan` dalam Claude Code** (tab Code → pilih folder), kemudian taip:
   > "Ini laptop Windows untuk Page 3 Everyday Decoded. Ikut irfan/page3/WINDOWS-SETUP.md bahagian B dan C."

   Claude akan buat:
   - `python -m venv .venv` dan install pakej (google-genai 1.47.0, faster-whisper 1.2.1, python-dotenv 1.2.1,
     pillow 11.3.0, numpy 2.0.2) + **pin `av==16.1.*`** (PyAV 19 breaks faster-whisper; found on the Asus 26 Nov)
   - `python tools/fetch_cc0.py` (aset CC0 dalam assets/cc0/manifest.json)
   - download aset Poly Haven `assets/polyhaven/` (HDRI kloofendal 2K + 3 tekstur 1K, senarai dalam README Mac; belum ada dalam manifest fetch_cc0)
   - semak Blender, ffmpeg (encoder `hevc_nvenc`) dan Codex dari Python

☐ **13. Fail `.env` (Irfan sendiri, JANGAN paste dalam chat)**
   - Di Mac, ambil fail **`irfan/.env.page3`** (ada `FB_PAGE_ID=1379706781903422` + FB_PAGE_TOKEN Page Everyday Decoded,
     dulu Beyond Measure). **Jangan guna `irfan/page3/.env`**: itu Page lama yang kosong (1465128156682768), dah tak dipakai.
   - Salin ke laptop guna pendrive (USB).
   - Di laptop, namakan semula jadi `Documents\irfan\.env` (nama mesti tepat `.env`), dan tambah juga baris
     `GEMINI_API_KEY=...` dari `.env` Mac, serta `SCHEDULE_TZ=America/New_York`.
   - Lepas tu Claude semak (baca sahaja, token tak ditunjuk): jenis PAGE, valid, Page ID 1379706781903422.
   - Laptop Page 2 guna token Page 2, bukan yang ini.
   - Fail `.env` tak masuk GitHub (dah di-ignore). Repo ni **public**, jadi jangan sekali-kali letak token
     dalam fail lain.

---

## C. Benchmark render (Claude buat, Irfan tunggu ~30–45 minit)

Tujuan: tahu berapa video sehari laptop ni boleh buat, sebelum janji 5 video/hari.

☐ **14. Ujian GPU**: Claude render beberapa frame dari episode WJH yang dah ada
   (`episodes/2026-11-24-1-plane-crash`, still sahaja, tak post apa-apa) dengan:
   - Cycles GPU (OptiX) + denoiser, 1080×1920
   - EEVEE (lebih laju, kualiti diperiksa)
   Claude akan catat: **saat per frame**, **VRAM maksimum** (`nvidia-smi`), **suhu GPU**.

☐ **15. Keputusan** (Claude tulis dalam `page3/BENCHMARK.md` dan beritahu chief):
   | Saat per frame | Maksudnya |
   |---|---|
   | ≤ 1.5 s | 5 video/hari boleh (~6 jam render) |
   | 1.5–3 s | 2–3 video/hari; turunkan samples atau guna EEVEE |
   | > 3 s, atau VRAM penuh | permudahkan scene dulu; mula 1–2 video/hari |

☐ **16. Ujian encode**: Claude encode satu video ujian guna `hevc_nvenc`, dan pastikan saiz < 10 MB untuk FB.

☐ **17. Ujian Graph API (baca sahaja, tak post)**: Claude semak token Everyday Decoded dari `.env` laptop
   (jenis PAGE, valid, tak expire), tanpa tunjuk token.

---

## D. Lepas setup

- Video sebenar Page 3 **belum boleh dibuat** sampai renderer one-shot (dibina oleh session Self-Made Engineer)
  dan pilihan overlay per-Page (session Page 3) siap dan di-push ke GitHub. Lepas tu, di laptop cukup taip:
  `git pull`.
- Jadual posting automatik (Windows Task Scheduler / Claude scheduled tasks) disediakan **selepas** video pilot
  diluluskan Irfan.
- Masalah biasa:
  - `python` tak dikenali: install semula Python dan tandakan "Add to PATH".
  - Blender lambat sangat / guna CPU: semak driver Studio NVIDIA, dan dalam Blender pilih Preferences → System
    → **OptiX** → tandakan RTX 3050.
  - Laptop panas sangat (> 85 °C): guna cooling pad, render satu-satu.
