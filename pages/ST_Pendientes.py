import streamlit as st
import pandas as pd
import altair as alt
import sys
from pathlib import Path

# --- Configuración del Path ---
src_path = str(Path(__file__).resolve().parent.parent / "src")
if src_path not in sys.path:
    sys.path.append(src_path)

import ui.ui_helpers as ui_helpers
import core.analysis as analysis
import ui.charts as charts

# --- 1. Configuración de Página ---
st.set_page_config(page_title="Monitor de Traslados", page_icon="💰", layout="wide")
ui_helpers.setup_locale()

# Intento de cargar estilo (si existe la función)
try:
    ui_helpers.hide_streamlit_style()
except AttributeError:
    pass 

st.title("🚛 Monitor de Solicitudes (Valorizado)")
st.markdown("Control de traslados pendientes con **análisis financiero**.")

# --- 2. Carga de Datos ---
if 'df_owtq' not in st.session_state:
    st.warning("⚠️ Datos no cargados. Ve al Menú Principal.")
    st.stop()

df = st.session_state.df_owtq

# Filtro Base: Solo lo pendiente
df = df[df['Cant. Pendiente'] > 0]

# --- 3. BARRA LATERAL (FILTROS) ---
with st.sidebar:
    st.header("🔍 Filtros")
    
    # A. Fechas
    min_date = df['Fecha Contab.'].min().date() if not df.empty else pd.Timestamp.now().date()
    max_date = df['Fecha Contab.'].max().date() if not df.empty else pd.Timestamp.now().date()
    
    fechas = st.date_input("Rango de Fechas:", (min_date, max_date))

    st.divider()

    # B. Filtro de Monto (NUEVO)
    # Permite filtrar "basura" pequeña y enfocarse en lo caro
    max_val = int(df['Valor Pendiente Total'].max()) if not df.empty else 1000
    monto_min = st.slider("Monto Mínimo ($) por Línea:", 0, max_val, 0, step=1000)

    st.divider()

    # C. Logística
    sel_origen = st.multiselect("Origen:", sorted(df['Almacén Origen'].unique()))
    sel_destino = st.multiselect("Destino:", sorted(df['Almacén Destino'].unique()))

    # D. Proyecto
    lista_proy = sorted(df['Nombre Proyecto'].unique()) if 'Nombre Proyecto' in df.columns else []
    sel_proy = st.multiselect("Nombre Proyecto:", lista_proy)

    # E. Buscador
    search = st.text_input("🔎 Buscar SKU/Desc:", "").lower()

# --- 4. MOTOR DE FILTRADO ---
if len(fechas) != 2: st.stop()
start, end = fechas

mask = (df['Fecha Contab.'].dt.date >= start) & (df['Fecha Contab.'].dt.date <= end)
mask &= (df['Valor Pendiente Total'] >= monto_min) # Filtro de dinero

if sel_origen: mask &= df['Almacén Origen'].isin(sel_origen)
if sel_destino: mask &= df['Almacén Destino'].isin(sel_destino)
if sel_proy: mask &= df['Nombre Proyecto'].isin(sel_proy)
if search:
    mask &= (df['Código Artículo'].str.lower().str.contains(search) | 
             df['Descripción'].str.lower().str.contains(search))

df_filtrado = df[mask].copy()

# (NUEVO) Enriquecer datos con análisis de antigüedad
df_filtrado = analysis.analizar_antiguedad_stock(df_filtrado)

# --- 5. KPIs ESTRATÉGICOS ---
col1, col2, col3, col4 = st.columns(4)

total_dinero = df_filtrado['Valor Pendiente Total'].sum()
total_unidades = df_filtrado['Cant. Pendiente'].sum()
num_docs = df_filtrado['Nº Solicitud'].nunique()
top_sku = df_filtrado.groupby('Código Artículo')['Valor Pendiente Total'].sum().idxmax() if not df_filtrado.empty else "-"

col1.metric("💰 Valor Total Pendiente", f"${total_dinero:,.0f}", delta="Capital Inmovilizado", delta_color="inverse")
col2.metric("📦 Unidades Pendientes", f"{total_unidades:,.0f}")
col3.metric("📄 Solicitudes Activas", num_docs)
col4.metric("💎 SKU Más Costoso", top_sku, help="Artículo con mayor valor acumulado pendiente")

