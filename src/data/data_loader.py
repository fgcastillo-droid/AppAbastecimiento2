# --- ARCHIVO: src/data_loader.py ---
import pandas as pd
import streamlit as st
import gspread
from src import config # Esto le dice: "Busca dentro del paquete src"
from src.data import limpieza 
import requests # para el notion



import requests
import pandas as pd

# --- FUNCIÓN 1: OBTENER TOKEN ---
def obtener_token(client_id, client_secret, base_url):
    """Va a la API, se identifica y devuelve el pase VIP temporal."""
    print("Obteniendo pase VIP (Token)...")
    auth_url = f"{base_url}/auth/token"
    auth_data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret
    }
    response = requests.post(auth_url, data=auth_data)
    if response.status_code == 200:
        print("¡Token obtenido con éxito!\n")
        return response.json().get("access_token")
    else:
        raise Exception(f"Error de autenticación: {response.text}")



# --- FUNCIÓN 2: DESCARGAR CUALQUIER TABLA ---
def descargar_tabla(base_url, endpoint, token):
    """Descarga automáticamente todas las páginas de la tabla que le pidas."""
    print(f"Descargando tabla completa de '/{endpoint}'...")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Armamos la URL inicial forzando la carga de 100 en 100
    siguiente_pagina = f"{base_url}/{endpoint}?limit=100" 
    todas_las_filas = []

    # El bucle de paginación que ya conoces
    while siguiente_pagina:
        response = requests.get(siguiente_pagina, headers=headers).json()
        todas_las_filas.extend(response.get("data", []))
        siguiente_pagina = response.get("next_url")

    # Convertimos a Pandas y devolvemos el resultado
    df = pd.DataFrame(todas_las_filas)
    print(f"¡Listo! Tabla '{endpoint}' descargada con {len(df)} filas.\n")
    return df




@st.cache_resource
def _get_gsheet_client():
    """Autoriza y retorna un cliente de gspread usando las librerías modernas. Cacheado para no repetir la autenticación."""
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    try:
        creds_dict = st.secrets["gcp_service_account"]
        client = gspread.service_account_from_dict(creds_dict, scopes=scope)
        return client
    except Exception as e:
        st.error(f"Error crítico al cargar credenciales de Google: {e}")
        return None

def _load_single_gsheet(client, sheet_id, sheet_name):
    """Descarga una pestaña específica de Google Sheets y la retorna como DataFrame."""
    if client is None:
        return pd.DataFrame()
    try:
        sheet = client.open_by_key(sheet_id).worksheet(sheet_name)
        all_rows = sheet.get_all_values()
        if not all_rows:
            return pd.DataFrame()
        df = pd.DataFrame(all_rows[1:], columns=all_rows[0])
        # Eliminar columnas completamente vacías que a veces crea G-Sheets
        df = df.loc[:, df.columns != '']
        return df
    except gspread.exceptions.SpreadsheetNotFound:
        print(f"Error G-Sheets: No se encontró el archivo con ID '{sheet_id}'. Verifique los permisos y el ID en config.py.")
        return pd.DataFrame()
    except gspread.exceptions.WorksheetNotFound:
        print(f"Error G-Sheets: No se encontró la pestaña '{sheet_name}' en el archivo con ID '{sheet_id}'.")
        return pd.DataFrame()
    except Exception as e:
        print(f"Error al descargar la hoja '{sheet_name}': {e}")
        return pd.DataFrame()

def _load_single_gsheet_ci(client, sheet_id, sheet_name):
    """Descarga una pestaña específica de Google Sheets y la retorna como DataFrame."""
    if client is None:
        return pd.DataFrame()
    try:
        sheet = client.open_by_key(sheet_id).worksheet(sheet_name)
        all_rows = sheet.get_all_values()
        if not all_rows:
            return pd.DataFrame()
        df = pd.DataFrame(all_rows[2:], columns=all_rows[1])
        # Eliminar columnas completamente vacías que a veces crea G-Sheets
        df = df.loc[:, df.columns != '']
        return df
    except gspread.exceptions.SpreadsheetNotFound:
        print(f"Error G-Sheets: No se encontró el archivo con ID '{sheet_id}'. Verifique los permisos y el ID en config.py.")
        return pd.DataFrame()
    except gspread.exceptions.WorksheetNotFound:
        print(f"Error G-Sheets: No se encontró la pestaña '{sheet_name}' en el archivo con ID '{sheet_id}'.")
        return pd.DataFrame()
    except Exception as e:
        print(f"Error al descargar la hoja '{sheet_name}': {e}")
        return pd.DataFrame()

