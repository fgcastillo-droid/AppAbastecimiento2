# --- ARCHIVO: src/analysis.py ---
# (NUEVO ARCHIVO para la lógica de negocio separada)
import pandas as pd
import streamlit as st
import numpy as np

def generar_pivot_sku_bodega(df, col_sku, col_nombre, col_bodega, col_valor):
    """Genera la matriz de SKU vs Bodega con totales."""
    try:
        df_pivot = df.pivot_table(
            index=[col_sku, col_nombre],
            columns=col_bodega,
            values=col_valor,
            aggfunc='sum',
            fill_value=0
        )
        # Totales y Ordenamiento
        df_pivot['TOTAL'] = df_pivot.sum(axis=1)
        df_pivot = df_pivot.sort_values('TOTAL', ascending=False)
        return df_pivot
    except Exception as e:
        st.error(f"Error calculando pivot SKU: {e}")
        return pd.DataFrame()

def generar_pivot_subfam_bodega(df, col_subfam, col_bodega, col_valor):
    """Genera la matriz de Subfamilia vs Bodega."""
    try:
        df_pivot = df.pivot_table(
            index=col_subfam,
            columns=col_bodega,
            values=col_valor,
            aggfunc='sum',
            fill_value=0
        )
        df_pivot['TOTAL'] = df_pivot.sum(axis=1)
        df_pivot = df_pivot.sort_values('TOTAL', ascending=False)
        return df_pivot
    except Exception as e:
        st.error(f"Error calculando pivot Subfamilia: {e}")
        return pd.DataFrame()

def calcular_rotacion_inventario(df_historia):
    """
    Calcula la Rotación y Días de Inventario (DOI) basado en la historia de VALOR.
    Este método es ahora consistente en usar VALOR en lugar de CANTIDAD.
    """
    # 1. Validar y preparar datos
    if df_historia.empty or 'ValorMovimiento' not in df_historia.columns or 'Familia' not in df_historia.columns or 'Mes' not in df_historia.columns:
        return pd.DataFrame()

    df = df_historia.sort_values(['Familia', 'Mes']).copy()
    
    # Derivar ValorSalida de ValorMovimiento (salidas son negativas)
    df['ValorSalida'] = df['ValorMovimiento'].apply(lambda x: abs(x) if x < 0 else 0)

    # 2. Calcular el Stock Final de cada mes (Acumulado de VALOR)
    df['StockCierre_Valor'] = df.groupby('Familia')['ValorMovimiento'].cumsum()
    
    # 3. Agrupar por Familia para obtener totales
    kpis = df.groupby('Familia').agg(
        SalidasTotales_Valor=('ValorSalida', 'sum'),
        StockPromedio_Valor=('StockCierre_Valor', 'mean')
    ).reset_index()
    
    # 4. Calcular Indicadores basados en VALOR
    # Rotación = Salidas / Stock Promedio
    kpis['Rotacion'] = kpis.apply(
        lambda x: x['SalidasTotales_Valor'] / x['StockPromedio_Valor'] if x['StockPromedio_Valor'] > 0 else 0, 
        axis=1
    )
    
    # Días de Inventario (DOI) = 365 / Rotación
    kpis['DiasInventario'] = kpis.apply(
        lambda x: 365 / x['Rotacion'] if x['Rotacion'] > 0 else 0, 
        axis=1
    )
    
    return kpis.sort_values('Rotacion', ascending=False)