st.divider()

# --- 6. GRÁFICOS (ALTAIR) ---
if not df_filtrado.empty:
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard Gerencial", "🚚 Rutas y Logística", "💎 Análisis ABC", "📋 Detalle Operativo"])
    
    with tab1:
        c1, c2 = st.columns(2)
        
        # (MEJORADO) GRÁFICO 1: Antigüedad de la Deuda
        with c1:
            st.altair_chart(charts.plot_antiguedad_saldos(df_filtrado), use_container_width=True)
            st.info("💡 **Insight:** Las barras más oscuras y a la derecha representan capital en riesgo de quedar obsoleto.")

        # GRÁFICO 2: Top Proyectos (Mantenemos el clásico)
        with c2:
            st.markdown("##### 🏆 Top Proyectos (Congestión)")
            df_proy = df_filtrado.groupby('Nombre Proyecto')['Valor Pendiente Total'].sum().reset_index()
            
            chart_proy = alt.Chart(df_proy).mark_bar().encode(
                x=alt.X('Valor Pendiente Total', title='Monto Pendiente ($)'),
                y=alt.Y('Nombre Proyecto', sort='-x'),
                color=alt.Color('Valor Pendiente Total', scale=alt.Scale(scheme='greens')),
                tooltip=[
                    alt.Tooltip('Nombre Proyecto'), 
                    alt.Tooltip('Valor Pendiente Total', format='$,.0f')
                ]
            ).transform_window(
                rank='rank(Valor Pendiente Total)',
                sort=[alt.SortField('Valor Pendiente Total', order='descending')]
            ).transform_filter(alt.datum.rank <= 10).properties(height=350)
            
            st.altair_chart(chart_proy, use_container_width=True)
    
    with tab2:
        st.subheader("🗺️ Mapa de Calor de Rutas")
        c_ruta1, c_ruta2 = st.columns([2, 1])
        
        df_rutas = analysis.analizar_rutas_logisticas(df_filtrado)
        
        with c_ruta1:
            st.altair_chart(charts.plot_heatmap_rutas(df_rutas), use_container_width=True)
        
        with c_ruta2:
            st.markdown("**Top Rutas Críticas**")
            st.dataframe(
                df_rutas.sort_values('Valor Pendiente Total', ascending=False).head(10),
                column_config={"Valor Pendiente Total": st.column_config.NumberColumn(format="$%.0f")},
                hide_index=True,
                use_container_width=True
            )

    with tab3:
        st.subheader("💎 Clasificación ABC (Pareto)")
        st.markdown("Enfócate en los artículos **Clase A**: Representan el 80% del valor pendiente.")
        
        df_pareto = analysis.calcular_pareto_pendientes(df_filtrado)
        
        if not df_pareto.empty:
            df_pareto['% Acumulado'] = df_pareto['% Acumulado'] * 100
        
        st.dataframe(
            df_pareto,
            column_config={
                "Valor Pendiente Total": st.column_config.NumberColumn(format="$%.0f"),
                "% Acumulado": st.column_config.NumberColumn(format="%.1f%%"),
                "Clasificación": st.column_config.Column(width="small")
            },
            use_container_width=True
        )

    with tab4:
        # --- 7. TABLA DETALLADA CON FORMATO ---
        st.subheader("Listado Detallado")
        
        df_show = df_filtrado.sort_values('Valor Pendiente Total', ascending=False)

        st.dataframe(
            df_show,
            column_config={
                "Fecha Contab.": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
                "Dias_Pendiente": st.column_config.NumberColumn("Días Antigüedad"), # Nueva columna visual
                "Costo Unitario": st.column_config.NumberColumn(
                    "Costo Unit.", format="$ %.0f"
                ),
                "Valor Pendiente Total": st.column_config.NumberColumn(
                    "Valor Total ($)", 
                    format="$ %.0f",
                    help="Cantidad * Costo Unitario"
                ),
                "Cant. Pendiente": st.column_config.NumberColumn(
                    "Pendiente", format="%.1f"
                ),
            },
            use_container_width=True,
            height=600,
            hide_index=True
        )

else:
    st.info("✅ No hay movimientos pendientes que cumplan con los filtros.")