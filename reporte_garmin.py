import os
import glob
import logging
import smtplib
from datetime import datetime
from email.message import EmailMessage

import gpxpy
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.colors as mcolors
import garth # Librería para la gestión de tokens
from fpdf import FPDF
from dotenv import load_dotenv
from garminconnect import Garmin

# --- CONFIGURACIÓN ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

FACTOR_21K, FACTOR_42K = 1.03, 1.08
DATA_FOLDER = "data"
SESSION_PATH = ".garth" # Carpeta donde se guardará tu sesión
SUEÑO_RECOMENDADO_MIN = 480 

# --- FUNCIÓN DE CONEXIÓN CON SESIÓN ---

def descargar_datos_garmin():
    print("🌐 Sincronizando con Garmin Connect...")
    user = os.getenv("GARMIN_USER")
    password = os.getenv("GARMIN_PASSWORD")
    
    client = Garmin(user, password)
    
    try:
        # 1. Intentar cargar sesión guardada para evitar login
        if os.path.exists(SESSION_PATH):
            print("🔑 Usando sesión guardada...")
            garth.resume(SESSION_PATH)
        else:
            # 2. Si no hay sesión, hacer login real y guardar
            print("🆕 Iniciando sesión nueva...")
            client.login()
            garth.dump(SESSION_PATH)
            print("✅ Sesión guardada para futuros usos.")

        hoy = datetime.now().strftime("%Y-%m-%d")
        sleep_data = client.get_sleep_data(hoy)
        hrv_data = client.get_hrv_data(hoy)
        
        dto = sleep_data['dailySleepDTO']
        return {
            "hrv": hrv_data['hrvSummary']['lastNightAvg'],
            "sleep_score": dto['sleepScore'],
            "sleep_quality": dto['sleepQualityTypeDTO']['qualityTypeKey'].capitalize(),
            "sueño_fases": {
                "profundo": dto['deepSleepSeconds'] // 60,
                "ligero": dto['lightSleepSeconds'] // 60,
                "rem": dto['remSleepSeconds'] // 60,
                "despierto": dto['awakeSleepSeconds'] // 60
            }
        }
    except Exception as e:
        if "429" in str(e):
            print("⚠️ Garmin ha bloqueado los intentos por ahora (Error 429).")
            print("👉 Espera 20 minutos o usa el internet de tu celular (Hotspot).")
        else:
            print(f"❌ Error: {e}")
        return None

# --- FUNCIONES DE APOYO ---

def format_duration(minutos):
    if minutos >= 60:
        h, m = minutos // 60, minutos % 60
        return f"{h}h {m}m"
    return f"{minutos}m"

def analizar_hrv(valor):
    if valor >= 65:
        return "Equilibrado", (0, 128, 0), "Sistema nervioso en equilibrio. Cuerpo listo para la intensidad planificada."
    elif 55 <= valor < 65:
        return "Tendencia Equilibrada", (218, 165, 32), "Recuperación en curso. Evita esfuerzos máximos."
    return "Desequilibrado", (200, 0, 0), "Sistema nervioso desequilibrado. Prioriza descanso o rodajes suaves."

def evaluar_riesgo_lesion(tsb, hrv, sleep_score):
    puntos = 0
    if tsb < -15: puntos += 30
    if hrv < 55: puntos += 40
    if sleep_score < 75: puntos += 30
    pos = (puntos / 100) * 6
    if puntos >= 70: return "Alto", (200, 0, 0), pos
    if puntos >= 30: return "Medio", (218, 165, 32), pos
    return "Bajo", (0, 128, 0), pos

# --- GENERACIÓN VISUAL ---

