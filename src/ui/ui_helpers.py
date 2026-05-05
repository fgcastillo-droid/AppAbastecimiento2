import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import locale
import altair as alt

try:
    from src import config
    from core import analysis
    from core import simulator
except ImportError:
    import config
    import core.analysis as analysis


def setup_locale():
    """Configura el locale a español para los nombres de los meses."""
    try:
        locale.setlocale(locale.LC_TIME, config.LOCALE_ES)
    except locale.Error:
        try:
            locale.setlocale(locale.LC_TIME, config.LOCALE_ES_FALLBACK)
        except locale.Error:
            print(f"Locale '{config.LOCALE_ES}' o '{config.LOCALE_ES_FALLBACK}' no encontrado.")

def create_sku_options(all_skus, df_stock):
    """
    Crea la lista de opciones para el selector de SKU (Req. 2).
    Formato: "SKU | Nombre"
    """
    mapa_nombres = df_stock.drop_duplicates(subset=['CodigoArticulo']).set_index('CodigoArticulo')['NombreArticulo'].to_dict()
    
    opciones_selector_sku = []
    for sku in all_skus:
        nombre = mapa_nombres.get(sku, "Nombre no encontrado")
        opciones_selector_sku.append(f"{sku} | {nombre}")
        
    # Buscar el índice del SKU por defecto
    default_sku = 'EXI-009231'
    default_index = 0
    for i, option in enumerate(opciones_selector_sku):
        if option.startswith(default_sku):
            default_index = i
            break
            
    return opciones_selector_sku, mapa_nombres, default_index

def create_sku_options_oc(all_skus, df_stock):
    """
    Crea la lista de opciones para el selector de SKU (Req. 2).
    Formato: "SKU | Nombre"
    """
    mapa_nombres = df_stock.drop_duplicates(subset=['Número de artículo']).set_index('Número de artículo')['Descripción artículo/serv.'].to_dict()
    
    opciones_selector_sku = []
    for sku in all_skus:
        nombre = mapa_nombres.get(sku, "Nombre no encontrado")
        opciones_selector_sku.append(f"{sku} | {nombre}")
        
    # Buscar el índice del SKU por defecto
    default_sku = 'EXI-009231'
    default_index = 0
    for i, option in enumerate(opciones_selector_sku):
        if option.startswith(default_sku):
            default_index = i
            break
            
    return opciones_selector_sku, mapa_nombres, default_index

def detectar_columna(df, candidatos):
    """
    Busca la primera columna que exista en el DataFrame de una lista de candidatos.
    Retorna el nombre real de la columna encontrada o None.
    Útil para manejar variaciones de nombres (ej: 'Subfamilia' vs 'U_SubFamilia').
    """
    if df is None or df.empty:
        return None
        
    for col in candidatos:
        if col in df.columns:
            return col
    return None