def calcular_kpis_rotacion(df_historia, agrupar_por='CodigoArticulo', fecha_inicio=None, fecha_fin=None):
    """
    Calcula KPIs considerando un rango de fechas específico, 
    pero manteniendo la historia para el cálculo del stock inicial.
    """
    # 1. Copia y ordenamiento (Vital para cumsum)
    df = df_historia.sort_values([agrupar_por, 'Mes']).copy()
    
    # 2. CÁLCULO DE STOCK (Usando TODA la historia)
    df['StockCierre_Q'] = df.groupby(agrupar_por)['CantidadMovimiento'].cumsum()
    df['StockCierre_V'] = df.groupby(agrupar_por)['ValorMovimiento'].cumsum()
    
    # 3. FILTRO DE FECHAS (Aquí recortamos para el análisis)
    # Convertimos 'Mes' a fecha para poder comparar
    if fecha_inicio and fecha_fin:
        # Asumimos que 'Mes' viene en formato 'YYYY-MM'
        df['Fecha_DT'] = pd.to_datetime(df['Mes'] + '-01').dt.date
        df = df[(df['Fecha_DT'] >= fecha_inicio) & (df['Fecha_DT'] <= fecha_fin)]
    
    # 4. Agregación (Sobre el periodo recortado)
    kpis = df.groupby(agrupar_por).agg(
        NombreArticulo=('NombreArticulo', 'first'),
        Familia=('Familia', 'first'),
        SalidasTotales_Q=('CantidadSalida', 'sum'), # Salidas solo del periodo seleccionado
        StockPromedio_Q=('StockCierre_Q', 'mean'),  # Stock promedio del periodo
        StockPromedio_V=('StockCierre_V', 'mean')
    ).reset_index()
    
    # 5. Indicadores Finales
    kpis['Rotacion'] = kpis.apply(
        lambda x: x['SalidasTotales_Q'] / x['StockPromedio_Q'] if x['StockPromedio_Q'] > 1 else 0, 
        axis=1
    )
    
    # Ajuste dinámico de días según el rango seleccionado (o 360 por defecto)
    dias_periodo = 360
    if fecha_inicio and fecha_fin:
        dias_periodo = (fecha_fin - fecha_inicio).days
        if dias_periodo == 0: dias_periodo = 30 # Evitar error si selecciona el mismo día
        
    kpis['DiasInventario'] = kpis.apply(
        lambda x: dias_periodo / x['Rotacion'] if x['Rotacion'] > 0 else 0, 
        axis=1
    )
    
    kpis['TipoRotacion'] = kpis['Rotacion'].apply(
        lambda x: 'Lenta' if x < 1 else ('Media' if x < 6 else 'Alta')
    )
    
    return kpis.sort_values('StockPromedio_V', ascending=False)

def calcular_valor_total_inventario(df_stock, codigo_bodega=None):
    """
    Calcula el valor monetario total del inventario.
    Permite filtrar por una bodega específica si se solicita.
    """
    col_valor = 'ValorTotalInventario'
    
    # 1. Validaciones básicas
    if df_stock is None or df_stock.empty or col_valor not in df_stock.columns:
        return 0.0

    df_calc = df_stock.copy()

    # 2. Filtro Opcional de Bodega
    if codigo_bodega:
        if 'CodigoBodega' in df_calc.columns:
            # Forzamos conversión a string para evitar errores de tipo
            df_calc = df_calc[df_calc['CodigoBodega'].astype(str) == str(codigo_bodega)]
        else:
            return 0.0 # Si pides filtrar bodega pero no existe la columna

    # 3. Retorno de la suma
    return df_calc[col_valor].sum()

def preparar_distribucion_bodega(df_stock):
    """
    Agrupa el valor del inventario por Bodega.
    Retorna un DataFrame listo para graficar con columnas: ['NombreBodega', 'ValorTotalInventario']
    """
    if df_stock is None or df_stock.empty:
        return pd.DataFrame()
    
    # Agrupamos por nombre de bodega y sumamos el valor
    # reset_index() convierte el índice en columnas normales para Altair
    df_agrupado = df_stock.groupby('NombreBodega')['ValorTotalInventario'].sum().reset_index()
    
    # Ordenamos de mayor a menor para que el gráfico se vea ordenado
    df_agrupado = df_agrupado.sort_values('ValorTotalInventario', ascending=False)
    
    return df_agrupado

