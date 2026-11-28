# Ambil alih Facebook Pages · 28–29 November 2026

**Codex jaga lima Page hingga Ahad, 29 Nov 2026, 22:00 MYT.** Kuota mingguan Claude pada masa serahan ialah 97%. Mac jadi chief. Semua waktu di sini waktu Malaysia.

## Yang Irfan perlu buat

1. Jika sesi belum bermula, buka projek tempatan di Codex dan tampal satu baris untuk mesin itu. [Baris mula](codex/START-HERE.md)
2. Pada Dell dan Asus, pilih **Full access** untuk GPU Blender. Pada Mac, luluskan permintaan izin khusus jika muncul.
3. Jika diperlukan, log masuk, taip kata laluan, lengkapkan 2FA atau CAPTCHA terus dalam aplikasi.
4. Buat tindakan fizikal yang diminta, seperti menyambung pengecas atau USB. Sahkan pembelian hanya selepas Codex menunjukkan harga.

## Persediaan oleh ejen

Semua fail pakej ini ada dalam git (branch claude/optimistic-hawking-lkruq9). Laptop hanya perlu `git pull`.

| Mesin | Folder projek | Prompt |
|---|---|---|
| Mac M2 Pro | `/Users/irfan/Documents/Facebook & Youtube Monetisation/irfan` | [Mac chief dan WJH](codex/prompts/mac-chief-wjh.md) |
| Dell G15 | `C:\Users\fines\irfan` | [Dell · Self-Made Engineer](codex/prompts/dell-sme.md) |
| Asus ROG | `Documents\irfan` dalam profil Windows Irfan | [Asus · Everyday Decoded](codex/prompts/asus-ed.md) |

