# --- ARCHIVO: pages/1_📈_Simulador.py ---
import streamlit as st
import pandas as pd
import sys
from pathlib import Path

# --- Configuración del Path ---
src_path = str(Path(__file__).resolve().parent.parent / "src")
if src_path not in sys.path:
    sys.path.append(src_path)

import config         # Importa constantes
import core.simulator as simulator      # Importa el motor de simulación
import ui.ui_helpers as ui_helpers     # Importa las funciones de gráficos y métricas
import data.data_loader as data_loader
import altair as alt  # Importamos Altair

# --- 1. CONFIGURACIÓN INICIAL ---
if 'data_loaded' not in st.session_state or not st.session_state.data_loaded:
    with st.spinner("Cargando datos... por favor, espere."):
        data_loader.load_data_into_session()
        
if 'data_loaded' not in st.session_state or not st.session_state.data_loaded:
    st.error("Los datos no se han cargado. Vuelva al Menú Principal.")
    st.stop()

ui_helpers.setup_locale()
st.title("Simulador de Proyección de Inventario 📈")

st.sidebar.markdown("---")

# --- 2. BARRA LATERAL (MODULARIZADA) ---
# Una sola línea hace todo el trabajo de renderizar la sidebar y capturar inputs
params = ui_helpers.render_simulation_sidebar(
    st.session_state.df_stock, 
    st.session_state.df_consumo
)

# Desempaquetamos para usar fácil
sku_sel = params["sku"]
bodegas_stk = params["bodegas_stock"]
bodegas_cons = params["bodegas_consumo"]

# --- 3. LÓGICA PRINCIPAL ---
if params["ejecutar"]:
    # Validaciones básicas
    if not bodegas_stk:
        st.error("Seleccione al menos una Bodega de Stock.")
        st.stop()
    if not bodegas_cons:
        st.error("Seleccione al menos una Bodega de Consumo.")
        st.stop()

    with st.spinner("Calculando simulación..."):
        # A. Motor Matemático
        df_sim, metrics, llegadas_map, df_llegadas_detalle = simulator.run_inventory_simulation(
            sku_to_simulate=sku_sel,
            warehouse_code=bodegas_stk,
            consumption_warehouse=bodegas_cons,
            df_stock_raw=st.session_state.df_stock,
            df_consumo_raw=st.session_state.df_consumo,
            df_oc_raw=st.session_state.df_oc,
            simulation_days=params["dias_sim"],
            lead_time_days=params["lead_time"],
            service_level_z=params["z_score"],
            use_randomness=params["use_variability"] # <--- Conectamos el checkbox
        )

        # B. Resultados Visuales (Usando helpers existentes)
        st.subheader(f"Resultados para: {sku_sel}")
        st.caption(f"Nombre: {params['mapa_nombres'].get(sku_sel, 'N/A')}")
        
        ui_helpers.display_metrics(metrics, params["lead_time"], params["z_score"])
        st.markdown("---")
        
        ui_helpers.display_order_recommendation(metrics, llegadas_map, df_sim, params["lead_time"])
        st.markdown("---")
        
        ui_helpers.display_arrival_details(df_llegadas_detalle)
        st.markdown("---")
        
        sku_name = params['mapa_nombres'].get(sku_sel, sku_sel)
        fig = ui_helpers.generate_simulation_plot(df_sim, metrics, llegadas_map, sku_name, params["dias_sim"])
        st.altair_chart(fig, use_container_width=True)

        # Tabla Fin de Mes
        df_tabla_resultados = ui_helpers.prepare_end_of_month_table(df_sim)
        st.subheader("Stock Simulado a Fin de Mes")
        st.dataframe(df_tabla_resultados, width='stretch', hide_index=True)

        # C. Detalle de Consumo (Modularizado)
        ui_helpers.render_consumption_details(sku_sel, bodegas_cons, st.session_state.df_consumo)

# --- 4. SECCIÓN MÁQUINA DEL TIEMPO (MODULARIZADA) ---
ui_helpers.render_historical_stock_section(
    sku_sel, 
    st.session_state.df_stock, 
    st.session_state.df_consumo,
    bodegas_seleccionadas=bodegas_stk # <--- Pasamos las bodegas seleccionadas
)