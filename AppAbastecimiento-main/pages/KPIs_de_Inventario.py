import streamlit as st
import pandas as pd
import sys
from pathlib import Path

# --- Configuración del Path ---
src_path = str(Path(__file__).resolve().parent.parent / "src")
if src_path not in sys.path:
    sys.path.append(src_path)

# Importamos tus módulos propios
import ui.ui_helpers as ui_helpers
import core.analysis as analysis
import ui.charts as charts

# --- Configuración de Página ---
st.set_page_config(page_title="KPIs de Inventario", page_icon="💰", layout="wide")
ui_helpers.setup_locale()

st.title("💰 KPIs y Valorización de Inventario")
st.markdown("---")

# ==============================================================================
# 1. CARGA Y FILTROS
# ==============================================================================
if 'data_loaded' not in st.session_state or not st.session_state.data_loaded:
    st.error("⚠️ Datos no cargados. Vaya al Menú Principal.")
    st.stop()

# Carga inicial
df_stock_raw = st.session_state.df_stock
df_historia_raw = st.session_state.get('df_historia_subfam', pd.DataFrame())

# Detectar columnas clave (Usando tu helper existente)
col_subfam = ui_helpers.detectar_columna(df_stock_raw, ['SubFamilia', 'Subfamilia', 'Categoria', 'Familia'])
col_bodega = 'NombreBodega'
col_valor = 'ValorTotalInventario'

# --- INTERFAZ DE FILTROS ---
st.subheader("🛠️ Filtros")
col_f1, col_f2 = st.columns(2)

with col_f1:
    lista_subfamilias = sorted(df_stock_raw[col_subfam].astype(str).unique())
    sel_subfamilias = st.multiselect(f"Seleccionar {col_subfam}:", options=lista_subfamilias, default=lista_subfamilias)

with col_f2:
    hoy = pd.Timestamp.now().date()
    fechas_sel = st.date_input("Rango de Fechas (Evolución):", value=(hoy - pd.DateOffset(months=12), hoy), format="DD/MM/YYYY")

# --- APLICACIÓN DE LOGICA DE FILTRO ---
if not sel_subfamilias:
    st.warning("⚠️ Selecciona al menos una Subfamilia.")
    st.stop()

df_stock = df_stock_raw[df_stock_raw[col_subfam].astype(str).isin(sel_subfamilias)].copy()

# Lógica de filtro histórico
df_historia = pd.DataFrame()
if not df_historia_raw.empty:
    col_sub_hist = ui_helpers.detectar_columna(df_historia_raw, ['SubFamilia', 'Subfamilia', 'Familia'])
    if col_sub_hist:
        df_historia = df_historia_raw[df_historia_raw[col_sub_hist].isin(sel_subfamilias)].copy()
        
        if len(fechas_sel) == 2:
            df_historia['Fecha_Dt'] = pd.to_datetime(df_historia['Mes'] + '-01')
            df_historia = df_historia[(df_historia['Fecha_Dt'].dt.date >= fechas_sel[0]) & (df_historia['Fecha_Dt'].dt.date <= fechas_sel[1])]

# ==============================================================================
# 2. DASHBOARD (KPIs)
# ==============================================================================
st.subheader("Resumen del Inventario Filtrado")

if col_valor in df_stock.columns:
    # --- Optimización: Calcular la agrupación una sola vez ---
    valor_por_subfam = df_stock.groupby(col_subfam)[col_valor].sum()

    val_total = valor_por_subfam.sum()
    skus_count = df_stock[df_stock['StockActual'] > 0]['CodigoArticulo'].nunique()
    
    # KPI Subfamilia Top
    if not valor_por_subfam.empty:
        top_fam_name = valor_por_subfam.idxmax()
        top_fam_val = valor_por_subfam.max()
    else:
        top_fam_name = "N/A"
        top_fam_val = 0

    k1, k2, k3 = st.columns(3)
    k1.metric("Valor Inventario (Filtrado)", f"${val_total:,.0f}")
    k2.metric("SKUs con Stock", f"{skus_count:,.0f}")
    k3.metric(f"Subfamilia Principal: {top_fam_name}", f"${top_fam_val:,.0f}")
else:
    st.error("Columna de valor no encontrada.")

st.markdown("---")

# --- Reestructuración con Pestañas ---
tab_visual, tab_detalle = st.tabs(["📊 Dashboard Visual", "📋 Tablas de Detalle"])

with tab_visual:
    st.subheader("Distribución del Capital")
    c1, c2 = st.columns(2)

    with c1:
        st.markdown(f"**Por {col_subfam}**")
        df_g1 = df_stock.groupby(col_subfam)[col_valor].sum().reset_index()
        st.altair_chart(charts.plot_barras_simple(df_g1, col_valor, col_subfam, 'Valor ($)'), use_container_width=True)

    with c2:
        st.markdown("**Por Bodega**")
        df_g2 = df_stock.groupby(col_bodega)[col_valor].sum().reset_index()
        st.altair_chart(charts.plot_barras_simple(df_g2, col_valor, col_bodega, 'Valor ($)', color='#E31C23'), use_container_width=True)

    st.subheader("Evolución Histórica del Valor")
    if not df_historia.empty:
        col_sub_hist = ui_helpers.detectar_columna(df_historia, ['SubFamilia', 'Subfamilia', 'Familia'])
        st.altair_chart(charts.plot_area_historica(df_historia, 'Mes', 'ValorStockCierre', col_sub_hist), use_container_width=True)
    else:
        st.info("No hay datos históricos disponibles para el rango seleccionado.")

with tab_detalle:
    st.subheader("Matriz de Valorización (SKU x Bodega)")

    # Generamos la data con el módulo analysis
    df_pivot_sku = analysis.generar_pivot_sku_bodega(df_stock, 'CodigoArticulo', 'NombreArticulo', col_bodega, col_valor)

    if not df_pivot_sku.empty:
        # Configuración visual (UI) se queda en el frontend
        cfg_cols = {col: st.column_config.NumberColumn(format="$%d") for col in df_pivot_sku.columns}
        st.dataframe(df_pivot_sku, column_config=cfg_cols, height=500, use_container_width=True)
        st.download_button("📥 Descargar Detalle SKU", df_pivot_sku.to_csv().encode('utf-8'), "detalle_sku_valorizado.csv")
    else:
        st.info("No hay datos para mostrar en la matriz de SKU.")

    st.subheader(f"Resumen por {col_subfam} y Bodega")

    # Generamos la data con el módulo analysis
    df_pivot_sub = analysis.generar_pivot_subfam_bodega(df_stock, col_subfam, col_bodega, col_valor)

    if not df_pivot_sub.empty:
        cfg_cols_sub = {col: st.column_config.NumberColumn(format="$%d") for col in df_pivot_sub.columns}
        st.dataframe(df_pivot_sub, column_config=cfg_cols_sub, use_container_width=True)
        st.download_button("📥 Descargar Resumen Subfamilia", df_pivot_sub.to_csv().encode('utf-8'), "resumen_subfamilia_valorizado.csv")
    else:
        st.info("No hay datos para mostrar en el resumen por subfamilia.")