Setiap ejen jalankan semakan Git dan kerja aktif dalam `AGENTS.md`, buat `git pull --ff-only` apabila selamat dan sambung dari checkpoint. Kekalkan arahan tanpa commit atau push. Chief semak kuasa, cegah mod tidur sementara jika perlu dan pastikan aplikasi Mac serta projek **Local** tersedia. Semak izin rangkaian untuk penyelidikan, TTS dan Graph. [Panduan Codex](https://learn.chatgpt.com/docs/automations)

Chief sendiri jalankan render penuh pada host Mac melalui akses yang diluluskan. Selepas audio, timing dan tekstur siap, sahkan tiada render aktif untuk episod itu. Guna arahan repo seperti `.venv/bin/python pipeline/make_episode.py "episodes/<id>/episode.json" --steps render` dengan ID sebenar. Semak peranti Metal dan kemajuan bingkai pada log Blender. Di laptop, ejen sahkan RTX OptiX atau CUDA selepas Irfan memberikan izin tempatan.

## Kerja yang perlu disambung pada 28 Nov

| Pemilik | Keadaan semasa serahan dan tindakan pertama |
|---|---|
| Mac · WJH | Set **Sun 29** sedang dirender mengikut laporan serahan. Slot ialah **28 Nov 21:00** turbulence, **29 Nov 01:30** black ice dan **29 Nov 08:00** world news this week. Semak bingkai, fail akhir dan queue Facebook sebelum sambung. [Penyelidikan set](research/2026-11-28.md) |
| Dell · SME | **Build #2 micro-hydro** dilaporkan sedang dirender. Semak bingkai terakhir, kemudian QC dan muka depan B. Build #1 ada tempahan **28 Nov 08:30** serta tugas komen Dell **08:45**. Semak komen sedia ada. |
| Asus · ED | Panjangkan **tiga reel Codex** dan siapkan **moka pot** pada 75–90 s. Kenal pasti tiga reel dalam rekod Asus. Audit menemui 17 eksport lama yang pendek. Kekalkan tempahan sedia ada. Had tiga reel sehari mengikut tarikh ET sehingga serahan balik. |
| Mac · DBT dan KBD | Dua Page sudah wujud. **Reel v2 sedang dibina dalam `page4/`** daripada skrip diluluskan. DBT menerangkan kolam takungan, KBD menunjukkan pengisar kayuh Bar. Preview 78/84 s ialah versi terdahulu. Render penuh BM hanya selepas set WJH selesai **dan** selepas 29 Nov 08:00. Sahkan akses Page dan kelulusan pilot akhir sebelum siaran. [Status produksi](page4/PRODUCTION-STATUS.md) |

## Automasi Mac

Chief sendiri semak status, run terakhir dan retry bagi dua tugas Claude bernama di bawah. Catat keadaan asal, jeda pencetus lama dan sahkan tiada pemilik bertindih sebelum mengaktifkan pengganti. Semak juga launchd, cron, tugas komen Dell dan jadual YouTube 09:15. Biarkan render yang masih maju diteruskan.

1. Senaraikan tugas Codex sedia ada untuk projek dan waktu ini. Guna semula entri yang sepadan walaupun namanya berlainan. Guna alat automasi Codex jika tersedia. Jika versi aplikasi menyokong pendaftaran melalui fail, chief sendiri cipta atau kemas kini `~/.codex/automations/<id>/automation.toml` mengikut skema tugas projek versi itu. Kekalkan ID entri yang sepadan. Jika kaedah fail tidak tersedia atau pendaftaran belum muncul, semak semula senarai dan kendalikan **Scheduled** dalam aplikasi sendiri.
2. Gunakan projek **irfan** di folder Mac dalam jadual mesin, mod **Local**, zon **Asia/Kuala_Lumpur (UTC+8)**. Jika aplikasi mengikut jam Mac, semak paparannya dalam MYT. Daftarkan dua tugas berikut sebagai tugas projek.

| Nama | Ulangan setiap hari (MYT) | Teks untuk medan Prompt |
|---|---|---|
| `wjh-daily-news-research` | **07:00** | `Read AGENTS.md and execute codex/prompts/automation-wjh-daily.md fully now. Log every action to CODEX-LOG.md. Stop at 29 Nov 2026 22:00 MYT.` |
| `wjh-auto-comments` | **02:30, 09:30, 21:30** | `Read AGENTS.md and execute codex/prompts/automation-auto-comments.md fully now. Log every action to CODEX-LOG.md. Stop at 29 Nov 2026 22:00 MYT.` |

Dalam **Custom**, guna `RRULE:FREQ=DAILY;BYHOUR=7;BYMINUTE=0` untuk WJH dan `RRULE:FREQ=DAILY;BYHOUR=2,9,21;BYMINUTE=30` untuk komen. Tetapkan tamat **29 Nov 22:00 MYT** jika disokong. Jika hanya satu waktu dibenarkan bagi setiap entri, guna `wjh-auto-comments` untuk 02:30, `wjh-auto-comments-0930` untuk 09:30 dan `wjh-auto-comments-2130` untuk 21:30 dengan teks sama. Pastikan hanya satu pencetus aktif bagi setiap waktu komen.

Selepas simpan, buka semula senarai melalui aplikasi atau alat automasi. Baca balik ID/nama, status aktif, projek Local, prompt tersimpan, ulangan dan **Next run** dalam MYT. Log bukti itu dalam `CODEX-LOG.md`. Fail TOML sahaja belum mengesahkan pendaftaran. Jika entri tiada, baiki pendaftarannya dan semak semula sebelum mencipta entri lain. Biarkan slot 07:00 yang sudah berlalu dan set Ahad yang sedang berjalan.

**Jika hanya Irfan boleh melengkapkan borang**, chief nyatakan halangannya dan isi semua medan yang boleh dicapai dahulu. Minta hanya klik yang masih perlu. Jika seluruh borang tidak boleh dicapai, beri laluan berikut bersama **nama, waktu dan teks prompt penuh** untuk setiap entri yang masih tiada. Di Mac, buka **Codex → Scheduled** (atau **Automations**) **→ New/+**. Pilih projek **irfan → Local**. Isi **Name** dan **Prompt**, pilih **Schedule → Daily/Custom**, kemudian **Create/Save**. Sertakan zon dan ketiga-tiga waktu jika tugas komen. Jika simpanan belum dapat disahkan, semak entri sedia ada dahulu. Chief baca balik **Next run** selepas tindakan Irfan.

## Tempahan dan komen

Pemilik slot semak `posting-log.md`, log Page sendiri dan resit. Sebelum menjadualkan atau mengulang cubaan, gunakan klien repo untuk sahkan `/me`, `/<page-id>/scheduled_posts` dan reel yang sudah live. Padankan ID, waktu dan kapsyen. Selepas QC dan pengesahan slot kosong, pemilik sendiri jalankan scheduler dan baca balik tempahan. [Semakan dan arahan repo](AGENTS.md#release-comments-and-handback)

Ejen Dell dan Asus sendiri pindahkan baris log baharu, `<keyword>.post.md` dan resit minimum melalui laluan peribadi. Chief gabungkan rekod mengikut `video_id` ke `page2/output/api-posts.json` (SME) atau `page3/output/api-posts.json` (ED). Sertakan `keyword`, `scheduled_ts` (saat Unix) dan `post_id` jika ada. Kekalkan rekod lama dan letakkan fail post di folder `output` Page yang sama. WJH guna `output/` di root. Story kekal dijeda.

## Serah balik kepada Claude

1. Pada **29 Nov 22:00 MYT**, ketiga-tiga ejen hentikan kerja baharu. Chief jeda semua pencetus Codex pakej ini termasuk entri komen berasingan. Sahkan statusnya dan semak run 21:30 serta retry. Rekod mesin, episod, bingkai terakhir dan pemilik seterusnya bagi render yang masih hidup.
2. Chief gabungkan baris log baharu Dell dan Asus. Padankan setiap tempahan dengan queue Facebook atau permalink live. Catat ID reel/post/komen, tempoh video, QC, fail, baki kerja, isu akses dan slot kosong seterusnya.
3. Chief sendiri serahkan `AGENTS.md`, runbook dan checkpoint `CODEX-LOG.md` kepada sesi Claude chief melalui laluan yang dibenarkan. Selepas pemilik Codex dilepaskan, pulihkan dua jadual Claude yang dijeda untuk serahan ini dan sahkan waktu seterusnya. Pada **30 Nov**, urutannya komen **02:30**, WJH **07:00**, komen **09:30**. Claude sambung Dell/Asus, naikkan ED ke lima sehari mengikut kapasiti dan ambil giliran BM yang masih terbuka.