def generar_visuales(fases, carga_info, hrv_val, sleep_val):
    # Dona de Sueño
    sizes = [fases['profundo'], fases['ligero'], fases['rem'], fases['despierto']]
    colors = ['#4a90e2', '#74b9ff', '#a29bfe', '#ff7675']
    fig, ax = plt.subplots(figsize=(4, 4))
    ax.pie(sizes, colors=colors, startangle=90, wedgeprops=dict(width=0.35))
    total_min = sum(sizes)
    ax.text(0, 0, f"{format_duration(total_min)}\nTotal", ha='center', va='center', fontsize=12, fontweight='bold')
    plt.savefig("data/sleep_chart.png", transparent=True, dpi=120, bbox_inches='tight'); plt.close()

    # Mapa de Riesgo
    _, _, pos_linea = evaluar_riesgo_lesion(carga_info['tsb'], hrv_val, sleep_val)
    my_cmap = mcolors.LinearSegmentedColormap.from_list("rg", ['#55af64', '#ffd966', '#f6b26b', '#cc0000'])
    fig, ax = plt.subplots(figsize=(4, 0.6)) 
    gradient = np.vstack((np.linspace(0, 1, 256), np.linspace(0, 1, 256)))
    ax.imshow(gradient, aspect='auto', cmap=my_cmap, extent=[0, 6, 0, 1])
    ax.vlines(x=pos_linea, ymin=0, ymax=1, color='black', linewidth=3)
    ax.set_xlim(0, 6); ax.axis('off')
    plt.savefig("data/risk_heatmap.png", transparent=True, dpi=120, bbox_inches='tight', pad_inches=0); plt.close()

    # Gráfico de Carga (Margen extra para Mac)
    fig, ax = plt.subplots(figsize=(10, 7.5)) 
    ax.plot(carga_info['hist']["Fecha"], carga_info['hist']["CTL"], label="Fitness (CTL)", color='#1f77b4', linewidth=2.5)
    ax.fill_between(carga_info['hist']["Fecha"], carga_info['hist']["TSB"], color='#ffeaa7', alpha=0.5, label="Balance (TSB)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    plt.xticks(rotation=45, ha='right')
    plt.legend(loc='lower left'); plt.grid(axis='y', alpha=0.2)
    plt.tight_layout(); plt.subplots_adjust(bottom=0.55)
    plt.savefig("data/load_chart.png", dpi=130, bbox_inches='tight'); plt.close()

# --- GENERACIÓN PDF ---

def generar_pdf(carga, pred, hoy, bio):
    generar_visuales(bio['sueño_fases'], carga, bio['hrv'], bio['sleep_score'])
    pdf = FPDF()
    pdf.add_page()
    
    # Header
    pdf.set_fill_color(26, 26, 26); pdf.rect(0, 0, 210, 35, 'F')
    pdf.set_text_color(255, 255, 255); pdf.set_font("Helvetica", "B", 24)
    pdf.cell(0, 15, "REPORTE DE ENTRENAMIENTO", ln=True, align="C")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 5, f"Análisis Biométrico y de Carga | {hoy.strftime('%d/%m/%Y')}", ln=True, align="C")
    
    pdf.set_text_color(0, 0, 0); pdf.ln(25)
    
    # 1. MÉTRICAS DE SUEÑO
    pdf.set_font("Helvetica", "B", 14); pdf.cell(0, 10, "1. MÉTRICAS DE SUEÑO", ln=True)
    pdf.set_font("Helvetica", "", 11); pdf.set_x(15)
    total_min = sum(bio['sueño_fases'].values())
    pdf.cell(0, 8, f"Calidad: {bio['sleep_quality']} ({bio['sleep_score']}/100)  I  Duración: {format_duration(total_min)}", ln=True)
    
    pdf.set_font("Helvetica", "", 10) 
    f = bio['sueño_fases']
    for fase, valor in [("Profundo", f['profundo']), ("Ligero", f['ligero']), ("REM", f['rem']), ("Despierto", f['despierto'])]:
        pdf.set_x(15); pdf.cell(0, 6, f"{fase}: {format_duration(valor)}", ln=True)
    
    pdf.set_x(15); pdf.set_font("Helvetica", "B", 10); pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, f"Recomendación: {format_duration(SUEÑO_RECOMENDADO_MIN)}", ln=True)
    pdf.image("data/sleep_chart.png", x=130, y=52, w=45); pdf.ln(8)

    # 2. RECUPERACIÓN Y RIESGO
    label_h, col_h, cons_h = analizar_hrv(bio['hrv'])
    label_r, col_r, _ = evaluar_riesgo_lesion(carga['tsb'], bio['hrv'], bio['sleep_score'])
    
    pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", "B", 14); pdf.cell(0, 10, "2. RECUPERACIÓN Y RIESGO DE LESIÓN", ln=True)
    pdf.set_x(15); pdf.set_font("Helvetica", "B", 11); pdf.set_text_color(*col_h)
    pdf.cell(0, 8, f"HRV: {label_h} ({bio['hrv']} ms)", ln=True)
    pdf.set_x(15); pdf.set_text_color(*col_r)
    pdf.cell(0, 8, f"Nivel de Riesgo: {label_r}", ln=True)
    
    pdf.ln(1); y_mapa = pdf.get_y()
    pdf.image("data/risk_heatmap.png", x=15, y=y_mapa, w=55)
    pdf.set_y(y_mapa + 12); pdf.set_text_color(0, 0, 0); pdf.ln(4)
    pdf.set_x(15); pdf.set_font("Helvetica", "", 10); pdf.multi_cell(0, 7, f"{cons_h}"); pdf.ln(10)

    # 3. ESTADO DE FORMA
    pdf.set_font("Helvetica", "B", 14); pdf.cell(0, 10, "3. ESTADO DE FORMA", ln=True)
    pdf.set_x(15); pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Fitness (CTL): {carga['ctl']:.1f}  I  Fatiga (ATL): {carga['atl']:.1f}  I  Balance (TSB): {carga['tsb']:.1f}", ln=True)
    pdf.ln(2); pdf.set_fill_color(242, 242, 242); pdf.set_x(15); pdf.set_font("Helvetica", "B", 10); pdf.cell(0, 8, " CONCLUSIÓN:", ln=True, fill=True)
    pdf.set_x(15); pdf.set_font("Helvetica", "", 10)
    concl = f"Tu fitness (CTL) de {carga['ctl']:.1f} indica una base sólida. Con un TSB de {carga['tsb']:.1f}, estás en {label_h.lower()} con tu sistema nervioso."
    pdf.multi_cell(0, 7, concl, fill=True)
    
    # 4. PROYECCIONES
    if pdf.get_y() > 180: pdf.add_page()
    pdf.ln(8); pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, f"Proyecciones: 10K: {pred['10k']}  21K: {pred['21k']}  42K: {pred['42k']}", ln=True)
    pdf.image("data/load_chart.png", x=10, y=pdf.get_y()+2, w=190)

    out_path = f"data/reporte_{hoy.strftime('%Y%m%d')}.pdf"
    pdf.output(out_path); return out_path

