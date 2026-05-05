import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from prophet import Prophet
import sys
from pathlib import Path

# --- Configuración del Path ---
src_path = str(Path(__file__).resolve().parent.parent / "src")
if src_path not in sys.path:
    sys.path.append(src_path)

import ui.ui_helpers as ui_helpers
import data.data_loader as data_loader

# --- Configuración Global ---
st.set_page_config(layout="wide", page_title="Simulador Prophet Avanzado", page_icon="🔮")
ui_helpers.setup_locale()

# --- 1. SECCIÓN EDUCATIVA (TEXTO) ---
def mostrar_explicacion_modelos():
    with st.expander("📚 Guía de Modelos y Parámetros (Leer aquí)", expanded=False):
        st.markdown("""
        ### 1. Conceptos Básicos
        
        **Prophet (El Modelo Principal):**
        Es un algoritmo de Meta (Facebook) que descompone tu historia en 3 fuerzas:
        * **Tendencia:** La dirección general (crecimiento/decrecimiento).
        * **Estacionalidad:** Patrones repetitivos (ej: ventas altas en verano).
        * **Feriados:** Impacto de días festivos en Chile.
        
        **Comparativa (Benchmarks):**
        * **Lineal:** Una recta simple. Si Prophet se aleja mucho, es porque detecta cambios complejos.
        * **Promedio Móvil:** Proyecta el promedio de los últimos 6 meses (conservador).

        ---
        ### 2. Diccionario de Parámetros (Panel Izquierdo)
        
        #### 📈 Tendencia (Trend)
        * **Flexibilidad (Prior Scale):** Es la "sensibilidad" del modelo.
            * *Valor Alto (>0.1):* El modelo es muy flexible y seguirá cada subida y bajada histórica. Riesgo: Puede confundir ruido con tendencia real.
            * *Valor Bajo (<0.05):* El modelo es rígido y prefiere trazar líneas rectas, ignorando cambios bruscos recientes.
        * **Puntos de Cambio (n_changepoints):** Cantidad máxima de veces que permitimos que la tendencia cambie de dirección en la historia.
        * **Rango de Detección:** Por defecto (0.8), el modelo solo busca cambios de tendencia en el primer 80% de los datos históricos. Esto se hace para evitar que un mes atípico al final distorsione toda la proyección futura.

        #### 📅 Estacionalidad (Seasonality)
        * **Modo (¡Muy Importante!):**
            * **Aditiva:** Úsala si las ventas fluctúan una cantidad **fija** (ej: "En verano siempre vendemos 5 proyectos más", sin importar el tamaño de la empresa).
            * **Multiplicativa:** Úsala si las ventas fluctúan un **porcentaje** (ej: "En verano vendemos un 20% más").  **Si tu empresa ha crecido mucho en el tiempo, usa Multiplicativa.**
        * **Fuerza Estacional:** Controla qué tan estrictamente debe repetirse el patrón año tras año.

        #### 🎉 Feriados
        * **Impacto Feriados:** Qué tanto peso le damos a los feriados de Chile (CL). Si tus ventas caen a cero en feriados, sube este valor.
        """)
# --- 2. PREPARACIÓN DE DATOS ---
def preparar_datos_prophet(df_raw, metrica_seleccionada):
    """Lógica de negocio: Filtro mes actual, nulos y agrupación mensual."""
    df = df_raw.copy()
    
    df = df[df['fecha_de_ganado']>= "2024-01-01"]
    
    # Filtro de Mes Incompleto
    hoy = pd.Timestamp.now().normalize()
    principio_mes = hoy.replace(day=1)
    df = df[df['fecha_de_ganado'] < principio_mes]

    df = df.sort_values('fecha_de_ganado')
    df = df.set_index('fecha_de_ganado')

    # Agrupación Mensual
    df_mensual = df.resample('ME').agg({
            'ceco': 'count',
            'kwp': 'sum',
            'kwh': 'sum'
    })
    df_mensual.columns = ['Cantidad_Proyectos', 'Total_kWp', 'Total_kWh']
    
    df_final = df_mensual[[metrica_seleccionada]].reset_index()
    df_final.columns = ['ds', 'y']
    
    return df_final

