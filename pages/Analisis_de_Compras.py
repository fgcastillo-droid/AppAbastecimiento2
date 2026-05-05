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

# --- Configuración de Página ---
st.set_page_config(layout="wide", page_title="Análisis de Compras Históricas", page_icon="🛍️")
ui_helpers.setup_locale()

st.title("🛍️ Análisis de Compras Históricas")
st.markdown("Explora el historial de compras (OCs) filtrando por categorías y ajustando la granularidad temporal.")

# --- 1. Carga de Datos ---
if 'data_loaded' not in st.session_state or not st.session_state.data_loaded:
    st.error("⚠️ Datos no cargados. Por favor, inicie desde el Menú Principal.")
    st.stop()

# Cargamos OCs y Stock (para categorías)
try:
    df_oc = st.session_state.df_oc
    df_stock = st.session_state.df_stock
except Exception as e:
    st.error(f"Error al cargar datos de sesión: {e}")
    st.stop()

# --- 2. Preparación y Enriquecimiento de Datos ---
with st.spinner("Procesando historial de compras..."):
    # A. Normalizar columnas clave para el cruce
    # En OC suele llamarse 'Número de artículo', en Stock 'CodigoArticulo'
    if 'Número de artículo' not in df_oc.columns:
        st.error("La tabla de OCs no tiene la columna 'Número de artículo'.")
        st.stop()

    # Creamos un subset temporal sin mutar la memoria original
    df_oc_temp = df_oc.assign(Codigo_Cruze=df_oc['Número de artículo'].astype(str).str.strip())


@st.cache_data(show_spinner=False)
def preparar_datos_compras(df_oc_raw, df_stock_raw):
    df_oc_local = df_oc_raw.copy()
    df_stock_local = df_stock_raw.copy()
    
    # Preparamos el maestro de categorías desde Stock
    if 'Número de artículo' not in df_oc_local.columns:
        return None
        
    df_oc_temp = df_oc_local.assign(Codigo_Cruze=df_oc_local['Número de artículo'].astype(str).str.strip())
    
    cols_maestro = ['CodigoArticulo', 'NombreArticulo', 'Familia', 'SubFamilia']
    # Validar que existan en df_stock
    cols_maestro = [c for c in cols_maestro if c in df_stock.columns]
    cols_maestro = [c for c in cols_maestro if c in df_stock_local.columns]
    
    df_maestro = df_stock[cols_maestro].drop_duplicates('CodigoArticulo').copy()
    df_maestro = df_stock_local[cols_maestro].drop_duplicates('CodigoArticulo').copy()
    df_maestro['CodigoArticulo'] = df_maestro['CodigoArticulo'].astype(str).str.strip()

    # B. Cruce (Left Join para mantener todas las compras aunque el SKU ya no esté activo)
    df_full = pd.merge(df_oc_temp, df_maestro, left_on='Codigo_Cruze', right_on='CodigoArticulo', how='left')
    df_full_local = pd.merge(df_oc_temp, df_maestro, left_on='Codigo_Cruze', right_on='CodigoArticulo', how='left')

    # C. Limpieza de Nulos post-cruce
    if 'Familia' not in df_full.columns:
        df_full['Familia'] = 'Sin Clasificar'
    df_full['Familia'] = df_full['Familia'].fillna('Sin Clasificar')
    if 'Familia' not in df_full_local.columns:
        df_full_local['Familia'] = 'Sin Clasificar'
    df_full_local['Familia'] = df_full_local['Familia'].fillna('Sin Clasificar')

    if 'SubFamilia' not in df_full.columns:
        df_full['SubFamilia'] = 'Sin Clasificar'
    df_full['SubFamilia'] = df_full['SubFamilia'].fillna('Sin Clasificar')
    if 'SubFamilia' not in df_full_local.columns:
        df_full_local['SubFamilia'] = 'Sin Clasificar'
    df_full_local['SubFamilia'] = df_full_local['SubFamilia'].fillna('Sin Clasificar')

    if 'NombreArticulo' in df_full.columns:
        # A veces el nombre viene en la OC como 'Descripción artículo/serv.'
        df_full['Nombre_Final'] = df_full['NombreArticulo'].fillna(df_full.get('Descripción artículo/serv.', 'Desconocido'))
    if 'NombreArticulo' in df_full_local.columns:
        df_full_local['Nombre_Final'] = df_full_local['NombreArticulo'].fillna(df_full_local.get('Descripción artículo/serv.', 'Desconocido'))
    else:
        df_full['Nombre_Final'] = df_full.get('Descripción artículo/serv.', 'Desconocido')
        df_full_local['Nombre_Final'] = df_full_local.get('Descripción artículo/serv.', 'Desconocido')

    # D. Asegurar Fechas y Números
    df_full['Fecha de contabilización'] = pd.to_datetime(df_full['Fecha de contabilización'])
    df_full['Total_Linea'] = pd.to_numeric(df_full['Total_Linea'], errors='coerce').fillna(0)
    df_full['Cantidad'] = pd.to_numeric(df_full['Cantidad'], errors='coerce').fillna(0)
    df_full_local['Fecha de contabilización'] = pd.to_datetime(df_full_local['Fecha de contabilización'])
    df_full_local['Total_Linea'] = pd.to_numeric(df_full_local['Total_Linea'], errors='coerce').fillna(0)
    df_full_local['Cantidad'] = pd.to_numeric(df_full_local['Cantidad'], errors='coerce').fillna(0)
    
    return df_full_local