def preparar_distribucion_subfamilia(df_stock):
    """
    Agrupa el valor del inventario por SubFamilia.
    Retorna un DataFrame listo para graficar.
    """
    if df_stock is None or df_stock.empty:
        return pd.DataFrame()
    
    # Intentamos detectar la columna correcta
    # A veces viene como 'SubFamilia', 'Subfamilia' o si no existe, usamos 'Familia'
    possible_cols = ['SubFamilia', 'Subfamilia', 'Familia']
    col_cat = next((c for c in possible_cols if c in df_stock.columns), None)
    
    if not col_cat:
        return pd.DataFrame()

    # Agrupamos y ordenamos
    df_agrupado = df_stock.groupby(col_cat)['ValorTotalInventario'].sum().reset_index()
    df_agrupado = df_agrupado.sort_values('ValorTotalInventario', ascending=False)
    
    # Renombramos la columna detectada a 'Categoria' para estandarizar el gráfico
    df_agrupado = df_agrupado.rename(columns={col_cat: 'Categoria'})
    
    return df_agrupado

def obtener_bodegas_origen(df_consumo):
    """Devuelve la lista de bodegas de origen disponibles para el filtro."""
    col_origen = 'BodegaOrigen_Solicitada'
    if df_consumo is not None and not df_consumo.empty and col_origen in df_consumo.columns:
        return sorted(df_consumo[col_origen].dropna().astype(str).unique())
    return []

def calcular_consumo_periodo(df_consumo, fecha_inicio, fecha_fin, bodega_origen, familias=None):
    """
    Calcula el consumo TOTAL ($) en el periodo seleccionado (SIN ANUALIZAR).
    Retorna: (monto_total, dias_periodo, df_filtrado)
    """
    # 1. Validación inicial
    if df_consumo is None or df_consumo.empty:
        return 0.0, 0, pd.DataFrame()

    df = df_consumo.copy()
    
    # 2. Aseguramos formato de fecha
    if 'FechaSolicitud' not in df.columns:
        return 0.0, 0, pd.DataFrame()
    
    df['FechaSolicitud'] = pd.to_datetime(df['FechaSolicitud'], errors='coerce')
    
    # 3. Filtros
    ts_inicio = pd.to_datetime(fecha_inicio).normalize()
    ts_fin = pd.to_datetime(fecha_fin).normalize()

    mask = (df['FechaSolicitud'].dt.normalize() >= ts_inicio) & (df['FechaSolicitud'].dt.normalize() <= ts_fin)
    
    if 'BodegaOrigen_Solicitada' in df.columns and bodega_origen:
        mask &= (df['BodegaOrigen_Solicitada'].astype(str) == str(bodega_origen))
        
    if familias:
        possible_cols = ['SubFamilia', 'Subfamilia', 'Familia_Articulo', 'Familia']
        col_fam = next((c for c in possible_cols if c in df.columns), None)
        if col_fam:
            mask &= (df[col_fam].isin(familias))
    
    df_filtrado = df[mask].copy()
    
    # 4. Cálculo Simple (Suma Pura)
    consumo_total = df_filtrado['ValorTotalSolicitado'].sum() if not df_filtrado.empty else 0.0
    
    # Calculamos días reales del periodo (útil para el KPI de Cobertura/DOI)
    dias = (ts_fin - ts_inicio).days
    if dias < 1: dias = 1
    
    return consumo_total, dias, df_filtrado

def preparar_evolucion_consumo(df_filtrado):
    """Agrupa el consumo filtrado por mes para el gráfico."""
    if df_filtrado.empty: return pd.DataFrame()
    
    # Hacemos una copia explícita para evitar SettingWithCopyWarning al agregar la columna 'Mes'
    df_filtrado = df_filtrado.copy()

    # Creamos columna Mes (YYYY-MM)
    df_filtrado['Mes'] = df_filtrado['FechaSolicitud'].dt.to_period('M').astype(str)
    
    # Agrupamos
    df_evo = df_filtrado.groupby('Mes')['ValorTotalSolicitado'].sum().reset_index()
    return df_evo

