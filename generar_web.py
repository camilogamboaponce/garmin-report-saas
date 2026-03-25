import os, glob
import gpxpy
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

DATA_FOLDER = "data"

# --- DATOS BIOMÉTRICOS MOCK (v7.1) ---
BIO = {
    "hrv": 66,
    "sleep_score": 85,
    "sueño_fases": {"Profundo": 57, "Ligero": 279, "REM": 103, "Despierto": 7}
}

def format_dur(minutos):
    if minutos >= 60:
        return f"{int(minutos // 60)}h {int(minutos % 60)}m"
    return f"{int(minutos)}m"

def evaluar_riesgo(tsb, hrv):
    # Lógica de riesgo: TSB muy bajo o HRV bajo suben el riesgo
    if tsb < -20 or hrv < 55: return "Alto", "#ff4b2b"
    if tsb < -10: return "Medio", "#f9ca24"
    return "Bajo", "#6ab04c"

def obtener_datos():
    reg = []
    archivos = glob.glob(os.path.join(DATA_FOLDER, "*.gpx"))
    for archivo in archivos:
        try:
            with open(archivo, 'r') as f:
                gpx = gpxpy.parse(f)
            for track in gpx.tracks:
                inicio = track.get_time_bounds().start_time
                if inicio:
                    reg.append({"Fecha": inicio.replace(tzinfo=None), 
                                "Distancia": track.length_2d()/1000, 
                                "Duracion": track.get_duration()/60})
        except: continue
    return pd.DataFrame(reg).sort_values("Fecha")

