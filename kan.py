import streamlit as st
import requests
import pandas as pd
import random
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from streamlit_autorefresh import st_autorefresh
import cv2
import torch
import time
import pathlib
import datetime
from PIL import Image
import numpy as np
import io

# Konversi path untuk Windows
temp = pathlib.PosixPath
pathlib.PosixPath = pathlib.WindowsPath

# --- CONFIG ---
UBIDOTS_TOKEN = "BBUS-JBKLQqTfq2CPXNytxeUfSaTjekeL1K"
DEVICE_LABEL = "hsc345"
VARIABLES = ["mq2", "humidity", "temperature", "lux"]
TELEGRAM_BOT_TOKEN = "7941979379:AAEWGtlb87RYkvht8GzL8Ber29uosKo3e4s"
TELEGRAM_CHAT_ID = "5721363432"
NOTIFICATION_INTERVAL = 300  # 5 menit dalam detik
ALERT_COOLDOWN = 60  # 1 menit cooldown untuk notifikasi langsung

# --- STYLE ---
st.markdown("""
    <style>
        .main-title {
            background-color: #001f3f;
            color: white;
            padding: 15px;
            text-align: center;
            font-size: 32px;
            border-radius: 8px;
            margin-bottom: 25px;
        }
        .data-box {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 20px;
            margin-bottom: 10px;
            font-size: 22px;
            background-color: #ffffff;
            color: #000000;
            border: 1px solid #e0e0e0;
            border-radius: 6px;
        }
        .label {
            font-weight: bold;
        }
        .data-value {
            font-size: 24px;
            font-weight: bold;
        }
        .refresh-btn {
            position: absolute;
            top: 30px;
            right: 30px;
            background-color: #0078d4;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
        }
        .refresh-btn:hover {
            background-color: #005a8d;
        }
        .tab-content {
            padding: 20px;
            background-color: #f9f9f9;
            border-radius: 8px;
        }
    </style>
""", unsafe_allow_html=True)

# --- TELEGRAM FUNCTIONS ---
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            st.error(f"Gagal mengirim pesan ke Telegram: {response.text}")
    except Exception as e:
        st.error(f"Error saat mengirim ke Telegram: {str(e)}")

def send_telegram_photo(photo, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    files = {'photo': ('snapshot.jpg', photo, 'image/jpeg')}
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "caption": caption,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, files=files, data=payload)
        if response.status_code != 200:
            st.error(f"Gagal mengirim foto ke Telegram: {response.text}")
    except Exception as e:
        st.error(f"Error saat mengirim foto ke Telegram: {str(e)}")