def display_metrics(metrics, lead_time_days, service_level_z):
    """Muestra todas las métricas en la app de Streamlit."""
    st.subheader("Métricas Clave")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Stock Inicial (Disp.)", f"{metrics['initial_stock']:,.0f}")
    col2.metric("Consumo Prom. (Simulación)", f"{metrics['monthly_demand_mean']:,.0f}", 
                help="Promedio mensual de todos los datos de consumo cargados, usado para calcular SS y ROP.")
    col3.metric("Desv. Estándar (Volatilidad)", f"{metrics.get('monthly_demand_std', 0):,.0f}",
                help="Desviación estándar del consumo mensual. Un valor alto indica ventas más irregulares.")
    col4.metric("Llegadas Programadas", f"{metrics['llegadas_count']}")
    st.markdown("---")
    # Requerimiento 1: Consumo histórico
    st.subheader("Consumo Histórico Reciente")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric(f"Demanda {metrics['demand_M_0'][0].strftime('%B').capitalize()} (Actual)", f"{metrics['demand_M_0'][1]:,.0f}")
    col2.metric(f"Demanda {metrics['demand_M_1'][0].strftime('%B').capitalize()}", f"{metrics['demand_M_1'][1]:,.0f}")
    col3.metric(f"Demanda {metrics['demand_M_2'][0].strftime('%B').capitalize()}", f"{metrics['demand_M_2'][1]:,.0f}")
    col4.metric(f"Demanda {metrics['demand_M_3'][0].strftime('%B').capitalize()}", f"{metrics['demand_M_3'][1]:,.0f}")
    col5.metric(f"Demanda {metrics['demand_M_4'][0].strftime('%B').capitalize()}", f"{metrics['demand_M_4'][1]:,.0f}")
    # Gráfico de Barras de Consumo Histórico
    st.write("") 
    try:
        hist_data = [
            {"Fecha": metrics['demand_M_4'][0], "Consumo": metrics['demand_M_4'][1], "Mes": metrics['demand_M_4'][0].strftime('%Y-%m')},
            {"Fecha": metrics['demand_M_3'][0], "Consumo": metrics['demand_M_3'][1], "Mes": metrics['demand_M_3'][0].strftime('%Y-%m')},
            {"Fecha": metrics['demand_M_2'][0], "Consumo": metrics['demand_M_2'][1], "Mes": metrics['demand_M_2'][0].strftime('%Y-%m')},
            {"Fecha": metrics['demand_M_1'][0], "Consumo": metrics['demand_M_1'][1], "Mes": metrics['demand_M_1'][0].strftime('%Y-%m')},
            {"Fecha": metrics['demand_M_0'][0], "Consumo": metrics['demand_M_0'][1], "Mes": metrics['demand_M_0'][0].strftime('%Y-%m')},
        ]
        df_hist = pd.DataFrame(hist_data)
        chart_hist = alt.Chart(df_hist).mark_line(point=True).encode(
            x=alt.X('Mes:O', 
                    sort=alt.EncodingSortField(field="Fecha", op="min", order='ascending'), 
                    title='Mes'), 
            y=alt.Y('Consumo:Q', title='Consumo Mensual'),
            tooltip=[
                alt.Tooltip('Mes:O'),
                alt.Tooltip('Consumo:Q', format=',.0f')
            ]
        ).properties(
            title='Consumo Histórico de Meses Usados para Simulación'
        )
        st.altair_chart(chart_hist, use_container_width=True)
    except Exception as e:
        st.warning(f"No se pudo generar el gráfico de consumo histórico: {e}")
    st.markdown("---")
    st.subheader("Parámetros de Simulación (Calculados)")
    col1, col2, col3 = st.columns(3)
    col1.metric("Lead Time (Días)", f"{lead_time_days}", help="Parámetro de entrada.")
    col2.metric("Safety Stock (SS)", f"{metrics['safety_stock']:,.0f}", f"Nivel Servicio {service_level_z}Z")
    col3.metric("Punto de Reorden (ROP)", f"{metrics['reorder_point']:,.0f}")

