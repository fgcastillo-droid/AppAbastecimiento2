# --- ARCHIVO: pages/kpis_compradores.py ---
# (Actualizado para corregir ArrowTypeError y SettingWithCopyWarning)

import streamlit as st
import pandas as pd
import altair as alt
import sys
from pathlib import Path

# --- 1. Configuración del Path (para importar data_loader) ---
# Añade el directorio 'src' al path si no está
src_path = str(Path(__file__).parent.parent / "src")
if src_path not in sys.path:
    sys.path.append(src_path)

import data.data_loader as data_loader 

# --- 2. Configuración de la Página ---
st.set_page_config(
    layout="wide",
    page_title="KPIs Compradores",
    page_icon="📊" # Ícono de ejemplo
)

# --- 3. Carga y Verificación de Datos ---
# Nos aseguramos de que los datos estén cargados en la sesión
if 'data_loaded' not in st.session_state:
    st.info("Cargando datos... por favor, espere.")
    # Intenta cargar los datos si no están (aunque app.py ya deberia haberlo hecho)
    data_loader.load_data_into_session()

# Si, después de intentar, sigue sin datos, detenemos.
if 'data_loaded' not in st.session_state:
    st.error("No se pudieron cargar los datos. Por favor, reinicie desde la página 'Menú'.")
    st.stop()

# Accedemos a los datos desde la sesión
try:
    df_oc = st.session_state.df_oc
    
    # --- Verificación de Columnas (Añadido 'Comentarios') ---
    columnas_necesarias = ['Creador', 'Fecha de contabilización', 'Número de documento', 'Total_Linea', 'Comentarios']
    if not all(col in df_oc.columns for col in columnas_necesarias):
        st.error(f"Error: El archivo 'OPOR.xlsx' no contiene las columnas necesarias: {columnas_necesarias}")
        st.stop()
        
except AttributeError:
    st.error("Error al acceder a 'df_oc' en st.session_state. Vuelva al 'Menú' principal.")
    st.stop()
except Exception as e:
    st.error(f"Ocurrió un error inesperado al preparar los datos: {e}")
    st.stop()


# --- 4. Título y Encabezado de la Página ---
st.image("assets/COPEC-FLUX.svg", width=150)
st.title("📊 KPIs del Equipo de Abastecimiento")
st.markdown("Análisis del rendimiento de los compradores basado en Órdenes de Compra (OC).")

st.markdown("---")

# --- 5. Filtros en la Barra Lateral (Sidebar) ---
st.sidebar.header("Filtros del Dashboard")

# Obtener lista de compradores únicos
lista_compradores = df_oc['Creador'].unique()
compradores_seleccionados = st.sidebar.multiselect(
    "Seleccione Comprador(es)",
    options=lista_compradores,
    default=lista_compradores
)

# Filtro de Rango de Fechas
min_fecha = df_oc['Fecha de contabilización'].min().date()
max_fecha = df_oc['Fecha de contabilización'].max().date()

# Calcular inicio de año actual para el valor por defecto
inicio_anio = pd.Timestamp.now().replace(month=1, day=1).date()

# Validamos que el inicio del año esté dentro de los datos disponibles
default_start = max(min_fecha, inicio_anio)
if default_start > max_fecha: default_start = min_fecha

fecha_inicio, fecha_fin = st.sidebar.date_input(
    "Seleccione Rango de Fechas",
    value=(default_start, max_fecha),
    min_value=min_fecha,
    max_value=max_fecha,
    format="DD/MM/YYYY"
)

# --- 6. Aplicación de Filtros y Correcciones ---
if not compradores_seleccionados:
    st.warning("Por favor, seleccione al menos un comprador en el filtro lateral.")
    st.stop()

# Convertir fechas de date_input (date) a Timestamp para comparar
fecha_inicio_ts = pd.to_datetime(fecha_inicio)
fecha_fin_ts = pd.to_datetime(fecha_fin)

# Filtrar el DataFrame
df_filtrado = df_oc[
    (df_oc['Creador'].isin(compradores_seleccionados)) &
    (df_oc['Fecha de contabilización'] >= fecha_inicio_ts) &
    (df_oc['Fecha de contabilización'] <= fecha_fin_ts)
].copy() # <--- *** CORRECCIÓN 1: Se añade .copy() para evitar SettingWithCopyWarning ***

# --- CORRECCIÓN 2: Forzar 'Comentarios' a string para evitar ArrowTypeError ---
# Esto convierte todos los valores (incluyendo números) a texto y rellena vacíos.
df_filtrado['Comentarios'] = df_filtrado['Comentarios'].astype(str).fillna('')


if df_filtrado.empty:
    st.warning("No se encontraron datos para los filtros seleccionados.")
    st.stop()

# --- 7. KPIs Principales (Métricas) ---
st.header("Métricas Globales (filtradas)")

col1, col2, col3 = st.columns(3)

# KPI 1: Monto Total Comprado
monto_total = df_filtrado['Total_Linea'].sum()
col1.metric("Monto Total Comprado", f"${monto_total:,.0f} CLP")

# KPI 2: OCs Únicas Generadas
ocs_unicas = df_filtrado['Número de documento'].nunique()
col2.metric("Nº OCs Únicas Generadas", f"{ocs_unicas}")

# KPI 3: Compradores Activos
compradores_activos = df_filtrado['Creador'].nunique()
col3.metric("Compradores Activos (en filtro)", f"{compradores_activos}")

st.markdown("---")

# --- 8. Visualizaciones ---
st.header("Análisis Visual")

# Preparar datos para gráficos mensuales
# (Esto ya no dará el Warning gracias al .copy() de arriba)
df_filtrado['Año-Mes'] = df_filtrado['Fecha de contabilización'].dt.to_period('M').astype(str)

