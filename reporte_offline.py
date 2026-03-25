import os
import glob
import smtplib
from datetime import datetime
from email.message import EmailMessage

import gpxpy
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.colors as mcolors
from fpdf import FPDF
from dotenv import load_dotenv

# --- CONFIGURACIÓN ---
load_dotenv()
BASE_DIR = os.getcwd() # GitHub corre desde la raíz del repo
DATA_FOLDER = os.path.join(BASE_DIR, "data")

# --- VALORES MANUALES (Simulando Garmin) ---
# Puedes cambiar estos valores para ver cómo cambia el PDF
DATOS_MOCK = {
    "hrv": 68,             # Ms (68 es "Equilibrado")
    "sleep_score": 85,      # 0 a 100
    "sleep_quality": "Buena",
    "sueño_fases": {
        "profundo": 90,     # Minutos
        "ligero": 320,
        "rem": 110,
        "despierto": 15
    }
}

# --- FUNCIONES DE APOYO (Igual que el original) ---
def format_duration(minutos):
    h, m = minutos // 60, minutos % 60
    return f"{h}h {m}m" if h > 0 else f"{m}m"

def analizar_hrv(valor):
    if valor >= 65: return "Equilibrado", (0, 128, 0), "Sistema nervioso en equilibrio."
    elif 55 <= valor < 65: return "Tendencia Equilibrada", (218, 165, 32), "Recuperación en curso."
    return "Desequilibrado", (200, 0, 0), "Prioriza descanso."

def evaluar_riesgo_lesion(tsb, hrv, sleep_score):
    puntos = 0
    if tsb < -15: puntos += 30
    if hrv < 55: puntos += 40
    if sleep_score < 75: puntos += 30
    pos = (puntos / 100) * 6
    label = "Alto" if puntos >= 70 else "Medio" if puntos >= 30 else "Bajo"
    col = (200, 0, 0) if puntos >= 70 else (218, 165, 32) if puntos >= 30 else (0, 128, 0)
    return label, col, pos

# --- PROCESAMIENTO DE ARCHIVOS GPX ---
def obtener_actividades():
    reg = []
    archivos = glob.glob(os.path.join(DATA_FOLDER, "*.gpx"))
    print(f"📁 Buscando archivos en: {DATA_FOLDER}")
    print(f"🔎 Encontrados {len(archivos)} archivos GPX.")
    
    for archivo in archivos:
        try:
            with open(archivo, 'r') as f:
                gpx = gpxpy.parse(f)
            for track in gpx.tracks:
                bounds = track.get_time_bounds()
                if bounds.start_time:
                    reg.append({"Fecha": bounds.start_time.replace(tzinfo=None), "Duracion": track.get_duration()/60})
        except Exception as e:
            print(f"❌ Error leyendo {archivo}: {e}")
            continue
    return pd.DataFrame(reg).sort_values("Fecha") if reg else pd.DataFrame()

def calcular_carga(df):
    hist = df.groupby(df["Fecha"].dt.date)["Duracion"].sum().reset_index()
    hist.columns = ["Fecha", "Carga"]
    hist["Fecha"] = pd.to_datetime(hist["Fecha"])
    hist["ATL"] = hist["Carga"].ewm(span=7, adjust=False).mean()
    hist["CTL"] = hist["Carga"].ewm(span=42, adjust=False).mean()
    hist["TSB"] = hist["CTL"] - hist["ATL"]
    return {"atl": hist["ATL"].iloc[-1], "ctl": hist["CTL"].iloc[-1], "tsb": hist["TSB"].iloc[-1], "hist": hist}

# --- GENERACIÓN DE VISUALES Y PDF ---
def generar_visuales(fases, carga_info, hrv_val, sleep_val):
    # Dona de Sueño
    sizes = [fases['profundo'], fases['ligero'], fases['rem'], fases['despierto']]
    colors = ['#4a90e2', '#74b9ff', '#a29bfe', '#ff7675']
    fig, ax = plt.subplots(figsize=(4, 4))
    ax.pie(sizes, colors=colors, startangle=90, wedgeprops=dict(width=0.3))
    total_min = sum(sizes)
    ax.text(0, 0, f"{format_duration(total_min)}\nTotal", ha='center', va='center', fontsize=12, fontweight='bold')
    plt.savefig("sleep_chart.png", transparent=True, dpi=100, bbox_inches='tight')
    plt.close()

    # Gráfico de Carga
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(carga_info['hist']["Fecha"], carga_info['hist']["CTL"], label="Fitness (CTL)", color='#1f77b4', lw=2)
    ax.fill_between(carga_info['hist']["Fecha"], carga_info['hist']["TSB"], color='#ffeaa7', alpha=0.4, label="Balance (TSB)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    plt.legend(); plt.grid(alpha=0.2)
    plt.savefig("load_chart.png", dpi=100, bbox_inches='tight')
    plt.close()

def generar_pdf(carga, hoy, bio):
    generar_visuales(bio['sueño_fases'], carga, bio['hrv'], bio['sleep_score'])
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 15, "REPORTE OFFLINE (Archivos Locales)", ln=True, align="C")
    
    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 14); pdf.cell(0, 10, "Métricas Biométricas (Simuladas):", ln=True)
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 7, f"HRV: {bio['hrv']} ms  |  Sueño: {bio['sleep_score']}/100", ln=True)
    pdf.image("sleep_chart.png", x=140, y=35, w=40)
    
    pdf.ln(15)
    pdf.set_font("Helvetica", "B", 14); pdf.cell(0, 10, "Análisis de Carga (GPX Locales):", ln=True)
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 7, f"Fitness (CTL): {carga['ctl']:.1f} | Balance (TSB): {carga['tsb']:.1f}", ln=True)
    pdf.image("load_chart.png", x=10, y=pdf.get_y()+5, w=190)

    out_path = f"reporte_offline_{hoy.strftime('%Y%m%d')}.pdf"
    pdf.output(out_path)
    return out_path

def enviar_email(path):
    msg = EmailMessage()
    msg["Subject"] = f"Reporte Local GPX – {datetime.today().strftime('%d/%m/%Y')}"
    msg["From"] = os.getenv("GMAIL_EMAIL")
    msg["To"] = os.getenv("GMAIL_TO")
    msg.set_content("Este reporte fue generado usando tus archivos GPX locales de la carpeta /data.")
    with open(path, "rb") as f:
        msg.add_attachment(f.read(), maintype="application", subtype="pdf", filename=path)
    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls()
        s.login(os.getenv("GMAIL_EMAIL"), os.getenv("GMAIL_APP_PASSWORD"))
        s.send_message(msg)

if __name__ == "__main__":
    print("🚀 Iniciando Reporte Offline...")
    df_act = obtener_actividades()
    if not df_act.empty:
        carga = calcular_carga(df_act)
        p_path = generar_pdf(carga, datetime.now(), DATOS_MOCK)
        enviar_email(p_path)
        print("✅ Reporte enviado exitosamente usando archivos locales.")
    else:
        print("❌ No se encontraron archivos GPX en la carpeta /data.")
