import streamlit as st
import pandas as pd
import sys
from pathlib import Path
import altair as alt # Importamos Altair para gráficos

# --- Setup Inicial ---
src_path = str(Path(__file__).resolve().parent.parent / "src")
if src_path not in sys.path: sys.path.append(src_path)

import config
import core.radar_engine as radar_engine 
import data.data_loader as data_loader

st.set_page_config(layout="wide", page_title="Radar de Inventario", page_icon="📡")
st.title("📡 Radar de Inventario")

# --- 0. RESUMEN METODOLÓGICO (NUEVO) ---
with st.expander("ℹ️ ¿Cómo funciona este Radar? (Ver Fórmulas y Lógica)"):
    st.markdown(r"""
    **Propósito:** Este módulo detecta riesgos de quiebre y sobre-stock cruzando el inventario actual con el comportamiento histórico de la demanda.

    ### 🧮 Fórmulas Matemáticas:
    El sistema calcula la salud de cada SKU basándose en los siguientes indicadores:

    1. **Demanda Diaria ($\mu_d$):** Es el promedio de consumo diario basado en la historia reciente (excluyendo el mes en curso).
    
    2. **Stock de Seguridad (SS):** Es el inventario "colchón" necesario para cubrir la variabilidad de la demanda durante el tiempo de espera.
       $$SS = Z \times \sigma_d \times \sqrt{LT}$$
       * $Z$: Factor de servicio (ej. 1.65 para 95%, 2.33 para 99%).
       * $\sigma_d$: Desviación estándar de la demanda diaria (volatilidad).
       * $LT$: Lead Time (Tiempo de reposición en días).

    3. **Punto de Reorden (ROP):** Nivel de stock crítico. Si el inventario cae por debajo de este número, se debería haber emitido una compra.
       $$ROP = (\mu_d \times LT) + SS$$

    4. **Días de Cobertura (DOS):** Cuántos días podemos operar con el stock actual antes de quedarnos en cero.
       $$DOS = \frac{\text{Stock Actual}}{\text{Demanda Diaria}}$$
    """)
    st.info("💡 **Tip:** Ajuste el 'Nivel de Servicio' y 'Lead Time' en los filtros para ver cómo impactan el Stock de Seguridad y el ROP.")


# --- Carga de Datos ---
if 'data_loaded' not in st.session_state:
    with st.spinner("Cargando datos... por favor, espere."):
        data_loader.load_data_into_session()

if 'data_loaded' not in st.session_state:
    st.error("⚠️ No se pudieron cargar los datos. Ve al inicio.")
    st.stop()

# --- 2. Panel de Control (Filtros) ---
st.subheader("🛠️ Configuración del Análisis")
col1, col2, col3, col4, col5, col6 = st.columns(6) 
with col1:
    # Obtener familias únicas
    familias = sorted(st.session_state.df_stock['SubFamilia'].dropna().unique())
    familia_sel = st.selectbox("1. Selecciona Familia:", ["(Seleccione)"] + ["Todas"] + familias)

with col2:
    bodegas = sorted(st.session_state.df_stock['CodigoBodega'].dropna().unique())
    bodega_stk = st.selectbox("2. Bodega Stock:", bodegas, index=0)
with col3:
    # Obtenemos la lista única de bodegas de consumo disponibles
    bodegas_cons_opts = sorted(st.session_state.df_consumo['BodegaDestino_Requerida'].dropna().unique())
    mis_defaults = ["Bodega de Proyectos RE", "Bodega de Proyectos CI VDI"] 
    
    # 3. Validación de Seguridad (Opcional pero recomendada)
    # Esto evita que la app se caiga si un día una de esas bodegas no viene en el Excel
    defaults_validos = [b for b in mis_defaults if b in bodegas_cons_opts]
    # USAMOS MULTISELECT
    lista_bodegas_cons = st.multiselect( 
        "Bodegas de Consumo:",
        options=bodegas_cons_opts,
        default=mis_defaults, # Por defecto selecciona todas
        placeholder="Seleccione bodegas..."
    )

