import pandas as pd
import numpy as np
import streamlit as st
from src import config 
from typing import Tuple, Optional, Dict, Any


def _calcular_demanda_historica(df_consumo: pd.DataFrame) -> Tuple:
    """
        Calcula el promedio diario y la volatilidad (desviación estándar) diaria 
        de la demanda basándose en el historial de consumo, excluyendo el mes en curso.

        Args:
            df_consumo (pd.DataFrame): DataFrame que debe contener al menos las columnas:
                - 'FechaSolicitud': (datetime) Fecha del movimiento.
                - 'CantidadSolicitada': (numeric) Cantidad consumida.

        Returns:
            Tuple[float, float]: Una tupla conteniendo:
                - promedio_diario (float): Demanda promedio esperada por día.
                - std_diaria (float): Desviación estándar diaria (volatilidad).
                Retorna (0.0, 0.0) si no hay datos históricos suficientes.
        """

    # 1. Validación inicial
    if df_consumo.empty:
        return 0.0, 0.0, 0.0, 0.0
    # -------------------------------------------------------------------------
    # PASO 1: Agrupación Mensual
    # -------------------------------------------------------------------------
    # Tipo: pd.Series
    # Índice: DatetimeIndex (frecuencia mensual 'MS') | Valores: Float (Suma)
    consumo_mensual: pd.Series = (
        df_consumo
        .set_index('FechaSolicitud')
        .resample('MS')['CantidadSolicitada']
        .sum()
    )
    # PASO 2: Filtrado de Fechas
    # Tipo: pd.Timestamp (Fecha actual normalizada al primer día del mes)
    mes_actual: pd.Timestamp = pd.Timestamp.now().floor('D').replace(day=1)
    
    # Tipo: DatetimeIndex (Rango de meses completo para rellenar con 0 los meses sin consumo)
    if df_consumo['FechaSolicitud'].empty:
        return 0.0, 0.0, 0.0, 0.0
    min_fecha = df_consumo['FechaSolicitud'].min().replace(day=1)
    rango_completo = pd.date_range(start=min_fecha, end=mes_actual - pd.DateOffset(days=1), freq='MS')
    
    # Reindexar asegura que los meses sin movimiento sean explícitamente 0
    historia: pd.Series = consumo_mensual.reindex(rango_completo, fill_value=0)
    # Validación secundaria: Si no hay meses cerrados anteriores, retornamos 0
    if len(historia) == 0:
        return 0.0, 0.0, 0.0, 0.0
    # -------------------------------------------------------------------------
    # PASO 3: Cálculos Estadísticos Mensuales
    # -------------------------------------------------------------------------
    # Tipo: float (Promedio simple de los meses históricos)
    promedio_mensual: float = historia.mean()
    # Tipo: float (Desviación estándar de los meses). Si hay 1 solo dato, es 0.0.
    std_mensual: float = historia.std() if len(historia) > 1 else 0.0
    # -------------------------------------------------------------------------
    # PASO 4: Conversión a Diario (Escalamiento)
    # -------------------------------------------------------------------------
    # Nota: config.AVERAGE_DAYS_PER_MONTH suele ser ~30.4 (int o float)
    # Tipo: float. Se divide linealmente.
    promedio_diario: float = promedio_mensual / config.AVERAGE_DAYS_PER_MONTH
    # Tipo: float. 
    # La desviación estándar NO se divide linealmente, se escala con la raíz cuadrada del tiempo.
    # Regla: Volatilidad T1 = Volatilidad T2 / sqrt(Tiempo)
    std_diaria: float = std_mensual / np.sqrt(config.AVERAGE_DAYS_PER_MONTH)
    return promedio_diario, std_diaria, promedio_mensual, std_mensual


def _simular_futuro(stock_inicial, demanda_diaria, mapa_llegadas, dias_a_simular):
    """Simula día a día si habrá un quiebre de stock."""
    stock = stock_inicial
    fecha_quiebre = None
    quiebre_detectado = False
    today = pd.Timestamp.now().floor('D')

    if demanda_diaria <= 0:
        return False, None

    for dia in range(1, int(dias_a_simular) + 1):
        fecha_sim = today + pd.DateOffset(days=dia)
        
        # 1. Restamos consumo
        stock -= demanda_diaria
        
        # 2. Sumamos llegadas si las hay
        if fecha_sim in mapa_llegadas.index:
            stock += mapa_llegadas[fecha_sim]
        
        # 3. Verificamos quiebre
        if stock < 0:
            quiebre_detectado = True
            fecha_quiebre = fecha_sim
            break # Paramos la simulación al primer problema
            
    return quiebre_detectado, fecha_quiebre

