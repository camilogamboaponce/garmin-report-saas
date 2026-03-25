import os, glob
import gpxpy
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

DATA_FOLDER = "data"

# --- DATOS BIOMÉTRICOS MOCK (v8.0 Legible y Responsivo) ---
# En el futuro, estos datos vendrán de Garmin Connect.
BIO = {
    "hrv": 66,
    "sleep_score": 85,
    "sueño_fases": {"Profundo": 57, "Ligero": 279, "REM": 103, "Despierto": 7}
}

def format_dur(minutos):
    """Formatea minutos en 'Xh Ym' o 'Ym'."""
    if minutos >= 60:
        h = int(minutos // 60)
        m = int(minutos % 60)
        return f"{h}h {m}m"
    return f"{int(minutos)}m"

def evaluar_riesgo(tsb, hrv):
    """Evalúa el riesgo de lesión según TSB y HRV."""
    # Lógica: TSB muy negativo o HRV bajo aumentan el riesgo
    if tsb < -20 or hrv < 55: return "Alto", "#ff4b2b" # Rojo
    if tsb < -10: return "Medio", "#f9ca24" # Amarillo
    return "Bajo", "#6ab04c" # Verde

def obtener_datos():
    """Lee y procesa los archivos GPX de la carpeta data."""
    reg = []
    archivos = glob.glob(os.path.join(DATA_FOLDER, "*.gpx"))
    if not archivos:
        return pd.DataFrame()
    
    for archivo in archivos:
        try:
            with open(archivo, 'r') as f:
                gpx = gpxpy.parse(f)
            for track in gpx.tracks:
                bounds = track.get_time_bounds()
                inicio = bounds.start_time
                if inicio:
                    dist = track.length_2d()/1000 # km
                    dur = track.get_duration()/60 # min
                    reg.append({"Fecha": inicio.replace(tzinfo=None), 
                                "Distancia": dist, 
                                "Duracion": dur})
        except Exception as e:
            print(f"Error procesando {archivo}: {e}")
            continue
    return pd.DataFrame(reg).sort_values("Fecha") if reg else pd.DataFrame()

def crear_dashboard():
    """Genera el archivo HTML del Dashboard."""
    print("--- 🏁 GENERANDO DASHBOARD INTERACTIVO ---")
    df = obtener_datos()
    if df.empty:
        print("❌ No se encontraron datos GPX. El dashboard estará incompleto.")
        riesgo_label, riesgo_color = "N/A", "#888"
        total_km = 0
    else:
        # Cálculos de Carga y Forma Física
        df["ATL"] = df["Duracion"].ewm(span=7, adjust=False).mean()
        df["CTL"] = df["Duracion"].ewm(span=42, adjust=False).mean()
        df["TSB"] = df["CTL"] - df["ATL"]
        
        riesgo_label, riesgo_color = evaluar_riesgo(df['TSB'].iloc[-1], BIO['hrv'])
        total_km = df['Distancia'].sum()

    # --- CONFIGURACIÓN DE GRÁFICOS RESPONSIVOS ---
    # Ocultamos la barra de herramientas para móviles (ModeBar)
    config_resp = {'responsive': True, 'displayModeBar': False}

    # 1. Gráfico de Carga (CTL/ATL/TSB)
    fig_carga = go.Figure()
    if not df.empty:
        fig_carga.add_trace(go.Scatter(x=df["Fecha"], y=df["CTL"], name="Fitness (CTL)", line=dict(color='#00d2ff', width=4)))
        fig_carga.add_trace(go.Scatter(x=df["Fecha"], y=df["ATL"], name="Fatiga (ATL)", line=dict(color='#ff4b2b', width=1.5, dash='dot')))
        fig_carga.add_trace(go.Bar(x=df["Fecha"], y=df["TSB"], name="Balance (TSB)", marker_color='#6ab04c', opacity=0.4))
    
    fig_carga.update_layout(
        template="plotly_dark", height=350, margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color="white")),
        xaxis=dict(tickformat="%d/%m", color="white", gridcolor="rgba(255,255,255,0.1)"),
        yaxis=dict(color="white", gridcolor="rgba(255,255,255,0.1)"),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color="white") # Asegurar texto blanco
    )

    # 2. Dona de Sueño (Horas/Minutos)
    fases_valores = list(BIO['sueño_fases'].values())
    labels_fases = [format_dur(v) for v in fases_valores]
    fig_sleep = px.pie(names=list(BIO['sueño_fases'].keys()), values=fases_valores, hole=0.7, 
                       color_discrete_sequence=['#4a90e2', '#74b9ff', '#a29bfe', '#ff7675'])
    fig_sleep.update_traces(text=labels_fases, textinfo='text')
    fig_sleep.update_layout(
        template="plotly_dark", showlegend=True, height=300, 
        margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color="white"), # Asegurar texto blanco
        legend=dict(orientation="h", y=-0.1, xanchor="center", x=0.5, font=dict(color="white"))
    )

    # 3. Mapa de Calor Mensual (Calendar Heatmap)
    # Mostramos los kilómetros diarios como cuadros de colores
    dias_es = {'Monday': 'Lun', 'Tuesday': 'Mar', 'Wednesday': 'Mie', 'Thursday': 'Jue', 'Friday': 'Vie', 'Saturday': 'Sab', 'Sunday': 'Dom'}
    if not df.empty:
        df['DiaSemana'] = df['Fecha'].dt.day_name().map(dias_es)
        df['Semana'] = df['Fecha'].dt.isocalendar().week
        heat_data = df.pivot_table(index='DiaSemana', columns='Semana', values='Distancia', aggfunc='sum').reindex(list(dias_es.values())).fillna(0)
        
        # Mapa de Calor Interactivos (Calendar Heatmap)
        fig_heat = px.imshow(heat_data, color_continuous_scale="Viridis", text_auto=".1f")
        fig_heat.update_layout(
            template="plotly_dark", height=250, margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color="white"), # Asegurar texto blanco
            coloraxis_showscale=False,
            xaxis=dict(color="white"), yaxis=dict(color="white")
        )
        graph_heat_html = fig_heat.to_html(full_html=False, include_plotlyjs=False, config=config_resp)
    else:
        graph_heat_html = "<p class='text-muted text-center py-5'>Sube archivos GPX para ver tu consistencia.</p>"

    # --- GENERAR HTML FINAL ---
    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>Dashboard Camilo v8.0 | Elite Running SaaS</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ background-color: #000; color: #fff; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }}
            .section-box {{ background: #111; border: 1px solid #222; border-radius: 16px; padding: 15px; margin-bottom: 15px; }}
            .stat-card {{ background: #1a1a1a; border-radius: 12px; padding: 12px; text-align: center; margin-bottom: 10px; border-bottom: 3px solid #00d2ff; }}
            .stat-label {{ color: #bbb; font-size: 0.75rem; text-transform: uppercase; font-weight: bold; letter-spacing: 1px; }}
            .stat-value {{ font-size: 1.4rem; font-weight: 800; display: block; color: #fff; }}
            .risk-badge {{ background: {riesgo_color}; color: #000; padding: 6px 16px; border-radius: 30px; font-weight: 900; font-size: 0.8rem; text-transform: uppercase; }}
            h2 {{ font-size: 1rem; color: #00d2ff; font-weight: bold; text-transform: uppercase; margin-bottom: 15px; border-bottom: 1px solid #222; padding-bottom: 5px; }}
            /* Asegurar visibilidad de leyendas y texto de Plotly */
            .gtitle, .xtitle, .ytitle, .legendtext {{ fill: #fff !important; color: #fff !important; }}
            @media (max-width: 768px) {{ .stat-value {{ font-size: 1.2rem; }} .stat-label {{ font-size: 0.7rem; }} }}
        </style>
    </head>
    <body>
        <div class="container-fluid py-3 px-2">
            <div class="header mb-4 d-flex justify-content-between align-items-start px-2">
                <div>
                    <h1 class="mb-0 fw-bold" style="color:#fff; font-size: 1.4rem;">CAMILO GAMBOA</h1>
                    <p class="text-muted small mb-0">Elite Performance SaaS | Maratonista</p>
                </div>
                <div class="text-end">
                    <span class="text-muted small d-block">Riesgo de Lesión</span>
                    <span class="risk-badge">{riesgo_label}</span>
                </div>
            </div>

            <div class="row g-2">
                <div class="col-12 col-xl-4">
                    <div class="section-box h-100">
                        <h2>1. Biometría y Recuperación</h2>
                        <div class="row g-2 mb-3">
                            <div class="col-6">
                                <div class="stat-card" style="border-color: #a29bfe;">
                                    <span class="stat-label">VFC / HRV Nocturno</span>
                                    <span class="stat-value">{BIO['hrv']} ms</span>
                                </div>
                            </div>
                            <div class="col-6">
                                <div class="stat-card" style="border-color: #74b9ff;">
                                    <span class="stat-label">Puntuación de Sueño</span>
                                    <span class="stat-value">{BIO['sleep_score']}/100</span>
                                </div>
                            </div>
                        </div>
                        <div class="text-center">
                            {fig_sleep.to_html(full_html=False, include_plotlyjs='cdn', config=config_resp)}
                        </div>
                    </div>
                </div>

                <div class="col-12 col-xl-8">
                    <div class="section-box h-100">
                        <h2>2. Carga y Estado de Forma</h2>
                        <div class="row g-2 mb-3">
                            <div class="col-4"><div class="stat-card"><span class="stat-label">Fitness (CTL)</span><span class="stat-value">{df['CTL'].iloc[-1] if not df.empty else 'N/A'}</span></div></div>
                            <div class="col-4"><div class="stat-card" style="border-color: #ff4b2b;"><span class="stat-label">Fatiga (ATL)</span><span class="stat-value">{df['ATL'].iloc[-1] if not df.empty else 'N/A'}</span></div></div>
                            <div class="col-4"><div class="stat-card" style="border-color: #6ab04c;"><span class="stat-label">Balance (TSB)</span><span class="stat-value">{df['TSB'].iloc[-1] if not df.empty else 'N/A'}</span></div></div>
                        </div>
                        {fig_carga.to_html(full_html=False, include_plotlyjs=False, config=config_resp)}
                    </div>
                </div>

                <div class="col-12">
                    <div class="section-box text-center">
                        <h2>3. Analítica de Kilometraje</h2>
                        <div class="mb-3">
                            <span class="stat-label">Kilómetros Totales Acumulados</span>
                            <span class="stat-value" style="color: #6ab04c; font-size: 2.5rem;">{total_km:.1f} km</span>
                        </div>
                        {graph_heat_html}
                    </div>
                </div>
            </div>

            <footer class="text-center text-muted py-4 small" style="font-size: 0.7rem;">
                Actualizado vía GitHub Actions (Chile): {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
            </footer>
        </div>
    </body>
    </html>
    """
    print(f"✅ Dashboard v8.0 generado con éxito. Km totales: {total_km:.1f}")
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

if __name__ == "__main__":
    if not os.path.exists(DATA_FOLDER):
        os.makedirs(DATA_FOLDER)
    crear_dashboard()
