import os, glob, json
import gpxpy
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

DATA_FOLDER = "data"

# --- DATOS BIOMÉTRICOS (Para el Dashboard) ---
BIO = {
    "hrv": 66,
    "sleep_score": 85,
    "sueño_fases": {"Profundo": 57, "Ligero": 279, "REM": 103, "Despierto": 7}
}

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
                    dist = track.length_2d()/1000
                    dur = track.get_duration()/60
                    reg.append({"Fecha": inicio.replace(tzinfo=None), "Distancia": dist, "Duracion": dur})
        except: continue
    return pd.DataFrame(reg).sort_values("Fecha")

def crear_dashboard():
    df = obtener_datos()
    if df.empty: return
    
    # Cálculos de Carga
    df["Carga"] = df["Duracion"]
    df["ATL"] = df["Carga"].ewm(span=7).mean()
    df["CTL"] = df["Carga"].ewm(span=42).mean()
    df["TSB"] = df["CTL"] - df["ATL"]

    # 1. Gráfico de Carga Interactivo
    fig_carga = go.Figure()
    fig_carga.add_trace(go.Scatter(x=df["Fecha"], y=df["CTL"], name="Fitness (CTL)", line=dict(color='#1f77b4', width=4)))
    fig_carga.add_trace(go.Scatter(x=df["Fecha"], y=df["TSB"], name="Balance (TSB)", fill='tozeroy', line=dict(color='#ff7f0e', width=0)))
    fig_carga.update_layout(template="plotly_dark", height=400, margin=dict(l=20, r=20, t=40, b=20))

    # 2. Dona de Sueño Interactiva
    fases = BIO['sueño_fases']
    fig_sleep = px.pie(names=list(fases.keys()), values=list(fases.values()), 
                 hole=0.7, color_discrete_sequence=['#4a90e2', '#74b9ff', '#a29bfe', '#ff7675'])
    fig_sleep.update_layout(template="plotly_dark", showlegend=False, height=300, margin=dict(l=0, r=0, t=0, b=0))
    fig_sleep.add_annotation(text=f"{BIO['sleep_score']}<br>Score", showarrow=False, font_size=20)

    # 3. Mapa de Calor Mensual
    df['DiaSemana'] = df['Fecha'].dt.day_name()
    df['Semana'] = df['Fecha'].dt.isocalendar().week
    dias_orden = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    heat_data = df.pivot_table(index='DiaSemana', columns='Semana', values='Distancia', aggfunc='sum').reindex(dias_orden).fillna(0)
    
    fig_heat = px.imshow(heat_data, labels=dict(x="Semana", y="Día", color="Km"),
                        color_continuous_scale="Viridis", text_auto=".1f")
    fig_heat.update_layout(template="plotly_dark", height=300, margin=dict(l=20, r=20, t=40, b=20))

    # --- GENERAR HTML FINAL ---
    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Garmin SaaS Elite - Camilo Gamboa</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ background-color: #000; color: #fff; font-family: 'Segoe UI', sans-serif; }}
            .card-saas {{ background: #111; border: 1px solid #333; border-radius: 15px; padding: 20px; margin-bottom: 20px; }}
            .stat-title {{ color: #888; font-size: 0.9rem; text-transform: uppercase; }}
            .stat-value {{ font-size: 1.8rem; font-weight: bold; color: #00d2ff; }}
            .badge-risk {{ padding: 5px 15px; border-radius: 20px; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="container py-4">
            <div class="d-flex justify-content-between align-items-center mb-4">
                <h1>📊 Camilo Gamboa <span class="text-muted" style="font-size: 1rem;">Atleta de Fondo</span></h1>
                <span class="badge bg-primary">Actualizado: {datetime.now().strftime('%d/%m %H:%M')}</span>
            </div>

            <div class="row">
                <div class="col-md-3"><div class="card-saas"><div class="stat-title">Fitness (CTL)</div><div class="stat-value">{df['CTL'].iloc[-1]:.1f}</div></div></div>
                <div class="col-md-3"><div class="card-saas"><div class="stat-title">HRV (VFC)</div><div class="stat-value">{BIO['hrv']} ms</div></div></div>
                <div class="col-md-3"><div class="card-saas"><div class="stat-title">Sueño</div><div class="stat-value">{BIO['sleep_score']}/100</div></div></div>
                <div class="col-md-3"><div class="card-saas"><div class="stat-title">Km Totales</div><div class="stat-value">{df['Distancia'].sum():.1f} km</div></div></div>
            </div>

            <div class="row">
                <div class="col-md-8">
                    <div class="card-saas">
                        <h5>Evolución de Carga y Forma Física</h5>
                        {fig_carga.to_html(full_html=False, include_plotlyjs='cdn')}
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="card-saas text-center">
                        <h5>Fases de Sueño</h5>
                        {fig_sleep.to_html(full_html=False, include_plotlyjs=False)}
                        <div class="mt-2 small text-muted">Profundo: {fases['Profundo']}m | REM: {fases['REM']}m</div>
                    </div>
                </div>
            </div>

            <div class="row">
                <div class="col-md-12">
                    <div class="card-saas">
                        <h5>Consistencia: Distribución de Km Semanales</h5>
                        {fig_heat.to_html(full_html=False, include_plotlyjs=False)}
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

if __name__ == "__main__":
    crear_dashboard()
