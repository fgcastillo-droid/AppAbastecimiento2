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
st.set_page_config(layout="wide", page_title="Modelo C&I - Simulación Futura", page_icon="🏗️")
ui_helpers.setup_locale()

# --- Configuración de Columnas ---
# Si en el futuro cambian los nombres en los Excel, ¡solo modifícalos aquí!

# 1. Maestro / Stock
COL_MAESTRO_SKU = 'CodigoArticulo'
COL_MAESTRO_NOMBRE = 'NombreArticulo'
COL_MAESTRO_FAMILIA = 'Familia'
COL_MAESTRO_SUBFAMILIA = 'SubFamilia'
COL_MAESTRO_BODEGA = 'CodigoBodega'
COL_MAESTRO_STOCK = 'StockActual'

# 2. Requerimientos (Proyectos)
COL_REQ_SKU = 'sku'
COL_REQ_FIRMADO = 'estado comercial (won,open)' # si se firmó el proyecto o no
COL_RQ_ESTADO_GLOBAL = 'estado global' # estado del proyecto
COL_REQ_FECHA = 'fecha tentativa'
COL_REQ_CANTIDAD = 'cantidad'
COL_REQ_PROYECTO = 'proyecto'
COL_REQ_ABASTECIMIENTO = 'Abastecimiento (orgánico - calzado)'

# 3. Órdenes de Compra (OCs)
COL_OC_SKU = 'Número de artículo'
COL_OC_FECHA = 'Fecha de entrega de la línea'
COL_OC_CANTIDAD = 'Cantidad'
COL_OC_DOC = 'Número de documento'
COL_OC_COMENTARIOS = 'Comentarios'

st.title("🏗️ Modelo de Disponibilidad Futura (C&I)")
st.markdown("""
Simulador de inventario proyectado.  
**Fórmula:** `Stock Proyectado (Día X)` = `Stock BF0001 (Hoy)` + `Llegadas OC (Acum)` - `Requerimientos Proyectos (Acum)`
""")

# --- 1. Verificación de Datos ---
if 'data_loaded' not in st.session_state or not st.session_state.data_loaded:
    st.error("⚠️ Datos no cargados. Por favor, inicie desde el Menú Principal.")
    st.stop()

if 'df_requerimientos' not in st.session_state:
    st.error("⚠️ No se encontró la tabla de Requerimientos. Verifique la carga de datos.")
    st.stop()

# Carga de datos
df_stock = st.session_state.df_stock
df_oc = st.session_state.df_oc
df_req = st.session_state.df_requerimientos

# --- 2. Preparación de Datos (Universo Requerimientos) ---
# Solo trabajamos con SKUs que están en la tabla de requerimientos
skus_requeridos = df_req[COL_REQ_SKU].unique()

# Cruzamos con Maestro de Artículos para obtener Familias y Nombres
cols_maestro = [COL_MAESTRO_SKU, COL_MAESTRO_NOMBRE, COL_MAESTRO_FAMILIA, COL_MAESTRO_SUBFAMILIA]
df_maestro = df_stock[cols_maestro].drop_duplicates(COL_MAESTRO_SKU)

# Cruzamos con Stock Físico (BF0001) para obtener stock actual
df_stock_bf = df_stock[df_stock[COL_MAESTRO_BODEGA] == 'BF0001'][[COL_MAESTRO_SKU, COL_MAESTRO_STOCK]].groupby(COL_MAESTRO_SKU).sum().reset_index()

# DataFrame Base (El universo de análisis)
df_base = pd.DataFrame({'SKU': skus_requeridos})
df_base = df_base.merge(df_maestro, left_on='SKU', right_on=COL_MAESTRO_SKU, how='left')
df_base = df_base.merge(df_stock_bf, left_on='SKU', right_on=COL_MAESTRO_SKU, how='left', suffixes=('', '_stock'))

