import os, glob
import gpxpy
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

DATA_FOLDER = "data"

# --- DATOS BIOMÉTRICOS ---
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
    puntos = 0
    if tsb < -15: puntos += 40
    if hrv < 55: puntos += 40
    # Retorna % de riesgo para el gradiente
    return min(puntos + 10, 100) 

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
    hoy = datetime.now()
    
    if df.empty:
        ctl, atl, tsb, total_km, riesgo_pct = 0, 0, 0, 0, 10
        df_semana = pd.DataFrame()
    else:
        df["ATL"] = df["Duracion"].ewm(span=7, adjust=False).mean()
        df["CTL"] = df["Duracion"].ewm(span=42, adjust=False).mean()
        df["TSB"] = df["CTL"] - df["ATL"]
        ctl, atl, tsb = df["CTL"].iloc[-1], df["ATL"].iloc[-1], df["TSB"].iloc[-1]
        riesgo_pct = evaluar_riesgo(tsb, BIO['hrv'])
        total_km = df['Distancia'].sum()
        
        # Filtrar solo semana actual para el gráfico de barras
        inicio_semana = hoy - timedelta(days=hoy.weekday())
        df_semana = df[df['Fecha'] >= inicio_semana.replace(hour=0, minute=0)]

    config_static = {'responsive': True, 'displayModeBar': False, 'scrollZoom': False}

    # 1. Gráfico de Rendimiento (Líneas + Fechas)
    fig_perf = go.Figure()
    if not df.empty:
        fig_perf.add_trace(go.Scatter(x=df["Fecha"], y=df["CTL"], name="Fitness", line=dict(color='#00d2ff', width=3)))
        fig_perf.add_trace(go.Scatter(x=df["Fecha"], y=df["ATL"], name="Fatiga", line=dict(color='#ff4b2b', width=2, dash='dot')))
        fig_perf.add_trace(go.Scatter(x=df["Fecha"], y=df["TSB"], name="Balance", line=dict(color='#6ab04c', width=2)))
    
    fig_perf.update_layout(
        template="plotly_dark", height=300, margin=dict(l=5, r=5, t=10, b=10),
        legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"),
        xaxis=dict(fixedrange=True, tickformat="%d/%m", nticks=10),
        yaxis=dict(fixedrange=True),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
    )

    # 2. Dona de Sueño (Limpieza de Labels)
    fases = BIO['sueño_fases']
    total_sueño = sum(fases.values())
    labels_clean = [format_dur(v) for v in fases.values()]
    
    fig_sleep = go.Figure(data=[go.Pie(
        labels=list(fases.keys()), 
        values=list(fases.values()),
        hole=0.7,
        text=labels_clean,
        textinfo='text',
        hovertemplate="<b>%{label}</b><br>Tiempo: %{text}<extra></extra>",
        marker=dict(colors=['#4a90e2', '#74b9ff', '#a29bfe', '#ff7675'])
    )])
    
    fig_sleep.update_layout(
        template="plotly_dark", height=280, margin=dict(l=10, r=10, t=10, b=10),
        showlegend=True, legend=dict(orientation="h", y=-0.2),
        paper_bgcolor='rgba(0,0,0,0)',
        annotations=[dict(text=f"Total<br>{format_dur(total_sueño)}", x=0.5, y=0.5, font_size=18, showarrow=False, font_color="white")]
    )

    # 3. Kilometraje de la Semana
    fig_km = go.Figure()
    if not df_semana.empty:
        fig_km.add_trace(go.Bar(x=df_semana["Fecha"], y=df_semana["Distancia"], marker_color='#6ab04c'))
    
    fig_km.update_layout(
        template="plotly_dark", height=200, margin=dict(l=5, r=5, t=5, b=5),
        xaxis=dict(fixedrange=True, tickformat="%a"), 
        yaxis=dict(fixedrange=True, title="Km"),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
    )

    # HTML
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
            .lbl {{ color: #ffffff; font-size: 0.7rem; text-transform: uppercase; font-weight: bold; }}
            .val {{ font-size: 1.3rem; font-weight: 800; display: block; }}
            h2 {{ font-size: 0.9rem; color: #00d2ff; font-weight: bold; text-transform: uppercase; margin-bottom: 15px; border-bottom: 1px solid #222; }}
            
            /* Mapa de Riesgo Difuminado */
            .risk-container {{ width: 100%; height: 12px; background: linear-gradient(to right, #6ab04c, #f9ca24, #ff4b2b); border-radius: 10px; position: relative; margin-top: 10px; }}
            .risk-pointer {{ width: 4px; height: 20px; background: #fff; position: absolute; top: -4px; left: {riesgo_pct}%; border-radius: 2px; box-shadow: 0 0 5px #fff; }}
        </style>
    </head>
    <body>
        <div class="container-fluid py-3">
            <div class="d-flex justify-content-between align-items-center mb-4 px-2">
                <h1 class="h4 fw-bold mb-0">CAMILO GAMBOA</h1>
                <div class="text-end" style="width: 120px;">
                    <span class="lbl">RIESGO DE LESIÓN</span>
                    <div class="risk-container"><div class="risk-pointer"></div></div>
                </div>
            </div>

            <div class="box">
                <h2>1. Biometría y Sueño</h2>
                <div class="row g-2 mb-3">
                    <div class="col-6"><div class="card-val" style="border-color:#a29bfe"><span class="lbl">VFC / HRV</span><span class="val">{BIO['hrv']} ms</span></div></div>
                    <div class="col-6"><div class="card-val" style="border-color:#74b9ff"><span class="lbl">Puntaje</span><span class="val">{BIO['sleep_score']}/100</span></div></div>
                </div>
                {fig_sleep.to_html(full_html=False, include_plotlyjs='cdn', config=config_static)}
            </div>

            <div class="box">
                <h2>2. Rendimiento y Carga</h2>
                <div class="row g-2 mb-3">
                    <div class="col-4"><div class="card-val"><span class="lbl">Fitness</span><span class="val">{ctl:.1f}</span></div></div>
                    <div class="col-4"><div class="card-val" style="border-color:#ff4b2b"><span class="lbl">Fatiga</span><span class="val">{atl:.1f}</span></div></div>
                    <div class="col-4"><div class="card-val" style="border-color:#6ab04c"><span class="lbl">Balance</span><span class="val">{tsb:.1f}</span></div></div>
                </div>
                {fig_perf.to_html(full_html=False, include_plotlyjs=False, config=config_static)}
            </div>

            <div class="box text-center">
                <h2>3. Kilómetros Semanales</h2>
                <div class="mb-3">
                    <span class="lbl">Total Acumulado</span><br>
                    <span class="val" style="color:#6ab04c; font-size: 2.2rem;">{total_km:.1f} km</span>
                </div>
                {fig_km.to_html(full_html=False, include_plotlyjs=False, config=config_static)}
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
