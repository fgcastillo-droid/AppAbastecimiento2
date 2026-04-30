import streamlit as st
import pandas as pd
import sys
from pathlib import Path

try:
    import google.generativeai as genai
except ImportError:
    genai = None

# --- Configuración del Path ---
src_path = str(Path(__file__).resolve().parent.parent / "src")
if src_path not in sys.path:
    sys.path.append(src_path)

import ui.ui_helpers as ui_helpers
import data.data_loader as data_loader

# --- 1. Título de la Página ---
st.title("Consulta de Próximas Llegadas 📦")

# Verifica si los datos están cargados
if 'data_loaded' not in st.session_state or not st.session_state.data_loaded:
    st.error("Los datos no se han cargado. Por favor, vuelva al Menú Principal e inténtelo de nuevo.")
    st.stop()

# --- 2. Acceder a los Datos desde st.session_state ---
df_stock = st.session_state.df_stock
df_oc = st.session_state.df_oc
df_consumo = st.session_state.df_consumo

today = pd.Timestamp.now().floor('D')
start_date = today - pd.Timedelta(days=10)

lista_skus_stock = df_stock['CodigoArticulo'].dropna().unique()
all_skus = sorted(set(lista_skus_stock))
opciones_selector_sku, mapa_nombres, _ = ui_helpers.create_sku_options(all_skus, df_stock=df_stock)

# --- 3. AGENTE DE IA (CON FUNCTION CALLING) ---
st.markdown("---")
st.subheader("🤖 Agente de Abastecimiento Autónomo")
st.write("Pregúntale al agente. Él buscará de forma autónoma en la base de datos.")

if genai is None:
    st.info("Para usar el asistente de IA, instala la librería: `pip install google-generativeai`")
else:
    api_key = st.secrets.get("gemini_api_key")
    if not api_key:
        st.info("Para usar el asistente de IA, configura 'gemini_api_key' en tus secrets de Streamlit (.streamlit/secrets.toml).")
    else:
        genai.configure(api_key=api_key)
        
        if "messages_llegadas" not in st.session_state:
            st.session_state.messages_llegadas = []

        # Mostrar historial de mensajes UI
        for message in st.session_state.messages_llegadas:
            # Ocultamos los mensajes técnicos de uso de herramientas para no confundir al usuario
            if message.get("is_tool_call"):
                continue
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if prompt := st.chat_input("Ej: ¿Cuándo llega el artículo XYZ? o ¿Cuántos paneles llegan la próxima semana?"):
            st.session_state.messages_llegadas.append({"role": "user", "content": prompt, "is_tool_call": False})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Pensando y consultando la base de datos..."):
                    try:
                        # --- PASO A: PREPARAR DATOS BASE ---
                        # Preparamos el dataframe general, pero NO lo convertimos a CSV
                        df_context = df_oc[
                            (df_oc['Cantidad'] > 0) &
                            (df_oc['Fecha de entrega de la línea'] >= start_date)
                        ].copy()
                        df_context['Descripción'] = df_context['Número de artículo'].map(mapa_nombres).fillna('Sin nombre')
                        df_context['Fecha de entrega de la línea'] = df_context['Fecha de entrega de la línea'].dt.strftime('%Y-%m-%d')
                        df_context = df_context[['Número de documento', 'Número de artículo', 'Descripción', 'Cantidad', 'Fecha de entrega de la línea']]

                        # --- PASO B: CREAR LA HERRAMIENTA (FUNCIÓN PYTHON) ---
                        # Esta es la "mano" del Agente. Los docstrings son CRÍTICOS porque Gemini los lee para saber cómo usarla.
                        def consultar_llegadas(termino_busqueda: str) -> str:
                            """
                            Busca en la base de datos de órdenes de compra las próximas llegadas de un producto.
                            Args:
                                termino_busqueda: El nombre del producto, palabra clave o código SKU a buscar (ej. "panel", "10405").
                            Returns:
                                Un string con los resultados encontrados en formato tabla.
                            """
                            termino = termino_busqueda.lower()
                            # Filtramos el dataframe buscando coincidencias en SKU o Descripción
                            mask = (
                                df_context['Número de artículo'].astype(str).str.lower().str.contains(termino) |
                                df_context['Descripción'].astype(str).str.lower().str.contains(termino)
                            )
                            resultados = df_context[mask]
                            
                            if resultados.empty:
                                return f"No se encontraron llegadas para la búsqueda: '{termino_busqueda}'."
                            
                            # Devolvemos solo las filas relevantes como texto para que el agente las lea
                            return resultados.to_csv(index=False)

                        # --- PASO C: CONFIGURAR EL AGENTE ---
                        system_prompt = """
                        Eres un agente de abastecimiento experto. 
                        NO tienes los datos en tu memoria. Para responder CUALQUIER pregunta sobre llegadas, 
                        DEBES usar tu herramienta 'consultar_llegadas' para buscar el SKU o nombre del producto.
                        Una vez que la herramienta te devuelva los datos, formula una respuesta amable y clara para el usuario.
                        Recuerda siempre mencionar la fecha tentativa, la cantidad y el N° de OC.
                        """
                        
                        # Inyectamos la herramienta al modelo
                        model = genai.GenerativeModel(
                            'gemini-2.5-flash', 
                            system_instruction=system_prompt,
                            tools=[consultar_llegadas] # <--- Le damos la herramienta
                        )
                        
                        # Reconstruimos el historial para Gemini
                        gemini_history = []
                        for msg in st.session_state.messages_llegadas[:-1]:
                            if not msg.get("is_tool_call"):
                                role = "user" if msg["role"] == "user" else "model"
                                gemini_history.append({"role": role, "parts": [msg["content"]]})
                            
                        # Activamos la autonomía del agente
                        chat = model.start_chat(
                            history=gemini_history, 
                            enable_automatic_function_calling=True # <--- Le damos permiso de usar la herramienta por su cuenta
                        )
                        
                        # Ejecutamos la consulta
                        response = chat.send_message(prompt)
                        
                        # Mostramos el resultado
                        st.markdown(response.text)
                        st.session_state.messages_llegadas.append({"role": "assistant", "content": response.text, "is_tool_call": False})
                        
                    except Exception as e:
                        st.error(f"Ocurrió un error en el agente: {e}")