def enriquecer_data_residencial(df):
    """
    Agrega columnas calculadas: Tiempos de ejecución, Flags de batería y Ratios.
    """
    df = df.copy()

    # A. Lógica de Baterías
    # Si kwh > 0, asumimos que tiene batería
    if 'kwh' in df.columns:
        df['Tiene_Bateria'] = df['kwh'] > 0
        df['Status_Bateria'] = df['Tiene_Bateria'].apply(lambda x: 'Con Batería' if x else 'Solo Solar')
    
    # B. Cálculo de Tiempos (Días)
    # Lead Time: Venta -> Inicio
    if 'fecha_de_inicio_de_instalacion_real' in df.columns and 'fecha_de_ganado' in df.columns:
        df['Dias_Venta_Inicio'] = (df['fecha_de_inicio_de_instalacion_real'] - df['fecha_de_ganado']).dt.days
        # Limpieza lógica: Si fecha inicio < fecha ganado (error), lo marcamos como nulo
        df.loc[df['Dias_Venta_Inicio'] < 0, 'Dias_Venta_Inicio'] = np.nan
    
    # Execution Time: Inicio -> Fin
    if 'fecha_de_termino_de_instalacion_real' in df.columns and 'fecha_de_inicio_de_instalacion_real' in df.columns:
        df['Dias_Ejecucion'] = (df['fecha_de_termino_de_instalacion_real'] - df['fecha_de_inicio_de_instalacion_real']).dt.days
        df.loc[df['Dias_Ejecucion'] < 0, 'Dias_Ejecucion'] = np.nan

    # C. Ratios Técnicos
    # Watts por Panel (para detectar anomalías o tecnologías)
    if 'kwp' in df.columns and 'cantidad_de_paneles' in df.columns:
        # Versión optimizada (vectorizada)
        df['Ratio_Wp_Panel'] = np.where(
            df['cantidad_de_paneles'] > 0,
            (df['kwp'] * 1000) / df['cantidad_de_paneles'],
            0
        )

    # D. Estado del Ciclo de Vida (NUEVO)
    cond_termino = df['fecha_de_termino_de_instalacion_real'].notna() if 'fecha_de_termino_de_instalacion_real' in df.columns else pd.Series(False, index=df.index)
    cond_inicio = df['fecha_de_inicio_de_instalacion_real'].notna() if 'fecha_de_inicio_de_instalacion_real' in df.columns else pd.Series(False, index=df.index)
    cond_ganado = df['fecha_de_ganado'].notna() if 'fecha_de_ganado' in df.columns else pd.Series(False, index=df.index)
    
    conditions = [cond_termino, cond_inicio, cond_ganado]
    choices = ['3. Finalizado', '2. En Ejecución', '1. Vendido (Sin Inicio)']
    df['Estado_Etapa'] = np.select(conditions, choices, default='0. Desconocido')

    return df

def filtrar_residencial(df, anos_sel, meses_sel, tipos_sel, status_bateria):
    """
    Aplica los filtros de la barra lateral, incluyendo Meses.
    meses_sel: Lista de números enteros (1=Enero, 12=Diciembre).
    """
    if df.empty: return df
    
    # Filtro base (Años, Meses, Tipos)
    mask = (
            (df['fecha_de_ganado'].dt.year.isin(anos_sel)) & 
            (df['fecha_de_ganado'].dt.month.isin(meses_sel)) & # <--- NUEVO FILTRO
            (df['tipo_proyecto'].isin(tipos_sel))
    )

    # Filtro de Batería
    if status_bateria == "Con Batería":
        mask &= (df['Tiene_Bateria'] == True)
    elif status_bateria == "Solo Solar":
        mask &= (df['Tiene_Bateria'] == False)
        
    return df[mask].copy()


