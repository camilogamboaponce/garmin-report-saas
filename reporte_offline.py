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

# Simulación de Biometría (Para que no esté vacío)
BIO = {"hrv": 68, "sleep": 85, "status": "Óptimo"}

def format_duration(minutos):
    return f"{int(minutos // 60)}h {int(minutos % 60)}m"

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
    hist = df.groupby(df["Fecha"].dt.date).agg({"Duracion": "sum", "Distancia": "sum"}).reset_index()
    hist.columns = ["Fecha", "Carga", "Distancia"]
    hist["Fecha"] = pd.to_datetime(hist["Fecha"])
    hist["ATL"] = hist["Carga"].ewm(span=7, adjust=False).mean()
    hist["CTL"] = hist["Carga"].ewm(span=42, adjust=False).mean()
    hist["TSB"] = hist["CTL"] - hist["ATL"]
    return {"atl": hist["ATL"].iloc[-1], "ctl": hist["CTL"].iloc[-1], "tsb": hist["TSB"].iloc[-1], "hist": hist, "total_km": hist["Distancia"].sum()}

def generar_pdf(carga, df_last):
    pdf = FPDF()
    pdf.add_page()
    
    # Encabezado Estilo "SaaS"
    pdf.set_fill_color(31, 119, 180) # Azul Garmin
    pdf.rect(0, 0, 210, 40, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 24)
    pdf.cell(0, 20, "DASHBOARD DEL ATLETA", ln=True, align="C")
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 5, f"Fecha del Reporte: {datetime.now().strftime('%d/%m/%Y')}", ln=True, align="C")
    
    # Sección 1: Métricas de Carga
    pdf.ln(20)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "B", 16); pdf.cell(0, 10, "Estado de Forma y Carga", ln=True)
    
    # Cuadros de métricas
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(60, 20, f"Fitness (CTL): {carga['ctl']:.1f}", 1, 0, 'C', True)
    pdf.cell(60, 20, f"Fatiga (ATL): {carga['atl']:.1f}", 1, 0, 'C', True)
    
    # Color del Balance (TSB)
    tsb = carga['tsb']
    if tsb < -15: pdf.set_fill_color(255, 200, 200) # Rojo
    elif tsb > 5: pdf.set_fill_color(200, 255, 200) # Verde
    else: pdf.set_fill_color(255, 255, 200) # Amarillo
    pdf.cell(60, 20, f"Balance (TSB): {tsb:.1f}", 1, 1, 'C', True)

    # Gráfico de Carga
    plt.figure(figsize=(10, 4))
    plt.plot(carga['hist']["Fecha"], carga['hist']["CTL"], label="Fitness (Forma)", color='#1f77b4', lw=3)
    plt.fill_between(carga['hist']["Fecha"], carga['hist']["TSB"], color='#ff7f0e', alpha=0.3, label="Balance (Fresco/Cansado)")
    plt.grid(alpha=0.3); plt.legend()
    plt.savefig("load.png", dpi=100, bbox_inches='tight')
    pdf.image("load.png", x=10, y=pdf.get_y()+5, w=190)
    
    # Sección 2: Últimas Actividades
    pdf.ln(75)
    pdf.set_font("Helvetica", "B", 16); pdf.cell(0, 10, "Últimos Entrenamientos (GPX)", ln=True)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(60, 10, "Fecha", 1); pdf.cell(60, 10, "Distancia", 1); pdf.cell(60, 10, "Duración", 1, 1)
    pdf.set_font("Helvetica", "", 10)
    
    for _, row in df_last.tail(3).iterrows():
        pdf.cell(60, 10, row['Fecha'].strftime('%d/%m %H:%M'), 1)
        pdf.cell(60, 10, f"{row['Distancia']:.2f} km", 1)
        pdf.cell(60, 10, format_duration(row['Duracion']), 1, 1)

    path = "reporte_atleta.pdf"
    pdf.output(path)
    return path

def enviar_email(path):
    msg = EmailMessage()
    msg["Subject"] = f"🏃 Reporte de Rendimiento – {datetime.today().strftime('%d/%m')}"
    msg["From"] = os.getenv("GMAIL_EMAIL")
    msg["To"] = os.getenv("GMAIL_TO")
    msg.set_content("Adjunto encuentras el análisis de carga basado en tus archivos locales.")
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
