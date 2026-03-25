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
from fpdf import FPDF
from dotenv import load_dotenv

# --- CONFIGURACIÓN ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

DATA_FOLDER = "data"
SUEÑO_RECOMENDADO_MIN = 480 

DATOS_DEL_DIA = {
    "hrv": 66,                
    "sleep_score": 85,
    "sleep_quality": "Bueno",
    "sueño_fases": {
        "profundo": 57,
        "ligero": 279,
        "rem": 103,
        "despierto": 7
    }
}

def format_duration(minutos):
    if minutos >= 60:
        h = int(minutos // 60)
        m = int(minutos % 60)
        return f"{h}h {m}m"
    return f"{int(minutos)}m"

def analizar_hrv(valor):
    if valor >= 65:
        return "Equilibrado", (0, 128, 0), "Sistema nervioso en equilibrio. Cuerpo listo para la intensidad."
    elif 55 <= valor < 65:
        return "Tendencia Equilibrada", (218, 165, 32), "Recuperación en curso. Evita esfuerzos máximos."
    else:
        return "Desequilibrado", (200, 0, 0), "Sistema nervioso desequilibrado. Prioriza descanso."

def evaluar_riesgo_lesion(tsb, hrv, sleep_score):
    puntos = 0
    if tsb < -15: puntos += 30
    if hrv < 55: puntos += 40
    if sleep_score < 75: puntos += 30
    posicion_linea = (puntos / 100) * 6
    if puntos >= 70: return "Alto", (200, 0, 0), posicion_linea
    if puntos >= 30: return "Medio", (218, 165, 32), posicion_linea
    return "Bajo", (0, 128, 0), posicion_linea

def generar_visuales(fases, carga_info, hrv_val, sleep_val):
    # 1. Dona de Sueño
    sizes = [fases['profundo'], fases['ligero'], fases['rem'], fases['despierto']]
    colors = ['#4a90e2', '#74b9ff', '#a29bfe', '#ff7675']
    fig, ax = plt.subplots(figsize=(4, 4))
    ax.pie(sizes, colors=colors, startangle=90, wedgeprops=dict(width=0.35))
    total_min = sum(sizes)
    ax.text(0, 0, f"{format_duration(total_min)}\nTotal", ha='center', va='center', fontsize=12, fontweight='bold')
    plt.savefig("sleep_chart.png", transparent=True, dpi=120, bbox_inches='tight'); plt.close()

    # 2. Mapa de Riesgo
    _, _, pos_linea = evaluar_riesgo_lesion(carga_info['tsb'], hrv_val, sleep_val)
    colors_list = ['#55af64', '#ffd966', '#f6b26b', '#cc0000']
    my_cmap = mcolors.LinearSegmentedColormap.from_list("risk", list(zip([0, 0.35, 0.65, 1], colors_list)))
    fig, ax = plt.subplots(figsize=(4, 0.6)) 
    ax.imshow(np.vstack((np.linspace(0, 1, 256), np.linspace(0, 1, 256))), aspect='auto', cmap=my_cmap, extent=[0, 6, 0, 1])
    ax.vlines(x=pos_linea, ymin=0, ymax=1, color='black', linewidth=3)
    ax.set_xlim(0, 6); ax.axis('off')
    plt.savefig("risk_heatmap.png", transparent=True, dpi=120, bbox_inches='tight', pad_inches=0); plt.close()

    # 3. Carga
    fig, ax = plt.subplots(figsize=(10, 6)) 
    ax.plot(carga_info['hist']["Fecha"], carga_info['hist']["CTL"], label="Fitness (CTL)", color='#1f77b4', linewidth=2.5)
    ax.fill_between(carga_info['hist']["Fecha"], carga_info['hist']["TSB"], color='#ffeaa7', alpha=0.5, label="Balance (TSB)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    plt.xticks(rotation=45); plt.legend(loc='upper left'); plt.grid(axis='y', alpha=0.2); plt.tight_layout()
    plt.savefig("load_chart.png", dpi=130, bbox_inches='tight'); plt.close()

def generar_pdf(carga, hoy, bio):
    generar_visuales(bio['sueño_fases'], carga, bio['hrv'], bio['sleep_score'])
    pdf = FPDF()
    pdf.add_page()
    
    # Header
    pdf.set_fill_color(26, 26, 26); pdf.rect(0, 0, 210, 35, 'F')
    pdf.set_text_color(255, 255, 255); pdf.set_font("Helvetica", "B", 24)
    pdf.cell(0, 15, "REPORTE DE ENTRENAMIENTO", ln=True, align="C")
    pdf.set_font("Helvetica", "", 11); pdf.cell(0, 5, f"Análisis Biométrico v6.1 | {hoy.strftime('%d/%m/%Y')}", ln=True, align="C")
    
    pdf.set_text_color(0, 0, 0); pdf.ln(25)
    
    # 1. SUEÑO
    pdf.set_font("Helvetica", "B", 14); pdf.cell(0, 10, "1. MÉTRICAS DE SUEÑO", ln=True)
    pdf.set_font("Helvetica", "", 11); pdf.set_x(15)
    total_min = sum(bio['sueño_fases'].values())
    pdf.cell(0, 8, f"Calidad: {bio['sleep_quality']} ({bio['sleep_score']}/100)  I  Duración: {format_duration(total_min)}", ln=True)
    
    pdf.set_font("Helvetica", "", 10) 
    for fase, valor in [("Profundo", bio['sueño_fases']['profundo']), ("Ligero", bio['sueño_fases']['ligero']), ("REM", bio['sueño_fases']['rem']), ("Despierto", bio['sueño_fases']['despierto'])]:
        pdf.set_x(15); pdf.cell(0, 6, f"{fase}: {format_duration(valor)}", ln=True)
    
    pdf.set_x(15); pdf.set_font("Helvetica", "B", 10); pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, f"Recomendación: {format_duration(SUEÑO_RECOMENDADO_MIN)}", ln=True)
    pdf.set_text_color(0, 0, 0); pdf.image("sleep_chart.png", x=130, y=52, w=45); pdf.ln(8)

    # 2. RIESGO
    label_h, col_h, cons_h = analizar_hrv(bio['hrv'])
    label_r, col_r, _ = evaluar_riesgo_lesion(carga['tsb'], bio['hrv'], bio['sleep_score'])
    
    pdf.set_font("Helvetica", "B", 14); pdf.cell(0, 10, "2. RECUPERACIÓN Y RIESGO DE LESIÓN", ln=True)
    pdf.set_x(15); pdf.set_font("Helvetica", "B", 11); pdf.set_text_color(*col_h)
    pdf.cell(0, 8, f"HRV: {label_h} ({bio['hrv']} ms)", ln=True)
    pdf.set_x(15); pdf.set_text_color(*col_r); pdf.cell(0, 8, f"Nivel de Riesgo: {label_r}", ln=True)
    
    pdf.ln(1); y_mapa = pdf.get_y()
    pdf.image("risk_heatmap.png", x=15, y=y_mapa, w=55)
    pdf.set_y(y_mapa + 12); pdf.set_text_color(0, 0, 0); pdf.ln(4)
    pdf.set_x(15); pdf.set_font("Helvetica", "", 10); pdf.multi_cell(0, 7, f"{cons_h}")
    pdf.ln(10)

    # 3. FORMA
    pdf.set_font("Helvetica", "B", 14); pdf.cell(0, 10, "3. ESTADO DE FORMA", ln=True)
    pdf.set_x(15); pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Fitness (CTL): {carga['ctl']:.1f}  I  Fatiga (ATL): {carga['atl']:.1f}  I  Balance (TSB): {carga['tsb']:.1f}", ln=True)
    
    pdf.ln(2); pdf.set_fill_color(242, 242, 242); pdf.set_x(15)
    pdf.set_font("Helvetica", "B", 10); pdf.cell(0, 8, " CONCLUSIÓN:", ln=True, fill=True)
    pdf.set_x(15); pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 7, f"Tu fitness de {carga['ctl']:.1f} indica una base sólida. Estás en {label_h.lower()}.", fill=True)
    
    pdf.ln(8); pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Proyecciones: 10K: 00:50:57  21K: 01:50:45  42K: 03:52:15", ln=True)
    pdf.image("load_chart.png", x=10, y=pdf.get_y()+2, w=190)

    out_path = f"reporte_{hoy.strftime('%Y%m%d')}.pdf"
    pdf.output(out_path); return out_path