def generate_simulation_plot(df_sim, metrics, llegadas_map, sku_name, simulation_days):
    """
    Genera un gráfico interactivo de Altair.
    (El contenido de esta función no cambia)
    """
    df_plot = df_sim.reset_index()
    df_plot['ROP'] = metrics['reorder_point']
    df_plot['SafetyStock'] = metrics['safety_stock']
    df_lines = df_plot.melt(
        id_vars=['Fecha'],
        value_vars=['NivelInventario', 'ROP', 'SafetyStock'],
        var_name='Leyenda', 
        value_name='Valor'
    )
    df_llegadas = pd.DataFrame(list(llegadas_map.items()), columns=['Fecha', 'CantidadLlegada'])
    df_llegadas = pd.merge(df_llegadas, df_plot, on='Fecha', how='left')
    df_llegadas['Leyenda'] = 'Llegada de OC' 
    df_zero_line = pd.DataFrame({'y': [0]})
    domain = ['NivelInventario', 'ROP', 'SafetyStock', 'Llegada de OC']
    range_colors = ['#1f77b4', '#ff7f0e', '#9467bd', '#2ca02c'] 
    inventory_line = alt.Chart(
        df_lines.loc[df_lines['Leyenda'] == 'NivelInventario']
    ).mark_line(
        interpolate='step-after', point=True
    ).encode(
        x=alt.X('Fecha:T', title='Fecha', axis=alt.Axis(format="%Y-%m-%d")),
        y=alt.Y('Valor:Q', title='Unidades en Stock'),
        color=alt.Color('Leyenda:N', scale=alt.Scale(domain=domain, range=range_colors), title='Leyenda'),
        tooltip=[
            alt.Tooltip('Fecha:T', format="%Y-%m-%d"), 
            alt.Tooltip('Leyenda:N', title='Tipo'),
            alt.Tooltip('Valor:Q', title='Stock Proyectado', format=',.0f')
        ]
    )
    reference_lines = alt.Chart(
        df_lines.loc[df_lines['Leyenda'] != 'NivelInventario']
    ).mark_line(
        strokeDash=[5, 5]
    ).encode(
        x=alt.X('Fecha:T'), 
        y=alt.Y('Valor:Q'),
        color=alt.Color('Leyenda:N', scale=alt.Scale(domain=domain, range=range_colors)),
        tooltip=[
            alt.Tooltip('Leyenda:N', title='Tipo'),
            alt.Tooltip('Valor:Q', title='Nivel', format=',.0f')
        ]
    )
    
    arrival_points = alt.Chart(df_llegadas).mark_circle(size=100, opacity=0.9).encode(
        x=alt.X('Fecha:T'),
        y=alt.Y('NivelInventario:Q'),
        color=alt.Color('Leyenda:N', scale=alt.Scale(domain=domain, range=range_colors)),
        tooltip=[
            alt.Tooltip('Fecha:T', title='Llegada de OC', format="%Y-%m-%d"),
            alt.Tooltip('CantidadLlegada:Q', title='Cantidad Recibida', format=',.0f')
        ]
    )
    zero_line = alt.Chart(df_zero_line).mark_rule(
        color='red', strokeDash=[2, 2]
    ).encode(
        y='y',
        tooltip=alt.value("Stock Cero") 
    )
    final_chart = (inventory_line + reference_lines + arrival_points + zero_line).properties(
        title=f'Proyección de Inventario para {sku_name} ({simulation_days} días)'
    ).interactive() 
    return final_chart

def prepare_end_of_month_table(df_sim):
    """
    Toma el DataFrame de simulación diaria y lo resume a fin de mes (Req. 3).
    (El contenido de esta función no cambia)
    """
    df_fin_de_mes = df_sim['NivelInventario'].resample('ME').last().reset_index()
    
    df_fin_de_mes['Mes'] = df_fin_de_mes['Fecha'].dt.strftime('%Y-%m (%B)')
    df_fin_de_mes['Stock al Cierre'] = df_fin_de_mes['NivelInventario'].apply(lambda x: f"{x:,.0f}")
    
    return df_fin_de_mes[['Mes', 'Stock al Cierre']]

def display_order_recommendation(metrics, llegadas_map, df_sim, lead_time_days):
    """
    Muestra la recomendación de pedido (UI).
    La lógica de cálculo ahora está en 'analysis.py' y usa la proyección.
    """
    
    # --- 1. Llamar a la función de análisis ---
    reco = analysis.calculate_order_recommendation(
        metrics, llegadas_map, df_sim, lead_time_days
    )

    # --- 2. Mostrar en la UI ---
    st.subheader("Recomendación de Abastecimiento 💡")
    
    # Manejar caso de error (simulación muy corta)
    if reco["status"] == "error":
        st.error(f"**Error de Proyección:** {reco['error_message']}")
        st.info("Aumente los 'Días a Simular' para que sean mayores o iguales al Lead Time.")
        return

    col1, col2, col3 = st.columns(3)
    
    col1.metric(
        f"Stock Proyectado (en {reco['lead_time_days']} días)", 
        f"{reco['projected_stock_at_lt']:,.0f}",
        help=f"Nivel de stock simulado para el {reco['forecast_date'].strftime('%Y-%m-%d')}."
    )
    
    col2.metric(
        "Safety Stock (ss)", 
        f"{reco['ss']:,.0f}", 
        help="Si el stock proyectado cae bajo este número, se debe pedir."
    )
    
    col3.metric(
        "Recomendación de Pedido",
        f"{reco['suggested_order_qty']:,.0f} uds.",
        delta=f"{reco['suggested_order_qty']:,.0f} uds." if reco['status'] == 'success' else None,
        delta_color="inverse"
    )


    # Mostrar el veredicto final
    if reco['status'] == 'success':
        st.success(f"**Recomendación:** Pedir **{reco['suggested_order_qty']:,.0f} unidades**.\n\n"
                   f"El stock proyectado ({reco['projected_stock_at_lt']:,.0f}) está por debajo del ss ({reco['ss']:,.0f}).")
    
    else: # 'info'
        st.info(f"**No se necesita pedido.** El stock proyectado ({reco['projected_stock_at_lt']:,.0f}) se mantiene por encima del Punto de Reorden ({reco['ss']:,.0f}).")