# --- 3. CÁLCULO DE MODELOS DE COMPARACIÓN ---
def calcular_lineas_base(df_history, meses_futuros):
    """Calcula proyecciones simples (Lineal y Promedio) para comparar."""
    df = df_history.copy()
    
    # A. Tendencia Lineal
    x = np.arange(len(df))
    y = df['y'].values
    if len(y) > 1:
        z = np.polyfit(x, y, 1)
        p = np.poly1d(z)
        x_future = np.arange(len(df), len(df) + meses_futuros)
        y_linear = p(x_future)
    else:
        y_linear = [y[0]] * meses_futuros # Fallback si no hay datos

    # B. Promedio Móvil (6 meses)
    last_6_avg = df['y'].tail(6).mean()
    y_ma = [last_6_avg] * meses_futuros
    
    last_date = df['ds'].max()
    future_dates = [last_date + pd.DateOffset(months=i+1) for i in range(meses_futuros)]
    
    return pd.DataFrame({
        'ds': future_dates,
        'y_linear': y_linear,
        'y_ma': y_ma
    })

# --- 4. NUEVO: CÁLCULO DE KPIs (BACKTESTING) ---
def calcular_kpis_backtest(df_full, params, meses_test=6):
    """
    Simula el pasado: Entrena con datos antiguos y prueba con los recientes (que ya conocemos).
    """
    if len(df_full) < (meses_test + 6):
        return None, None # No hay suficientes datos para hacer pruebas

    # 1. Separar Entrenamiento y Prueba
    df_train = df_full.iloc[:-meses_test] # Todo menos los últimos X meses
    df_test_real = df_full.iloc[-meses_test:].reset_index(drop=True) # Los últimos X meses (La verdad)

    # 2. Entrenar Prophet con el conjunto recortado
    m = Prophet(**params)
    m.add_country_holidays(country_name='CL')
    m.fit(df_train)

    # 3. Predecir el periodo de prueba
    future = m.make_future_dataframe(periods=meses_test, freq='ME')
    forecast = m.predict(future)
    
    # Extraemos solo la parte que corresponde al test
    df_pred = forecast.tail(meses_test)[['ds', 'yhat']].reset_index(drop=True)

    # 4. Calcular Métricas
    df_result = df_test_real.copy()
    df_result['Prediccion_Prophet'] = df_pred['yhat']
    
    # Error simple (Predicción - Real)
    df_result['Error_Bias'] = df_result['Prediccion_Prophet'] - df_result['y']
    
    # Error Absoluto Porcentual (|Error| / Real)
    # Evitamos división por cero reemplazando 0 con NaN o un número pequeño
    df_result['APE'] = np.abs(df_result['Error_Bias'] / df_result['y'].replace(0, 0.001))

    kpis = {
        'MAPE': df_result['APE'].mean() * 100, # En Porcentaje
        'BIAS_Total': df_result['Error_Bias'].sum(), # Suma de errores (Sobre/Sub estimación neta)
        'BIAS_Promedio': df_result['Error_Bias'].mean(),
        'MAE': np.abs(df_result['Error_Bias']).mean()
    }

    return kpis, df_result

@st.cache_data(show_spinner=False)
def ejecutar_prophet(df_train, meses_futuros, params):
    """Entrena Prophet con todos los datos para predecir futuro real."""
    m = Prophet(**params)
    m.add_country_holidays(country_name='CL')
    m.fit(df_train)
    future = m.make_future_dataframe(periods=meses_futuros, freq='ME')
    forecast = m.predict(future)
    return m, forecast

# --- 5. INTERFAZ ---

st.title("🔮 Laboratorio de Predicción Avanzado")
mostrar_explicacion_modelos()

if 'df_residencial' not in st.session_state:
    with st.spinner("Cargando datos... por favor, espere."):
        data_loader.load_data_into_session()
        
