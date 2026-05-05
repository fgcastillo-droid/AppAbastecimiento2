import altair as alt
import pandas as pd

def generate_historical_consumo_chart(metrics):
    """
    Genera el gráfico de líneas del consumo histórico reciente.
    (Extraído de la función display_metrics para modularidad)
    """
    hist_data = [
        {"Fecha": metrics['demand_M_3'][0], "Consumo": metrics['demand_M_3'][1], "Mes": metrics['demand_M_3'][0].strftime('%Y-%m')},
        {"Fecha": metrics['demand_M_2'][0], "Consumo": metrics['demand_M_2'][1], "Mes": metrics['demand_M_2'][0].strftime('%Y-%m')},
        {"Fecha": metrics['demand_M_1'][0], "Consumo": metrics['demand_M_1'][1], "Mes": metrics['demand_M_1'][0].strftime('%Y-%m')},
        {"Fecha": metrics['demand_M_0'][0], "Consumo": metrics['demand_M_0'][1], "Mes": metrics['demand_M_0'][0].strftime('%Y-%m')},
    ]
    df_hist = pd.DataFrame(hist_data)
    
    chart = alt.Chart(df_hist).mark_line(point=True).encode(
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
    return chart

def plot_barras_simple(df, x_col, y_col, x_title, color=None):
    """Gráfico de barras horizontal genérico."""
    
    # 1. Definimos la base del gráfico (con o sin color fijo)
    if color:
        # Si hay un color específico (ej. '#E31C23'), lo usamos.
        base = alt.Chart(df).mark_bar(color=color)
    else:
        # Si es None, NO pasamos el argumento color.
        base = alt.Chart(df).mark_bar()

    # 2. Definimos la codificación (ejes y tooltip)
    chart = base.encode(
        x=alt.X(f'{x_col}:Q', title=x_title, axis=alt.Axis(format='$,.0s')),
        y=alt.Y(f'{y_col}:N', sort='-x', title=''),
        tooltip=[y_col, alt.Tooltip(x_col, format='$,.0f')]
    )
    
    # 3. Si no dimos un color fijo, coloreamos por categoría automáticamente
    if not color: 
        chart = chart.encode(color=alt.Color(f'{y_col}:N', legend=None))
        
    return chart.properties(height=300)

def plot_distribucion_bodega(df):
    """
    Gráfico pre-configurado para mostrar Valorización por Bodega.
    Usa el color corporativo rojo y configura los ejes automáticamente.
    """
    return plot_barras_simple(
        df=df, 
        x_col='ValorTotalInventario', 
        y_col='NombreBodega', 
        x_title='Monto Invertido ($)',
        color='#E31C23' # Rojo Copec Flux
    ).properties(
        title="Distribución de Capital Inmovilizado"
    )

def plot_distribucion_subfamilia(df):
    """
    Gráfico de Valorización por SubFamilia.
    """
    return plot_barras_simple(
        df=df, 
        x_col='ValorTotalInventario', 
        y_col='Categoria', # Usamos el nombre estandarizado en analysis
        x_title='Monto Invertido ($)',
        color='#E31C23' # Mismo rojo corporativo para consistencia
    ).properties(
        title="Distribución por SubFamilia"
    )

def plot_area_historica(df, x_col, y_col, color_col):
    """Gráfico de área para la evolución histórica."""
    return alt.Chart(df).mark_area().encode(
        x=alt.X(f'{x_col}:O', title='Mes', axis=alt.Axis(labelAngle=-45)),
        y=alt.Y(f'{y_col}:Q', title='Valor Stock ($)', stack='zero', axis=alt.Axis(format='$,.0s')),
        color=alt.Color(f'{color_col}:N', title=color_col),
        tooltip=[
            alt.Tooltip(x_col),
            alt.Tooltip(color_col),
            alt.Tooltip(y_col, format='$,.0f', title='Valor')
        ]
    ).properties(height=400).interactive()

def plot_matriz_rotacion(df, x_col, y_col, tooltip_cols):
    """
    Gráfico de Dispersión:
    Eje X: Inversión Promedio ($)
    Eje Y: Rotación (Veces)
    """
    base = alt.Chart(df).mark_circle(size=80).encode(
        x=alt.X(f'{x_col}:Q', title='Inversión Promedio ($)', axis=alt.Axis(format='$,.0s')),
        y=alt.Y(f'{y_col}:Q', title='Rotación (Veces/Año)'),
        color=alt.Color('TipoRotacion:N', 
                        scale=alt.Scale(domain=['Alta', 'Media', 'Lenta'], 
                                        range=['#2ca02c', '#ff7f0e', '#d62728']),
                        title="Velocidad"),
        tooltip=tooltip_cols
    ).interactive()
    
    # Líneas promedio (para crear cuadrantes visuales)
    mean_rot = alt.Chart(df).mark_rule(color='gray', strokeDash=[5,5]).encode(y=f'mean({y_col}):Q')
    mean_inv = alt.Chart(df).mark_rule(color='gray', strokeDash=[5,5]).encode(x=f'mean({x_col}):Q')
    
    return (base + mean_rot + mean_inv).properties(
        title="Matriz de Eficiencia: Inversión vs Rotación",
        height=500
    )

def plot_evolucion_consumo(df):
    """Gráfico de línea para la tendencia de salidas ($)."""
    return alt.Chart(df).mark_line(point=True, color='#E31C23').encode(
        x=alt.X('Mes:O', title='Mes'),
        y=alt.Y('ValorTotalSolicitado:Q', title='Consumo ($)', axis=alt.Axis(format='$,.0s')),
        tooltip=['Mes', alt.Tooltip('ValorTotalSolicitado', format='$,.0f', title='Salidas')]
    ).properties(
        title="Tendencia de Salidas",
        height=200
    )

def plot_res_ventas_evolucion(df):
    """
    Gráfico de Evolución de Ventas (Cantidad).
    Se agrega clip=False para que no corte los números de arriba.
    """
    base = alt.Chart(df).encode(x=alt.X('yearmonth(fecha_de_ganado):T', title='Mes Venta'))
    
    # 1. Barras
    barras = base.mark_bar(opacity=0.8).encode(
        y=alt.Y('count():Q', title='N° Proyectos'),
        color=alt.Color('tipo_proyecto:N', legend=alt.Legend(title="Tipo", orient="top")),
        tooltip=['yearmonth(fecha_de_ganado)', 'tipo_proyecto', 'count()']
    )
    
    # 2. Línea
    linea = base.mark_line(color='red', strokeWidth=2, point=True).encode(
        y=alt.Y('count():Q')
    )

    # 3. Textos (CORREGIDO)
    # Agregamos clip=False para evitar el corte superior
    textos = base.mark_text(dy=-15, color='black', clip=False).encode(
        y=alt.Y('count():Q'),       
        text=alt.Text('count():Q')   
    )
    
    return (barras + linea + textos).interactive()

def plot_res_instalados_evolucion(df):
    """
    Gráfico de Evolución de INSTALACIONES FINALIZADAS (Por fecha de término).
    Muestra cantidad de proyectos terminados por mes.
    """
    # Filtramos solo lo que tiene fecha de término
    df_term = df.dropna(subset=['fecha_de_termino_de_instalacion_real']).copy()
    
    if df_term.empty:
        return alt.Chart(pd.DataFrame({'A': []})).mark_text().encode(text=alt.value("Sin datos de término"))

    base = alt.Chart(df_term).encode(
        x=alt.X('yearmonth(fecha_de_termino_de_instalacion_real):T', title='Mes de Término')
    )
    
    # 1. Barras (Cantidad Instalada)
    barras = base.mark_bar(opacity=0.8).encode(
        y=alt.Y('count():Q', title='Proyectos Instalados'),
        color=alt.Color('tipo_proyecto:N', legend=alt.Legend(title="Tipo")),
        tooltip=['yearmonth(fecha_de_termino_de_instalacion_real)', 'tipo_proyecto', 'count()']
    )
    
    # 2. Línea de Tendencia
    linea = base.mark_line(color='green', strokeWidth=2, point=True).encode(
        y=alt.Y('count():Q')
    )

    # 3. Textos (Total arriba)
    textos = base.mark_text(dy=-15, color='black', clip=False).encode(
        y=alt.Y('count():Q'),       
        text=alt.Text('count():Q')   
    )
    
    return (barras + linea + textos).interactive()

def plot_res_tendencia_kwp(df):
    """
    Gráfico de Tendencia kWp.
    Se agrega clip=False para que no corte los números de arriba.
    """
    base = alt.Chart(df).encode(x=alt.X('yearmonth(fecha_de_ganado):T', title='Mes'))
    
    # 1. Barras
    barras = base.mark_bar().encode(
        y=alt.Y('sum(kwp):Q', title='Potencia (kWp)'),
        color=alt.Color('tipo_proyecto:N', legend=alt.Legend(title="Tipo")),
        tooltip=[
            alt.Tooltip('yearmonth(fecha_de_ganado)', title='Fecha'),
            'tipo_proyecto', 
            alt.Tooltip('sum(kwp)', format='.2f', title='Potencia')
        ]
    )
    # 2. Textos
    # Agregamos clip=False aquí también
    textos = base.mark_text(dy=-10, color='black', size=11, clip=False).encode(
        y=alt.Y('sum(kwp):Q'),
        text=alt.Text('sum(kwp):Q', format='.0f')
    )
    
    return (barras + textos).interactive().properties(height=300)

def plot_res_heatmap(df):
    return alt.Chart(df).mark_rect().encode(
        x=alt.X('month(fecha_de_ganado):O', title='Mes'),
        y=alt.Y('year(fecha_de_ganado):O', title='Año'),
        color=alt.Color('count():Q', title='Ventas', scale=alt.Scale(scheme='orangered')),
        tooltip=['year(fecha_de_ganado)', 'month(fecha_de_ganado)', 'count()', 'sum(kwp)']
    ).properties(height=300)

def plot_res_scatter_tecnico(df):
    return alt.Chart(df).mark_circle(size=80).encode(
        x=alt.X('kwp:Q', title='Potencia Instalada (kWp)'),
        y=alt.Y('cantidad_de_paneles:Q', title='N° Paneles'),
        color=alt.Color('Status_Bateria:N', scale=alt.Scale(domain=['Con Batería', 'Solo Solar'], range=['#9b59b6', '#f1c40f'])),
        tooltip=['ceco', 'kwp', 'cantidad_de_paneles', 'kwh', 'tipo_proyecto']
    ).interactive().properties(height=350)

def plot_res_baterias_hist(df):
    return alt.Chart(df).mark_bar().encode(
        x=alt.X('kwh:Q', bin=alt.Bin(step=5), title='Capacidad Batería (kWh)'),
        y=alt.Y('count()', title='Frecuencia'),
        color=alt.value('#9b59b6'),
        tooltip=['count()']
    ).properties(height=350)

def plot_res_eficiencia_scatter(df):
    """
    Scatter plot: Potencia (kWp) vs Días Ejecución.
    Incluye línea de tendencia para ver la correlación.
    """
    base = alt.Chart(df).mark_circle(size=80, opacity=0.6).encode(
        x=alt.X('kwp:Q', title='Tamaño del Sistema (kWp)'),
        y=alt.Y('Dias_Ejecucion:Q', title='Días de Instalación (Inicio -> Fin)'),
        color=alt.Color('tipo_proyecto:N', legend=alt.Legend(title="Tipo")),
        tooltip=[
            alt.Tooltip('ceco', title='ID Proyecto'),
            alt.Tooltip('kwp', format='.1f'),
            alt.Tooltip('Dias_Ejecucion', title='Días Ejec.'),
            'tipo_proyecto'
        ]
    )
    
    # Línea de regresión (Tendencia)
    regression = base.transform_regression('kwp', 'Dias_Ejecucion').mark_line(color='red', strokeDash=[5,5])
    
    return (base + regression).interactive().properties(
        title="Eficiencia: ¿Los proyectos grandes demoran más?"
    )

def plot_heatmap_rutas(df):
    """Mapa de calor Origen vs Destino."""
    return alt.Chart(df).mark_rect().encode(
        x=alt.X('Almacén Destino:N', title='Bodega Destino'),
        y=alt.Y('Almacén Origen:N', title='Bodega Origen'),
        color=alt.Color('Valor Pendiente Total:Q', title='Monto ($)', scale=alt.Scale(scheme='orangered')),
        tooltip=['Almacén Origen', 'Almacén Destino', alt.Tooltip('Valor Pendiente Total', format='$,.0f')]
    ).properties(title="Mapa de Calor: Rutas Logísticas (Congestión $)", height=350)

def plot_antiguedad_saldos(df):
    """Gráfico de barras con la antigüedad de la deuda."""
    base = alt.Chart(df).encode(
        x=alt.X('Rango_Antiguedad:O', title='Antigüedad Solicitud', sort=['0-30 días', '31-60 días', '61-90 días', '>90 días'])
    )
    
    barras = base.mark_bar().encode(
        y=alt.Y('sum(Valor Pendiente Total):Q', title='Monto Pendiente ($)', axis=alt.Axis(format='$,.0s')),
        color=alt.Color('Rango_Antiguedad:O', legend=None, scale=alt.Scale(scheme='reds')),
        tooltip=[alt.Tooltip('Rango_Antiguedad'), alt.Tooltip('sum(Valor Pendiente Total)', format='$,.0f')]
    )
    
    textos = base.mark_text(dy=-10).encode(
        y=alt.Y('sum(Valor Pendiente Total):Q'),
        text=alt.Text('sum(Valor Pendiente Total):Q', format='$.2s')
    )
    
    return (barras + textos).properties(title="Antigüedad del Stock Solicitado", height=300)

def plot_res_tiempos(df, col_dias, color_bar, title_x):
    return alt.Chart(df).mark_bar().encode(
        x=alt.X(f'{col_dias}:Q', bin=alt.Bin(maxbins=20), title=title_x),
        y=alt.Y('count()', title='N° Proyectos'),
        color=alt.value(color_bar),
        tooltip=['count()']
    ).interactive()

def generate_simulation_plot(df_sim, metrics, llegadas_map, sku_name, simulation_days):
    """
    Genera un gráfico interactivo de Altair para la simulación.
    """
    # 1. Aseguramos que el índice se llame 'Fecha' antes de resetear
    df_sim.index.name = 'Fecha'
    df_plot = df_sim.reset_index()

    # Agregamos referencias al dataframe para graficar
    df_plot['ROP'] = metrics['reorder_point']
    df_plot['SafetyStock'] = metrics['safety_stock']
    
    # Transformamos a formato largo (melt) para Altair
    df_lines = df_plot.melt(
        id_vars=['Fecha'],
        value_vars=['NivelInventario', 'ROP', 'SafetyStock'],
        var_name='Leyenda', 
        value_name='Valor'
    )
    
    # Preparamos las llegadas
    df_llegadas = pd.DataFrame(list(llegadas_map.items()), columns=['Fecha', 'CantidadLlegada'])
    # Merge para obtener la altura (Y) correcta en la línea de inventario
    df_llegadas = pd.merge(df_llegadas, df_plot[['Fecha', 'NivelInventario']], on='Fecha', how='left')
    df_llegadas['Leyenda'] = 'Llegada de OC' 

    df_zero_line = pd.DataFrame({'y': [0]})

    # Definición de colores
    domain = ['NivelInventario', 'ROP', 'SafetyStock', 'Llegada de OC']
    range_colors = ['#1f77b4', '#ff7f0e', '#9467bd', '#2ca02c'] 

    # Capa 1: Línea de Inventario
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
    
    # Capa 2: Líneas de Referencia (ROP y SS)
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
    
    # Capa 3: Puntos de Llegada (OCs)
    arrival_points = alt.Chart(df_llegadas).mark_circle(size=100, opacity=0.9).encode(
        x=alt.X('Fecha:T'),
        y=alt.Y('NivelInventario:Q'),
        color=alt.Color('Leyenda:N', scale=alt.Scale(domain=domain, range=range_colors)),
        tooltip=[
            alt.Tooltip('Fecha:T', title='Llegada de OC', format="%Y-%m-%d"),
            alt.Tooltip('CantidadLlegada:Q', title='Cantidad Recibida', format=',.0f')
        ]
    )

    # Capa 4: Línea de Cero
    zero_line = alt.Chart(df_zero_line).mark_rule(
        color='red', strokeDash=[2, 2]
    ).encode(
        y='y',
        tooltip=alt.value("Stock Cero") 
    )

    # Combinar y Renderizar
    final_chart = (inventory_line + reference_lines + arrival_points + zero_line).properties(
        title=f'Proyección de Inventario para {sku_name} ({simulation_days} días)'
    ).interactive() 
    
    return final_chart