def display_arrival_details(df_llegadas_detalle):
    """
    Muestra una tabla con el detalle de las próximas llegadas (OCs).
    """
    st.subheader("Detalle de Próximas Llegadas (OC)")
    
    columna_oc = 'Número de documento' 
    
    if columna_oc not in df_llegadas_detalle.columns:
        st.error(f"Error: La columna '{columna_oc}' no se encontró en el archivo OPOR.")
        st.info("No se puede mostrar el detalle de OCs.")
        return

    if df_llegadas_detalle.empty:
        st.info("No hay órdenes de compra programadas para este SKU.")
    else:
        # Seleccionamos, renombramos y ordenamos las columnas para mostrar
        df_display = df_llegadas_detalle[[
            'Fecha de entrega de la línea', 
            columna_oc, 
            'Cantidad',
            'Comentarios'
        ]].copy()
        
        df_display.rename(columns={
            'Fecha de entrega de la línea': 'Fecha Llegada',
            columna_oc: 'N° Orden Compra',
            'Cantidad': 'Cantidad',
            'Comentarios': 'Comentarios'
        }, inplace=True)
        
        df_display = df_display.sort_values(by='Fecha Llegada')
        
        # Formatear para mejor visualización
        df_display['Fecha Llegada'] = df_display['Fecha Llegada'].dt.strftime('%Y-%m-%d')
        df_display['Cantidad'] = df_display['Cantidad'].apply(lambda x: f"{x:,.0f}")
        
        # Mostramos la tabla
        st.dataframe(df_display, width="stretch", hide_index=True)

def render_header():
    """Muestra el logo corporativo en el encabezado."""
    col1, col2 = st.columns([1, 5])
    with col1:
        # Intenta cargar el logo si existe
        try:
            st.image("assets/COPEC-FLUX.svg", width=150)
        except:
            st.write("") # Fallback silencioso si no encuentra la imagen

def render_historical_stock_section(sku_seleccionado, df_stock, df_consumo, bodegas_seleccionadas=None):
    """
    Renderiza la sección completa de 'Máquina del Tiempo' para consultar stock histórico.
    """
    st.markdown("---")
    st.subheader("🕰️ Máquina del Tiempo: Stock Histórico")
    st.info(f"Consulta el stock pasado del SKU seleccionado: **{sku_seleccionado}**")

    col_h1, col_h2, col_h3 = st.columns([2, 1, 2])

    with col_h1:
        fecha_historia = st.date_input(
            "Seleccione fecha del pasado:",
            value=pd.Timestamp.now() - pd.Timedelta(days=7),
            max_value=pd.Timestamp.now()
        )

    with col_h2:
        st.write("") 
        st.write("")
        # Usamos key única
        btn_calc_hist = st.button("🔍 Consultar Stock", key="btn_historia_ui")

    if btn_calc_hist:
        with col_h3:
            try:
                # Llamada al motor lógico
                stock_pasado = simulator.obtener_stock_historico_con_owtr(
                    sku=sku_seleccionado, 
                    fecha_objetivo=fecha_historia,
                    df_stock_actual=df_stock, 
                    df_owtr=df_consumo,
                    bodegas_filtro=bodegas_seleccionadas # <--- Pasamos la selección
                )
                
                st.metric(
                    label=f"Stock Real al {fecha_historia.strftime('%d-%m-%Y')}",
                    value=f"{stock_pasado:,.0f} un.",
                    delta="Calculado vs BF0001",
                    delta_color="off"
                )
                
                if stock_pasado < 0:
                    st.error("⚠️ El cálculo dió negativo. Posible falta de 'Entradas' históricas.")
                    
            except Exception as e:
                st.error(f"Error al calcular historia: {e}")