# Limpieza de Nulos
df_base[COL_MAESTRO_FAMILIA] = df_base[COL_MAESTRO_FAMILIA].fillna('Sin Clasificar')
df_base[COL_MAESTRO_SUBFAMILIA] = df_base[COL_MAESTRO_SUBFAMILIA].fillna('Sin Clasificar')
df_base[COL_MAESTRO_NOMBRE] = df_base[COL_MAESTRO_NOMBRE].fillna('Desconocido')
df_base[COL_MAESTRO_STOCK] = df_base[COL_MAESTRO_STOCK].fillna(0)

# --- 2. Filtros y Selección ---
st.sidebar.header("🔍 Configuración")

dias_simulacion = st.sidebar.slider("Días a proyectar:", 30, 365, 200)
st.sidebar.divider()

# Filtro de Estado 'Firmado'
opciones_firmado = sorted(df_req[COL_REQ_FIRMADO].unique()) if COL_REQ_FIRMADO in df_req.columns else []
sel_firmado = st.sidebar.multiselect("Estado 'Firmado':", opciones_firmado, default=opciones_firmado, help="Seleccione 'si' para ver solo compromisos firmados, o agregue otros estados para proyecciones.")

# Filtro de Abastecimiento (Orgánico/Calzado)
opciones_abastecimiento = sorted(df_req[COL_REQ_ABASTECIMIENTO].unique()) if COL_REQ_ABASTECIMIENTO in df_req.columns else []
sel_abastecimiento = st.sidebar.multiselect("Tipo Abastecimiento:", opciones_abastecimiento, default=opciones_abastecimiento)

# Filtro por Proyecto
opciones_proyecto = sorted(df_req[COL_REQ_PROYECTO].unique()) if COL_REQ_PROYECTO in df_req.columns else []
sel_proyectos = st.sidebar.multiselect("Filtrar por Proyecto:", opciones_proyecto, default=[])

st.sidebar.divider()

# Filtros Jerárquicos
familias_disp = sorted(df_base[COL_MAESTRO_FAMILIA].unique())
sel_familias = st.sidebar.multiselect("Filtrar Familia:", familias_disp, default=familias_disp)

# Filtrar subfamilias basado en familia
df_base_filt = df_base[df_base[COL_MAESTRO_FAMILIA].isin(sel_familias)]
subfam_disp = sorted(df_base_filt[COL_MAESTRO_SUBFAMILIA].unique())
sel_subfam = st.sidebar.multiselect("Filtrar Subfamilia:", subfam_disp, default=subfam_disp)

# Dataset Final para Simulación
df_target = df_base_filt[df_base_filt[COL_MAESTRO_SUBFAMILIA].isin(sel_subfam)].copy()

if df_target.empty:
    st.warning("No hay productos que coincidan con los filtros seleccionados.")
    st.stop()

st.sidebar.markdown(f"**Total Artículos:** {len(df_target)}")

# --- 3. Motor de Cálculo ---