# --- 4. Crear Selectores de Filtro ---
st.markdown("---")
st.subheader("🔍 Filtros de Búsqueda Manuales")

opciones_con_todas = ["Todas"] + opciones_selector_sku

col1, col2 = st.columns(2)
col3, col4 = st.columns(2)

with col1:
    sku_seleccionado_formateado = st.selectbox(
        "Filtrar por SKU:",
        opciones_con_todas,
        index=0,
        help="Seleccione el producto para ver sus Órdenes de Compra futuras."
    )
    sku_seleccionado = sku_seleccionado_formateado.split(" | ")[0]

with col2:
    nombre_buscado = st.text_input(
        "Filtrar por Nombre de Producto:",
        help="Escriba cualquier texto para buscar en el nombre del producto."
    )

with col3:
    oc_buscada = st.text_input(
        "Filtrar por N° de Orden de Compra (OC):",
        help="Escriba un número de OC para filtrar los resultados (búsqueda parcial)."
    )

with col4:
    comentarios_buscados = st.text_input(
        "Filtrar por Comentarios:",
        help="Escriba cualquier texto para buscar en la columna 'Comentarios' (búsqueda parcial)."
    )

st.subheader("Resultados de la Búsqueda")
st.markdown("---")

# --- 5. Filtrar y Mostrar OCs ---
df_llegadas_detalle = df_oc[
    (df_oc['Cantidad'] > 0) &
    (df_oc['Fecha de entrega de la línea'] >= start_date)
].copy()

if 'Comentarios' not in df_llegadas_detalle.columns:
    df_llegadas_detalle['Comentarios'] = 'N/A'

df_llegadas_detalle['Número de documento'] = df_llegadas_detalle['Número de documento'].astype(str)
df_llegadas_detalle['Comentarios'] = df_llegadas_detalle['Comentarios'].astype(str)

df_llegadas_detalle['Descripción artículo/serv.'] = df_llegadas_detalle['Número de artículo'].map(mapa_nombres).fillna('Nombre no encontrado')
df_llegadas_detalle['Descripción artículo/serv.'] = df_llegadas_detalle['Descripción artículo/serv.'].astype(str)

if sku_seleccionado != "Todas":
    df_llegadas_detalle = df_llegadas_detalle[df_llegadas_detalle['Número de artículo'] == sku_seleccionado]

if oc_buscada:
    df_llegadas_detalle = df_llegadas_detalle[df_llegadas_detalle['Número de documento'].str.contains(oc_buscada, case=False, na=False, regex=False)]

if comentarios_buscados:
    df_llegadas_detalle = df_llegadas_detalle[df_llegadas_detalle['Comentarios'].str.contains(comentarios_buscados, case=False, na=False, regex=False)]

if nombre_buscado:
    df_llegadas_detalle = df_llegadas_detalle[df_llegadas_detalle['Descripción artículo/serv.'].str.contains(nombre_buscado, case=False, na=False, regex=False)]

# --- 6. Mostrar DataFrame ---
if df_llegadas_detalle.empty:
    st.info("No se encontraron llegadas programadas que coincidan con los filtros.")
else:
    if 'Número de documento' not in df_llegadas_detalle.columns:
        st.error("Columna 'Número de documento' (OC) no encontrada.")
        st.stop()

    df_display = df_llegadas_detalle[[
        'Número de documento', 'Número de artículo', 'Descripción artículo/serv.',
        'Cantidad', 'Fecha de entrega de la línea', 'Comentarios'
    ]].copy()

    df_display.rename(columns={
        'Número de documento': 'N° Orden Compra',
        'Número de artículo': 'SKU',
        'Descripción artículo/serv.': 'Producto',
        'Cantidad': 'Cantidad',
        'Fecha de entrega de la línea': 'Fecha Llegada',
        'Comentarios': 'Comentarios'
    }, inplace=True)

    df_display = df_display.sort_values(by='Fecha Llegada')
    df_display['Fecha Llegada'] = df_display['Fecha Llegada'].dt.strftime('%Y-%m-%d')
    df_display['Cantidad'] = df_display['Cantidad'].apply(lambda x: f"{x:,.0f}")

    st.dataframe(df_display, width='stretch', hide_index=True)