import os, glob
import gpxpy
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

DATA_FOLDER = "data"

# --- DATOS BIOMÉTRICOS MOCK (v8.1) ---
BIO = {
    "hrv": 66,
    "sleep_score": 85,
    "sueño_fases": {"Profundo": 57, "Ligero": 279, "REM": 103, "Despierto": 7}
}

def format_dur(minutos):
    if minutos >= 60:
        h = int(minutos // 60)
        m = int(minutos % 60)
        return f"{h}h {m}m"
    return f"{int(minutos)}m"

def evaluar_riesgo(tsb, hrv):
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
                bounds = track.get_time_bounds()
                if bounds.start_time:
                    reg.append({"Fecha": bounds.start_time.replace(tzinfo=None), 
                                "Distancia": track.length_2d()/1000, 
                                "Duracion": track.get_duration()/60})
        except: continue
    return pd.DataFrame(reg).sort_values("Fecha") if reg else pd.DataFrame()

def crear_dashboard():
    df = obtener_datos()
    if df.empty:
        riesgo_label, riesgo_color, total_km = "N/A", "#888", 0.0
        ctl, atl, tsb = 0, 0, 0
    else:
        df["ATL"] = df["Duracion"].ewm(span=7, adjust=False).mean()
        df["CTL"] = df["Duracion"].ewm(span=42, adjust=False).mean()
        df["TSB"] = df["CTL"] - df["ATL"]
        ctl, atl, tsb = df["CTL"].iloc[-1], df["ATL"].iloc[-1], df["TSB"].iloc[-1]
        riesgo_label, riesgo_color = evaluar_riesgo(tsb, BIO['hrv'])
        total_km = df['Distancia'].sum()

    # CONFIGURACIÓN RESPONSIVA Y BLOQUEO DE ZOOM
    config_static = {
        'responsive': True, 
        'displayModeBar': False, 
        'scrollZoom': False,
        'staticPlot': False # Permite hover pero previene zoom accidental
    }

    # 1. Gráfico de Carga
    fig_carga = go.Figure()
    if not df.empty:
        fig_carga.add_trace(go.Scatter(x=df["Fecha"], y=df["CTL"], name="Fitness", line=dict(color='#00d2ff', width=3)))
        fig_carga.add_trace(go.Bar(x=df["Fecha"], y=df["TSB"], name="Balance", marker_color='#6ab04c', opacity=0.4))
    
    fig_carga.update_layout(
        template="plotly_dark", height=300, margin=dict(l=5, r=5, t=10, b=10),
        legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"),
        xaxis=dict(fixedrange=True, tickformat="%d/%m"), # fixedrange evita zoom
        yaxis=dict(fixedrange=True),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
    )

    # 2. Dona de Sueño
    fig_sleep = px.pie(names=list(BIO['sueño_fases'].keys()), values=list(BIO['sueño_fases'].values()), 
                       hole=0.7, color_discrete_sequence=['#4a90e2', '#74b9ff', '#a29bfe', '#ff7675'])
    fig_sleep.update_traces(textinfo='none')
    fig_sleep.update_layout(
        template="plotly_dark", height=280, margin=dict(l=10, r=10, t=10, b=10),
        showlegend=True, legend=dict(orientation="h", y=-0.2),
        paper_bgcolor='rgba(0,0,0,0)'
    )

    # 3. Mapa de Calor
    dias_es = {'Monday': 'Lun', 'Tuesday': 'Mar', 'Wednesday': 'Mie', 'Thursday': 'Jue', 'Friday': 'Vie', 'Saturday': 'Sab', 'Sunday': 'Dom'}
    if not df.empty:
        df['Dia'] = df['Fecha'].dt.day_name().map(dias_es)
        df['Sem'] = df['Fecha'].dt.isocalendar().week
        heat = df.pivot_table(index='Dia', columns='Sem', values='Distancia', aggfunc='sum').reindex(list(dias_es.values())).fillna(0)
        fig_heat = px.imshow(heat, color_continuous_scale="Viridis", text_auto=".1f")
        fig_heat.update_layout(template="plotly_dark", height=250, margin=dict(l=5, r=5, t=5, b=5), 
                               coloraxis_showscale=False, xaxis=dict(fixedrange=True), yaxis=dict(fixedrange=True))
        heat_html = fig_heat.to_html(full_html=False, include_plotlyjs=False, config=config_static)
    else:
        heat_html = "<p style='color:#666; padding:20px;'>Sin datos GPX</p>"

    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>Dashboard Camilo</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ background-color: #000; color: #fff; font-family: sans-serif; overflow-x: hidden; }}
            .box {{ background: #111; border: 1px solid #222; border-radius: 12px; padding: 15px; margin-bottom: 15px; }}
            .card-val {{ background: #1a1a1a; border-radius: 10px; padding: 10px; text-align: center; border-bottom: 3px solid #00d2ff; }}
            .lbl {{ color: #eee; font-size: 0.7rem; text-transform: uppercase; font-weight: bold; }}
            .val {{ font-size: 1.3rem; font-weight: 800; display: block; }}
            .badge-r {{ background: {riesgo_color}; color: #000; padding: 5px 12px; border-radius: 20px; font-weight: bold; font-size: 0.8rem; }}
            h2 {{ font-size: 0.9rem; color: #00d2ff; font-weight: bold; text-transform: uppercase; margin-bottom: 15px; border-bottom: 1px solid #222; }}
            .text-white {{ color: #ffffff !important; }}
        </style>
    </head>
    <body>
        <div class="container-fluid py-3">
            <div class="d-flex justify-content-between align-items-center mb-4 px-2">
                <h1 class="h4 fw-bold mb-0">CAMILO GAMBOA</h1>
                <div class="text-end">
                    <span class="text-white small d-block" style="font-size: 0.7rem;">RIESGO DE LESIÓN</span>
                    <span class="badge-r">{riesgo_label}</span>
                </div>
            </div>

            <div class="box">
                <h2>1. Biometría y Sueño</h2>
                <div class="row g-2 mb-3">
                    <div class="col-6"><div class="card-val" style="border-color:#a29bfe"><span class="lbl">VFC / HRV</span><span class="val">{BIO['hrv']} ms</span></div></div>
                    <div class="col-6"><div class="card-val" style="border-color:#74b9ff"><span class="lbl">Sueño</span><span class="val">{BIO['sleep_score']}/100</span></div></div>
                </div>
                {fig_sleep.to_html(full_html=False, include_plotlyjs='cdn', config=config_static)}
            </div>

            <div class="box">
                <h2>2. Carga y Forma</h2>
                <div class="row g-2 mb-3">
                    <div class="col-4"><div class="card-val"><span class="lbl">Fitness</span><span class="val">{ctl:.1f}</span></div></div>
                    <div class="col-4"><div class="card-val" style="border-color:#ff4b2b"><span class="lbl">Fatiga</span><span class="val">{atl:.1f}</span></div></div>
                    <div class="col-4"><div class="card-val" style="border-color:#6ab04c"><span class="lbl">Balance</span><span class="val">{tsb:.1f}</span></div></div>
                </div>
                {fig_carga.to_html(full_html=False, include_plotlyjs=False, config=config_static)}
            </div>

            <div class="box text-center">
                <h2>3. Kilometraje</h2>
                <div class="mb-2">
                    <span class="lbl text-white">Kilómetros Totales</span><br>
                    <span class="val" style="color:#6ab04c; font-size: 2.5rem;">{total_km:.1f} km</span>
                </div>
                {heat_html}
            </div>

            <footer class="text-center text-muted py-3" style="font-size: 0.6rem;">
                Actualizado: {datetime.now().strftime('%d/%m %H:%M')}
            </footer>
        </div>
    </body>
    </html>
    """
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

if __name__ == "__main__":
    crear_dashboard()
