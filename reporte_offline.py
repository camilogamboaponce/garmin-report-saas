import os, glob, smtplib
from datetime import datetime
from email.message import EmailMessage
import gpxpy
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from fpdf import FPDF
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = os.getcwd()
DATA_FOLDER = os.path.join(BASE_DIR, "data")

# --- BIOMETRÍA SIMULADA ---
BIO = {"hrv": 68, "sleep": 85, "fases": {"profundo": 90, "ligero": 320, "rem": 110, "despierto": 15}}

def format_duration(minutos):
    h, m = int(minutos // 60), int(minutos % 60)
    return f"{h}h {m}m" if h > 0 else f"{m}m"

def obtener_actividades():
    reg = []
    archivos = glob.glob(os.path.join(DATA_FOLDER, "*.gpx"))
    for archivo in archivos:
        try:
            with open(archivo, 'r') as f:
                gpx = gpxpy.parse(f)
            for track in gpx.tracks:
                bounds = track.get_time_bounds()
                if bounds.start_time:
                    dist = track.get_moving_data().moving_distance / 1000
                    dur = track.get_duration() / 60
                    reg.append({"Fecha": bounds.start_time.replace(tzinfo=None), "Distancia": dist, "Duracion": dur})
        except: continue
    return pd.DataFrame(reg).sort_values("Fecha") if reg else pd.DataFrame()

def calcular_carga(df):
    hist = df.groupby(df["Fecha"].dt.date).agg({"Duracion": "sum"}).reset_index()
    hist.columns = ["Fecha", "Carga"]
    hist["Fecha"] = pd.to_datetime(hist["Fecha"])
    hist["ATL"] = hist["Carga"].ewm(span=7, adjust=False).mean()
    hist["CTL"] = hist["Carga"].ewm(span=42, adjust=False).mean()
    hist["TSB"] = hist["CTL"] - hist["ATL"]
    return {"atl": hist["ATL"].iloc[-1], "ctl": hist["CTL"].iloc[-1], "tsb": hist["TSB"].iloc[-1], "hist": hist}

def generar_visuales(carga_info):
    # Dona de Sueño (Como el original)
    fases = BIO['fases']
    sizes = [fases['profundo'], fases['ligero'], fases['rem'], fases['despierto']]
    colors = ['#4a90e2', '#74b9ff', '#a29bfe', '#ff7675']
    fig, ax = plt.subplots(figsize=(4, 4))
    ax.pie(sizes, colors=colors, startangle=90, wedgeprops=dict(width=0.3))
    total_min = sum(sizes)
    ax.text(0, 0, f"{format_duration(total_min)}\nTotal", ha='center', va='center', fontsize=12, fontweight='bold')
    plt.savefig("sleep_chart.png", transparent=True, dpi=100, bbox_inches='tight')
    plt.close()

    # Gráfico de Carga (Como el original)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(carga_info['hist']["Fecha"], carga_info['hist']["CTL"], label="Fitness (CTL)", color='#1f77b4', lw=2)
    ax.fill_between(carga_info['hist']["Fecha"], carga_info['hist']["TSB"], color='#ffeaa7', alpha=0.4, label="Balance (TSB)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    plt.grid(alpha=0.2); plt.legend()
    plt.savefig("load_chart.png", dpi=100, bbox_inches='tight')
    plt.close()

def generar_pdf(carga, df_last):
    generar_visuales(carga)
    pdf = FPDF()
    pdf.add_page()
    
    # Título principal
    pdf.set_font("Helvetica", "B", 22)
    pdf.cell(0, 20, "REPORTE DE RENDIMIENTO", ln=True, align="C")
    
    # Bloque Biometría (Izquierda) + Dona (Derecha)
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 14); pdf.cell(0, 10, "Métricas Biométricas (Simuladas):", ln=True)
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 7, f"HRV: {BIO['hrv']} ms  |  Sueño: {BIO['sleep']}/100", ln=True)
    pdf.image("sleep_chart.png", x=145, y=30, w=45) # Posición original
    
    # Análisis de Carga
    pdf.ln(15)
    pdf.set_font("Helvetica", "B", 14); pdf.cell(0, 10, "Análisis de Carga (GPX Locales):", ln=True)
    pdf.set_font("Helvetica", "", 12)
    
    # Balance con color
    pdf.write(7, f"Fitness (CTL): {carga['ctl']:.1f} | ")
    tsb = carga['tsb']
    if tsb < -15: pdf.set_text_color(200, 0, 0)
    elif tsb > 5: pdf.set_text_color(0, 128, 0)
    pdf.write(7, f"Balance (TSB): {tsb:.1f}")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(10)
    
    # Imagen del gráfico
    pdf.image("load_chart.png", x=10, y=pdf.get_y(), w=190)
    
    # Tabla de últimas actividades (Abajo para que no se cruce)
    pdf.set_y(175)
    pdf.set_font("Helvetica", "B", 14); pdf.cell(0, 10, "Últimos Entrenamientos:", ln=True)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(60, 8, "Fecha", 1, 0, 'C', True); pdf.cell(60, 8, "Distancia", 1, 0, 'C', True); pdf.cell(60, 8, "Duración", 1, 1, 'C', True)
    
    pdf.set_font("Helvetica", "", 10)
    for _, row in df_last.tail(3).iterrows():
        pdf.cell(60, 8, row['Fecha'].strftime('%d/%m %H:%M'), 1, 0, 'C')
        pdf.cell(60, 8, f"{row['Distancia']:.2f} km", 1, 0, 'C')
        pdf.cell(60, 8, format_duration(row['Duracion']), 1, 1, 'C')

    path = "reporte_atleta_fondo.pdf"
    pdf.output(path)
    return path

def enviar_email(path):
    msg = EmailMessage()
    msg["Subject"] = f"🏃 Reporte Actualizado – {datetime.today().strftime('%d/%m')}"
    msg["From"] = os.getenv("GMAIL_EMAIL")
    msg["To"] = os.getenv("GMAIL_TO")
    msg.set_content("Reporte generado con éxito. Estética corregida.")
    with open(path, "rb") as f:
        msg.add_attachment(f.read(), maintype="application", subtype="pdf", filename=path)
    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls()
        s.login(os.getenv("GMAIL_EMAIL"), os.getenv("GMAIL_APP_PASSWORD"))
        s.send_message(msg)

if __name__ == "__main__":
    df = obtener_actividades()
    if not df.empty:
        carga = calcular_carga(df)
        p = generar_pdf(carga, df)
        enviar_email(p)