if 'df_residencial' not in st.session_state:
    st.error("⚠️ Datos no cargados. Vaya al inicio.")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configuración")

    # 1. Datos Generales
    st.subheader("1. Datos")
    opciones_metricas = {
        "Cantidad de Proyectos": "Cantidad_Proyectos",
        "Potencia Solar (kWp)": "Total_kWp",
        "Capacidad Baterías (kWh)": "Total_kWh"
    }
    nombre_metrica = st.selectbox("KPI a Predecir:", list(opciones_metricas.keys()))
    col_metrica = opciones_metricas[nombre_metrica]
    meses_futuros = st.slider("Meses a proyectar (Futuro):", 1, 24, 6)

    st.divider()

    # 2. Configuración Backtest (Nuevo)
    st.subheader("2. Validación (Backtest)")
    meses_backtest = st.slider(
        "Meses de Prueba:", 3, 12, 6,
        help="Cuántos meses del pasado usaremos para poner a prueba el modelo."
    )
    
    st.divider()

    # 3. Hiperparámetros Prophet
    st.subheader("3. Ajuste Prophet")
    
    with st.expander("📈 Tendencia", expanded=True):
        changepoint_scale = st.slider("Flexibilidad", 0.001, 0.5, 0.05, 0.001, format="%.3f")
        n_changepoints = st.slider("Puntos de Cambio", 0, 50, 25)
        changepoint_range = st.slider("Rango Detección", 0.5, 0.95, 0.8)

    with st.expander("📅 Estacionalidad", expanded=False):
        seasonality_mode = st.selectbox("Modo", ["additive", "multiplicative"])
        seasonality_scale = st.slider("Fuerza Estacional", 0.01, 20.0, 10.0)
        yearly_seasonality = st.radio("Estacionalidad Anual", ["auto", True, False], horizontal=True)

    with st.expander("🎉 Feriados", expanded=False):
        holidays_scale = st.slider("Impacto Feriados", 0.01, 20.0, 10.0)

    params_modelo = {
        'changepoint_prior_scale': changepoint_scale,
        'n_changepoints': n_changepoints,
        'changepoint_range': changepoint_range,
        'seasonality_mode': seasonality_mode,
        'seasonality_prior_scale': seasonality_scale,
        'holidays_prior_scale': holidays_scale,
        'yearly_seasonality': yearly_seasonality
    }

# --- EJECUCIÓN PRINCIPAL ---

if st.session_state.df_residencial.empty:
    st.warning("⚠️ No hay datos de proyectos residenciales disponibles para realizar proyecciones.")
    st.stop()
    
if 'fecha_de_ganado' not in st.session_state.df_residencial.columns:
    st.error(f"⚠️ Error de formato: Falta la columna 'fecha_de_ganado'. Columnas recibidas desde la API: {list(st.session_state.df_residencial.columns)}")
    st.stop()

df_prophet = preparar_datos_prophet(st.session_state.df_residencial, col_metrica)

# Pestañas Principales
tab_graf, tab_kpis, tab_comps, tab_data = st.tabs([
    "📊 Proyección Futura", 
    "🎯 Precisión y KPIs", 
    "🧩 Componentes", 
    "📄 Datos"
])

# 1. CÁLCULO DEL FUTURO (Entrena con TODO)
with st.spinner("Calculando proyección futura..."):
    model_futuro, forecast_futuro = ejecutar_prophet(df_prophet, meses_futuros, params_modelo)
    df_bench = calcular_lineas_base(df_prophet, meses_futuros)