def aplicar_filtros_avanzados(df, sidebar=True):
    """
    Genera una barra lateral con filtros completos de inventario 
    y retorna el DataFrame filtrado + un diccionario con los filtros aplicados.
    """
    container = st.sidebar if sidebar else st.expander("🔍 Filtros de Inventario", expanded=True)
    
    with container:
        st.header("🔍 Filtros de Gestión")
        
        # 1. Filtro de Texto (Buscador Global)
        busqueda = st.text_input("🔎 Buscar (SKU o Nombre)", placeholder="Ej: Inversor...").upper()
        
        # 2. Filtro de Bodegas (CRÍTICO para gestión en terreno)
        lista_bodegas = sorted(df['NombreBodega'].unique())
        sel_bodegas = st.multiselect("🏭 Bodegas", lista_bodegas, default=lista_bodegas)
        
        # 3. Filtro de Familia
        lista_familias = sorted(df['Familia'].astype(str).unique())
        sel_familias = st.multiselect("📂 Familias", lista_familias, default=lista_familias)
        
        # 4. Filtro de Categoría (Dinámico basado en Familia seleccionada)
        df_filtered_pre = df[df['Familia'].isin(sel_familias)]
        col_cat = 'SubFamilia' if 'SubFamilia' in df.columns else 'Familia'
        lista_cats = sorted(df_filtered_pre[col_cat].astype(str).unique())
        sel_cats = st.multiselect("📑 Sub-Categorías", lista_cats, default=lista_cats)
        
        # 5. Switches Rápidos
        solo_stock = st.toggle("📦 Ocultar Stock 0", value=True)
        
    # --- APLICACIÓN DE LÓGICA ---
    df_out = df.copy()
    
    # Filtro Bodega
    if sel_bodegas:
        df_out = df_out[df_out['NombreBodega'].isin(sel_bodegas)]
        
    # Filtro Familia
    if sel_familias:
        df_out = df_out[df_out['Familia'].isin(sel_familias)]
        
    # Filtro Categoría
    if sel_cats:
        df_out = df_out[df_out[col_cat].isin(sel_cats)]
        
    # Filtro Stock 0
    if solo_stock:
        df_out = df_out[df_out['StockActual'] > 0.01] # Usamos 0.01 para evitar errores de float
        
    # Filtro de Texto
    if busqueda:
        mask_sku = df_out['CodigoArticulo'].astype(str).str.upper().str.contains(busqueda)
        mask_nom = df_out['NombreArticulo'].astype(str).str.upper().str.contains(busqueda)
        df_out = df_out[mask_sku | mask_nom]
        
    return df_out

def plot_barras_horizontal(df, x_col, y_col, color_hex='#1f77b4', title="", format_str='$,.0f'):
    return alt.Chart(df).mark_bar(color=color_hex).encode(
        x=alt.X(f'{x_col}:Q', title=title, axis=alt.Axis(format='$,.0s')),
        y=alt.Y(f'{y_col}:N', sort='-x', title=''),
        tooltip=[alt.Tooltip(y_col), alt.Tooltip(x_col, format=format_str)]
    ).properties(height=300)

def plot_evolucion_historica(df, x_col='Mes', y_col='ValorStockCierre', color_col='Subfamilia'):
    return alt.Chart(df).mark_area().encode(
        x=alt.X(f'{x_col}:O', axis=alt.Axis(labelAngle=-45)),
        y=alt.Y(f'{y_col}:Q', stack='zero', axis=alt.Axis(format='$,.0s')),
        color=alt.Color(f'{color_col}:N'),
        tooltip=[x_col, color_col, alt.Tooltip(y_col, format='$,.0f')]
    ).interactive()