def calcular_kpis_sku(
    sku: str, 
    datos: Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame], 
    parametros: Tuple[float, float]
) -> Optional[Dict[str, Any]]:
    """
    Calcula los indicadores clave de inventario (KPIs) para un SKU específico.
    
    Procesa el stock actual, la historia de consumo y las órdenes de compra para
    determinar puntos de reorden, cobertura y niveles de seguridad.

    Args:
        sku (str): Código único del artículo (SKU).
        datos (Tuple): Tupla con 3 DataFrames:
            1. df_stk: Datos de inventario (Stock).
            2. df_cons: Historial de consumo/ventas.
            3. df_oc: Órdenes de compra (tránsito).
        parametros (Tuple): Tupla con 2 valores numéricos:
            1. lt_dias (float): Lead Time o tiempo de reposición en días.
            2. z_score (float): Factor de servicio (ej: 1.64 para 95%).

    Returns:
        Optional[Dict[str, Any]]: Diccionario con los KPIs calculados.
                                  Retorna None si ocurre un error interno.
    """
    try:
        # ---------------------------------------------------------------------
        # 1. Desempaquetado de entradas
        # ---------------------------------------------------------------------
        # Tipos: DataFrames de pandas
        df_stk, df_cons, df_oc = datos
        # Tipos: Flotantes (números decimales)
        lt_dias, z_score = parametros
        
        # ---------------------------------------------------------------------
        # 2. Cálculo de Stock Físico Disponible
        # ---------------------------------------------------------------------
        # Tipo: float. Suma total del stock disponible en todas las bodegas filtradas.
        stock_actual: float = df_stk['DisponibleParaPrometer'].sum()
        
        # ---------------------------------------------------------------------
        # 3. Estadísticas de Demanda
        # ---------------------------------------------------------------------
        # Nota: Asume que _calcular_demanda_historica retorna 4 valores floats.
        # demanda_dia: Promedio diario.
        # std_dia: Volatilidad diaria.
        # promedio_mensual: Promedio mensual puro.
        # std_mensual: Desviación estándar mensual pura.
        demanda_dia, std_dia, promedio_mensual, std_mensual = _calcular_demanda_historica(df_cons)
        # ---------------------------------------------------------------------
        # 4. Parámetros de Reposición (ROP y SS)
        # ---------------------------------------------------------------------
        # Tipo: float. Demanda esperada durante el tiempo de espera.
        demanda_en_lt: float = demanda_dia * lt_dias
        # Tipo: float. Stock de Seguridad = Z * Desviación * Raíz(Tiempo)
        stock_seguridad: float = z_score * std_dia * np.sqrt(lt_dias)
        # Tipo: float. Punto de Reorden = Demanda en LT + Stock Seguridad.
        rop: float = demanda_en_lt + stock_seguridad
        # ---------------------------------------------------------------------
        # 5. Cobertura de Inventario (DOS - Days of Supply)
        # ---------------------------------------------------------------------
        # Tipo: float. Cuántos días dura mi stock actual. Si demanda es 0, asignamos 999.
        dos: float = (stock_actual / demanda_dia) if demanda_dia > 0 else 999.0
        # ---------------------------------------------------------------------
        # 6. Procesamiento de Llegadas Futuras (OCs)
        # ---------------------------------------------------------------------
        # Tipo: Timestamp. Fecha de hoy a las 00:00:00.
        today = pd.Timestamp.now().floor('D')
        # Tipo: DataFrame. Filtramos OCs con cantidad > 0 y fecha futura o presente.
        llegadas_validas = df_oc[
            (df_oc['Cantidad'] > 0) & 
            (df_oc['Fecha de entrega de la línea'] >= today)
        ]

        # Si hay llegadas, tomamos la fecha mínima. Si no, queda como None (vacío).
        proxima_llegada = None
        if not llegadas_validas.empty:
            proxima_llegada = llegadas_validas['Fecha de entrega de la línea'].min()

        # Tipo: Series. Índice=Fecha, Valor=Suma de Cantidad. Agrupamos llegadas por día.
        mapa_llegadas = llegadas_validas.groupby('Fecha de entrega de la línea')['Cantidad'].sum()
        # ---------------------------------------------------------------------
        # 7. Proyección de Stock (Foto al final del Lead Time)
        # ---------------------------------------------------------------------
        # Tipo: Timestamp. Fecha objetivo (Hoy + Lead Time).
        fecha_fin_lt = today + pd.DateOffset(days=lt_dias)
        # Tipo: float. Suma de todas las OCs que llegan antes de que termine el Lead Time.
        total_llegadas_en_lt: float = mapa_llegadas[mapa_llegadas.index <= fecha_fin_lt].sum()
        # Tipo: float. Saldo proyectado teórico.
        stock_proyectado: float = stock_actual + total_llegadas_en_lt - demanda_en_lt
        # ---------------------------------------------------------------------
        # 10. Retorno de Resultados
        # ---------------------------------------------------------------------
        return {
            "SKU": sku,                         # str
            "Stock Actual": stock_actual,       # float
            "Demanda Diaria": demanda_dia,      # float
            "DOS": dos,                         # float
            "SS": stock_seguridad,              # float
            "ROP": rop,                         # float
            "Demanda mensual": promedio_mensual,# float
            "Desv. mensual": std_mensual,        # float
            "Próxima Llegada": proxima_llegada  # datetime
        }
    
    except Exception as e:
        print(f"Error en SKU {sku}: {e}")
        return None