def filtrar_datos_inventario(df_movimientos, df_stock, dias_analisis, bodegas_validas):
    """Filtra movimientos y stock según los días y bodegas indicadas."""
    df_stock_clean = df_stock[df_stock['CodigoBodega'].isin(bodegas_validas)].copy()

    df_movs_clean = df_movimientos.copy()
    if 'fecha' in df_movs_clean.columns:
        df_movs_clean['fecha'] = pd.to_datetime(df_movs_clean['fecha'])
    
    hoy = pd.Timestamp.now().normalize()
    fecha_corte = hoy - pd.Timedelta(days=dias_analisis)

    # Aplicamos condiciones
    cond_salidas = df_movs_clean['ValorMovimiento'] < 0
    cond_fecha = df_movs_clean['fecha'] > fecha_corte
    cond_bodegas = df_movs_clean['CodigoBodega'].isin(bodegas_validas)

    df_movs_clean = df_movs_clean[cond_salidas & cond_fecha & cond_bodegas]

    return df_movs_clean, df_stock_clean

def calcular_kpis_rotacion(df_movs_clean: pd.DataFrame, df_stock_clean: pd.DataFrame, dias_analisis: int) -> pd.DataFrame:
    """Agrupa por artículo y calcula Rotación y DOI."""
    col_salidas = f'Salidas_{dias_analisis}D'
    col_rotacion = f'Rotacion_{dias_analisis}D'

    # --- 1. Agrupaciones por SKU (Código de Artículo) para precisión ---
    salidas_sku = df_movs_clean.groupby("CodigoArticulo")["ValorMovimiento"].sum().abs().rename(col_salidas)
    stock_sku = df_stock_clean.groupby("CodigoArticulo")["ValorTotalInventario"].sum().rename("Valor_Inventario")
    
    # (NUEVO) Fecha de la última salida para identificar stock muerto
    last_sale_date = df_movs_clean.groupby('CodigoArticulo')['fecha'].max().rename('Ultima_Salida')

    # --- 2. Merge de Datos ---
    # Unimos stock y salidas por CodigoArticulo
    df_kpis = pd.merge(stock_sku, salidas_sku, on="CodigoArticulo", how='outer').fillna(0)
    # Unimos la fecha de última salida
    df_kpis = pd.merge(df_kpis, last_sale_date, on="CodigoArticulo", how='left') # how='left' para mantener items con stock pero sin venta

    # --- 3. Cálculos de KPIs ---
    df_kpis[col_rotacion] = np.where(
        df_kpis['Valor_Inventario'] > 0, 
        df_kpis[col_salidas] / df_kpis['Valor_Inventario'], 
        0 
    )
    df_kpis['Rotacion_Anualizada'] = df_kpis[col_rotacion] * (365 / dias_analisis)
    df_kpis['DOI'] = np.where(
        df_kpis[col_salidas] > 0, 
        (df_kpis['Valor_Inventario'] / df_kpis[col_salidas]) * dias_analisis, 
        np.inf # Usamos infinito para lo que no tiene salida
    )

    # --- 4. Enriquecimiento con Atributos ---
    # Creamos un mapa único de atributos desde el stock para evitar duplicados
    mapa_atributos = df_stock_clean.drop_duplicates('CodigoArticulo').set_index('CodigoArticulo')[['NombreArticulo', 'SubFamilia', 'Familia']]
    df_kpis = df_kpis.merge(mapa_atributos, on="CodigoArticulo", how='left')
    
    # Rellenar nombres para SKUs que tuvieron salida pero ya no tienen stock
    df_kpis['NombreArticulo'] = df_kpis['NombreArticulo'].fillna('Nombre no encontrado')
    df_kpis['SubFamilia'] = df_kpis['SubFamilia'].fillna('Sin Subfamilia')
    df_kpis['Familia'] = df_kpis['Familia'].fillna('Sin Familia')

    # --- 5. Limpieza y Ordenamiento ---
    df_kpis = df_kpis.sort_values(by='Valor_Inventario', ascending=False).reset_index() # reset_index() convierte CodigoArticulo de índice a columna
    df_kpis['DOI'] = df_kpis['DOI'].round(1)
    df_kpis[col_rotacion] = df_kpis[col_rotacion].round(2)
    df_kpis['Rotacion_Anualizada'] = df_kpis['Rotacion_Anualizada'].round(2)

    # Reordenar columnas para mejor legibilidad
    cols_ordenadas = ['CodigoArticulo', 'NombreArticulo', 'SubFamilia', 'Familia', 'Valor_Inventario', col_salidas, 'DOI', col_rotacion, 'Rotacion_Anualizada', 'Ultima_Salida']
    df_kpis = df_kpis[[c for c in cols_ordenadas if c in df_kpis.columns]]

    return df_kpis