with st.spinner("Procesando historial de compras..."):
    df_full = preparar_datos_compras(df_oc, df_stock)
    if df_full is None:
        st.error("La tabla de OCs no tiene la columna 'Número de artículo'.")
        st.stop()

# --- 3. Barra Lateral de Filtros ---
st.sidebar.header("🔍 Filtros de Análisis")

# 3.1 Filtro de Fechas
min_date = df_full['Fecha de contabilización'].min().date()
max_date = df_full['Fecha de contabilización'].max().date()
fechas_sel = st.sidebar.date_input("Rango de Fechas:", value=(min_date, max_date), min_value=min_date, max_value=max_date)

# 3.2 Granularidad Temporal
opcion_tiempo = st.sidebar.radio("Agrupar por:", ["Mensual", "Trimestral", "Anual"], index=0)
mapa_freq = {"Mensual": "M", "Trimestral": "Q", "Anual": "Y"}
freq_pandas = mapa_freq[opcion_tiempo]

st.sidebar.divider()

# 3.3 Filtros de Categoría (Cascada)
# Familia
familias_disp = sorted(df_full['Familia'].astype(str).unique())
sel_familias = st.sidebar.multiselect("Familia:", familias_disp, default=familias_disp)

# Filtrar dataframe temporal para opciones de Subfamilia
df_temp = df_full[df_full['Familia'].isin(sel_familias)]

# Subfamilia
subfam_disp = sorted(df_temp['SubFamilia'].astype(str).unique())
sel_subfam = st.sidebar.multiselect("Subfamilia:", subfam_disp, default=subfam_disp)

# Filtrar dataframe temporal para opciones de SKU
df_temp = df_temp[df_temp['SubFamilia'].isin(sel_subfam)]

# SKU (Opcional, búsqueda)
sku_disp = sorted(df_temp['Codigo_Cruze'].unique())
# Para que no se llene la sidebar, usamos un multiselect vacío por defecto (significa "Todos")
sel_skus = st.sidebar.multiselect("Filtrar Artículos Específicos (SKU):", sku_disp)

# --- 4. Aplicación de Filtros ---
if len(fechas_sel) == 2:
    start_d, end_d = fechas_sel
    mask = (
        (df_full['Fecha de contabilización'].dt.date >= start_d) &
        (df_full['Fecha de contabilización'].dt.date <= end_d) &
        (df_full['Familia'].isin(sel_familias)) &
        (df_full['SubFamilia'].isin(sel_subfam))
    )
    if sel_skus:
        mask &= (df_full['Codigo_Cruze'].isin(sel_skus))
    
    df_filtered = df_full[mask].copy()
else:
    st.info("Seleccione un rango de fechas válido.")
    st.stop()

if df_filtered.empty:
    st.warning("No se encontraron compras con los filtros seleccionados.")
    st.stop()

# --- 5. Agrupación Temporal ---
# Creamos la columna de Periodo según la selección
df_filtered['Periodo'] = df_filtered['Fecha de contabilización'].dt.to_period(freq_pandas).astype(str)

