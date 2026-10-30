import csv
import json
import os
from datetime import datetime, timezone
import time

try:
    import requests
    from dotenv import load_dotenv
    load_dotenv()
    _TG_TOKEN = os.getenv("TG_TOKEN")
    _TG_CHAT  = os.getenv("TG_CHAT")
except Exception:
    requests = None; _TG_TOKEN = None; _TG_CHAT = None

_last_alert = {"grade": None, "t": 0.0}

import paho.mqtt.client as mqtt

# ==========================================
# 1. KONFIGURASI MQTT
# ==========================================

MQTT_HOST = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPIC = "jelantah/scanner/data"

CLIENT_ID = "jelantah-python-subscriber-01"

# ==========================================
# 2. KONFIGURASI PENYIMPANAN DATA
# ==========================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CSV_FILE = os.path.join(DATA_DIR, "sensor_data.csv")

FIELDNAMES = [
    "received_at",
    "device",
    "ts",
    "temp_c",
    "temp_valid",
    "moisture_pct",
    "turbidity_ntu",
    "color_bright",
    "iqk",            
    "confidence",     
    "grade",
    "status",
    "yield_pct",
    "price_rp",
    "pump",
    "route"
]

os.makedirs(DATA_DIR, exist_ok=True)


# ==========================================
# 3. INISIALISASI CSV
# ==========================================

def initialize_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=FIELDNAMES
            )
            writer.writeheader()

        print(f"[INFO] File CSV dibuat: {CSV_FILE}")


# ==========================================
# 4. MENYIMPAN DATA SENSOR
# ==========================================

def save_to_csv(data):
    row = {
        "received_at": datetime.now(timezone.utc).isoformat(),
        **{f: data.get(f) for f in FIELDNAMES if f != "received_at"},
    }

    with open(CSV_FILE, "a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writerow(row)
        file.flush()


# ==========================================
# 5. CALLBACK KONEKSI MQTT
# ==========================================

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("[MQTT] Berhasil terhubung ke broker.")

        client.subscribe(MQTT_TOPIC)

        print(f"[MQTT] Subscribe topic: {MQTT_TOPIC}")

    else:
        print(f"[MQTT] Koneksi gagal: {reason_code}")


# ==========================================
# 6. CALLBACK PENERIMAAN PESAN
# ==========================================

def on_message(client, userdata, message):
    try:
        # Decode payload JSON
        payload = message.payload.decode("utf-8")

        data = json.loads(payload)

        # Validasi field utama
        required_fields = [
            "device",
            "temp_c",
            "moisture_pct",
            "turbidity_ntu",
            "color_bright"
        ]

        missing_fields = [
            field for field in required_fields
            if field not in data
        ]

        if missing_fields:
            print(
                f"[WARNING] Field tidak ditemukan: {missing_fields}"
            )
            return

        # Simpan data
        save_to_csv(data)

        try:
            is_alert = (data.get("grade") == "REJECT") or (data.get("temp_valid") is False)
            now = time.time()
            changed = data.get("grade") != _last_alert["grade"]
            if is_alert and requests and _TG_TOKEN and _TG_CHAT \
               and (changed or now - _last_alert["t"] > 300):
                requests.post(
                    f"https://api.telegram.org/bot{_TG_TOKEN}/sendMessage",
                    data={"chat_id": _TG_CHAT,
                          "text": f"JELANTAH {data.get('grade')} | {data.get('status')} | {data.get('device')}"},
                    timeout=5,
                )
                _last_alert["t"] = now
            if is_alert:
                _last_alert["grade"] = data.get("grade")
        except Exception as e:
            print("[TG] skip:", e)

        # Tampilkan hasil penerimaan
        print("\n" + "=" * 45)
        print("[DATA SENSOR DITERIMA]")
        print("=" * 45)

        print(f"Device       : {data.get('device')}")
        print(f"Temperature  : {data.get('temp_c')} °C")
        print(f"Moisture     : {data.get('moisture_pct')} %")
        print(f"Turbidity    : {data.get('turbidity_ntu')}")
        print(f"Color        : {data.get('color_bright')}")
        print(f"Grade        : {data.get('grade')}")
        print(f"Route        : {data.get('route')}")

        print(f"[CSV] Data tersimpan di {CSV_FILE}")

    except json.JSONDecodeError:
        print("[ERROR] Payload bukan JSON yang valid.")

    except Exception as error:
        print(f"[ERROR] Gagal memproses pesan: {error}")


# ==========================================
# 7. MENJALANKAN MQTT CLIENT
# ==========================================

def main():
    initialize_csv()
    print("[INFO] CSV path:", os.path.abspath(CSV_FILE))

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=CLIENT_ID,
        protocol=mqtt.MQTTv311
    )

    client.on_connect = on_connect
    client.on_message = on_message

    print("[INFO] Menghubungkan ke MQTT broker...")

    try:
        client.connect(
            MQTT_HOST,
            MQTT_PORT,
            keepalive=60
        )

        print("[INFO] Subscriber berjalan.")
        print("[INFO] Tekan CTRL+C untuk menghentikan.")

        client.loop_forever()

    except KeyboardInterrupt:
        print("\n[INFO] Subscriber dihentikan.")

    except Exception as error:
        print(f"[ERROR] MQTT: {error}")

    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
