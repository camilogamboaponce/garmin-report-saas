import os
import glob
import logging
import smtplib
from datetime import datetime
from email.message import EmailMessage

import gpxpy
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.colors as mcolors
from fpdf import FPDF
from dotenv import load_dotenv

# --- CONFIGURACIÓN ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

DATA_FOLDER = "data"
SUEÑO_RECOMENDADO_MIN = 480 

# 1. DATOS SIMULADOS (Para el reporte de hoy)
DATOS_DEL_DIA = {
    "hrv": 66,                
    "sleep_score": 85,
    "sleep_quality": "Bueno",
    "sueño_fases": {
        "profundo": 57,
        "ligero": 279,
        "rem": 103,
        "despierto": 7
    }
}

# --- FUNCIONES DE APOYO ---

def format_duration(minutos):
    if minutos >= 60:
        h = int(minutos // 60)
        m = int(minutos % 60)
        return f"{h}h {m}m"
    return f"{int(minutos)}m"

def analizar_hrv(valor):
    if valor >= 65:
        return "Equilibrado", (0, 128, 0), "Sistema nervioso en equilibrio. Cuerpo listo para la intensidad planificada."
    elif 55 <= valor < 65:
        return "Tendencia Equilibrada", (218, 165, 32), "Recuperación en curso. Evita esfuerzos máximos."
    else:
        return "Desequilibrado", (200, 0, 0), "Sistema nervioso desequilibrado. Prioriza descanso."

def evaluar_riesgo_lesion(tsb, hrv, sleep_score):
    puntos = 0
    if tsb < -15: puntos += 30
    if hrv < 55: puntos += 40
    if sleep_score < 75: puntos += 30
    
    posicion_linea = (puntos / 100) * 6
    if puntos >= 70: return "Alto", (200, 0, 0), posicion_linea
    if puntos >= 30: return "Medio", (218, 165, 32), posicion_linea
    return "Bajo", (0, 128, 0), posicion_linea

# --- GENERACIÓN DE ELEMENTOS VISUALES ---

def generar_visuales(fases, carga_info, hrv_val, sleep_val):
    print("🎨 Generando visuales v6.1...")
    
    # 1. Dona de Sueño
    sizes = [fases['profundo'], fases['ligero'], fases['rem'], fases['despierto']]
    colors = ['#4a90e2', '#74b9ff', '#a29bfe', '#ff7675']
    fig, ax = plt.subplots(figsize=(4, 4))
    ax.pie(sizes, colors=colors, startangle=90, wedgeprops=dict(width=0.35))
    total_min = sum(sizes)
    ax.text(0, 0, f"{format_duration(total_min)}\nTotal", ha='center', va='center', fontsize=12, fontweight='bold')
    plt.savefig("sleep_chart.png", transparent=True, dpi=120, bbox_inches='tight'); plt.close()

    # 2. Mapa de Calor de Riesgo
    _, _, pos_linea = evaluar_riesgo_lesion(carga_info['tsb'], hrv_val, sleep_val)
    colors_list = ['#55af64', '#ffd966', '#f6b26b', '#cc0000']
    nodes = [0.0, 0.35, 0.65, 1.0]
    my_cmap = mcolors.LinearSegmentedColormap.from_list("risk_gradient", list(zip(nodes, colors_list)))

    fig, ax = plt.subplots(figsize=(4, 0.6)) 
    gradient = np.vstack((np.linspace(0, 1, 256), np.linspace(0, 1, 256)))
    ax.imshow(gradient, aspect='auto', cmap=my_cmap, extent=[0, 6, 0, 1])
    ax.vlines(x=pos_linea, ymin=0, ymax=1, color='black', linewidth=3)
    ax.set_xlim(0, 6); ax.axis('off')
    plt.savefig("risk_heatmap.png", transparent=True, dpi=120, bbox_inches='tight', pad_inches=0); plt.close()

    # 3. Gráfico de Carga
    fig, ax = plt.subplots(figsize=(10, 6)) 
    ax.plot(carga_info['hist']["Fecha"], carga_info['hist']["CTL"], label="Fitness (CTL)", color='#1f77b4', linewidth=2.5)
    ax.fill_between(carga_info['hist']["Fecha"], carga_info['hist']["TSB"], color='#ffeaa7', alpha=0.5, label="Balance (TSB)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    plt.xticks(rotation=45)
    plt.legend(loc='upper left'); plt.grid(axis='y', alpha=0.2)
    plt.tight_layout()
    plt.savefig("load_chart.png", dpi=130, bbox_inches='tight'); plt.close()

# --- GENERACIÓN DEL PDF ---

def generar_pdf(carga, hoy, bio):
    generar_visuales(bio['sueño_fases'], carga, bio['hrv'], bio['sleep_score'])
    pdf = FPDF()
    pdf.add_page()
    
    # Header (Negro)
    pdf.set_fill_color(26, 26, 26); pdf.rect(0, 0, 210, 35, 'F')
    pdf.set_text_color(255, 255, 255); pdf.set_font("Helvetica", "B", 24)
    pdf.cell(0, 15, "REPORTE DE ENTRENAMIENTO", ln=True, align="C")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 5, f"Análisis Biométrico y de Carga | {hoy.strftime('%d/%m/%Y')}", ln=True, align="C")
    
    pdf.set_text_color(0, 0, 0); pdf.ln(25)
    
    # 1. MÉTRICAS DE SUEÑO
    pdf.set_font("Helvetica", "B", 14); pdf.cell(0, 10, "1. MÉTRICAS DE SUEÑO", ln=True)
    pdf.set_font("Helvetica", "", 11)
    total_min = sum(bio['sueño_fases'].values())
    pdf.set_x(15)
    pdf.cell(0, 8, f"Calidad: {bio['sleep_quality']} ({bio['sleep_score']}/100)  I  Duración: {format_duration(total_min)}", ln=True)
    
    pdf.set_font("Helvetica", "", 10) 
    f = bio['sueño_fases']
    for fase, valor in [("Profundo", f['profundo']), ("Ligero", f['ligero']), ("REM", f['rem']), ("Despierto", f['despierto'])]:
        pdf.set_x(15); pdf.cell(0, 6, f"{fase}: {format_duration(valor)}", ln=True)
    
    pdf.set_x(15); pdf.set_font("Helvetica", "B", 10); pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, f"Recomendación: {format_duration(SUEÑO_RECOMENDADO_MIN)}", ln=True)
    pdf.set_text_color(0, 0, 0); pdf.image("sleep_chart.png", x=130, y=52, w=45); pdf.ln(8)

    # 2. RECUPERACIÓN Y RIESGO
    label_h, col_h, cons_h = analizar_hrv(bio['hrv'])
    label_r, col_r, _ = evaluar_riesgo_lesion(carga['tsb'], bio['hrv'], bio['sleep_score'])
    
    pdf.set_font("Helvetica", "B", 14); pdf.cell(0, 10, "2. RECUPERACIÓN Y RIESGO DE LESIÓN", ln=True)
    pdf.set_x(