def render_simulation_sidebar(df_stock, df_consumo):
    """
    Renderiza todos los controles de la barra lateral y retorna los parámetros seleccionados.
    """
    st.sidebar.header("Configuración de Simulación")

    # 1. Preparar Listas
    lista_skus_stock = df_stock['CodigoArticulo'].dropna().unique()
    lista_skus_consumo = df_consumo['CodigoArticulo'].dropna().unique()
    all_skus = sorted(list(set(lista_skus_stock) | set(lista_skus_consumo)))

    lista_bodegas_stock = sorted(df_stock['CodigoBodega'].dropna().unique())
    lista_bodegas_consumo = sorted(df_consumo['BodegaDestino_Requerida'].dropna().unique())

    # 2. Selector de SKU
    opciones_selector_sku, mapa_nombres, default_index = create_sku_options(all_skus, df_stock)
    sku_formateado = st.sidebar.selectbox(
        "1. Seleccione un SKU (busque por código o nombre):",
        opciones_selector_sku, 
        index=default_index
    )
    sku_seleccionado = sku_formateado.split(" | ")[0]

    # 3. Selectores de Bodega (Con lógica de defaults)
    # Default Stock
    def_stock = 'BF0001'
    def_stock_sel = [def_stock] if def_stock in lista_bodegas_stock else ([lista_bodegas_stock[0]] if lista_bodegas_stock else [])
    
    bodega_stock_sel = st.sidebar.multiselect(
        "2. Seleccione Bodega(s) de Stock:",
        options=lista_bodegas_stock,
        default=def_stock_sel
    )

    # Default Consumo
    def_cons = 'Bodega de Proyectos RE'
    def_cons_sel = [def_cons] if def_cons in lista_bodegas_consumo else ([lista_bodegas_consumo[0]] if lista_bodegas_consumo else [])
    
    bodega_consumo_sel = st.sidebar.multiselect(
        "3. Seleccione Bodega(s) de Consumo:",
        options=lista_bodegas_consumo,
        default=def_cons_sel
    )

    st.sidebar.markdown("---")

    # 4. Parámetros Numéricos
    service_level_str = st.sidebar.select_slider(
        "4. Nivel de Servicio (para Safety Stock):",
        options=list(config.Z_SCORE_MAP.keys()),
        value="99%"
    )
    service_level_z = config.Z_SCORE_MAP[service_level_str]
    
    lead_time_days = st.sidebar.number_input("5. Lead Time (Días):", min_value=1, max_value=120, value=90)
    dias_a_simular = st.sidebar.number_input("6. Días a Simular:", min_value=30, max_value=365, value=100)
    
    # NUEVO CONTROL
    use_variability = st.sidebar.checkbox("🎲 Simular Variabilidad (Estocástico)", value=False, help="Si se activa, la demanda diaria variará aleatoriamente según la desviación estándar histórica.")

    # 5. Botón de Ejecución
    ejecutar = st.sidebar.button("🚀 Ejecutar Simulación", type="primary")

    # Retornamos un diccionario o tupla con TODO lo que la página necesita
    return {
        "sku": sku_seleccionado,
        "bodegas_stock": bodega_stock_sel,
        "bodegas_consumo": bodega_consumo_sel,
        "z_score": service_level_z,
        "lead_time": lead_time_days,
        "dias_sim": dias_a_simular,
        "use_variability": use_variability, # Retornamos el valor
        "ejecutar": ejecutar,
        "mapa_nombres": mapa_nombres
    }

def render_consumption_details(sku, bodegas_consumo, df_consumo_global):
    """
    Muestra el expander con los datos de consumo filtrados.
    """
    st.markdown("---")
    with st.expander("Ver datos de consumo utilizados para esta simulación"):
        st.subheader(f"Historial de Consumo para {sku}")
        st.caption(f"Filtrado por bodegas: {', '.join(bodegas_consumo)}")
        
        # Filtrado local
        df_consumo_usado = df_consumo_global[
            (df_consumo_global['CodigoArticulo'] == sku) &
            (df_consumo_global['BodegaDestino_Requerida'].isin(bodegas_consumo))
        ].copy()

        if df_consumo_usado.empty:
            st.warning("No se encontró historial de consumo.")
        else:
            cols_mostrar = [
                'FechaSolicitud', 'CantidadSolicitada', 'BodegaDestino_Requerida',
                'SolicitadoPor', 'CodigoProyecto', 'NombreProyecto', 'CodigoUnidadNegocio'
            ]
            # Intersección de columnas para evitar errores si falta alguna
            cols_reales = [c for c in cols_mostrar if c in df_consumo_usado.columns]
            
            st.dataframe(
                df_consumo_usado[cols_reales].sort_values(by='FechaSolicitud', ascending=False), 
                width="stretch"
            )