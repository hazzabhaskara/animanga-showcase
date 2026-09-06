# 🌟 Animanga Showcase & Personal Catalog

[![Website](https://img.shields.io/badge/Website-Live%20on%20Vercel-black?style=flat&logo=vercel)](https://vercel.com)
[![Data](https://img.shields.io/badge/Anime%20%26%20Manga-266%20Titles-indigo)](#)
[![Format](https://img.shields.io/badge/Excel-Animanga__Showcase.xlsx-107C41?logo=microsoftexcel)](#)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](#)

Interactive, aesthetic Notion & Airtable-style catalog and database for **Hazza's Anime and Manga collection**, enriched with official high-resolution posters, genres, synopses, studios, and ratings.

---

## ✨ Fitur Unggulan

- 🗂️ **Dual View Modes**:
  - **Gallery / Cards View**: Tampilan kartu visual dengan poster cover resmi, bintang rating, dan badge status.
  - **Airtable / Table View**: Spreadsheet spreadsheet interaktif dengan kolom yang bisa di-sort (Judul, Skor, Status, Progress, Studio).
- ⚡ **Instant Search & Multi-Filter**: Pencarian instan (<2ms) berdasarkan judul, studio, pengarang, filter Media Type (Anime/Manga), Status, Skor, dan Genre.
- 🎯 **Mood & Recommendation Engine**: Pilih suasana hati (*Emotional, Mind-Bending, Romcom, Dark Fantasy, Psychological, Chill*) untuk mendapatkan kurasi anime/manga terbaik dari Hazza.
- 🤝 **Friend Taste Matcher**: Teman bisa mencentang judul favorit mereka untuk menghitung tingkat kecocokan selera wibu (0 - 100%) dengan Hazza.
- 📇 **Share Taste Card**: Salin ringkasan profil selera Hazza untuk dibagikan ke WhatsApp, Discord, atau media sosial.
- 📊 **Excel Workbook Estetik (Animanga_Showcase.xlsx)**: File Excel profesional dengan palet Slate Navy #1E293B, conditional formatting heatmap skor 1-10, freeze panes, dan auto-filter.
- 🌓 **Dark & Light Mode**: Desain nyaman di mata dengan token tema modern.
- 🚀 **100% Offline Compatible**: Berjalan mulus di browser lokal (ile://) tanpa server, dan siap di-deploy ke Vercel Edge CDN.

---

## 📊 Statistik Koleksi

- **Total Judul**: 266 Entri (219 Anime & 47 Manga)
- **Status Selesai**: 227 Selesai Ditonton / Dibaca
- **Rata-rata Skor**: 8.1 / 10
- **All-Time Masterpieces (Skor 10/10)**:
  - *Clannad: After Story*
  - *Steins;Gate*
  - *Berserk*
  - *Oyasumi Punpun*
  - *Kaguya-sama wa Kokurasetai: Ultra Romantic*
  - *Shingeki no Kyojin Season 3 Part 2*
  - *Takopii no Genzai*

---

## 🛠️ Cara Menjalankan Secara Lokal

1. Clone repositori ini:
   `ash
   git clone https://github.com/hazzabhaskara/animanga-showcase.git
   cd animanga-showcase
   `
2. Cukup klik ganda file index.html di browser favorit kamu (Chrome, Edge, Firefox). Tidak perlu 
pm install atau web server!

---

## 🔄 Pembaruan Data di Masa Depan

Jika kamu memiliki backup XML baru dari MyAnimeList:
1. Masukkan file .xml.gz ke dalam folder proyek.
2. Jalankan pipeline otomatis:
   `ash
   python build_catalog.py
   `
3. Verifikasi integritas data:
   `ash
   python verify_catalog.py
   `

---

Dibuat dengan ❤️ oleh **Hazza Bhaskara**.
