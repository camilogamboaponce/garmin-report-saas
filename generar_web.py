import os, glob, json
import gpxpy
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

DATA_FOLDER = "data"
PIN_MAESTRO = "1234" 

# --- DATOS DE ATLETAS (Simulados) ---
DATOS_ATLETAS = {
    "Camilo Gamboa": {"hrv": 66, "sleep": 85, "ctl": 43.1, "atl": 51.5, "tsb": -8.4, "km": 235.1, "fases": {"Profundo": 57, "Ligero": 279, "REM": 103, "Despierto": 7}},
    "Juan Perez (Pro)": {"hrv": 72, "sleep": 88, "ctl": 65.2, "atl": 70.1, "tsb": -4.9, "km": 312.4, "fases": {"Profundo": 65, "Ligero": 290, "REM": 115, "Despierto": 5}},
    "Marta Silva": {"hrv": 58, "sleep": 78, "ctl": 28.4, "atl": 22.1, "tsb": 6.3, "km": 145.8, "fases": {"Profundo": 42, "Ligero": 255, "REM": 88, "Despierto": 12}}
}

def format_dur(minutos):
    if minutos >= 60: return f"{int(minutos // 60)}h {int(minutos % 60)}m"
    return f"{int(minutos)}m"

def crear_dashboard():
    # Pre-generamos los gráficos para cada atleta y los guardamos en JSON
    # Solo simulamos una tendencia para la demo
    fechas = pd.date_range(end=datetime.now(), periods=10).strftime('%d/%m').tolist()
    
    html_atletas = {}
    for nombre, info in DATOS_ATLETAS.items():
        # Gráfico Rendimiento (Tendencia Simulada)
        fig_r = go.Figure()
        fig_r.add_trace(go.Scatter(x=fechas, y=np.linspace(info['ctl']-5, info['ctl'], 10), name="Fitness", line=dict(color='#00d2ff', width=3)))
        fig_r.add_trace(go.Scatter(x=fechas, y=np.linspace(info['atl']-8, info['atl'], 10), name="Fatiga", line=dict(color='#ff4b2b', width=2, dash='dot')))
        fig_r.add_trace(go.Bar(x=fechas, y=np.linspace(info['tsb']-2, info['tsb']+2, 10), name="Balance", marker_color='#6ab04c', opacity=0.3))
        
        fig_r.update_layout(template="plotly_dark", height=280, margin=dict(l=10,r=10,t=10,b=10), paper_bgcolor='rgba(0,0,0,0)', 
                            plot_bgcolor='rgba(0,0,0,0)', xaxis=dict(fixedrange=True, nticks=10), yaxis=dict(fixedrange=True))

        html_atletas[nombre] = {
            "perf_html": fig_r.to_html(full_html=False, include_plotlyjs=False)
        }

    # --- HTML CON LLAVES ESCAPADAS {{ }} PARA PYTHON ---
    options_atleta = "".join([f'<option value="{n}">{n}</option>' for n in DATOS_ATLETAS.keys()])
    
    html_template = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>SaaS Coach | Dashboard</title>
        <link href="