def crear_dashboard():
    df = obtener_datos()
    if df.empty: return
    
    # Cálculos de Carga
    df["ATL"] = df["Duracion"].ewm(span=7).mean()
    df["CTL"] = df["Duracion"].ewm(span=42).mean()
    df["TSB"] = df["CTL"] - df["ATL"]
    
    riesgo_label, riesgo_color = evaluar_riesgo(df['TSB'].iloc[-1], BIO['hrv'])

    # 1. Gráfico de Carga (CTL/ATL/TSB)
    fig_carga = go.Figure()
    fig_carga.add_trace(go.Scatter(x=df["Fecha"], y=df["CTL"], name="Fitness (CTL)", line=dict(color='#00d2ff', width=4)))
    fig_carga.add_trace(go.Scatter(x=df["Fecha"], y=df["ATL"], name="Fatiga (ATL)", line=dict(color='#ff4b2b', width=2, dash='dot')))
    fig_carga.add_trace(go.Bar(x=df["Fecha"], y=df["TSB"], name="Balance (TSB)", marker_color='#6ab04c', opacity=0.5))
    fig_carga.update_layout(template="plotly_dark", height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="white"))

    # 2. Dona de Sueño (Horas/Minutos)
    fases_nombres = list(BIO['sueño_fases'].keys())
    fases_valores = list(BIO['sueño_fases'].values())
    labels_formateados = [format_dur(v) for v in fases_valores]
    
    fig_sleep = px.pie(names=fases_nombres, values=fases_valores, hole=0.7, 
                       color_discrete_sequence=['#4a90e2', '#74b9ff', '#a29bfe', '#ff7675'])
    fig_sleep.update_traces(text=labels_formateados, textinfo='text+percent')
    fig_sleep.update_layout(template="plotly_dark", showlegend=True, height=350, paper_bgcolor='rgba(0,0,0,0)', font=dict(color="white"))

    # 3. Mapa de Calor (Días en Español)
    dias_es = {'Monday': 'Lun', 'Tuesday': 'Mar', 'Wednesday': 'Mie', 'Thursday': 'Jue', 'Friday': 'Vie', 'Saturday': 'Sab', 'Sunday': 'Dom'}
    df['DiaSemana'] = df['Fecha'].dt.day_name().map(dias_es)
    df['Semana'] = df['Fecha'].dt.isocalendar().week
    
    heat_data = df.pivot_table(index='DiaSemana', columns='Semana', values='Distancia', aggfunc='sum').reindex(list(dias_es.values())).fillna(0)
    fig_heat = px.imshow(heat_data, color_continuous_scale="Viridis", text_auto=".1f")
    fig_heat.update_layout(template="plotly_dark", height=300, paper_bgcolor='rgba(0,0,0,0)', font=dict(color="white"))

    # HTML
    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Garmin SaaS Elite v7.1</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ background-color: #000; color: #fff; font-family: 'Inter', sans-serif; }}
            .section-box {{ background: #111; border: 1px solid #222; border-radius: 12px; padding: 25px; margin-bottom: 20px; }}
            .stat-card {{ background: #1a1a1a; border-radius: 8px; padding: 15px; text-align: center; border-left: 4px solid #00d2ff; }}
            .stat-label {{ color: #aaa; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; }}
            .stat-value {{ font-size: 1.6rem; font-weight: 800; color: #fff; display: block; }}
            .risk-badge {{ background: {riesgo_color}; color: #000; padding: 4px 12px; border-radius: 20px; font-weight: bold; font-size: 0.9rem; }}
            h2 {{ font-size: 1.2rem; color: #00d2ff; border-bottom: 1px solid #222; padding-bottom: 10px; margin-bottom: 20px; }}
        </style>
    </head>
    <body>
        <div class="container py-5">
            <div class="header mb-5 d-flex justify-content-between align-items-end">
                <div>
                    <h1 class="fw-bold mb-0">CAMILO GAMBOA</h1>
                    <p class="text-muted mb-0">SaaS de Rendimiento para Atletas de Fondo</p>
                </div>
                <div class="text-end">
                    <span class="text-muted small">Nivel de Riesgo de Lesión</span><br>
                    <span class="risk-badge">{riesgo_label}</span>
                </div>
            </div>

            <div class="section-box">
                <h2>1. BIOMETRÍA Y RECUPERACIÓN</h2>
                <div class="row align-items-center">
                    <div class="col-md-4">
                        <div class="stat-card mb-3" style="border-left-color: #a29bfe;">
                            <span class="stat-label">VFC / HRV Nocturno</span>
                            <span class="stat-value">{BIO['hrv']} ms</span>
                        </div>
                        <div class="stat-card" style="border-left-color: #74b9ff;">
                            <span class="stat-label">Puntuación de Sueño</span>
                            <span class="stat-value">{BIO['sleep_score']}/100</span>
                        </div>
                    </div>
                    <div class="col-md-8 text-center">
                        {fig_sleep.to_html(full_html=False, include_plotlyjs='cdn')}
                    </div>
                </div>
            </div>

            <div class="section-box">
                <h2>2. ESTADO DE FORMA (CTL / ATL / TSB)</h2>
                <div class="row g-3 mb-4">
                    <div class="col-md-4"><div class="stat-card"><span class="stat-label">Fitness (CTL)</span><span class="stat-value">{df['CTL'].iloc[-1]:.1f}</span></div></div>
                    <div class="col-md-4"><div class="stat-card" style="border-left-color: #ff4b2b;"><span class="stat-label">Fatiga (ATL)</span><span class="stat-value">{df['ATL'].iloc[-1]:.1f}</span></div></div>
                    <div class="col-md-4"><div class="stat-card" style="border-left-color: #6ab04c;"><span class="stat-label">Balance (TSB)</span><span class="stat-value">{df['TSB'].iloc[-1]:.1f}</span></div></div>
                </div>
                {fig_carga.to_html(full_html=False, include_plotlyjs=False)}
            </div>

            <div class="section-box">
                <h2>3. ANALÍTICA DE KILOMETRAJE</h2>
                <div class="text-center mb-3">
                    <span class="stat-label">Kilómetros Totales Acumulados</span>
                    <span class="stat-value" style="color: #6ab04c; font-size: 3rem;">{df['Distancia'].sum():.1f} km</span>
                </div>
                {fig_heat.to_html(full_html=False, include_plotlyjs=False)}
            </div>

            <footer class="text-center text-muted mt-5 small">
                Actualizado vía GitHub Actions: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
            </footer>
        </div>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

if __name__ == "__main__":
    crear_dashboard()