# --- DATA FETCH ---
def get_ubidots_data(variable_label):
    url = f"https://industrial.api.ubidots.com/api/v1.6/devices/{DEVICE_LABEL}/{variable_label}/values"
    headers = {
        "X-Auth-Token": UBIDOTS_TOKEN,
        "Content-Type": "application/json"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get("results", [])
    return None

# --- SIMULASI DATA DAN MODEL ---
@st.cache_data
def generate_mq2_simulation_data(n_samples=100):
    data = []
    for _ in range(n_samples):
        label = random.choices([0, 1], weights=[0.7, 0.3])[0]
        value = random.randint(400, 1000) if label == 1 else random.randint(100, 400)
        data.append((value, label))
    df = pd.DataFrame(data, columns=["mq2_value", "label"])
    return df

@st.cache_resource
def train_mq2_model():
    df = generate_mq2_simulation_data()
    X = df[['mq2_value']]
    y = df['label']
    model = LogisticRegression()
    model.fit(X, y)
    return model

model_iot = train_mq2_model()

# --- AI LOGIC ---
def predict_smoke_status(mq2_value):
    if mq2_value > 800:
        return "🚨 Bahaya! Terdeteksi asap rokok!"
    elif mq2_value >= 500:
        return "⚠️ Mencurigakan: kemungkinan ada asap, tapi belum pasti rokok."
    else:
        return "✅ Semua aman, tidak terdeteksi asap mencurigakan."

def evaluate_lux_condition(lux_value, mq2_value):
    if lux_value <= 50:
        if "Bahaya" in predict_smoke_status(mq2_value):
            return "🚨 Agak mencurigakan: gelap dan ada indikasi asap rokok!"
        elif "Mencurigakan" in predict_smoke_status(mq2_value):
            return "⚠️ Toilet gelap dan ada kemungkinan asap, perlu dipantau."
        else:
            return "🌑 Toilet dalam kondisi gelap, tapi tidak ada asap. Masih aman."
    else:
        return "💡 Lampu menyala, kondisi toilet terang."

def evaluate_temperature_condition(temp_value):
    if temp_value >= 31:
        return "🔥 Suhu sangat panas, bisa tidak nyaman, bisa berbahaya!"
    elif temp_value >= 29:
        return "🌤️ Suhu cukup panas, kurang nyaman."
    elif temp_value <= 28:
        return "✅ Suhu normal dan nyaman."
    else:
        return "❄️ Suhu terlalu dingin, bisa tidak nyaman."

def chatbot_response(question, mq2_value, lux_value=None, temperature_value=None):
    question = question.lower()
    if "rokok" in question or "situasi" in question:
        status = predict_smoke_status(mq2_value)
        return status.replace("🚨", "").replace("⚠️", "").replace("✅", "").strip()
    elif "lampu" in question or "lux" in question or "cahaya" in question or "gelap" in question:
        if lux_value is not None:
            status = evaluate_lux_condition(lux_value, mq2_value)
            return status.replace("🚨", "").replace("🌑", "").replace("💡", "").replace("⚠️", "").strip()
        else:
            return "Saya belum bisa membaca data lux sekarang."
    elif "suhu" in question or "temperature" in question or "panas" in question or "dingin" in question:
        if temperature_value is not None:
            status = evaluate_temperature_condition(temperature_value)
            return status.replace("🔥", "").replace("🌤️", "").replace("✅", "").replace("❄️", "").strip()
        else:
            return "Saya belum bisa membaca data suhu sekarang."
    elif "status" in question:
        status_mq2 = predict_smoke_status(mq2_value)
        status_lux = evaluate_lux_condition(lux_value, mq2_value) if lux_value is not None else ""
        return f"Status asap: {status_mq2.replace('🚨','').replace('⚠️','').replace('✅','').strip()} | Penerangan: {status_lux.replace('🚨','').replace('⚠️','').replace('🌑','').replace('💡','').strip()}"
    else:
        return "Maaf, saya belum paham pertanyaannya."

# --- ESP32-CAM DETECTION ---
@st.cache_resource
def load_yolo_model():
    return torch.hub.load('ultralytics/yolov5', 'custom', path='model/best.pt')

model_cam = load_yolo_model()

def run_camera_detection(frame_placeholder, status_placeholder):
    cap = cv2.VideoCapture('http://192.168.1.12:81/stream')
    last_saved_time = 0
    last_smoking_notification = 0
    save_interval = 600  # 10 menit untuk penyimpanan gambar lokal

    detection_active = True
    while detection_active:
        ret, frame = cap.read()
        if not ret:
            status_placeholder.error("Gagal membaca frame dari kamera. Periksa koneksi ESP32-CAM.")
            break

        img_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        results = model_cam(img_pil)
        results.render()
        rendered = results.ims[0]
        frame = cv2.cvtColor(rendered, cv2.COLOR_RGB2BGR)

        df = results.pandas().xyxy[0]
        found_person = 'person' in df['name'].values
        found_smoke = 'smoke' in df['name'].values

        current_time = time.time()

        # Simpan frame terbaru untuk pengiriman Telegram
        _, buffer = cv2.imencode('.jpg', frame)
        st.session_state.latest_frame = buffer.tobytes()

        if found_person and found_smoke:
            status_placeholder.warning("Merokok terdeteksi!")
            # Kirim notifikasi langsung dengan cooldown
            if current_time - last_smoking_notification > ALERT_COOLDOWN:
                caption = (
                    f"🚨 *Peringatan*: Aktivitas merokok terdeteksi!\n"
                    f"🕒 *Waktu*: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                send_telegram_photo(st.session_state.latest_frame, caption)
                last_smoking_notification = current_time

            if current_time - last_saved_time > save_interval:
                filename = datetime.datetime.now().strftime("smoking_%Y%m%d_%H%M%S.jpg")
                cv2.imwrite(filename, frame)
                last_saved_time = current_time
                status_placeholder.info(f"Gambar disimpan: {filename}")
        else:
            status_placeholder.success("Tidak ada aktivitas merokok terdeteksi.")

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_pil = Image.fromarray(frame_rgb)
        frame_placeholder.image(frame_pil, channels="RGB", use_container_width=True)

        time.sleep(0.1)

        if not st.session_state.get("cam_running", False):
            detection_active = False

    cap.release()
    cv2.destroyAllWindows()

# --- UI START ---
st.markdown('<div class="main-title">Sistem Deteksi Merokok Terintegrasi</div>', unsafe_allow_html=True)

# Tab selection
tab1, tab2 = st.tabs(["IoT Sensor", "ESP32-CAM"])

# --- IOT TAB ---
with tab1:
    st.markdown('<div class="tab-content">', unsafe_allow_html=True)
    st.header("Live Stream Data + AI Deteksi Rokok & Cahaya")

    mq2_value_latest = None
    lux_value_latest = None
    temperature_value_latest = None

    auto_refresh = st.checkbox("Aktifkan Auto-Refresh Data", value=True, key="iot_refresh")
    if auto_refresh:
        st_autorefresh(interval=5000, key="iot_auto_refresh")

    if 'last_notification' not in st.session_state:
        st.session_state.last_notification = {
            'mq2': {'status': None, 'value': None, 'last_alert_sent': 0},
            'lux': {'status': None, 'value': None},
            'temperature': {'status': None, 'value': None},
            'last_sent': 0
        }

    if 'latest_frame' not in st.session_state:
        st.session_state.latest_frame = None

    for var_name in VARIABLES:
        data = get_ubidots_data(var_name)
        if data:
            df = pd.DataFrame(data)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            value = round(df.iloc[0]['value'], 2)

            if var_name == "mq2":
                var_label = "ASAP/GAS"
                emoji = "💨"
            elif var_name == "humidity":
                var_label = "KELEMBAPAN"
                emoji = "💧"
            elif var_name == "temperature":
                var_label = "SUHU"
                emoji = "🌡️"
            elif var_name == "lux":
                var_label = "INTENSITAS CAHAYA"
                emoji = "💡"

            st.markdown(
                f'<div class="data-box"><span class="label">{emoji} {var_label}</span><span class="data-value">{value}</span></div>',
                unsafe_allow_html=True
            )

            st.line_chart(df[['timestamp', 'value']].set_index('timestamp'))

            current_time = time.time()

            if var_name == "mq2":
                mq2_value_latest = value
                status = predict_smoke_status(value)
                # Kirim notifikasi langsung dengan foto jika mencurigakan atau berbahaya
                if ("Mencurigakan" in status or "Bahaya" in status) and \
                   current_time - st.session_state.last_notification['mq2']['last_alert_sent'] > ALERT_COOLDOWN:
                    caption = (
                        f"🚨 *Peringatan Asap*: {status}\n"
                        f"📊 *Nilai MQ2*: {value}\n"
                        f"🕒 *Waktu*: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                    if st.session_state.latest_frame is not None:
                        send_telegram_photo(st.session_state.latest_frame, caption)
                    else:
                        send_telegram_message(caption + "\n⚠️ *Foto*: Kamera tidak aktif")
                    st.session_state.last_notification['mq2']['last_alert_sent'] = current_time
                st.session_state.last_notification['mq2']['status'] = status
                st.session_state.last_notification['mq2']['value'] = value
                if "Bahaya" in status:
                    st.error(status)
                elif "Mencurigakan" in status:
                    st.warning(status)
                else:
                    st.success(status)

            if var_name == "lux":
                lux_value_latest = value
                lux_status = evaluate_lux_condition(value, mq2_value_latest or 0)
                st.session_state.last_notification['lux']['status'] = lux_status
                st.session_state.last_notification['lux']['value'] = value
                if "mencurigakan" in lux_status.lower():
                    st.warning(lux_status)
                else:
                    st.info(lux_status)

            if var_name == "temperature":
                temperature_value_latest = value
                temp_status = evaluate_temperature_condition(value)
                st.session_state.last_notification['temperature']['status'] = temp_status
                st.session_state.last_notification['temperature']['value'] = value
                if "panas" in temp_status.lower() or "berbahaya" in temp_status.lower():
                    st.warning(temp_status)
                elif "dingin" in temp_status.lower():
                    st.info(temp_status)
                else:
                    st.success(temp_status)

            # Kirim laporan berkala setiap 5 menit
            if current_time - st.session_state.last_notification['last_sent'] > NOTIFICATION_INTERVAL:
                mq2_status = st.session_state.last_notification['mq2']['status'] or "Tidak ada data"
                mq2_value = st.session_state.last_notification['mq2']['value'] or "N/A"
                lux_status = st.session_state.last_notification['lux']['status'] or "Tidak ada data"
                lux_value = st.session_state.last_notification['lux']['value'] or "N/A"
                temp_status = st.session_state.last_notification['temperature']['status'] or "Tidak ada data"
                temp_value = st.session_state.last_notification['temperature']['value'] or "N/A"

                caption = (
                    f"📊 *Laporan Status (Setiap 5 Menit)*\n"
                    f"🚨 *Asap*: {mq2_status} (MQ2: {mq2_value})\n"
                    f"💡 *Pencahayaan*: {lux_status} (Lux: {lux_value})\n"
                    f"🌡️ *Suhu*: {temp_status} (Suhu: {temp_value}°C)\n"
                    f"🕒 *Waktu*: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )

                if st.session_state.latest_frame is not None:
                    send_telegram_photo(st.session_state.latest_frame, caption)
                else:
                    send_telegram_message(caption + "\n⚠️ *Foto*: Kamera tidak aktif")

                st.session_state.last_notification['last_sent'] = current_time

        else:
            st.error(f"Gagal mengambil data dari variabel: {var_name}")

    if mq2_value_latest is not None:
        st.markdown("---")
        st.subheader("💬 Chatbot Pengawas")
        questions = [
            "Ada asap rokok di sini?",
            "Bagaimana situasi asap rokok?",
            "Apakah terdeteksi asap rokok?",
            "Ada bahaya asap rokok?",
            "Status umum di sekitar?",
            "Apa status cahaya di toilet?",
            "Bagaimana kondisi cahaya di sini?",
            "Apakah lampu menyala?",
            "Cahaya di sini bagaimana?",
            "Bagaimana situasi pencahayaan?",
            "Apa status terbaru tentang keadaan?",
            "Bagaimana kondisi sekarang?",
            "Apa yang terdeteksi di sini?",
            "Apakah ada bahaya yang perlu diwaspadai?",
            "Ada indikasi asap atau gelap?",
            "Adakah perubahan pada suhu, kelembapan, atau cahaya?",
            "Apa kondisi suhu di sini?",
            "Apakah suhu terlalu panas atau dingin?",
            "Bagaimana kenyamanan suhu sekarang?"
        ]
        selected_question = st.selectbox("Pilih pertanyaan yang ingin ditanyakan:", questions)
        if selected_question:
            response = chatbot_response(selected_question, mq2_value_latest, lux_value_latest, temperature_value_latest)
            st.write(f"🤖: {response}")
    st.markdown('</div>', unsafe_allow_html=True)

# --- ESP32-CAM TAB ---
with tab2:
    st.markdown('<div class="tab-content">', unsafe_allow_html=True)
    st.header("Deteksi Merokok dengan ESP32-CAM")
    st.write("Mendeteksi aktivitas merokok secara real-time menggunakan kamera ESP32-CAM dan model YOLOv5.")

    frame_placeholder = st.empty()
    status_placeholder = st.empty()

    start_cam = st.checkbox("Mulai Deteksi", key="cam_start")
    if start_cam:
        st.session_state.cam_running = True
        run_camera_detection(frame_placeholder, status_placeholder)
    else:
        st.session_state.cam_running = False
        st.session_state.latest_frame = None
        status_placeholder.info("Klik 'Mulai Deteksi' untuk memulai streaming dari kamera.")
    st.markdown('</div>', unsafe_allow_html=True)

# --- End of File ---