def simular_sku(sku, stock_ini, dias, df_oc_global, df_req_global):
    """Calcula proyección rápida para un SKU"""
    hoy = pd.Timestamp.now().floor('D')
    fecha_fin = hoy + pd.Timedelta(days=dias)

    # B. Llegadas (OCs)
    llegadas = df_oc_global[
        (df_oc_global[COL_OC_SKU] == sku) &
        (df_oc_global[COL_OC_FECHA] >= hoy) &
        (df_oc_global[COL_OC_CANTIDAD] > 0)
    ].copy()
    
    if COL_OC_COMENTARIOS not in llegadas.columns:
        llegadas[COL_OC_COMENTARIOS] = ""

    llegadas = llegadas[[COL_OC_FECHA, COL_OC_CANTIDAD, COL_OC_DOC, COL_OC_COMENTARIOS]].rename(
        columns={COL_OC_FECHA: 'Fecha', COL_OC_CANTIDAD: 'Cantidad_Entrada', COL_OC_DOC: 'Detalle'}
    )

    # C. Salidas (Requerimientos)
    salidas = df_req_global[
        (df_req_global[COL_REQ_SKU] == sku) &
        (df_req_global[COL_REQ_FECHA] >= hoy)
    ].copy()
    salidas = salidas[[COL_REQ_FECHA, COL_REQ_CANTIDAD, COL_REQ_PROYECTO]].rename(
        columns={COL_REQ_FECHA: 'Fecha', COL_REQ_CANTIDAD: 'Cantidad_Salida', COL_REQ_PROYECTO: 'Detalle'}
    )

    # D. Construcción de Línea de Tiempo
    rango_fechas = pd.date_range(start=hoy, end=fecha_fin, freq='D')
    df_timeline = pd.DataFrame({'Fecha': rango_fechas})
    
    llegadas_dia = llegadas.groupby('Fecha')['Cantidad_Entrada'].sum().reset_index()
    salidas_dia = salidas.groupby('Fecha')['Cantidad_Salida'].sum().reset_index()

    df_sim = df_timeline.merge(llegadas_dia, on='Fecha', how='left').merge(salidas_dia, on='Fecha', how='left').fillna(0)
    
    df_sim['Saldo_Diario'] = df_sim['Cantidad_Entrada'] - df_sim['Cantidad_Salida']
    df_sim['Stock_Proyectado'] = stock_ini + df_sim['Saldo_Diario'].cumsum()

    # Identificar quiebres
    min_stock = df_sim['Stock_Proyectado'].min()
    fecha_quiebre = df_sim[df_sim['Stock_Proyectado'] < 0]['Fecha'].min() if min_stock < 0 else None
    
    return {
        'SKU': sku,
        'Stock_Inicial': stock_ini,
        'Total_Llegadas': llegadas['Cantidad_Entrada'].sum(),
        'Total_Salidas': salidas['Cantidad_Salida'].sum(),
        'Stock_Min_Proyectado': min_stock,
        'Fecha_Primer_Quiebre': fecha_quiebre,
        'df_sim': df_sim,
        'df_llegadas': llegadas,
        'df_salidas': salidas
    }

# Ejecución Masiva
resultados = []
with st.spinner(f"Simulando {len(df_target)} artículos..."):
    # Pre-filtramos las tablas grandes para optimizar el bucle
    df_oc_subset = df_oc[df_oc[COL_OC_SKU].isin(df_target['SKU'])].copy()

    # Construimos una máscara de filtros para los requerimientos
    mask_req = pd.Series(True, index=df_req.index)

    # 1. Filtro por SKUs relevantes para la simulación
    mask_req &= df_req[COL_REQ_SKU].isin(df_target['SKU'])

    # 2. Filtro por Estado Comercial (won, open, etc.)
    if COL_REQ_FIRMADO in df_req.columns:
        mask_req &= df_req[COL_REQ_FIRMADO].isin(sel_firmado)

    # 3. Filtro por Tipo de Abastecimiento (Orgánico / Calzado)
    if COL_REQ_ABASTECIMIENTO in df_req.columns:
        mask_req &= df_req[COL_REQ_ABASTECIMIENTO].isin(sel_abastecimiento)

    # 4. Filtro por Proyecto
    if sel_proyectos:
        if COL_REQ_PROYECTO in df_req.columns:
            mask_req &= df_req[COL_REQ_PROYECTO].isin(sel_proyectos)

    df_req_subset = df_req[mask_req].copy()

    for idx, row in df_target.iterrows():
        res = simular_sku(row['SKU'], row[COL_MAESTRO_STOCK], dias_simulacion, df_oc_subset, df_req_subset)
        res['Nombre'] = row[COL_MAESTRO_NOMBRE]
        resultados.append(res)

# DataFrame Resumen
df_resumen = pd.DataFrame(resultados)
df_resumen['Estado'] = df_resumen['Stock_Min_Proyectado'].apply(lambda x: "🔴 Quiebre" if x < 0 else "🟢 Cubierto")
df_resumen = df_resumen.sort_values('Stock_Min_Proyectado')

# --- 4. Vista Resumen (Global) ---
st.subheader("📊 Resumen de Disponibilidad Global")

