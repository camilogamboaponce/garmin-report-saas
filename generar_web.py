import os, glob
import gpxpy
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

DATA_FOLDER = "data"

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
                    reg.append({"Fecha": inicio, "Distancia": dist, "Duracion": dur})
        except: continue
    return pd.DataFrame(reg).sort_values("Fecha")

def crear_dashboard():
    df = obtener_datos()
    if df.empty: return
    
    # Cálculos de Carga (CTL/TSB)
    df["Carga"] = df["Duracion"]
    df["ATL"] = df["Carga"].ewm(span=7).mean()
    df["CTL"] = df["Carga"].ewm(span=42).mean()
    df["TSB"] = df["CTL"] - df["ATL"]

    # --- GRÁFICO INTERACTIVO ---
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["Fecha"], y=df["CTL"], name="Fitness (CTL)", line=dict(color='#1f77b4', width=3)))
    fig.add_trace(go.Bar(x=df["Fecha"], y=df["TSB"], name="Balance (TSB)", marker_color='#ff7f0e', opacity=0.4))
    
    fig.update_layout(
        title="Dashboard de Rendimiento - Camilo Gamboa",
        template="plotly_dark",
        xaxis_title="Fecha",
        yaxis_title="Puntos de Carga",
        hovermode="x unified"
    )

    # --- GENERAR HTML ---
    html_content = f"""
    <html>
    <head>
        <title>Garmin SaaS Dashboard</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ background-color: #121212; color: white; padding: 20px; }}
            .card {{ background-color: #1e1e1e; border: none; margin-bottom: 20px; }}
            .stat-val {{ font-size: 2rem; font-weight: bold; color: #1f77b4; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1 class="mb-4">🏃 Rendimiento Elite</h1>
            <div class="row">
                <div class="col-md-4"><div class="card p-3"><span>Fitness (CTL)</span><div class="stat-val">{df['CTL'].iloc[-1]:.1f}</div></div></div>
                <div class="col-md-4"><div class="card p-3"><span>Balance (TSB)</span><div class="stat-val">{df['TSB'].iloc[-1]:.1f}</div></div></div>
                <div class="col-md-4"><div class="card p-3"><span>Total KM</span><div class="stat-val">{df['Distancia'].sum():.1f}</div></div></div>
            </div>
            <div class="card p-3">
                {fig.to_html(full_html=False, include_plotlyjs='cdn')}
            </div>
            <p class="text-muted">Última actualización: {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
        </div>
    </body>
    </html>
    """
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

if __name__ == "__main__":
    crear_dashboard()