# Agrupar por mes y comprador para los gráficos mensuales
df_mensual_monto = df_filtrado.groupby(['Año-Mes', 'Creador'])['Total_Linea'].sum().reset_index()


# --- Gráfico 1: Compras Mensuales (Monto) - Líneas ---
with st.container(border=True):
    st.subheader("Evolución de Compras Mensuales (Monto Total)")
    
    chart_linea_monto = alt.Chart(df_mensual_monto).mark_line(point=True).encode(
        x=alt.X('Año-Mes', title='Mes'),
        y=alt.Y('Total_Linea', title='Monto Total Comprado (CLP)', axis=alt.Axis(format='$,.0f')),
        color=alt.Color('Creador', title='Comprador'),
        tooltip=[
            alt.Tooltip('Año-Mes', title='Mes'),
            alt.Tooltip('Creador', title='Comprador'),
            alt.Tooltip('Total_Linea', title='Monto Total', format='$,.0f')
        ]
    ).interactive()
    
    st.altair_chart(chart_linea_monto, use_container_width=True)

# --- Gráfico 2: Compras Mensuales (Monto) - Barras Apiladas (NUEVO) ---
with st.container(border=True):
    st.subheader("Compras Mensuales (Monto Total) - Barras Apiladas")
    
    # Reutilizamos df_mensual_monto
    
    chart_barra_monto_mensual = alt.Chart(df_mensual_monto).mark_bar().encode(
        # Ejes X e Y
        x=alt.X('Año-Mes', title='Mes'),
        y=alt.Y('Total_Linea', title='Monto Total Comprado (CLP)', axis=alt.Axis(format='$,.0f')),
        # Color apilado por Comprador
        color=alt.Color('Creador', title='Comprador'),
        # Tooltip para detalles
        tooltip=[
            alt.Tooltip('Año-Mes', title='Mes'),
            alt.Tooltip('Creador', title='Comprador'),
            alt.Tooltip('Total_Linea', title='Monto Total', format='$,.0f')
        ]
    ).interactive()
    
    st.altair_chart(chart_barra_monto_mensual, use_container_width=True)

# --- Gráfico 3: OCs Mensuales (Conteo) - Barras Apiladas (NUEVO) ---
with st.container(border=True):
    st.subheader("OCs Únicas Mensuales - Barras Apiladas")
    
    # Agrupar por mes y comprador, contando OCs únicas
    df_mensual_ocs = df_filtrado.groupby(['Año-Mes', 'Creador']).agg(
        Conteo_OCs=('Número de documento', 'nunique')
    ).reset_index()
    
    chart_barra_ocs_mensual = alt.Chart(df_mensual_ocs).mark_bar().encode(
        # Ejes X e Y
        x=alt.X('Año-Mes', title='Mes'),
        y=alt.Y('Conteo_OCs', title='Nº OCs Únicas'),
        # Color apilado por Comprador
        color=alt.Color('Creador', title='Comprador'),
        # Tooltip para detalles
        tooltip=[
            alt.Tooltip('Año-Mes', title='Mes'),
            alt.Tooltip('Creador', title='Comprador'),
            alt.Tooltip('Conteo_OCs', title='Nº OCs Únicas')
        ]
    ).interactive()
    
    st.altair_chart(chart_barra_ocs_mensual, use_container_width=True)


# --- Gráfico 4: OCs Únicas Generadas por Comprador (Total) ---
with st.container(border=True):
    st.subheader("Total OCs Únicas Generadas por Comprador")
    
    # Agrupar por comprador para KPIs
    df_kpi_comprador = df_filtrado.groupby('Creador').agg(
        Monto_Total=('Total_Linea', 'sum'),
        OCs_Unicas=('Número de documento', 'nunique')
    ).reset_index().sort_values(by='OCs_Unicas', ascending=False)
    
    chart_barra_ocs = alt.Chart(df_kpi_comprador).mark_bar().encode(
        x=alt.X('OCs_Unicas', title='Cantidad de OCs Únicas'),
        y=alt.Y('Creador', title='Comprador', sort='-x'),
        color=alt.Color('Creador', title='Comprador'),
        tooltip=[
            alt.Tooltip('Creador', title='Comprador'),
            alt.Tooltip('OCs_Unicas', title='OCs Únicas'),
            alt.Tooltip('Monto_Total', title='Monto Total', format='$,.0f')
        ]
    ).interactive()
    
    st.altair_chart(chart_barra_ocs, use_container_width=True)


# --- Gráfico 5: Monto Total Comprado por Comprador (Total) ---
with st.container(border=True):
    st.subheader("Monto Total Comprado por Comprador")
    
    # Reutilizamos df_kpi_comprador, pero ordenado por Monto_Total
    df_kpi_comprador_monto = df_kpi_comprador.sort_values(by='Monto_Total', ascending=False)

    chart_barra_monto = alt.Chart(df_kpi_comprador_monto).mark_bar().encode(
        x=alt.X('Monto_Total', title='Monto Total Comprado (CLP)', axis=alt.Axis(format='$,.0f')),
        y=alt.Y('Creador', title='Comprador', sort='-x'),
        color=alt.Color('Creador', title='Comprador'),
        tooltip=[
            alt.Tooltip('Creador', title='Comprador'),
            alt.Tooltip('Monto_Total', title='Monto Total', format='$,.0f'),
            alt.Tooltip('OCs_Unicas', title='OCs Únicas')
        ]
    ).interactive()
    
    st.altair_chart(chart_barra_monto, use_container_width=True)

# --- 9. Vista de Datos (Detalle) ---
with st.expander("Ver tabla de datos filtrados"):
    # Esto ya no dará error gracias a la corrección de 'Comentarios'
    st.dataframe(df_filtrado)