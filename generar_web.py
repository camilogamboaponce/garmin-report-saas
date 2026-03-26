import os, glob, json
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

# Configuración
DATA_FOLDER = "data"
PIN_MAESTRO = "1234" 

# Datos Simulados (SaaS Demo)
DATOS_ATLETAS = {
    "Camilo Gamboa": {"hrv": 66, "sleep": 85, "ctl": 43.1, "atl": 51.5, "tsb": -8.4, "km": 235.1, "fases": {"Profundo": 57, "Ligero": 279, "REM": 103, "Despierto": 7}},
    "Juan Perez (Pro)": {"hrv": 72, "sleep": 88, "ctl": 65.2, "atl": 70.1, "tsb": -4.9, "km": 312.4, "fases": {"Profundo": 65, "Ligero": 290, "REM": 115, "Despierto": 5}},
    "Marta Silva": {"hrv": 58, "sleep": 78, "ctl": 28.4, "atl": 22.1, "tsb": 6.3, "km": 145.8, "fases": {"Profundo": 42, "Ligero": 255, "REM": 88, "Despierto": 12}}
}

def format_dur(minutos):
    if minutos >= 60: return f"{int(minutos // 60)}h {int(minutos % 60)}m"
    return f"{int(minutos)}m"

def crear_dashboard():
    html_data = {}
    
    # Generar gráficos por cada atleta
    for nombre, info in DATOS_ATLETAS.items():
        # 1. Gráfico Rendimiento
        fechas = pd.date_range(end=datetime.now(), periods=10).strftime('%d/%m').tolist()
        fig_r = go.Figure()
        fig_r.add_trace(go.Scatter(x=fechas, y=np.linspace(info['ctl']-5, info['ctl'], 10), name="Fitness", line=dict(color='#00d2ff', width=3)))
        fig_r.add_trace(go.Scatter(x=fechas, y=np.linspace(info['atl']-8, info['atl'], 10), name="Fatiga", line=dict(color='#ff4b2b', width=2, dash='dot')))
        fig_r.update_layout(template="plotly_dark", height=250, margin=dict(l=10,r=10,t=10,b=10), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', xaxis=dict(fixedrange=True), yaxis=dict(fixedrange=True))

        # 2. Gráfico Dona de Sueño
        fig_s = go.Figure(data=[go.Pie(labels=list(info['fases'].keys()), values=list(info['fases'].values()), hole=0.7, 
                                      text=[format_dur(v) for v in info['fases'].values()], textinfo='text',
                                      marker=dict(colors=['#4a90e2', '#74b9ff', '#a29bfe', '#ff7675']))])
        fig_s.update_layout(template="plotly_dark", height=250, showlegend=True, margin=dict(l=0,r=0,t=0,b=0), paper_bgcolor='rgba(0,0,0,0)', legend=dict(orientation="h", y=-0.2))

        html_data[nombre] = {
            "hrv": info['hrv'], "sleep": info['sleep'], "ctl": info['ctl'], "atl": info['atl'], "tsb": info['tsb'], "km": info['km'],
            "perf_html": fig_r.to_html(full_html=False, include_plotlyjs=False),
            "sueño_html": fig_s.to_html(full_html=False, include_plotlyjs=False)
        }

    # Plantilla HTML (String puro, sin f-string para evitar errores)
    options_atleta = "".join([f'<option value="{n}">{n}</option>' for n in DATOS_ATLETAS.keys()])
    
    html_template = '''
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>SaaS Coach | Dashboard</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <style>
            body { background: #000; color: #fff; font-family: sans-serif; overflow-x: hidden; }
            #login-screen { position: fixed; inset: 0; background: #000; z-index: 1000; display: flex; flex-direction: column; justify-content: center; align-items: center; }
            .pin-input { background: #111; border: 2px solid #333; color: #00d2ff; font-size: 2.5rem; text-align: center; width: 180px; border-radius: 12px; letter-spacing: 8px; outline: none; }
            #main-content { display: none; padding: 15px; }
            .box { background: #111; border: 1px solid #222; border-radius: 12px; padding: 15px; margin-bottom: 15px; }
            .stat-card { background: #1a1a1a; border-radius: 10px; padding: 10px; text-align: center; border-bottom: 3px solid #00d2ff; }
            .stat-lbl { color: #888; font-size: 0.7rem; text-transform: uppercase; font-weight: bold; }
            .stat-val { font-size: 1.3rem; font-weight: 800; display: block; color: #fff; }
            select { background: #1a1a1a; color: #fff; border: 1px solid #333; padding: 12px; border-radius: 8px; width: 100%; margin-bottom: 20px; font-weight: bold; }
            h2 { font-size: 0.9rem; color: #00d2ff; text-transform: uppercase; margin-bottom: 15px; }
        </style>
    </head>
    <body>
        <div id="login-screen">
            <h1 class="h4 mb-4 fw-bold">PANEL DEL ENTRENADOR</h1>
            <input type="password" id="pinField" class="pin-input" maxlength="4" placeholder="PIN">
            <button onclick="validar()" class="btn btn-info mt-4 px-5">Acceder</button>
            <p id="errorMsg" class="text-danger mt-3" style="display:none;">PIN Incorrecto</p>
        </div>

        <div id="main-content" class="container-fluid">
            <div class="d-flex justify-content-between align-items-center mb-4">
                <h1 class="h5 fw-bold mb-0">EQUIPO ELITE</h1>
                <button onclick="location.reload()" class="btn btn-sm btn-outline-danger">Salir</button>
            </div>
            <select id="selector">VAR_OPTIONS</select>
            <div id="dinamico"></div>
        </div>

        <script>
            const data = VAR_JSON;
            const PIN_CORRECTO = "VAR_PIN";

            function validar() {
                const pin = document.getElementById('pinField').value;
                if(pin === PIN_CORRECTO) {
                    document.getElementById('login-screen').style.display = 'none';
                    document.getElementById('main-content').style.display = 'block';
                    render('Camilo Gamboa');
                } else {
                    document.getElementById('errorMsg').style.display = 'block';
                    document.getElementById('pinField').value = '';
                }
            }
            document.getElementById('pinField').onkeypress = (e) => { if(e.key === 'Enter') validar(); };

            function render(name) {
                const a = data[name];
                document.getElementById('dinamico').innerHTML = `
                    <div class="row g-2 mb-3">
                        <div class="col-6"><div class="stat-card" style="border-color:#a29bfe"><span class="stat-lbl">VFC / HRV</span><span class="stat-val">${a.hrv} ms</span></div></div>
                        <div class="col-6"><div class="stat-card" style="border-color:#74b9ff"><span class="stat-lbl">Sueño</span><span class="stat-val">${a.sleep}/100</span></div></div>
                    </div>
                    
                    <div class="box">
                        <h2>Análisis de Sueño</h2>
                        ${a.sueño_html}
                    </div>

                    <div class="box">
                        <h2>Carga de Rendimiento</h2>
                        ${a.perf_html}
                    </div>

                    <div class="row g-2 mb-3">
                        <div class="col-4"><div class="stat-card"><span class="stat-lbl">Fitness</span><span class="stat-val">${a.ctl.toFixed(1)}</span></div></div>
                        <div class="col-4"><div class="stat-card" style="border-color:#ff4b2b"><span class="stat-lbl">Fatiga</span><span class="stat-val">${a.atl.toFixed(1)}</span></div></div>
                        <div class="col-4"><div class="stat-card" style="border-color:#6ab04c"><span class="stat-lbl">Balance</span><span class="stat-val">${a.tsb.toFixed(1)}</span></div></div>
                    </div>

                    <div class="box text-center">
                        <h2>Kilómetros Acumulados</h2>
                        <span class="stat-val" style="color:#6ab04c; font-size: 2.5rem;">${a.km.toFixed(1)} km</span>
                    </div>
                `;
                // Forzar redibujado de gráficos
                setTimeout(() => { window.dispatchEvent(new Event('resize')); }, 150);
            }
            document.getElementById('selector').onchange = (e) => render(e.target.value);
        </script>
    </body>
    </html>
    '''
    
    # Inyección segura de variables
    final_html = html_template.replace("VAR_JSON", json.dumps(html_data))
    final_html = final_html.replace("VAR_PIN", PIN_MAESTRO)
    final_html = final_html.replace("VAR_OPTIONS", options_atleta)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(final_html)

if __name__ == "__main__":
    crear_dashboard()