with col4:
    nivel_servicio = st.select_slider("4. Nivel Servicio:", options=list(config.Z_SCORE_MAP.keys()), value="99%")

with col5:
    lead_time = st.number_input("5. Lead Time (Días):", value=90, min_value=1)

with col6:
    meses_cobertura = st.number_input("6. Meta (Meses):", value=2.0, min_value=0.5, step=0.5, help="¿Para cuántos meses queremos tener stock?")

if familia_sel != "(Seleccione)":    
    # Validación: Si el usuario borra todas las bodegas, mostramos advertencia
    if not lista_bodegas_cons:
        st.warning("⚠️ Debe seleccionar al menos una bodega de consumo.")
        st.stop()
    
    # Llamada al motor
    df_resultado = radar_engine.ejecutar_analisis_masivo(
        st.session_state.df_stock,
        st.session_state.df_consumo,
        st.session_state.df_oc,
        familia_sel,
        ([bodega_stk], lista_bodegas_cons), 
        (lead_time, config.Z_SCORE_MAP[nivel_servicio])
    )
    if df_resultado.empty:
        st.warning("No hay datos para esta selección.")
    else:
        # --- 4. Transformación Visual (La "Magia") ---
        df_visual = df_resultado.copy()
        # ---------------------------------------------------------
        # [NUEVO] CÁLCULO DE STOCK PROYECTADO (Simulación a LT)
        # ---------------------------------------------------------
        # 1. Definir fecha límite (Hoy + Lead Time seleccionado)
        fecha_fin_lt = pd.Timestamp.now() + pd.DateOffset(days=lead_time)
        
        # 2. Preparar OCs (Los datos ya están limpios desde data_loader)
        df_oc_temp = st.session_state.df_oc
        col_fecha_oc = 'Fecha de entrega de la línea'
        if col_fecha_oc in df_oc_temp.columns:
            # 3. Filtrar llegadas relevantes (Desde hoy hasta fin del LT)
            mask_llegadas = (
                (df_oc_temp[col_fecha_oc] <= fecha_fin_lt) & 
                (df_oc_temp[col_fecha_oc] >= pd.Timestamp.now().floor('D'))
            )
            # Sumar por SKU
            llegadas_lt = df_oc_temp[mask_llegadas].groupby('Número de artículo')['Cantidad'].sum()
            # 4. Mapear al DataFrame visual
            df_visual['Llegadas LT'] = df_visual['SKU'].map(llegadas_lt).fillna(0)
        else:
            df_visual['Llegadas LT'] = 0
        # Aplicar Fórmula: Stock Final = Actual + Llegadas - (Demanda * Dias)
        df_visual['Stock Proyectado'] = (
            df_visual['Stock Actual'] + 
            df_visual['Llegadas LT'] - 
            (df_visual['Demanda Diaria'] * lead_time)
        )

        # ---------------------------------------------------------
        # [NUEVO] CÁLCULO DE STOCK IDEAL
        # ---------------------------------------------------------
        # Regla: Stock Ideal = Demanda Mensual * Meses Objetivo (Selector)
        df_visual['Stock Ideal'] = df_visual['Demanda mensual'] * meses_cobertura
        
        # Regla 2: Q (Cantidad a Pedir) = Stock Ideal - Stock Proyectado
        # Usamos .clip(lower=0) para evitar números negativos si estamos sobrados de stock
        df_visual['Q'] = (df_visual['Stock Ideal'] - df_visual['Stock Proyectado']).clip(lower=0)

        # ---------------------------------------------------------
        # [MEJORA] INTEGRACIÓN FINANCIERA (COSTOS)
        # ---------------------------------------------------------
        # Obtenemos costo unitario promedio/maximo por SKU desde el maestro de stock
        mapa_costos = st.session_state.df_stock.groupby('CodigoArticulo')['CostoUnitario'].max().to_dict()
        df_visual['CostoUnitario'] = df_visual['SKU'].map(mapa_costos).fillna(0)
        
        # Calculamos la inversión requerida para la sugerencia Q
        df_visual['Inversion_Requerida'] = df_visual['Q'] * df_visual['CostoUnitario']

        # [NUEVO] Lógica del Semáforo de Estado
        def obtener_estado(row):
            stock = row['Stock Actual']
            ss = row['SS']
            rop = row['ROP']
            ideal = row['Stock Ideal']
            
            if stock < ss:
                return "🔴 Crítico"   # Bajo nivel de seguridad
            elif stock < rop:
                return "🟡 Reorden"   # Bajo punto de reorden (pero sobre SS)
            elif stock > (ideal * 1.5) and ideal > 0: # Si supera por 50% el ideal
                return "🔵 Excedido"
            else:
                return "🟢 Saludable" # Sobre punto de reorden
            
        df_visual["Estado"] = df_visual.apply(obtener_estado, axis=1)
        
        # 2. Identificar columnas de consumo
        cols_consumo = [c for c in df_visual.columns if c.startswith("C.")]
        cols_consumo.sort()        
        
        # 3. Definir columnas fijas (Agregamos "Estado" al inicio)
        cols_fijas_deseadas = [
                    "SKU", "Nombre", "Estado", 
                    "Stock Actual", "Stock Proyectado", "Stock Ideal", "Q",
                    "Inversion_Requerida", # <--- NUEVA
                    "Llegadas LT", "Próxima Llegada", # <--- AGREGA ESTO AQUÍ
                    "DOS", "Demanda mensual", "Demanda Diaria", "SS", "ROP"
        ]
        cols_fijas_reales = [c for c in cols_fijas_deseadas if c in df_visual.columns]
        cols_finales_ordenadas = cols_fijas_reales + cols_consumo
        df_visual = df_visual[cols_finales_ordenadas] 
        
        # Filtramos basura: Ocultamos SKUs completamente inactivos (Sin stock, sin demanda, sin llegadas)
        mask_inactivos = (df_visual["Stock Actual"] <= 0) & (df_visual["Demanda mensual"] <= 0) & (df_visual["Llegadas LT"] <= 0)
        df_visual = df_visual[~mask_inactivos]

        # Ordenar: Primero los críticos (Rojo), luego Reorden (Amarillo)
        orden_map = {"🔴 Crítico": 0, "🟡 Reorden": 1, "🟢 Saludable": 2, "🔵 Excedido": 3}
        df_visual["_orden"] = df_visual["Estado"].map(orden_map)
        df_visual = df_visual.sort_values(by="_orden").drop(columns=["_orden"])

        # --- DASHBOARD DE RESUMEN (KPIs) ---
        st.divider()
        st.subheader("📊 Resumen Ejecutivo")
        
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        
        n_criticos = len(df_visual[df_visual['Estado'] == "🔴 Crítico"])
        n_reorden = len(df_visual[df_visual['Estado'] == "🟡 Reorden"])
        inv_total = df_visual['Inversion_Requerida'].sum()
        sku_top_inversion = df_visual.sort_values('Inversion_Requerida', ascending=False).iloc[0]['Nombre'] if not df_visual.empty else "N/A"

        kpi1.metric("SKUs Críticos", f"{n_criticos}", delta="Riesgo Quiebre", delta_color="inverse")
        kpi2.metric("SKUs en Reorden", f"{n_reorden}", delta="Planificar Compra", delta_color="normal")
        kpi3.metric("Inversión Sugerida Total", f"${inv_total:,.0f}", help="Costo total de comprar la cantidad Q sugerida para todos los items.")
        kpi4.metric("SKU Mayor Inversión", f"{sku_top_inversion}", help="El artículo que requiere más dinero para reponer.")

        # --- GRÁFICO DE ESTADOS ---
        df_chart = df_visual['Estado'].value_counts().reset_index()
        df_chart.columns = ['Estado', 'Cantidad']
        
        chart_estados = alt.Chart(df_chart).mark_bar().encode(
            x=alt.X('Cantidad', title='N° SKUs'),
            y=alt.Y('Estado', sort=['🔴 Crítico', '🟡 Reorden', '🟢 Saludable', '🔵 Excedido']),
            color=alt.Color('Estado', scale=alt.Scale(
                domain=['🔴 Crítico', '🟡 Reorden', '🟢 Saludable', '🔵 Excedido'],
                range=['#E31C23', '#F1C40F', '#2ECC71', '#3498DB']
            )),
            tooltip=['Estado', 'Cantidad']
        ).properties(height=200)
        
        st.altair_chart(chart_estados, use_container_width=True)

        # --- TABS DE GESTIÓN ---
        st.divider()
        tab_gestion, tab_todo = st.tabs(["🚨 Gestión de Urgencias", "📋 Análisis Completo"])

        # Configuración de columnas
        columnas_config = {
            "SKU": st.column_config.TextColumn("Código SKU"),
            "Nombre": st.column_config.TextColumn("Producto"),
            "Estado": st.column_config.TextColumn("Estado"),
            "Stock Actual": st.column_config.NumberColumn("Stock Hoy", format="%.0f"),
            # Proyección
            "Stock Proyectado": st.column_config.NumberColumn(
                f"Proy. {int(lead_time)}d", 
                help="Stock estimado al final del Lead Time (considerando llegadas)",
                format="%.0f"
            ),
            # [NUEVO] Stock Ideal
            "Stock Ideal": st.column_config.NumberColumn(
                f"Meta ({meses_cobertura}m)", 
                help=f"Objetivo: Consumo Promedio Mensual x {meses_cobertura}",
                format="%.0f"
            ),
            "Q": st.column_config.NumberColumn(
                "🛒 Cant. a Pedir",
                help="Sugerencia = Stock Ideal - Stock Proyectado",
                format="%.0f"
            ),
            "Inversion_Requerida": st.column_config.NumberColumn(
                "💰 Inversión ($)",
                help="Q * Costo Unitario",
                format="$%.0f"
            ),
            "Llegadas LT": st.column_config.NumberColumn("Llegadas (OC)", format="%.0f"),
            "Próxima Llegada": st.column_config.DateColumn("Próxima Llegada", format="DD/MM/YYYY", help="Fecha más cercana de recepción de mercadería."),
            "DOS": st.column_config.NumberColumn("Días Cobertura", format="%.1f d"),
            "SS": st.column_config.NumberColumn("Stock Seguridad", format="%.0f", help="Stock de seguridad en unidades."),
            "ROP": st.column_config.NumberColumn("Punto Reorden", format="%.0f", help="Punto de reorden en unidades."),
            "Demanda mensual": st.column_config.NumberColumn("Dem. Mensual", format="%.0f", help="Promedio mensual histórico de consumo en unidades."),
            "Demanda Diaria": st.column_config.NumberColumn("Dem. Diaria", format="%.0f"),
        }
        # Configuración dinámica para columnas de consumo
        for col in cols_consumo:
            columnas_config[col] = st.column_config.NumberColumn(col, format="%.0f", width="small")
        
        with tab_gestion:
            st.subheader("⚠️ Artículos que requieren atención")
            st.markdown("Mostrando solo items en estado **Crítico** o **Reorden**.")
            
            df_urgente = df_visual[df_visual['Estado'].isin(["🔴 Crítico", "🟡 Reorden"])].copy()
            
            if df_urgente.empty:
                st.success("🎉 ¡Excelente! No tienes productos en riesgo de quiebre bajo estos parámetros.")
            else:
                st.dataframe(
                    df_urgente,
                    column_config=columnas_config,
                    use_container_width=True,
                    hide_index=True
                )

        with tab_todo:
            st.subheader("Listado Maestro Completo")
            
            # Buscador en cliente
            search_term = st.text_input("🔍 Buscar en tabla (Nombre o SKU):", "")
            df_show = df_visual.copy()
            
            if search_term:
                df_show = df_show[
                    df_show['SKU'].str.contains(search_term, case=False) | 
                    df_show['Nombre'].str.contains(search_term, case=False)
                ]

            st.dataframe(
                df_show,
                column_config=columnas_config,
                use_container_width=True,
                hide_index=True
            )

        # Botón descarga
        st.download_button(
            "📥 Descargar CSV",
            data=df_visual.to_csv(index=False).encode('utf-8'),
            file_name="radar_inventario.csv"
        )
else:
    st.info("👆 Selecciona una familia arriba para comenzar.")