def generar_reporte_inventario(df_movimientos, df_stock, dias=60, bodegas=None):
    """Orquesta la limpieza y cálculo."""
    if bodegas is None:
        bodegas = ["BF0001", "BF0004", "BF0008", "BF0009"]

    df_movs_clean, df_stock_clean = filtrar_datos_inventario(df_movimientos, df_stock, dias, bodegas)
    df_resultado = calcular_kpis_rotacion(df_movs_clean, df_stock_clean, dias)
    
    return df_resultado

def analizar_antiguedad_stock(df, col_fecha='Fecha Contab.'):
    """
    Calcula la antigüedad de las solicitudes y las agrupa en rangos (Aging).
    """
    if df.empty or col_fecha not in df.columns:
        return df
    
    df = df.copy()
    hoy = pd.Timestamp.now().normalize()
    
    # Asegurar datetime
    df[col_fecha] = pd.to_datetime(df[col_fecha], errors='coerce')
    
    # Calcular días
    df['Dias_Pendiente'] = (hoy - df[col_fecha]).dt.days
    df['Dias_Pendiente'] = df['Dias_Pendiente'].fillna(0).astype(int)
    
    # Categorizar en Buckets
    bins = [0, 30, 60, 90, 9999]
    labels = ['0-30 días', '31-60 días', '61-90 días', '>90 días']
    df['Rango_Antiguedad'] = pd.cut(df['Dias_Pendiente'], bins=bins, labels=labels, right=False)
    
    return df

def analizar_rutas_logisticas(df):
    """Agrupa por Origen y Destino para mapa de calor."""
    if df.empty: return pd.DataFrame()
    return df.groupby(['Almacén Origen', 'Almacén Destino'])['Valor Pendiente Total'].sum().reset_index()

def calcular_pareto_pendientes(df):
    """Calcula la clasificación ABC de los artículos pendientes."""
    if df.empty: return pd.DataFrame()
    
    df_agg = df.groupby(['Código Artículo', 'Descripción'])['Valor Pendiente Total'].sum().reset_index()
    df_agg = df_agg.sort_values('Valor Pendiente Total', ascending=False)
    
    df_agg['Acumulado'] = df_agg['Valor Pendiente Total'].cumsum()
    df_agg['% Acumulado'] = df_agg['Acumulado'] / df_agg['Valor Pendiente Total'].sum()
    
    # Clasificación A: hasta 80%, B: 80-95%, C: resto
    df_agg['Clasificación'] = df_agg['% Acumulado'].apply(lambda x: 'A' if x <= 0.8 else ('B' if x <= 0.95 else 'C'))
    return df_agg
