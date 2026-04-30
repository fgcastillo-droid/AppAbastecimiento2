import streamlit as st
import pandas as pd
import altair as alt
import sys
from pathlib import Path

# --- Configuración de Rutas ---
src_path = str(Path(__file__).resolve().parent.parent / "src")
if src_path not in sys.path:
    sys.path.append(src_path)

import ui.ui_helpers as ui_helpers
import core.analysis as analysis # Importamos nuestra nueva función modular

# --- Configuración Página ---
st.set_page_config(page_title="Evolución Histórica", page_icon="📈", layout="wide")
ui_helpers.setup_locale()

# ==============================================================================
# 1. FUNCIONES AUXILIARES (UI & LÓGICA)
# ==============================================================================

def configurar_filtros(df):
    """Renderiza la barra lateral y retorna un diccionario con la configuración seleccionada."""
    with st.sidebar:
        st.header("⚙️ Configuración")
        
        opcion_visual = st.radio("Ver evolución por:", options=["Familia", "SubFamilia", "Bodega"], index=0)
        mapa_columnas = {"Familia": "Familia", "SubFamilia": "SubFamilia", "Bodega": "CodigoBodega"}
        
        st.divider()
        st.header("🔍 Filtros")
        
        # Filtros en cascada
        lista_familias = sorted(df['Familia'].astype(str).unique())
        sel_familias = st.multiselect("Familia", options=lista_familias)
        
        # Filtrado intermedio para SubFamilia
        df_temp = df[df['Familia'].isin(sel_familias)] if sel_familias else df
        
        sel_subfamilias = []
        if 'SubFamilia' in df.columns:
            lista_subfam = sorted(df_temp['SubFamilia'].astype(str).unique())
            sel_subfamilias = st.multiselect("SubFamilia", options=lista_subfam)
            if sel_subfamilias:
                df_temp = df_temp[df_temp['SubFamilia'].isin(sel_subfamilias)]
            
        lista_skus = sorted(df_temp['SKU_Display'].astype(str).unique())
        sel_skus = st.multiselect("🔎 SKU / Producto (Opcional)", options=lista_skus)
        
        lista_bodegas = sorted(df['CodigoBodega'].astype(str).unique())
        sel_bodegas = st.multiselect("Bodega", lista_bodegas, default=lista_bodegas)

        st.divider()
        st.header("📅 Rango de Fechas")
        
        fecha_min, fecha_max = df['fecha'].min(), df['fecha'].max()
        rango = st.date_input("Periodo:", value=(fecha_min, fecha_max), min_value=fecha_min, max_value=fecha_max)
        
        # Validación y conversión de fechas inmediata
        if isinstance(rango, tuple) and len(rango) == 2:
            start, end = pd.to_datetime(rango[0]), pd.to_datetime(rango[1])
        else:
            start, end = pd.to_datetime(fecha_min), pd.to_datetime(fecha_max)

        return {
            "nivel_agrupacion": mapa_columnas[opcion_visual],
            "nombre_visual": opcion_visual,
            "familias": sel_familias,
            "subfamilias": sel_subfamilias,
            "skus": sel_skus,
            "bodegas": sel_bodegas,
            "start_date": start,
            "end_date": end
        }

def aplicar_filtros_memoria(df_movs, df_stock, cfg):
    """Aplica los filtros seleccionados a los DataFrames."""
    mask_movs = pd.Series(True, index=df_movs.index)
    mask_stock = pd.Series(True, index=df_stock.index)
    
    if cfg["familias"]:
        mask_movs &= df_movs['Familia'].isin(cfg["familias"])
        mask_stock &= df_stock['Familia'].isin(cfg["familias"])
    
    if cfg["subfamilias"]:
        mask_movs &= df_movs['SubFamilia'].isin(cfg["subfamilias"])
        mask_stock &= df_stock['SubFamilia'].isin(cfg["subfamilias"])
    
    if cfg["skus"]:
        mask_movs &= df_movs['SKU_Display'].isin(cfg["skus"])
        # Extraemos solo el código para el df_stock
        codigos = [s.split(" | ")[0] for s in cfg["skus"]]
        mask_stock &= df_stock['CodigoArticulo'].astype(str).isin(codigos)
    
    if cfg["bodegas"]:
        mask_movs &= df_movs['CodigoBodega'].isin(cfg["bodegas"])
        mask_stock &= df_stock['CodigoBodega'].isin(cfg["bodegas"])
    
    return df_movs[mask_movs].copy(), df_stock[mask_stock].copy()