# A. Agrupamos los KPIs globales en un contenedor limpio
with st.container(border=True):
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("Total Artículos Analizados", len(df_resumen))
    quiebres = len(df_resumen[df_resumen['Stock_Min_Proyectado'] < 0])
    kpi2.metric("Artículos con Riesgo de Quiebre", quiebres, delta=f"{quiebres} alertas", delta_color="inverse")
    kpi3.metric("Total Unidades Requeridas", f"{df_resumen['Total_Salidas'].sum():,.0f}")

# B. Pestañas para organizar la vista de resumen
tab_riesgos, tab_demanda = st.tabs(["🚨 Resumen de Riesgos", "📈 Análisis de Demanda"])

with tab_riesgos:
    st.dataframe(
        df_resumen[['Estado', 'SKU', 'Nombre', 'Stock_Inicial', 'Total_Salidas', 'Total_Llegadas', 'Stock_Min_Proyectado', 'Fecha_Primer_Quiebre']],
        column_config={
            "Fecha_Primer_Quiebre": st.column_config.DateColumn("Fecha Quiebre", format="DD/MM/YYYY"),
            "Stock_Min_Proyectado": st.column_config.NumberColumn("Mínimo Futuro"),
            "Stock_Inicial": st.column_config.NumberColumn("Stock Hoy")
        },
        use_container_width=True, hide_index=True
    )

with tab_demanda:
    if not df_req_subset.empty:
        st.markdown("#### Requerimientos por Mes (Unidades)")
        
        # Copiamos para no alterar el df original usado en la simulación
        df_demanda_vis = df_req_subset.copy()
        df_demanda_vis[COL_REQ_FECHA] = pd.to_datetime(df_demanda_vis[COL_REQ_FECHA], errors='coerce')
        df_demanda_vis.dropna(subset=[COL_REQ_FECHA], inplace=True)

        # Agrupamos por mes
        df_demanda_vis['Mes_Tentativo'] = df_demanda_vis[COL_REQ_FECHA].dt.to_period('M').astype(str)
        demanda_mensual = df_demanda_vis.groupby('Mes_Tentativo')[COL_REQ_CANTIDAD].sum().reset_index()

        chart_demanda_mes = alt.Chart(demanda_mensual).mark_bar().encode(
            x=alt.X('Mes_Tentativo:O', title='Mes Tentativo de Requerimiento', sort=alt.SortField('Mes_Tentativo')),
            y=alt.Y(f'{COL_REQ_CANTIDAD}:Q', title='Total Unidades Requeridas'),
            tooltip=['Mes_Tentativo', alt.Tooltip(f'{COL_REQ_CANTIDAD}:Q', title='Unidades')]
        ).properties(
            title='Demanda Futura Agrupada por Mes'
        )
        st.altair_chart(chart_demanda_mes, use_container_width=True)

        st.markdown("---")

        st.markdown("#### Top 10 Proyectos con Mayor Demanda (Unidades)")
        demanda_proyecto = df_demanda_vis.groupby(COL_REQ_PROYECTO)[COL_REQ_CANTIDAD].sum().reset_index()
        top_10_proyectos = demanda_proyecto.nlargest(10, COL_REQ_CANTIDAD)

        chart_demanda_proy = alt.Chart(top_10_proyectos).mark_bar().encode(
            x=alt.X(f'{COL_REQ_CANTIDAD}:Q', title='Total Unidades Requeridas'),
            y=alt.Y(f'{COL_REQ_PROYECTO}:N', title='Proyecto', sort='-x'),
            color=alt.Color(f'{COL_REQ_PROYECTO}:N', legend=None),
            tooltip=[f'{COL_REQ_PROYECTO}:N', alt.Tooltip(f'{COL_REQ_CANTIDAD}:Q', title='Unidades')]
        ).properties(
            title='Top 10 Proyectos por Unidades Requeridas'
        )
        st.altair_chart(chart_demanda_proy, use_container_width=True)
    else:
        st.info("No hay datos de requerimientos para los filtros seleccionados.")

st.divider()