def _obtener_consumo_mensual_pivot(df_consumo, skus_validos):
    """[NUEVO] Genera columnas con el consumo de los últimos 6 meses por SKU."""
    if df_consumo.empty:
        return pd.DataFrame()

    # 1. Definir ventana de tiempo (últimos 6 meses completos + mes actual si quieres)
    hoy = pd.Timestamp.now().floor('D')
    inicio_ventana = (hoy - pd.DateOffset(months=6)).replace(day=1)
    
    # 2. Filtrar
    df = df_consumo[
        (df_consumo['FechaSolicitud'] >= inicio_ventana) & 
        (df_consumo['CodigoArticulo'].isin(skus_validos))
    ].copy()

    if df.empty:
        return pd.DataFrame()

    # 3. Crear columna de Mes (YYYY-MM) para que se ordenen cronológicamente
    df['Mes_Str'] = df['FechaSolicitud'].dt.strftime('%Y-%m')

    # 4. Pivotear (Filas=SKU, Columnas=Meses, Valor=Suma Cantidad)
    pivot_consumo = df.pivot_table(
        index='CodigoArticulo', 
        columns='Mes_Str', 
        values='CantidadSolicitada', 
        aggfunc='sum', 
        fill_value=0
    )
    
    # 5. Agregar prefijo para que se vea bien en la tabla (ej: "Cons. 2024-01")
    pivot_consumo.columns = [f"C. {col}" for col in pivot_consumo.columns]
    
    return pivot_consumo