def render_grafico_distribucion_bodega(df_movs, df_stock, end_date):
    """Calcula y muestra el gráfico de barras de distribución por bodega."""
    st.markdown("---")
    st.subheader(f"🏢 Distribución por Bodega al {end_date.strftime('%d/%m/%Y')}")

    # Calcular movimientos ocurridos DESPUÉS de la fecha de corte (para restarlos)
    movs_post_corte = df_movs[df_movs['fecha'] > end_date].groupby('CodigoBodega')['ValorMovimiento'].sum().reset_index()
    stock_hoy_bodega = df_stock.groupby('CodigoBodega')['ValorTotalInventario'].sum().reset_index()

    # Merge y Cálculo de Retroceso
    df_bodega_corte = pd.merge(stock_hoy_bodega, movs_post_corte, on='CodigoBodega', how='outer').fillna(0)
    df_bodega_corte['Valor_Corte'] = df_bodega_corte['ValorTotalInventario'] - df_bodega_corte['ValorMovimiento']
    
    # Limpieza visual
    df_bodega_corte = df_bodega_corte[df_bodega_corte['Valor_Corte'] > 100].sort_values('Valor_Corte', ascending=False)

    if not df_bodega_corte.empty:
        chart_bodegas = alt.Chart(df_bodega_corte).mark_bar(cornerRadiusEnd=4).encode(
            x=alt.X('Valor_Corte:Q', axis=alt.Axis(format='$,.0s'), title='Capital Inmovilizado ($)'),
            y=alt.Y('CodigoBodega:N', sort='-x', title='Bodega'),
            color=alt.Color('CodigoBodega:N', legend=None),
            tooltip=[alt.Tooltip('CodigoBodega:N'), alt.Tooltip('Valor_Corte:Q', format='$,.0f')]
        ).properties(height=max(150, len(df_bodega_corte) * 40))
        
        text_bodegas = chart_bodegas.mark_text(align='left', dx=3).encode(text=alt.Text('Valor_Corte:Q', format='$,.0f'))
        st.altair_chart(chart_bodegas + text_bodegas, use_container_width=True)

# ==============================================================================
# 2. EJECUCIÓN PRINCIPAL
# ==============================================================================

st.title("📈 Evolución Histórica del Inventario (Vista Diaria)")

if 'df_historia_full' not in st.session_state or 'df_stock' not in st.session_state:
    st.warning("⚠️ Data no cargada. Revise data_loader.py")
    st.stop()

# 1. Preprocesamiento ligero
df_raw = st.session_state.df_historia_full.dropna(subset=['fecha']).copy()
df_stock_raw = st.session_state.df_stock

df_raw['SKU_Display'] = df_raw['CodigoArticulo'].astype(str)
if 'NombreArticulo' in df_raw.columns:
    df_raw['SKU_Display'] += " | " + df_raw['NombreArticulo'].astype(str)

# 2. Configuración (Sidebar)
cfg = configurar_filtros(df_raw)

# 3. Filtrado
df_movs, df_stock = aplicar_filtros_memoria(df_raw, df_stock_raw, cfg)

if df_movs.empty:
    st.warning("⚠️ No hay datos con los filtros seleccionados.")
    st.stop()

# 4. Cálculos (Motor modular)
df_grouped = analysis.calcular_kardex_diario(df_movs, df_stock, cfg["nivel_agrupacion"], cfg["start_date"], cfg["end_date"])

# 5. Visualización
st.subheader(f"Vista por: {cfg['nombre_visual']}")

tab1, tab2 = st.tabs(["💰 Valor ($)", "📦 Unidades (Q)"])

with tab1:
    chart_val = alt.Chart(df_grouped).mark_line(point=True).encode(
        x=alt.X('fecha:T', axis=alt.Axis(format="%d %b", title="Fecha")),
        y=alt.Y('StockValorizado:Q', axis=alt.Axis(format='$,.0s'), title='Valor Inventario'),
        color=alt.Color(f'{cfg["nivel_agrupacion"]}:N', title=cfg["nombre_visual"]),
        tooltip=['fecha:T', cfg["nivel_agrupacion"], alt.Tooltip('StockValorizado:Q', format='$,.0f')]
    ).properties(height=400).interactive()
    st.altair_chart(chart_val, use_container_width=True)
    
    col_m1, col_m2 = st.columns(2)
    valor_corte = df_grouped.groupby(cfg["nivel_agrupacion"]).last()['StockValorizado'].sum()
    col_m1.metric(f"Total al {cfg['end_date'].strftime('%d/%m')}", f"${valor_corte:,.0f}")
    col_m2.metric("Total Físico HOY", f"${df_stock['ValorTotalInventario'].sum():,.0f}")

with tab2:
    chart_qty = alt.Chart(df_grouped).mark_line(point=True).encode(
        x=alt.X('fecha:T', title="Fecha"),
        y=alt.Y('StockCantidad:Q', title='Unidades'),
        color=alt.Color(f'{cfg["nivel_agrupacion"]}:N', title=cfg["nombre_visual"]),
        tooltip=['fecha:T', cfg["nivel_agrupacion"], alt.Tooltip('StockCantidad:Q', format=',.0f')]
    ).properties(height=400).interactive()
    st.altair_chart(chart_qty, use_container_width=True)

# 6. Gráficos Secundarios
render_grafico_distribucion_bodega(df_movs, df_stock, cfg["end_date"])

if cfg["nombre_visual"] != "Bodega":
    st.markdown("---")
    st.subheader("📈 Tendencia por Bodega (Contexto)")
    # Recalculamos agrupando por Bodega para dar contexto
    df_bodega = analysis.calcular_kardex_diario(df_movs, df_stock, 'CodigoBodega', cfg["start_date"], cfg["end_date"])
    
    chart_ctx = alt.Chart(df_bodega).mark_line().encode(
        x='fecha:T',
        y='StockValorizado:Q',
        color='CodigoBodega:N'
    ).properties(height=300)
    st.altair_chart(chart_ctx, use_container_width=True)

# 7. Tabla de Datos
with st.expander("📅 Ver Tabla de Datos Diarios"):
    df_pivot = df_grouped.pivot_table(
        index=cfg["nivel_agrupacion"], 
        columns=df_grouped['fecha'].dt.strftime('%Y-%m-%d'), 
        values='StockValorizado', 
        aggfunc='sum'
    ).fillna(0)
    st.dataframe(df_pivot.style.format("${:,.0f}"), use_container_width=True)