# --- 5. Tabla Completa de Requerimientos ---
st.subheader("🗄️ Base de Datos Completa de Requerimientos")
st.markdown("La siguiente tabla muestra los requerimientos filtrados según las selecciones de la barra lateral.")

# 1. Enriquecer df_req con datos de familia/subfamilia para poder filtrar
df_mostrar = df_req.merge(
    df_maestro[[COL_MAESTRO_SKU, COL_MAESTRO_FAMILIA, COL_MAESTRO_SUBFAMILIA]], 
    left_on=COL_REQ_SKU, 
    right_on=COL_MAESTRO_SKU, 
    how='left'
)
df_mostrar[COL_MAESTRO_FAMILIA] = df_mostrar[COL_MAESTRO_FAMILIA].fillna('Sin Clasificar')
df_mostrar[COL_MAESTRO_SUBFAMILIA] = df_mostrar[COL_MAESTRO_SUBFAMILIA].fillna('Sin Clasificar')

# 2. Aplicar filtros globales de la barra lateral
# Filtro por Estado Comercial (won, open, etc.)
if sel_firmado:
    if COL_REQ_FIRMADO in df_mostrar.columns:
        df_mostrar = df_mostrar[df_mostrar[COL_REQ_FIRMADO].isin(sel_firmado)]

# Filtro por Tipo de Abastecimiento (Orgánico / Calzado)
if sel_abastecimiento:
    if COL_REQ_ABASTECIMIENTO in df_mostrar.columns:
        df_mostrar = df_mostrar[df_mostrar[COL_REQ_ABASTECIMIENTO].isin(sel_abastecimiento)]

# Filtro por Proyecto
if sel_proyectos:
    if COL_REQ_PROYECTO in df_mostrar.columns:
        df_mostrar = df_mostrar[df_mostrar[COL_REQ_PROYECTO].isin(sel_proyectos)]

# Filtro por Familia
df_mostrar = df_mostrar[df_mostrar[COL_MAESTRO_FAMILIA].isin(sel_familias)]

# Filtro por Subfamilia
df_mostrar = df_mostrar[df_mostrar[COL_MAESTRO_SUBFAMILIA].isin(sel_subfam)]

# --- Limpieza de Nulos para Visualización ---
# Para que la tabla se vea limpia y no muestre 'NaN' o 'NaT' y evitar errores.

# Columnas de texto: Reemplazar NaN con un string vacío ''
cols_texto_clean = df_mostrar.select_dtypes(include=['object', 'string']).columns
df_mostrar[cols_texto_clean] = df_mostrar[cols_texto_clean].fillna('')

# Columnas numéricas: Reemplazar NaN con 0
cols_num_clean = df_mostrar.select_dtypes(include=['number']).columns
df_mostrar[cols_num_clean] = df_mostrar[cols_num_clean].fillna(0)

# Configuración dinámica para ocultar la hora en las columnas de fecha
col_config = {}
for col in df_mostrar.select_dtypes(include=['datetime', 'datetimetz']).columns:
    col_config[col] = st.column_config.DateColumn(format="DD/MM/YYYY")

st.dataframe(df_mostrar, use_container_width=True, hide_index=True, column_config=col_config)
st.divider()

# --- 6. Análisis de Detalle por Producto ---
st.subheader("🔍 Simulación Detallada por Producto")

# Selector
sku_list = df_resumen['SKU'].tolist()
sku_labels = {row['SKU']: f"{row['SKU']} | {row['Nombre']} ({row['Estado']})" for _, row in df_resumen.iterrows()}
sku_sel = st.selectbox("Seleccione un Artículo para proyectar:", sku_list, format_func=lambda x: sku_labels[x])

data_sku = next(item for item in resultados if item["SKU"] == sku_sel)

df_sim = data_sku['df_sim']
stock_inicial = data_sku['Stock_Inicial']
salidas = data_sku['df_salidas']
llegadas = data_sku['df_llegadas']
hay_quiebre = data_sku['Stock_Min_Proyectado'] < 0
fecha_quiebre = data_sku['Fecha_Primer_Quiebre']

