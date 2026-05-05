import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import sys
from pathlib import Path

# --- Configuración del Path ---
src_path = str(Path(__file__).resolve().parent.parent / "src")
if src_path not in sys.path:
    sys.path.append(src_path)

import ui.ui_helpers as ui_helpers

# Intentar importar LightGBM
try:
    import lightgbm as lgb
except ImportError:
    st.error("⚠️ La librería 'lightgbm' no está instalada. Por favor, instálela para usar este módulo.")
    st.stop()

# --- Configuración de Página ---
st.set_page_config(layout="wide", page_title="Predicción Consumo LightGBM", page_icon="🤖")
ui_helpers.setup_locale()

st.title("🤖 Predicción de Consumo (LightGBM)")
st.markdown("""
Este módulo utiliza un modelo **LightGBM** con hiperparámetros estándar para proyectar el consumo de SKUs a 12 meses.
Se alimenta de la tabla de Transferencias (OWTR/Consumo) y utiliza únicamente variables temporales (Mes, Año, Trimestre) 
para evitar fugas de información (data leakage).
""")

# --- 1. Carga de Datos ---
if 'data_loaded' not in st.session_state or not st.session_state.data_loaded:
    st.error("⚠️ Datos no cargados. Por favor, inicie desde el Menú Principal.")
    st.stop()

df_raw = st.session_state.df_consumo
df_stock = st.session_state.df_stock

# --- 1.1 Enriquecer datos con Maestro de Artículos (Subfamilia y Nombre) ---
# Cruzamos el consumo con el stock para obtener la Subfamilia y Nombre del artículo
# Detectar nombre real de la columna de agrupación en df_stock
col_subfam_real = ui_helpers.detectar_columna(df_stock, ['SubFamilia', 'Subfamilia', 'Categoria', 'Familia'])

cols_maestro = ['CodigoArticulo', 'NombreArticulo']
if col_subfam_real:
    cols_maestro.append(col_subfam_real)

# Validamos que existan las columnas en df_stock antes de cruzar
cols_existentes = [c for c in cols_maestro if c in df_stock.columns]

if 'CodigoArticulo' in cols_existentes:
    # 1. Preparar subset de stock y renombrar ANTES del cruce para evitar colisiones (_x, _y)
    df_stock_clean = df_stock[cols_existentes].drop_duplicates('CodigoArticulo').copy()
    
    if col_subfam_real and col_subfam_real != 'SubFamilia':
        df_stock_clean.rename(columns={col_subfam_real: 'SubFamilia'}, inplace=True)
    
    # 2. Merge (Usamos suffixes para dar prioridad a la data del maestro si hay choque)
    df_maestro = df_raw.merge(df_stock_clean, on='CodigoArticulo', how='left', suffixes=('', '_Maestro'))
    
    # 3. Resolver columna SubFamilia (Si hubo colisión, usamos la del maestro)
    if 'SubFamilia_Maestro' in df_maestro.columns:
        df_maestro['SubFamilia'] = df_maestro['SubFamilia_Maestro'].fillna(df_maestro.get('SubFamilia', 'Sin Clasificar'))
    
    # Crear columna si no existe tras el cruce
    if 'SubFamilia' not in df_maestro.columns:
        df_maestro['SubFamilia'] = 'Sin Clasificar'
        
    df_maestro['SubFamilia'] = df_maestro['SubFamilia'].fillna('Sin Clasificar')
    
    if 'NombreArticulo' in df_maestro.columns:
        df_maestro['NombreArticulo'] = df_maestro['NombreArticulo'].fillna('Sin Nombre')
    else:
        df_maestro['NombreArticulo'] = 'Sin Nombre'
else:
    df_maestro = df_raw.copy()
    df_maestro['SubFamilia'] = 'Desconocido'
    df_maestro['NombreArticulo'] = 'Desconocido'

# --- 2. Filtros Laterales ---
st.sidebar.header("🛠️ Configuración de Datos")

# Obtener listas únicas para filtros
bodegas_origen_disp = sorted(df_maestro['BodegaOrigen_Solicitada'].dropna().astype(str).unique())
bodegas_destino_disp = sorted(df_maestro['BodegaDestino_Requerida'].dropna().astype(str).unique())