# --- PROCESAMIENTO GPX ---

def obtener_actividades(carpeta):
    reg = []
    archivos = glob.glob(os.path.join(carpeta, "*.gpx"))
    for archivo in archivos:
        try:
            with open(archivo, 'r') as f:
                gpx = gpxpy.parse(f)
            for track in gpx.tracks:
                bounds = track.get_time_bounds()
                if not bounds.start_time: continue
                dist, dur = track.length_2d()/1000, track.get_duration()/60
                reg.append({"Fecha": bounds.start_time.replace(tzinfo=None), "Duracion": dur})
        except: continue
    return pd.DataFrame(reg).sort_values("Fecha") if reg else pd.DataFrame()

def calcular_carga(df):
    hist = df.groupby(df["Fecha"].dt.date)["Duracion"].sum().reset_index()
    hist.columns = ["Fecha", "Carga"]; hist["Fecha"] = pd.to_datetime(hist["Fecha"])
    hist["ATL"] = hist["Carga"].ewm(span=7, adjust=False).mean()
    hist["CTL"] = hist["Carga"].ewm(span=42, adjust=False).mean()
    hist["TSB"] = hist["CTL"] - hist["ATL"]
    return {"atl": hist["ATL"].iloc[-1], "ctl": hist["CTL"].iloc[-1], "tsb": hist["TSB"].iloc[-1], "hist": hist}

def enviar_email(path):
    msg = EmailMessage()
    msg["Subject"] = f"Reporte Garmin Sincronizado – {datetime.today().strftime('%d/%m/%Y')}"
    msg["From"], msg["To"] = os.getenv("GMAIL_EMAIL"), os.getenv("GMAIL_TO")
    msg.set_content("Reporte v7.1 con sesión persistente y sangrías corregidas.")
    with open(path, "rb") as f:
        msg.add_attachment(f.read(), maintype="application", subtype="pdf", filename=os.path.basename(path))
    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls(); s.login(os.getenv("GMAIL_EMAIL"), os.getenv("GMAIL_APP_PASSWORD"))
        s.send_message(msg)

# --- MAIN ---

if __name__ == "__main__":
    print("--- 🏁 INICIANDO REPORTE v7.1 ---")
    hoy_dt = datetime.now()
    if not os.path.exists("data"): os.makedirs("data")
    
    DATOS_REALES = descargar_datos_garmin()
    
    if DATOS_REALES:
        df_act = obtener_actividades(DATA_FOLDER)
        if not df_act.empty:
            carga = calcular_carga(df_act)
            preds = {"10k": "00:50:57", "21k": "01:50:45", "42k": "03:52:15"}
            p_path = generar_pdf(carga, preds, hoy_dt, DATOS_REALES)
            try:
                enviar_email(p_path)
                print("✅ ¡Éxito! Reporte enviado.")
            except Exception as e: print(f"❌ Error email: {e}")