def obtener_actividades():
    reg = []
    archivos = glob.glob(os.path.join(DATA_FOLDER, "*.gpx"))
    for archivo in archivos:
        try:
            with open(archivo, 'r') as f:
                gpx = gpxpy.parse(f)
            for track in gpx.tracks:
                inicio = track.get_time_bounds().start_time
                if inicio:
                    reg.append({"Fecha": inicio.replace(tzinfo=None), "Duracion": track.get_duration()/60})
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
    msg["Subject"] = f"Reporte de Entrenamiento v6.1 – {datetime.today().strftime('%d/%m/%Y')}"
    msg["From"] = os.getenv("GMAIL_EMAIL"); msg["To"] = os.getenv("GMAIL_TO")
    msg.set_content("Adjunto reporte v6.1 corregido.")
    with open(path, "rb") as f:
        msg.add_attachment(f.read(), maintype="application", subtype="pdf", filename=os.path.basename(path))
    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls(); s.login(os.getenv("GMAIL_EMAIL"), os.getenv("GMAIL_APP_PASSWORD"))
        s.send_message(msg)

if __name__ == "__main__":
    df = obtener_actividades()
    if not df.empty:
        res = calcular_carga(df)
        p = generar_pdf(res, datetime.now(), DATOS_DEL_DIA)
        enviar_email(p)