sel_origen = st.sidebar.multiselect(
    "Bodega Origen:",
    options=bodegas_origen_disp,
    default=bodegas_origen_disp,
    help="Filtra las transferencias según desde dónde salió la mercadería."
)

sel_destino = st.sidebar.multiselect(
    "Bodega Destino:",
    options=bodegas_destino_disp,
    default=bodegas_destino_disp,
    help="Filtra las transferencias según a dónde fue la mercadería."
)

# Filtro por Subfamilia (Nuevo para modelo global)
subfamilias_disp = sorted(df_maestro['SubFamilia'].astype(str).unique())
sel_subfam = st.sidebar.multiselect(
    "Seleccionar Subfamilias:",
    options=subfamilias_disp,
    help="El modelo predecirá todos los SKUs pertenecientes a estas familias."
)

if not sel_origen or not sel_destino or not sel_subfam:
    st.warning("Seleccione Origen, Destino y al menos una Subfamilia para continuar.")
    st.stop()

# --- 3. Preprocesamiento ---
with st.spinner("Procesando datos históricos..."):
    # Filtrar datos
    mask = (df_maestro['BodegaOrigen_Solicitada'].isin(sel_origen)) & \
           (df_maestro['BodegaDestino_Requerida'].isin(sel_destino)) & \
           (df_maestro['SubFamilia'].isin(sel_subfam))
    df_filtered = df_maestro[mask].copy()

    if df_filtered.empty:
        st.error("No hay registros de consumo para las bodegas seleccionadas.")
        st.stop()

    # Asegurar formato fecha
    df_filtered['FechaSolicitud'] = pd.to_datetime(df_filtered['FechaSolicitud'])

    # Agrupar por Mes y SKU
    # Usamos Grouper para asegurar frecuencia mensual correcta
    df_mensual = df_filtered.groupby(
        [pd.Grouper(key='FechaSolicitud', freq='MS'), 'CodigoArticulo']
    )['CantidadSolicitada'].sum().reset_index()

    # Rellenar meses sin consumo con 0 (Producto Cartesiano Fechas x SKUs)
    # Esto es vital para que el modelo aprenda que en ciertos meses NO hubo consumo.
    all_dates = pd.date_range(start=df_mensual['FechaSolicitud'].min(), end=df_mensual['FechaSolicitud'].max(), freq='MS')
    all_skus = df_mensual['CodigoArticulo'].unique()
    
    idx_full = pd.MultiIndex.from_product([all_dates, all_skus], names=['FechaSolicitud', 'CodigoArticulo'])
    df_train = df_mensual.set_index(['FechaSolicitud', 'CodigoArticulo']).reindex(idx_full, fill_value=0).reset_index()

    # Ingeniería de Características (Variables Temporales)
    def agregar_features_temporales(df):
        df = df.copy()
        df['Mes'] = df['FechaSolicitud'].dt.month
        df['Ano'] = df['FechaSolicitud'].dt.year
        df['Trimestre'] = df['FechaSolicitud'].dt.quarter
        # Convertir SKU a categoría para LightGBM
        df['SKU_Cat'] = df['CodigoArticulo'].astype('category')
        return df

    df_train = agregar_features_temporales(df_train)

# --- 4. Entrenamiento LightGBM ---
st.subheader("Entrenamiento y Proyección")

X_train = df_train[['Mes', 'Ano', 'Trimestre', 'SKU_Cat']]
y_train = df_train['CantidadSolicitada']

model = lgb.LGBMRegressor(random_state=42, n_jobs=-1)

with st.spinner(f"Entrenando modelo global para {len(all_skus)} SKUs..."):
    model.fit(X_train, y_train)

# --- 5. Predicción Futura (12 Meses) ---
last_date = df_train['FechaSolicitud'].max()
future_dates = pd.date_range(start=last_date + pd.DateOffset(months=1), periods=12, freq='MS')

idx_future = pd.MultiIndex.from_product([future_dates, all_skus], names=['FechaSolicitud', 'CodigoArticulo'])
df_future = pd.DataFrame(index=idx_future).reset_index()
df_future = agregar_features_temporales(df_future)

