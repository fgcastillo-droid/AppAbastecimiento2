# --- ARCHIVO: pages/6_📦_Consulta_Stock.py ---
# (Modificado para incluir soporte de Expresiones Regulares - Regex)

import re
import streamlit as st
import pandas as pd
import sys
from pathlib import Path

# --- Configuración del Path ---
# (Necesario en CADA archivo de 'pages' para encontrar 'src')
src_path = str(Path(__file__).resolve().parent.parent / "src")
if src_path not in sys.path:
    sys.path.append(src_path)

try:
    import ui.ui_helpers as ui_helpers # Para la localización
except ImportError:
    st.warning("No se pudo importar 'ui_helpers.py'. Se usarán configuraciones por defecto.")
    # Definir una función ficticia si no existe
    class DummyUIHelpers:
        def setup_locale(self):
            pass
    ui_helpers = DummyUIHelpers()


# --- 1. Configuración de Página y Verificación de Datos ---
st.set_page_config(layout="wide", page_title="Consulta de Stock")
ui_helpers.setup_locale() # Configura meses en español

st.title("Consulta de Inventario en Bodega")
st.markdown("Busque y filtre el stock disponible por SKU, nombre o bodega.")

if 'data_loaded' not in st.session_state or not st.session_state.data_loaded:
    st.error("Los datos no se han cargado. Por favor, vuelva al Menú Principal.")
    st.stop()

# --- 2. Acceder y Preparar los Datos ---
# Columnas que esperamos encontrar. AJUSTA ESTOS NOMBRES SI SON DIFERENTES.
COL_SKU = 'CodigoArticulo'
COL_NOMBRE = 'NombreArticulo' #df stock
COL_BODEGA = 'CodigoBodega'
COL_STOCK = 'DisponibleParaPrometer'
COL_SUBFAMILIA = 'SubFamilia'

try:
    df_stock_raw = st.session_state.df_stock

    # Nota: Los datos ya vienen limpios de src/limpieza.py
    # df_stock_raw[COL_STOCK] ya es float y df_stock_raw[COL_NOMBRE] ya es str

    # Listas para los filtros
    all_skus = sorted(df_stock_raw[COL_SKU].dropna().unique())
    all_bodegas = sorted(df_stock_raw[COL_BODEGA].dropna().unique())
    all_subfamilia = sorted(df_stock_raw[COL_SUBFAMILIA].dropna().unique())

except KeyError as e:
    st.error(f"Error de Configuración: No se pudo encontrar la columna {e}.")
    st.info(f"""
    Asegúrese de que su archivo 'Stock.xlsx' contenga las columnas esperadas.
    - Columna de SKU: Se esperaba '{COL_SKU}'
    - Columna de Nombre: Se esperaba '{COL_NOMBRE}' (Esta es una suposición)
    - Columna de Bodega: Se esperaba '{COL_BODEGA}'
    - Columna de Stock: Se esperaba '{COL_STOCK}'

    Si los nombres son diferentes, por favor ajuste las variables (COL_SKU, COL_NOMBRE, etc.)
    al inicio del archivo `6_📦_Consulta_Stock.py`.
    """)
    st.stop()
except Exception as e:
    st.error(f"Error inesperado al cargar datos: {e}")
    st.stop()

# --- 3. Filtros en la Barra Lateral ---
st.sidebar.header("Filtros de Búsqueda")

# Filtro 1: Búsqueda por Nombre (Texto)
nombre_search = st.sidebar.text_input(
    "1. Buscar por Nombre de Artículo:",
    help="Buscará cualquier coincidencia parcial. Escriba 'panel' para encontrar 'Panel Solar 550W'."
)

# --- (NUEVO) Checkbox para activar Regex ---
use_regex = st.sidebar.checkbox(
    "Usar expresiones regulares (avanzado)", 
    value=False, 
    help="Permite búsquedas complejas. Ej: '^(Panel|Inversor)' para buscar texto que comience con 'Panel' o 'Inversor'."
)

# Filtro 2: Selección de SKU (Multiselect)
sku_selected = st.sidebar.multiselect(
    "2. Filtrar por SKU:",
    options=all_skus
)

# Filtro 3: Selección de Bodega (Multiselect)
bodega_selected = st.sidebar.multiselect(
    "3. Filtrar por Bodega:",
    options=all_bodegas
)

# Filtro 4: SubFamilia
subfamilia_selected = st.sidebar.multiselect(
    "4. Filtrar por SubFamilia:",
    options=all_subfamilia
)


# Filtro 4: Ocultar sin stock
hide_zero_stock = st.sidebar.checkbox("Ocultar artículos sin stock", value=True)

# --- 4. Lógica de Filtrado ---

# Empezamos con el dataframe completo
df_filtered = df_stock_raw

# Aplicar filtro de nombre (case-insensitive)
if nombre_search:
    try:
        # --- (MODIFICADO) ---
        # Ahora usamos el parámetro 'regex=use_regex'
        df_filtered = df_filtered[df_filtered[COL_NOMBRE].str.contains(
            nombre_search, 
            case=False, 
            na=False, 
            regex=use_regex 
        )]
    except re.error as e:
        # Captura errores si la expresión regular es inválida
        st.sidebar.error(f"Expresión regular inválida. Intente desactivar la casilla o corrija la expresión.")
        df_filtered = df_stock_raw.iloc[0:0] # Devuelve un DF vacío
    except Exception as e:
        st.sidebar.error(f"Error en el filtro de nombre: {e}")
        df_filtered = df_stock_raw.iloc[0:0]

# Aplicar filtro de SKU
if sku_selected: # if list is not empty
    df_filtered = df_filtered[df_filtered[COL_SKU].isin(sku_selected)]

# Aplicar filtro de Bodega
if bodega_selected: # if list is not empty
    df_filtered = df_filtered[df_filtered[COL_BODEGA].isin(bodega_selected)]

# Aplicar filtro de Bodega
if subfamilia_selected: # if list is not empty
    df_filtered = df_filtered[df_filtered[COL_SUBFAMILIA].isin(subfamilia_selected)]



# Aplicar filtro de stock
if hide_zero_stock:
    df_filtered = df_filtered[df_filtered[COL_STOCK] > 0]

# --- 5. Mostrar Resultados ---
total_items = len(df_filtered)
total_stock = df_filtered[COL_STOCK].sum()
st.subheader(f"Resultados de la Búsqueda ({total_items} líneas encontradas)")
# Métricas
col1, col2 = st.columns(2)
col1.metric("Líneas de Stock Únicas", f"{total_items}")
col2.metric("Unidades Totales Disponibles", f"{total_stock:,.0f} Uds.")
st.markdown("---")

# Tabla de datos
st.dataframe(
    df_filtered.sort_values(by=COL_STOCK, ascending=False), # Ordenar por stock descendente
    width="stretch",
    column_config={
        COL_SKU: st.column_config.TextColumn("SKU"),
        COL_NOMBRE: st.column_config.TextColumn("Nombre Artículo", width="large"),
        COL_BODEGA: st.column_config.TextColumn("Bodega"),
        COL_STOCK: st.column_config.NumberColumn("Stock Disponible", format="%.0f"),
    },
    hide_index=True
)

# --- Botón de Descarga ---
@st.cache_data
def convert_df_to_csv(df):
    # Función para convertir el DF a CSV en cache
    return df.to_csv(index=False).encode('utf-8')

csv_data = convert_df_to_csv(df_filtered)

st.download_button(
     label="📥 Descargar resultados (.csv)",
     data=csv_data,
     file_name="consulta_stock.csv",
     mime="text/csv",
 )