# TAB 1: Visualización Futura
with tab_graf:
    st.markdown(f"### 🔮 Predicción: {nombre_metrica}")
    
    fig, ax = plt.subplots(figsize=(12, 6))
    # Historia
    ax.plot(df_prophet['ds'], df_prophet['y'], 'k.', alpha=0.5, label='Historia Real')
    ax.plot(df_prophet['ds'], df_prophet['y'], 'k-', alpha=0.1)
    
    # Prophet Futuro
    ax.plot(forecast_futuro['ds'], forecast_futuro['yhat'], 'b-', linewidth=2, label='Prophet')
    ax.fill_between(forecast_futuro['ds'], forecast_futuro['yhat_lower'], forecast_futuro['yhat_upper'], color='blue', alpha=0.1)
    
    # Benchmarks
    ax.plot(df_bench['ds'], df_bench['y_linear'], 'g--', linewidth=1, label='Lineal')
    ax.plot(df_bench['ds'], df_bench['y_ma'], 'r--', linewidth=1, label='Prom. Móvil')
    
    ax.set_title(f"Proyección Próximos {meses_futuros} Meses")
    ax.legend()
    ax.grid(True, alpha=0.3)
    st.pyplot(fig)

    # Tarjetas de Resumen Futuro
    col1, col2, col3 = st.columns(3)
    val_hoy = df_prophet['y'].iloc[-1]
    val_fut = forecast_futuro['yhat'].iloc[-1]
    delta = val_fut - val_hoy
    
    col1.metric("Último Mes Real", f"{val_hoy:,.1f}")
    col2.metric(f"Proyección Mes +{meses_futuros}", f"{val_fut:,.1f}")
    col3.metric("Tendencia Neta", f"{delta:,.1f}", delta_color="normal")

# TAB 2: KPIs y Backtesting (NUEVO)
with tab_kpis:
    st.markdown("### 🧪 Prueba de Calidad (Backtesting)")
    st.markdown(f"Entrenamos el modelo ocultando los últimos **{meses_backtest} meses** reales y le pedimos que los prediga para ver cuánto se equivoca.")
    
    kpis, df_test_res = calcular_kpis_backtest(df_prophet, params_modelo, meses_test=meses_backtest)
    
    if kpis:
        # 1. Tarjetas de KPIs
        k1, k2, k3 = st.columns(3)
        
        # MAPE
        k1.metric(
            "MAPE (Error %)", 
            f"{kpis['MAPE']:.1f}%", 
            help="Promedio del error porcentual absoluto. Menos es mejor. <10% es excelente, <20% es bueno."
        )
        
        # BIAS
        bias_val = kpis['BIAS_Promedio']
        if bias_val > 0:
            lbl_bias = "Sobreestima (Optimista)"
            color_bias = "normal" # Verde si es positivo en ventas puede ser confuso, dejemos gris
        else:
            lbl_bias = "Subestima (Conservador)"
            color_bias = "off"
            
        k2.metric(
            "Bias Promedio", 
            f"{bias_val:,.1f}", 
            delta=lbl_bias,
            help="Si es positivo, el modelo suele predecir más de lo real. Si es negativo, predice menos."
        )
        
        # MAE
        k3.metric("MAE (Error Absoluto)", f"{kpis['MAE']:,.1f}", help="En promedio, se equivoca en esta cantidad de unidades.")
        
        # 2. Gráfico de Validación
        st.subheader("Gráfico: Realidad vs Predicción (Periodo de Prueba)")
        fig_test, ax_test = plt.subplots(figsize=(10, 4))
        
        ax_test.plot(df_test_res['ds'], df_test_res['y'], 'ko-', label='Realidad (Lo que pasó)')
        ax_test.plot(df_test_res['ds'], df_test_res['Prediccion_Prophet'], 'b--', label='Lo que dijo Prophet')
        ax_test.fill_between(df_test_res['ds'], df_test_res['y'], df_test_res['Prediccion_Prophet'], color='red', alpha=0.1, label='Error')
        
        ax_test.set_title(f"Validación últimos {meses_backtest} meses")
        ax_test.legend()
        ax_test.grid(True, alpha=0.3)
        st.pyplot(fig_test)
        
        # 3. Tabla de errores
        with st.expander("Ver tabla detalle errores"):
            st.dataframe(df_test_res.style.format({
                'y': '{:,.1f}', 
                'Prediccion_Prophet': '{:,.1f}', 
                'Error_Bias': '{:,.1f}',
                'APE': '{:.1%}'
            }))
            
    else:
        st.warning("No hay suficientes datos históricos para realizar el backtest solicitado. Disminuye los meses de prueba o carga más datos.")

# TAB 3: Componentes
with tab_comps:
    st.subheader("Descomposición de Fuerzas")
    fig2 = model_futuro.plot_components(forecast_futuro)
    st.pyplot(fig2)

# TAB 4: Datos
with tab_data:
    st.dataframe(forecast_futuro.tail(24))