# 5.1 KPIs del SKU Seleccionado
c1, c2, c3, c4 = st.columns(4)
c1.metric("Stock Actual (BF0001)", f"{stock_inicial:,.0f}")
c2.metric("Total Requerido", f"{data_sku['Total_Salidas']:,.0f}", delta="Salida", delta_color="inverse")
c3.metric("Llegadas Confirmadas", f"{data_sku['Total_Llegadas']:,.0f}", delta="Entrada")

if hay_quiebre:
    c4.metric("⚠️ Riesgo de Quiebre", f"{fecha_quiebre.strftime('%d/%m/%Y')}", delta="Crítico", delta_color="inverse")
else:
    c4.metric("Estado Proyectado", "Cubierto ✅", delta="Sin Riesgo")

# 5.2 Gráfico Altair (Corregido)
st.markdown("#### 📉 Curva de Disponibilidad Proyectada")

base = alt.Chart(df_sim).encode(
    x=alt.X('Fecha:T', title='Timeline')
)

# Línea de 0 (Piso crítico)
regla_cero = alt.Chart(pd.DataFrame({'y': [0]})).mark_rule(color='red', strokeDash=[5, 5]).encode(y='y:Q')

# Línea de Stock (Cambia de color si baja de cero)
linea_stock = base.mark_line(interpolate='step-after', strokeWidth=3).encode(
    y=alt.Y('Stock_Proyectado:Q', title='Unidades'),
    # Condición: Azul si es positivo, Rojo si es negativo
    color=alt.condition(alt.datum.Stock_Proyectado >= 0, alt.value('#2980b9'), alt.value('#e74c3c')),
    tooltip=[
        alt.Tooltip('Fecha:T', title='Fecha', format='%d %b %Y'), 
        alt.Tooltip('Stock_Proyectado:Q', title='Stock', format=',.0f')
    ]
)

# Barras de Flujo inferior
barras_flujo = alt.Chart(df_sim[df_sim['Saldo_Diario'] != 0]).mark_bar().encode( # Filtramos los días sin movimiento
    x='Fecha:T',
    y=alt.Y('Saldo_Diario:Q', title='Flujo Neto'),
    color=alt.condition(alt.datum.Saldo_Diario > 0, alt.value('#27ae60'), alt.value('#c0392b')),
    tooltip=['Fecha:T', 'Saldo_Diario:Q']
).properties(height=120)

# Unimos línea de stock + la línea del cero
grafico_principal = (linea_stock + regla_cero).properties(height=350)

# Concatenamos verticalmente
st.altair_chart(alt.vconcat(grafico_principal, barras_flujo).resolve_scale(x='shared'), use_container_width=True)

# 4.3 Tablas de Detalle
c_left, c_right = st.columns(2)

with c_left:
    st.subheader("📋 Detalle de Requerimientos (Salidas)")
    if not salidas.empty:
        st.dataframe(
            salidas[['Fecha', 'Detalle', 'Cantidad_Salida']].sort_values('Fecha'),
            column_config={"Fecha": st.column_config.DateColumn("Fecha Entrega"), "Detalle": "Proyecto", "Cantidad_Salida": st.column_config.NumberColumn("Cant.")},
            use_container_width=True, hide_index=True
        )
    else:
        st.info("No hay requerimientos futuros registrados para este SKU.")

with c_right:
    st.subheader("📦 Detalle de Llegadas (OCs)")
    if not llegadas.empty:
        st.dataframe(
            llegadas[['Fecha', 'Detalle', 'Cantidad_Entrada', 'Comentarios']].sort_values('Fecha'),
            column_config={
                "Fecha": st.column_config.DateColumn("Fecha Llegada"), 
                "Detalle": "N° OC", 
                "Cantidad_Entrada": st.column_config.NumberColumn("Cant."),
                "Comentarios": st.column_config.TextColumn("Comentarios", width="medium")
            },
            use_container_width=True, hide_index=True
        )
    else:
        st.info("No hay órdenes de compra en tránsito.")