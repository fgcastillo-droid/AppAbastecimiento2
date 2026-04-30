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

st.set_page_config(page_title="Agente de IA", page_icon="🤖", layout="wide")
ui_helpers.setup_locale()

st.title("🤖 Agente de IA (Asistente Global)")
st.markdown("Pregúntame cualquier cosa sobre **inventario (Bodega BF0001), ventas residenciales o próximas llegadas**.")

# Verifica si los datos están cargados
if 'data_loaded' not in st.session_state or not st.session_state.data_loaded:
    st.error("Los datos no se han cargado. Por favor, vuelva al Menú Principal e inténtelo de nuevo.")
    st.stop()

if genai is None:
    st.error("Para usar el asistente de IA, instala la librería: `pip install google-generativeai`")
    st.stop()

api_key = st.secrets.get("gemini_api_key")
if not api_key:
    st.info("Para usar el asistente de IA, configura 'gemini_api_key' en tus secrets de Streamlit (.streamlit/secrets.toml).")
    st.stop()

genai.configure(api_key=api_key)

if "messages_global_agent" not in st.session_state:
    st.session_state.messages_global_agent = []

# Mostrar historial de mensajes
for message in st.session_state.messages_global_agent:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ej: ¿Cuál es el artículo con más stock? ¿Cuántas ventas hubo este mes? ¿Qué está pendiente de traslado?"):
    st.session_state.messages_global_agent.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analizando toda la base de datos de la empresa..."):
            try:
                # --- Preparación del Contexto ---
                # Convertimos partes esenciales de cada tabla a CSV para ahorrar tokens y dar contexto claro
                
                df_stock = st.session_state.df_stock.copy()
                # Filtrar por bodega BF0001 y stock positivo para ahorrar tokens
                if 'CodigoBodega' in df_stock.columns:
                    df_stock = df_stock[df_stock['CodigoBodega'] == 'BF0001']
                if 'DisponibleParaPrometer' in df_stock.columns:
                    df_stock = df_stock[df_stock['DisponibleParaPrometer'] > 0]
                    
                cols_stock = [c for c in ['CodigoArticulo', 'NombreArticulo', 'CodigoBodega', 'StockActual','Comprometido', 'DisponibleParaPrometer', 'ValorTotalInventario'] if c in df_stock.columns]
                csv_stock = df_stock[cols_stock].to_csv(index=False) if not df_stock.empty else "Sin datos"
                csv_stock = df_stock[cols_stock].head(150).to_csv(index=False) if not df_stock.empty else "Sin datos"

                df_oc = st.session_state.df_oc.copy()
                df_oc = df_oc[ df_oc['Fecha de entrega de la línea'] >= pd.Timestamp.now()]
                cols_oc = [c for c in ['Número de documento', 'Número de artículo', 'Cantidad', 'Fecha de entrega de la línea', 'Comentarios'] if c in df_oc.columns]
                csv_oc = df_oc[cols_oc].to_csv(index=False) if not df_oc.empty else "Sin datos"
                csv_oc = df_oc[cols_oc].head(150).to_csv(index=False) if not df_oc.empty else "Sin datos"

                df_residencial = st.session_state.df_residencial.copy()
                cols_res = [c for c in ['ceco', 'tipo_proyecto', 'fecha_de_ganado', 'kwp', 'cantidad_de_paneles', 'kwh'] if c in df_residencial.columns]
                csv_residencial = df_residencial[cols_res].to_csv(index=False) if not df_residencial.empty else "Sin datos"
                csv_residencial = df_residencial[cols_res].head(150).to_csv(index=False) if not df_residencial.empty else "Sin datos"

                system_prompt = f"""
                Eres un asistente de Inteligencia Artificial experto en logística, inventario y análisis de datos.
                Tu tarea es responder preguntas complejas cruzando información de las siguientes bases de datos de la empresa:
                Nota Importante: Por límites del sistema, solo estás viendo una muestra de las primeras 150 filas.
                
                --- DATOS DE STOCK (BODEGA BF0001, STOCK POSITIVO) ---
                {csv_stock}
                
                --- DATOS DE ÓRDENES DE COMPRA (LLEGADAS FUTURAS) ---
                {csv_oc}
                
                --- DATOS DE PROYECTOS RESIDENCIALES (VENTAS) ---
                {csv_residencial}
                
                Responde de manera amable, estructurada y precisa basándote ÚNICAMENTE en los datos provistos.
                Si necesitas hacer listados, utiliza viñetas.
                """
                
                model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=system_prompt)
                
                gemini_history = []
                for msg in st.session_state.messages_global_agent[:-1]:
                    role = "user" if msg["role"] == "user" else "model"
                    gemini_history.append({"role": role, "parts": [msg["content"]]})
                    
                chat = model.start_chat(history=gemini_history)
                response = chat.send_message(prompt)
                
                st.markdown(response.text)
                st.session_state.messages_global_agent.append({"role": "assistant", "content": response.text})
            except Exception as e:
                st.error(f"Ocurrió un error al consultar al asistente: {e}")