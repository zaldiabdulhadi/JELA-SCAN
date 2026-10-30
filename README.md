# Jelantah Scanner - Dashboard Monitoring

Dashboard Streamlit lokal untuk memonitor hasil scan proyek IoT **Jelantah Scanner**
(ESP32, saat ini disimulasikan di Wokwi). Perangkat mengirim satu pesan JSON ke
HiveMQ Cloud setiap tombol scan ditekan. Dashboard hanya menerima data (subscribe)
dan tidak mengirim perintah apa pun ke perangkat.

## Fitur

- Subscriber MQTT (paho-mqtt v2) berjalan di thread background, terpisah dari UI.
- TLS wajib dengan verifikasi sertifikat memakai CA default sistem.
- Reconnect otomatis dengan exponential backoff.
- Setiap payload valid disimpan ke SQLite lokal (`data/scans.db`, mode WAL).
- UI auto-refresh tiap 3 detik memakai `st.fragment`, tanpa reload halaman.
- Demo mode lewat toggle di sidebar: menampilkan data dummy lokal tanpa koneksi
  MQTT dan tanpa menulis ke SQLite. Aktif otomatis bila `.env` belum lengkap.
- Kartu hasil scan terakhir, badge grade berwarna, metrik dengan selisih terhadap
  scan sebelumnya, grafik tren Plotly, distribusi grade, ringkasan route, tabel
  riwayat dengan filter, dan download CSV.
- Banner peringatan untuk grade `REJECT`, `HOLD`, atau `temp_valid=false`.
- Payload rusak atau tidak lengkap dicatat ke log lalu diabaikan, dashboard tetap hidup.

## Struktur proyek

```
.
|-- app.py              # UI Streamlit
|-- mqtt_client.py      # subscriber MQTT + validasi payload
|-- demo_data.py        # generator data dummy untuk demo mode
|-- db.py               # akses SQLite (WAL)
|-- config.py           # env, ambang grafik, helper waktu/TLS/logging
|-- simulator.py        # publisher payload palsu untuk pengujian
|-- requirements.txt
|-- .env.example
|-- .gitignore
|-- README.md
`-- data/               # dibuat otomatis, tidak di-commit (scans.db, log)
```

## 1. Instalasi

Prasyarat: Python 3.10 atau lebih baru.

Windows (PowerShell / CMD):

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Linux / macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Konfigurasi .env

Salin `.env.example` menjadi `.env`, lalu isi kredensial HiveMQ Cloud:

```bat
copy .env.example .env
```

```dotenv
MQTT_HOST=your-cluster-id.s1.eu.hivemq.cloud
MQTT_PORT=8883
MQTT_USERNAME=your-username
MQTT_PASSWORD=your-password
MQTT_TOPIC=jelantah/scanner/data
```

Catatan:

- Port HiveMQ Cloud untuk TLS adalah `8883`. Jangan memakai port non-TLS.
- File `.env` tidak boleh di-commit (sudah masuk `.gitignore`).
- Setelah mengubah `.env`, **restart dashboard** karena subscriber di-cache oleh
  `st.cache_resource`.

## 3. Menjalankan dashboard

```bash
streamlit run app.py
```

`python app.py` juga bisa dipakai; skrip otomatis meneruskan ke server
Streamlit.

Buka URL yang ditampilkan Streamlit (biasanya `http://localhost:8501`).

Jika `.env` belum lengkap, dashboard otomatis masuk **Demo mode** dan langsung
menampilkan data dummy. Data demo hanya ada di memori dan tidak masuk ke SQLite.
Matikan toggle **Demo mode** di sidebar untuk kembali memakai data MQTT asli.

Saat database masih kosong, dashboard menampilkan pesan:

> Belum ada data, tekan tombol scan di Wokwi

Data yang masuk akan muncul otomatis dalam sekitar 3 detik tanpa refresh manual.

## 4. Menjalankan simulator

Simulator mem-publish payload dengan format yang sama ke broker dan topic yang
sama, sehingga dashboard bisa dites tanpa Wokwi menyala.

