# --- ARCHIVO: Menu.py ---
import streamlit as st
import pandas as pd
import sys
from pathlib import Path
import altair as alt
import numpy as np

# --- 1. Configuración de la Página y Rutas ---
st.set_page_config(
    layout="wide",
    page_title="Portal Abastecimiento | Copec Flux",
    page_icon="assets/COPEC-FLUX.svg"
)

# Aseguramos que Python encuentre la carpeta 'src'
src_path = str(Path(__file__).parent / "src")
if src_path not in sys.path:
    sys.path.append(src_path)

# Importamos los módulos internos
try:
    from data import data_loader
    from core import analysis
    from ui import menu_ui
except ImportError as error_importacion:
    # Mostramos en la interfaz el mensaje exacto devuelto por el intérprete
    st.error(f"🚨 Error de importación detallado: {error_importacion}")
    st.stop()
except Exception as error_inesperado:
    st.error(f"🚨 Fallo de ejecución general: {error_inesperado}")
    st.stop()

def obtener_datos_filtrados(familia_sel):
    """Retorna copias filtradas de los dataframes principales solo por SUBFAMILIA."""
    
    # 🔴 SOLUCIÓN: Si la sesión se perdió, recargamos (será instantáneo gracias a la caché)
    if 'data_loaded' not in st.session_state or not st.session_state.data_loaded:
        st.toast("Restaurando sesión...", icon="🔄")
        data_loader.load_data_into_session()
        
        # Si aún después de intentar cargar, no están, devolvemos DataFrames vacíos para no romper la UI
        if 'data_loaded' not in st.session_state:
             st.error("Error al restaurar los datos.")
             return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    df_s = st.session_state.df_stock.copy()
    df_o = st.session_state.df_oc.copy()
    df_h = st.session_state.df_historia_full.copy() if 'df_historia_full' in st.session_state else pd.DataFrame()
    df_c = st.session_state.df_consumo.copy() if 'df_consumo' in st.session_state else pd.DataFrame()
    
    if familia_sel != "Todas":
        if 'SubFamilia' in df_s.columns:
            df_s = df_s[df_s['SubFamilia'] == familia_sel]
        
        # Filtrar OCs e Historia basado en los SKUs del stock filtrado
        skus_validos = df_s['CodigoArticulo'].unique()
        if 'Número de artículo' in df_o.columns:
             df_o = df_o[df_o['Número de artículo'].isin(skus_validos)]
        if 'CodigoArticulo' in df_h.columns:
             df_h = df_h[df_h['CodigoArticulo'].isin(skus_validos)]
        if 'CodigoArticulo' in df_c.columns:
             df_c = df_c[df_c['CodigoArticulo'].isin(skus_validos)]
             
    return df_s, df_o, df_h, df_c

def main():
    menu_ui.cargar_estilos()
    
    # Carga de Datos
    with st.spinner("Conectando con base de datos..."):
        data_loader.load_data_into_session()
    
    menu_ui.render_header()
    familia_sel, dias_calc = menu_ui.configurar_sidebar()
    
    # Obtención de Datos
    df_s, df_o, df_h, df_c = obtener_datos_filtrados(familia_sel)
    
    if df_s is not None:
        menu_ui.render_kpis_principales(df_s, df_o, df_h, dias_calc)
        st.markdown("---")
        menu_ui.render_kpis_consumo_equipos(df_c, df_s)
        st.markdown("---")
        menu_ui.render_analisis_historico(df_h)
        st.markdown("---")
        menu_ui.render_tarjetas_navegacion()
    else:
        st.warning("⚠️ **Modo Offline:** No se pudieron cargar los datos.")
        
    # Footer
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #888; font-size: 0.8rem;'>"
        "© 2025 Copec Flux S.A. | Desarrollado por el equipo de Abastecimiento.<br>"
        "Build v3.2 (Compatible con SAP Querys)"
        "</div>", 
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()