def calcular_kardex_diario(df_movimientos: pd.DataFrame, df_stock_hoy: pd.DataFrame, col_agrupacion: str, start_date, end_date) -> pd.DataFrame:
    """
    Calcula la evolución diaria del inventario realizando un rollback exacto.
    """
    # 1. Agrupar el stock físico de HOY
    if not df_stock_hoy.empty:
        stock_hoy = df_stock_hoy.groupby(col_agrupacion)[['ValorTotalInventario', 'StockActual']].sum().reset_index()
    else:
        stock_hoy = pd.DataFrame(columns=[col_agrupacion, 'ValorTotalInventario', 'StockActual'])

    # 2. Rollback (Viaje en el tiempo)
    movs_rollback = df_movimientos[df_movimientos['fecha'] >= start_date].groupby(col_agrupacion)[['ValorMovimiento', 'CantidadMovimiento']].sum().reset_index()

    # 3. Saldo Inicial
    df_saldo_ini = pd.merge(stock_hoy, movs_rollback, on=col_agrupacion, how='outer').fillna(0)
    df_saldo_ini['Saldo_Valor'] = df_saldo_ini['ValorTotalInventario'] - df_saldo_ini['ValorMovimiento']
    df_saldo_ini['Saldo_Cant'] = df_saldo_ini['StockActual'] - df_saldo_ini['CantidadMovimiento']

    # 4. Construir "Día Cero"
    df_day0 = df_saldo_ini[[col_agrupacion, 'Saldo_Valor', 'Saldo_Cant']].copy()
    df_day0['fecha'] = start_date
    df_day0['ValorMovimiento'] = df_day0['Saldo_Valor']
    df_day0['CantidadMovimiento'] = df_day0['Saldo_Cant']
    df_day0['Es_Saldo_Inicial'] = True

    # 5. Movimientos reales dentro del rango
    df_movs_rango = df_movimientos[(df_movimientos['fecha'] >= start_date) & (df_movimientos['fecha'] <= end_date)].copy()
    df_movs_rango = df_movs_rango.groupby(['fecha', col_agrupacion])[['ValorMovimiento', 'CantidadMovimiento']].sum().reset_index()
    df_movs_rango['Es_Saldo_Inicial'] = False

    # 6. Unir e iniciar CumSum
    df_grouped = pd.concat([df_day0, df_movs_rango], ignore_index=True)
    df_grouped = df_grouped.sort_values(['fecha', 'Es_Saldo_Inicial'], ascending=[True, False])

    df_grouped['StockValorizado'] = df_grouped.groupby(col_agrupacion)['ValorMovimiento'].cumsum()
    df_grouped['StockCantidad'] = df_grouped.groupby(col_agrupacion)['CantidadMovimiento'].cumsum()
    
    return df_grouped

def calculate_order_recommendation(metrics, llegadas_map, df_sim, lead_time_days):
    """
    Calcula la lógica de recomendación de pedido (cuánto pedir) basado
    en la proyección futura del inventario.
    
    Lógica:
    1. Encuentra el stock proyectado en T + lead_time_days.
    2. Compara ese stock con el ROP.
    3. Si el stock proyectado < ROP, recomienda pedir (ROP - stock_proyectado).
    
    Retorna un diccionario con los cálculos y la decisión.
    """
    
    # --- 1. Obtener Métricas Clave ---
    ss = metrics['safety_stock']
    
    # --- 2. Calcular Proyección Futura ---
    
    # Aseguramos que el índice sea Datetime
    if not isinstance(df_sim.index, pd.DatetimeIndex):
         df_sim.index = pd.to_datetime(df_sim.index)
         
    today = df_sim.index.min()
    forecast_date = today + pd.DateOffset(days=lead_time_days)
    
    # --- 3. Validar si la simulación cubre la fecha de pronóstico ---
    if forecast_date > df_sim.index.max():
        msg = f"La simulación ({len(df_sim)} días) es más corta que el Lead Time ({lead_time_days} días). No se puede proyectar la recomendación."
        return { "status": "error", "error_message": msg }

    # --- 4. Obtener Stock Proyectado y Generar Recomendación ---
    
    # Usamos .asof para encontrar el valor más cercano si la fecha exacta no existe
    projected_stock = df_sim.asof(forecast_date)['NivelInventario']
    
    is_below_rop = projected_stock < ss
    suggested_order_qty = 0.0
    status = "info"

    if is_below_rop:
        suggested_order_qty = ss - projected_stock
        suggested_order_qty = max(0.0, suggested_order_qty) 
        
        if suggested_order_qty > 0:
            status = "success"
    else:
        status = "info"
        
    # --- 5. Retornar los resultados ---
    return {
        "projected_stock_at_lt": projected_stock,
        "ss": ss,
        "lead_time_days": lead_time_days,
        "forecast_date": forecast_date,
        "suggested_order_qty": suggested_order_qty,
        "is_below_rop": is_below_rop,
        "status": status,
        "error_message": None
    }