@st.cache_data(ttl=3600)
def ejecutar_analisis_masivo(df_stock, df_consumo, df_oc, familia, bodegas, params):
    """Función principal que orquesta el análisis."""
    
    # --- 1. Filtrado Inicial ---
    if familia != "Todas":
        df_stock = df_stock[df_stock['SubFamilia'] == familia]

    # Filtramos por SKUs válidos de la familia seleccionada
    skus_validos = df_stock['CodigoArticulo'].unique()
    
     # Capturamos nombres ANTES de filtrar por bodega para no perderlos si no tienen stock
    mapa_nombres = df_stock.drop_duplicates('CodigoArticulo').set_index('CodigoArticulo')['NombreArticulo']
    
    # Filtro de seguridad para los otros DFs
    df_consumo = df_consumo[df_consumo['CodigoArticulo'].isin(skus_validos)].copy()
    df_oc = df_oc[df_oc['Número de artículo'].isin(skus_validos)].copy()

    # --- CAMBIO AQUÍ: Filtro de Bodegas ---
    lista_bodegas_stk, lista_bodegas_cons = bodegas # Desempaquetamos listas de ambas selecciones
    
    # 1. Filtro Stock (Ahora soporta múltiples bodegas o lista unitaria)
    # Usamos .isin() porque ui_helpers retorna una lista (multiselect)
    df_stock = df_stock[df_stock['CodigoBodega'].isin(lista_bodegas_stk)]
    
    # 2. Filtro Consumo (AHORA MÚLTIPLE)
    # Usamos .isin() para filtrar por cualquiera de las bodegas seleccionadas
    df_consumo = df_consumo[df_consumo['BodegaDestino_Requerida'].isin(lista_bodegas_cons)]

    # -------------------------------------

    # --- 2. Preparación ---
    if df_stock.empty:
        return pd.DataFrame()
        
    lista_skus = df_stock['CodigoArticulo'].unique()
    lt_dias, z_score = params
    today = pd.Timestamp.now().floor('D')
    mes_actual = today.replace(day=1)
    
    # --- 3. VECTORIZACIÓN DE CÁLCULOS (Reemplazo del Bucle Lento) ---
    # a) Enriquecer datos con VALOR
    if 'CostoUnitario' in df_stock.columns:
        df_stock['ValorActual'] = df_stock['DisponibleParaPrometer'] * df_stock['CostoUnitario']
    else:
        df_stock['ValorActual'] = 0.0

    # b) Stock Actual por SKU (en Unidades y Valor)
    stock_actual_units = df_stock.groupby('CodigoArticulo')['DisponibleParaPrometer'].sum()
    stock_actual_valor = df_stock.groupby('CodigoArticulo')['ValorActual'].sum()

    # c) Estadísticas de Consumo Histórico (basado en UNIDADES)
    historia_cons = df_consumo[df_consumo['FechaSolicitud'] < mes_actual]
    if not historia_cons.empty:
        # Generar pivot table para asegurar divisor equitativo (meses 0 se contemplan)
        historia_cons = historia_cons.copy()
        historia_cons['Mes_Period'] = historia_cons['FechaSolicitud'].dt.to_period('M')
        pivot_historia = historia_cons.pivot_table(
            index='CodigoArticulo',
            columns='Mes_Period',
            values='CantidadSolicitada',
            aggfunc='sum',
            fill_value=0
        )
        
        # Forzar un rango completo de meses para rellenar vacíos absolutos
        min_mes = historia_cons['Mes_Period'].min()
        # Forzar que el rango llegue siempre hasta el mes pasado, haya o no haya consumo
        max_mes = (mes_actual - pd.DateOffset(months=1)).to_period('M')
        rango_meses = pd.period_range(start=min_mes, end=max_mes, freq='M')
        pivot_historia = pivot_historia.reindex(columns=rango_meses, fill_value=0)
        
        stats_sku = pd.DataFrame({
            'promedio_mensual': pivot_historia.mean(axis=1),
            'std_mensual': pivot_historia.std(axis=1)
        }).fillna(0.0)
    else:
        stats_sku = pd.DataFrame(columns=['promedio_mensual', 'std_mensual'])
        
    # d) OCs y Llegadas Programadas (esto sigue siendo en unidades)
    llegadas_validas = df_oc[(df_oc['Cantidad'] > 0) & (df_oc['Fecha de entrega de la línea'] >= today)]
    if not llegadas_validas.empty:
        proxima_llegada = llegadas_validas.groupby('Número de artículo')['Fecha de entrega de la línea'].min()
    else:
        proxima_llegada = pd.Series(dtype='datetime64[ns]')
        
    # e) Ensamblaje de Resultados
    df_res = pd.DataFrame(index=skus_validos)
    df_res.index.name = 'CodigoArticulo'
    df_res['Stock Actual'] = stock_actual_units # Para visualización
    df_res['Valor Stock Actual'] = stock_actual_valor # Para cálculos
    df_res = df_res.join(stats_sku)
    
    # Rellenar nulos
    df_res['Stock Actual'] = df_res['Stock Actual'].fillna(0)
    df_res['Valor Stock Actual'] = df_res['Valor Stock Actual'].fillna(0)
    df_res['promedio_mensual'] = df_res['promedio_mensual'].fillna(0)
    df_res['std_mensual'] = df_res['std_mensual'].fillna(0)
    
    # f) Cálculos de Radar (basados en UNIDADES)
    df_res['Demanda Diaria'] = df_res['promedio_mensual'] / config.AVERAGE_DAYS_PER_MONTH
    df_res['std_diaria'] = df_res['std_mensual'] / np.sqrt(config.AVERAGE_DAYS_PER_MONTH)
    
    # DOS, SS y ROP se calculan en unidades
    df_res['DOS'] = np.where(df_res['Demanda Diaria'] > 0, df_res['Stock Actual'] / df_res['Demanda Diaria'], 999.0)
    df_res['SS'] = z_score * df_res['std_diaria'] * np.sqrt(lt_dias)
    df_res['ROP'] = (df_res['Demanda Diaria'] * lt_dias) + df_res['SS']
    df_res = df_res.join(proxima_llegada.rename('Próxima Llegada'))
    
    # g) Nombres e Historial de Consumo (en unidades para visualización)
    df_res['Nombre'] = df_res.index.map(mapa_nombres).fillna('Sin Nombre')
    
    df_pivot = _obtener_consumo_mensual_pivot(df_consumo, skus_validos)
    if not df_pivot.empty:
        df_res = df_res.join(df_pivot)
        
    # h) Renombrar columnas para la salida final
    df_res = df_res.reset_index().rename(columns={
        'CodigoArticulo': 'SKU',
        'promedio_mensual': 'Demanda mensual',
        'std_mensual': 'Desv. mensual'
    })
    
    return df_res