# Agrupamos
df_grouped = df_filtered.groupby('Periodo').agg(
    Monto_Comprado=('Total_Linea', 'sum'),
    Unidades_Compradas=('Cantidad', 'sum'),
    Num_Ordenes=('Número de documento', 'nunique')
).reset_index()

# --- 6. Dashboard ---

# 6.1 KPIs Superiores
col1, col2, col3, col4 = st.columns(4)
col1.metric("Monto Total Comprado", f"${df_filtered['Total_Linea'].sum():,.0f}")
col2.metric("Unidades Totales", f"{df_filtered['Cantidad'].sum():,.0f}")
col3.metric("OCs Emitidas", f"{df_filtered['Número de documento'].nunique():,.0f}")
col4.metric("SKUs Distintos", f"{df_filtered['Codigo_Cruze'].nunique():,.0f}")

st.divider()

# 6.2 Gráficos de Evolución
tab_graf, tab_detalle = st.tabs(["📊 Evolución Temporal", "📋 Detalle por Artículo"])

with tab_graf:
    st.subheader(f"Evolución de Compras ({opcion_tiempo})")
    
    # Gráfico Dual: Barras (Monto) y Línea (Unidades)
    base = alt.Chart(df_grouped).encode(x=alt.X('Periodo', title='Periodo'))

    barras = base.mark_bar(color='#3498db').encode(
        y=alt.Y('Monto_Comprado', title='Monto ($)', axis=alt.Axis(format='$,.0f')),
        tooltip=['Periodo', alt.Tooltip('Monto_Comprado', format='$,.0f')]
    )

    linea = base.mark_line(color='#e74c3c', point=True).encode(
        y=alt.Y('Unidades_Compradas', title='Unidades', axis=alt.Axis(grid=False)),
        tooltip=['Periodo', alt.Tooltip('Unidades_Compradas', format=',.0f')]
    )

    st.altair_chart(alt.layer(barras, linea).resolve_scale(y='independent'), use_container_width=True)

    # Desglose por Familia (Gráfico de Área)
    st.subheader("Composición por Familia")
    df_familia_periodo = df_filtered.groupby(['Periodo', 'Familia'])['Total_Linea'].sum().reset_index()
    
    chart_area = alt.Chart(df_familia_periodo).mark_area().encode(
        x='Periodo',
        y=alt.Y('Total_Linea', title='Monto ($)', stack='center'),
        color='Familia',
        tooltip=['Periodo', 'Familia', alt.Tooltip('Total_Linea', format='$,.0f')]
    ).interactive()
    st.altair_chart(chart_area, use_container_width=True)

with tab_detalle:
    st.subheader("Matriz de Compras: Artículo vs Periodo")
    
    # Switch para ver Dinero o Cantidad
    ver_monto = st.toggle("Ver Montos ($)", value=True, help="Si está desactivado, muestra Unidades.")
    col_valor = 'Total_Linea' if ver_monto else 'Cantidad'
    fmt_valor = "$%d" if ver_monto else "%d"

    # Pivot Table Dinámica
    df_pivot = df_filtered.pivot_table(
        index=['Codigo_Cruze', 'Nombre_Final', 'Familia'],
        columns='Periodo',
        values=col_valor,
        aggfunc='sum',
        fill_value=0
    )
    
    # Añadir total por fila
    df_pivot['TOTAL'] = df_pivot.sum(axis=1)
    df_pivot = df_pivot.sort_values('TOTAL', ascending=False)

    # Configuración de columnas para Streamlit
    col_config = {
        "TOTAL": st.column_config.NumberColumn("Total Periodo", format=fmt_valor),
        "Codigo_Cruze": st.column_config.TextColumn("SKU"),
        "Nombre_Final": st.column_config.TextColumn("Descripción", width="large")
    }
    # Configurar columnas de fechas dinámicamente
    for col in df_pivot.columns:
        if col not in col_config and col not in ['Codigo_Cruze', 'Nombre_Final', 'Familia']:
            col_config[col] = st.column_config.NumberColumn(col, format=fmt_valor)

    st.dataframe(df_pivot.reset_index(), column_config=col_config, use_container_width=True, hide_index=True)
    