```bash
python simulator.py
```

Opsi yang tersedia:

```bash
python simulator.py --interval 2 --count 10 --grade B
python simulator.py --interval 5 --count 0
python simulator.py --topic jelantah/scanner/data --grade REJECT
```

- `--interval` jeda antar pesan dalam detik (default 5).
- `--count` jumlah pesan; `0` berarti tanpa batas (default 0).
- `--topic` override topic tujuan (default dari `.env`).
- `--grade` memaksa satu grade (`A`, `B`, `C`, `REJECT`, `HOLD`); bila kosong
  grade dipilih acak dengan bobot realistis.

Nilai sensor pada simulator dibuat konsisten dengan grade yang dikirim. Grade di
dashboard selalu diambil dari payload, tidak dihitung ulang.

## 5. Konfigurasi perangkat (Wokwi)

Arahkan koneksi MQTT perangkat ke broker yang sama:

- Host: nilai `MQTT_HOST`
- Port: `8883`
- TLS: aktif, verifikasi sertifikat
- Username/password: sesuai `.env`
- Topic publish: `jelantah/scanner/data`
- QoS: bebas (dashboard subscribe QoS 1), **tanpa retain**

Field `ts` pada payload adalah `millis()` ESP32, bukan waktu asli. Dashboard
mencatat waktu terima pesan dalam UTC dan menampilkannya dalam WIB
(`Asia/Jakarta`).

Contoh payload:

```json
{
  "device": "jelantah-scanner-01",
  "ts": 123456,
  "temp_c": 28.0,
  "temp_valid": true,
  "moisture_pct": 0.35,
  "turbidity_ntu": 42.5,
  "color_bright": 55,
  "grade": "B",
  "status": "Layak + pretreatment",
  "yield_pct": 80,
  "price_rp": 5000,
  "pump": "on",
  "route": "Pre-Tank"
}
```

`turbidity_ntu` adalah skala 0-100 hasil konversi sensor LDR, bukan NTU asli.
Di UI ditampilkan sebagai **Kekeruhan (skala 0-100)**.

## 6. Ambang grafik

Ambang hanya dipakai sebagai garis referensi pada grafik dan tidak mengubah
grade. Ubah nilainya di `config.py` pada dictionary `THRESHOLDS`:

| Sensor | Ambang |
| --- | --- |
| Suhu valid | 15 - 45 C |
| Kadar air | 0.21 (A/B), 1.0 (REJECT) |
| Kekeruhan | 35 (A/B), 65 (C/REJECT) |
| Kecerahan warna | 60 (A/B), 20 (C), 30 (REJECT bersama kekeruhan >= 65) |

## 7. Penyimpanan data

- Database: `data/scans.db` (SQLite, mode WAL).
- Log: `data/dashboard.log` (rotasi otomatis, maksimal 3 file cadangan).
- Folder `data/` di-ignore oleh git. Menghapus file database akan menghapus
  seluruh riwayat.
- Restart dashboard tidak menghilangkan riwayat karena UI selalu membaca SQLite.

## 8. Alur data

```
Wokwi / simulator --MQTT/TLS--> mqtt_client.py (thread background)
                                      |
                                      v validasi payload
                                  db.py (SQLite WAL)
                                      |
                                      v baca tiap 3 detik
                                  app.py (st.fragment)
```

## 9. Troubleshooting

- **Tidak ada data masuk**: cek topic, username/password, dan port 8883. Lihat
  `data/dashboard.log` untuk alasan payload ditolak atau koneksi gagal.
- **Error sertifikat TLS**: pastikan jam sistem benar, port 8883, dan CA sistem
  terbaru. Jangan menonaktifkan verifikasi sertifikat.
- **Broker putus**: status di header berubah menjadi "Terputus"; subscriber
  mencoba reconnect otomatis dengan exponential backoff. Dashboard tetap berjalan.
- **Perubahan .env tidak terbaca**: restart proses Streamlit.
- **Zona waktu salah**: paket `tzdata` sudah ada di `requirements.txt`; pastikan
  dependencies terpasang di environment yang dipakai.