@st.cache_data(ttl=43200) # Cache por 12 horas
def _load_all_data():
    """
    Función principal de carga. Orquesta la extracción desde fuentes locales y APIs,
    y luego llama a los módulos de limpieza.
    """
    print("--- (EJECUTANDO CACHE) Cargando y Limpiando Datos Globales ---")
    
    # --- 1. EXTRACCIÓN (SECUENCIAL) ---
    gsheet_client = _get_gsheet_client()
    
    # Extraer credenciales de Notion
    notion_token = None
    notion_db_id = None
    try:
        notion_token = st.secrets["notion"]["token"]
        notion_db_id = st.secrets["notion"]["database_id"]
    except Exception:
        print("Nota: No se encontraron secretos de Notion. Se omitirá esa carga.")
    
    # Carga secuencial desde Google Sheets
    df_stock_raw = _load_single_gsheet(gsheet_client, config.GSHEET_IDS["STOCK"], "STOCK")
    df_oc_raw = _load_single_gsheet(gsheet_client, config.GSHEET_IDS["LLEGADAS"], "OPOR")
    df_consumo_raw = _load_single_gsheet(gsheet_client, config.GSHEET_IDS["CONSUMO"], "OWTR")
    df_historia_stock_raw = _load_single_gsheet(gsheet_client, config.GSHEET_IDS["OINM"], "OINM")
    df_owtq_raw = _load_single_gsheet(gsheet_client, config.GSHEET_IDS["ST"], "OWTQ")        
    df_req_raw = _load_single_gsheet(gsheet_client, config.GSHEET_IDS["REQUERIMIENTOS"], "requerimientos")
        
    # --- Carga de C&I y Residencial mediante API REST ---
    try:
        api_base_url = st.secrets["api"]["base_url"]
        api_client_id = st.secrets["api"]["client_id"]
        api_client_secret = st.secrets["api"]["client_secret"]
        
        api_token = obtener_token(api_client_id, api_client_secret, api_base_url)
        # NOTA: Cambia "residencial" por el nombre exacto de tu endpoint si es diferente (ej. "bdtotal", "proyectos")
        # Si C&I viene en un endpoint separado, puedes hacer otro descargar_tabla y concatenar ambos DataFrames con pd.concat()
        df_residencial_raw = descargar_tabla(api_base_url, "planilla-master", api_token)
    except Exception as e:
        print(f"Error al cargar datos de C&I/Residencial desde la API (o faltan credenciales en secrets.toml): {e}")
        df_residencial_raw = pd.DataFrame()

    # Carga de archivos locales (CPU/Disco)
    try:
        df_historia_subfam = pd.read_excel("data/var_inventario.xlsx")
    except Exception as e:
        print(f"No se pudo cargar excel local: {e}")
        df_historia_subfam = pd.DataFrame()
        
    # Carga desde APIs externas (Notion)
    df_notion_raw = _load_notion_importaciones(notion_token, notion_db_id)

    # --- 2. TRANSFORMACIÓN (Limpieza) ---
    df_oc = limpieza.limpiar_ordenes_compra(df_oc_raw)
    df_consumo = limpieza.limpiar_consumos(df_consumo_raw)
    df_stock = limpieza.limpiar_stock(df_stock_raw)
    df_movimientos = limpieza.limpiar_movimientos(df_historia_stock_raw)
    df_owtq = limpieza.limpiar_solicitudes(df_owtq_raw) 
    df_residencial = limpieza.limpiar_residencial(df_residencial_raw)
    df_notion = _procesar_dataframe_notion(df_notion_raw)
    df_req = limpieza.limpiar_requerimientos(df_req_raw)

    return df_stock, df_oc, df_consumo, df_residencial, df_historia_subfam, df_movimientos, df_owtq, df_notion, df_req

def load_data_into_session():
    """
    Wrapper que llama a la función cacheada y guarda los datos
    en st.session_state para que todas las páginas los usen.
    """
    if 'data_loaded' not in st.session_state:
        try:
            # Llama a la función cacheada y desempaqueta TODOS los valores en el mismo orden del return
            (st.session_state.df_stock, 
             st.session_state.df_oc, 
             st.session_state.df_consumo, 
             st.session_state.df_residencial,
             st.session_state.df_historia_subfam,
             st.session_state.df_historia_full, # Este mapea a df_movimientos en el return
             st.session_state.df_owtq,
             st.session_state.df_notion,
             st.session_state.df_requerimientos) = _load_all_data() 
            
            st.session_state.data_loaded = True
            print("Datos cargados en st.session_state.")

        except FileNotFoundError as e:
            st.error(f"Error Crítico: No se pudo encontrar el archivo: {e.filename}.")
            st.info(f"Por favor, asegúrese de que el archivo '{e.filename}' esté en la carpeta 'data/'.")
            st.stop()
        except Exception as e:
            st.error(f"Ocurrió un error inesperado durante la carga de datos: {e}")
            st.stop()

def _load_notion_importaciones(token, database_id):
    """Conecta con la API de Notion y trae la tabla cruda"""
    if not token or not database_id:
        return []
    
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    
    try:
        response = requests.post(url, headers=headers)
        response.raise_for_status() 
        return response.json().get("results", [])
    except requests.exceptions.RequestException as e:
        print(f"Error al conectar con la API de Notion: {e}")
        return []

def _procesar_dataframe_notion(results):
    """Limpia el JSON crudo de Notion y lo convierte en DataFrame legible"""
    if not results:
        return pd.DataFrame()

    def extraer_valor(prop):
        t = prop.get('type')
        if not t: return ""
        try:
            if t == 'title': return prop['title'][0]['plain_text'] if prop['title'] else ""
            if t == 'rich_text': return prop['rich_text'][0]['plain_text'] if prop['rich_text'] else ""
            if t == 'select': return prop['select']['name'] if prop['select'] else ""
            if t == 'date': return prop['date']['start'] if prop['date'] else ""
            if t == 'number': return prop['number']
            if t == 'formula':
                f_type = prop['formula'].get('type')
                return prop['formula'].get(f_type)
        except Exception:
            return ""
        return ""

    rows = []
    for page in results:
        props = page.get("properties", {})
        row = {col_name: extraer_valor(col_data) for col_name, col_data in props.items()}
        rows.append(row)
    
    df = pd.DataFrame(rows)
    return df

def limpiar_cache_y_recargar():
    """
    Borra la caché global de _load_all_data y fuerza la recarga 
    de los Excels/Google Sheets más actualizados.
    """
    _load_all_data.clear() # Limpia la memoria RAM cacheadada
    # También limpiar la conexión para forzar re-autenticación si es necesario
    _get_gsheet_client.clear() 
    
    if 'data_loaded' in st.session_state:
        del st.session_state['data_loaded'] # Resetea la bandera de sesión
    st.rerun() # Reinicia la aplicación instantáneamente