X_future = df_future[['Mes', 'Ano', 'Trimestre', 'SKU_Cat']]
df_future['Prediccion'] = model.predict(X_future)
df_future['Prediccion'] = df_future['Prediccion'].clip(lower=0) # Evitar consumos negativos
df_future['Prediccion'] = np.ceil(df_future['Prediccion']).astype(int) # Redondear hacia arriba

# Agregar nombres para la visualización
mapa_nombres = df_maestro[['CodigoArticulo', 'NombreArticulo']].drop_duplicates(subset=['CodigoArticulo']).set_index('CodigoArticulo')['NombreArticulo']
df_future['NombreArticulo'] = df_future['CodigoArticulo'].map(mapa_nombres).fillna('Sin Nombre')

# --- 6. Visualización ---
st.markdown("### 📅 Tabla de Predicciones (Próximos 12 Meses)")

# 6.1 Tabla Pivote Global
df_pivot = df_future.pivot_table(
    index=['CodigoArticulo', 'NombreArticulo'], 
    columns='FechaSolicitud', 
    values='Prediccion'
).reset_index()

# Formatear columnas de fecha a string limpio (YYYY-MM)
cols_fecha = [c for c in df_pivot.columns if isinstance(c, pd.Timestamp)]
mapping_cols = {c: c.strftime('%Y-%m') for c in cols_fecha}
df_pivot.rename(columns=mapping_cols, inplace=True)

st.dataframe(
    df_pivot,
    use_container_width=True,
    column_config={
        "CodigoArticulo": st.column_config.TextColumn("SKU", pinned=True),
        "NombreArticulo": st.column_config.TextColumn("Descripción", width="large", pinned=True)
    },
    hide_index=True
)

# Descarga Global
csv_data = df_pivot.to_csv(index=False).encode('utf-8')
st.download_button("📥 Descargar Reporte Completo", csv_data, "prediccion_consumo_global.csv", "text/csv")

st.divider()

# 6.2 Visualización Individual
c1, c2 = st.columns([1, 3])

with c1:
    st.markdown("##### Visualizar SKU")
    # Encontrar SKU con más movimiento para default
    top_sku = df_mensual.groupby('CodigoArticulo')['CantidadSolicitada'].sum().idxmax()
    
    # Ordenar lista de SKUs por Nombre para facilitar la búsqueda visual
    skus_ordenados = sorted(all_skus, key=lambda x: str(mapa_nombres.get(x, "zzzzz")))
    
    # Indice por defecto
    idx_def = skus_ordenados.index(top_sku) if top_sku in skus_ordenados else 0

    # Selector con formato: Nombre (SKU)
    sku_sel = st.selectbox("Seleccione Producto:", options=skus_ordenados, index=idx_def, format_func=lambda x: f"{mapa_nombres.get(x, 'Sin Nombre')} ({x})")

with c2:
    # Preparar datos para gráfico (Histórico + Futuro)
    df_hist_plot = df_train[df_train['CodigoArticulo'] == sku_sel].copy()
    df_hist_plot['Tipo'] = 'Histórico'
    
    df_fut_plot = df_future[df_future['CodigoArticulo'] == sku_sel].copy()
    df_fut_plot['Tipo'] = 'Predicción'
    df_fut_plot.rename(columns={'Prediccion': 'CantidadSolicitada'}, inplace=True)
    
    df_plot = pd.concat([df_hist_plot, df_fut_plot], ignore_index=True)
    
    chart = alt.Chart(df_plot).mark_line(point=True).encode(
        x=alt.X('FechaSolicitud:T', title='Fecha', axis=alt.Axis(format='%b %Y')),
        y=alt.Y('CantidadSolicitada:Q', title='Unidades Consumidas'),
        color=alt.Color('Tipo:N', scale=alt.Scale(domain=['Histórico', 'Predicción'], range=['#95a5a6', '#2ecc71'])),
        tooltip=[alt.Tooltip('FechaSolicitud', format='%Y-%m'), 'CantidadSolicitada', 'Tipo']
    ).properties(
        title=f"Proyección de Consumo: {sku_sel}",
        height=400
    ).interactive()
    
    st.altair_chart(chart, use_container_width=True)