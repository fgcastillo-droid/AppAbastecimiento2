# --- ARCHIVO: src/simulator.py ---
# (Modificado para importar 'config' desde 'src' y aceptar listas de bodegas)
# (v2 - Corregido el cálculo del promedio mensual para incluir meses con consumo 0)

import pandas as pd
import numpy as np
import config # Importa config.py desde la misma carpeta 'src'

def run_inventory_simulation(
    sku_to_simulate: str,
    warehouse_code: list[str], # <-- (MODIFICADO) Acepta una lista
    consumption_warehouse: list[str], # <-- (MODIFICADO) Acepta una lista
    df_stock_raw: pd.DataFrame,
    df_consumo_raw: pd.DataFrame,
    df_oc_raw: pd.DataFrame,
    simulation_days: int,
    lead_time_days: int, 
    service_level_z: float,
    use_randomness: bool = False # <--- NUEVO PARÁMETRO
):
    """
    Ejecuta la lógica de simulación de inventario día a día.
    (El contenido de esta función no cambia)
    """
    
    # Define la fecha de 'hoy' (inicio de la simulación)
    today = pd.Timestamp.now().floor('D')
    
    # --- B. CÁLCULO DE STOCK INICIAL (I_0) ---
    # (MODIFICADO) Filtra el DataFrame de stock para el SKU y MÚLTIPLES bodegas
    df_stock_filtered = df_stock_raw[
        (df_stock_raw['CodigoArticulo'] == sku_to_simulate) &
        (df_stock_raw['CodigoBodega'].isin(warehouse_code)) # <-- (MODIFICADO) Usa .isin()
    ].copy()
    
    # Asegura que el stock sea numérico y calcula el total
    initial_stock = df_stock_filtered['DisponibleParaPrometer'].sum()

    # --- C. CÁLCULO DE CONSUMO ---
    # (MODIFICADO) Filtra el DataFrame de consumo para el SKU y MÚLTIPLES bodegas
    df_consumo_filtered = df_consumo_raw[
        (df_consumo_raw['CodigoArticulo'] == sku_to_simulate) &
        (df_consumo_raw['BodegaDestino_Requerida'].isin(consumption_warehouse)) # <-- (MODIFICADO) Usa .isin()
    ].copy()
    
    # Inicializa métricas de demanda (buena práctica para asegurar que existan)
    daily_demand_mean = 0.0
    daily_demand_std = 0.0
    monthly_demand_mean = 0.0
    monthly_demand_std = 0.0
    demand_M_0, demand_M_1, demand_M_2, demand_M_3, demand_M_4 = 0.0, 0.0, 0.0, 0.0, 0.0

    # Define las fechas de inicio para los meses a analizar (M, M-1, M-2, M-3)
    start_of_current_month = today.replace(day=1)                               # Type: pd.Timestamp     | Ex: 2025-11-01 00:00:00
    start_of_M_minus_1 = start_of_current_month - pd.DateOffset(months=1)       # Type: pd.Timestamp     | Ex: 2025-10-01 00:00:00
    start_of_M_minus_2 = start_of_current_month - pd.DateOffset(months=2)       # Type: pd.Timestamp     | Ex: 2025-09-01 00:00:00
    start_of_M_minus_3 = start_of_current_month - pd.DateOffset(months=3)       # Type: pd.Timestamp     | Ex: 2025-08-01 00:00:00
    start_of_M_minus_4 = start_of_current_month - pd.DateOffset(months=4)       # Type: pd.Timestamp     | Ex: 2025-07-01 00:00:00
    
    # Solo procesa si hay historial de consumo
    if not df_consumo_filtered.empty:
        # 1. Preparación de datos de consumo
        # Asegura que la cantidad sea numérica (ignora errores de formato)
        # Establece la fecha como índice para poder re-muestrear (resample)
        df_consumo_indexed = df_consumo_filtered.set_index('FechaSolicitud')    # Type: pd.DataFrame     | Ex: DF donde el índice son fechas (DatetimeIndex)
        # Agrupa el consumo por mes ('MS' = Month Start) y suma las cantidades
        # NOTA: Esto crea una serie 'sparse' (solo con meses que tuvieron consumo)
        consumo_mensual = df_consumo_indexed.resample('MS')['CantidadSolicitada'].sum() # Type: pd.Series    | Ex: Indice: [2025-10-01, 2025-11-01], Valores: [150.0, 200.0]
        # 2. Cálculo para SS y ROP (promedios históricos)
        # --- INICIO DE LA MODIFICACIÓN (Arreglo del Promedio) ---
        # Creamos un rango de fechas completo para los 4 meses históricos 
        # (El período de datos que se carga en data_loader.py es de 4 meses)
        # (Ej: Si hoy es Nov, el rango es Jul-01, Ago-01, Sep-01, Oct-01)
        full_historical_range = pd.date_range(                                  # Type: pd.DatetimeIndex | Ex: ['2025-07-01', '2025-08-01', '2025-09-01', '2025-10-01']
            start=(today - pd.DateOffset(months=4)).replace(day=1), 
            end=start_of_current_month, 
            freq='MS',
            inclusive='left' # 'left' excluye la fecha 'end' (Nov-01)
        )
        
        # Re-indexamos 'consumo_mensual' (que era 'sparse') a este rango completo.
        # Los meses que no estaban en 'consumo_mensual' (consumo 0) se crearán con 'fill_value=0'.
        consumo_historico_completo = consumo_mensual.reindex(full_historical_range, fill_value=0)
        # --- FIN DE LA MODIFICACIÓN ---

        if len(consumo_historico_completo) > 1:
            # Calcula la media y std usando TODOS los meses históricos completos (incluyendo los 0)
            monthly_demand_mean = consumo_historico_completo.mean()
            monthly_demand_std = consumo_historico_completo.std()
            
            # Convierte las métricas mensuales a diarias
            daily_demand_mean = monthly_demand_mean / config.AVERAGE_DAYS_PER_MONTH
            daily_demand_std = monthly_demand_std / np.sqrt(config.AVERAGE_DAYS_PER_MONTH) 
            
        elif len(consumo_historico_completo) == 1:
            monthly_demand_mean = consumo_historico_completo.mean()
            daily_demand_mean = monthly_demand_mean / config.AVERAGE_DAYS_PER_MONTH
            # daily_demand_std se mantiene en 0.0 (inicializado)

        # 3. Cálculo para Req. 1 (meses individuales)
        
        # Aquí SÍ usamos 'consumo_mensual' (el original 'sparse')
        # .get() busca la fecha; si no la encuentra, devuelve 0 (comportamiento correcto)
        demand_M_0 = consumo_mensual.get(start_of_current_month, 0)
        demand_M_1 = consumo_mensual.get(start_of_M_minus_1, 0)
        demand_M_2 = consumo_mensual.get(start_of_M_minus_2, 0)
        demand_M_3 = consumo_mensual.get(start_of_M_minus_3, 0)
        demand_M_4 = consumo_mensual.get(start_of_M_minus_4, 0)

    # --- D. CÁLCULO DE SS y ROP ---
    
    demand_during_lead_time = daily_demand_mean * lead_time_days
    std_dev_during_lead_time = daily_demand_std * np.sqrt(lead_time_days)
    safety_stock = service_level_z * std_dev_during_lead_time
    reorder_point = demand_during_lead_time + safety_stock

    # --- E. CÁLCULO DE LLEGADAS (OC) ---
    
    df_oc_clean = df_oc_raw.copy()
    # Filtra OC relevantes
    df_llegadas_detalle = df_oc_clean[
        (df_oc_clean['Número de artículo'] == sku_to_simulate) &
        (df_oc_clean['Cantidad'] > 0) & 
        (df_oc_clean['Fecha de entrega de la línea'] >= today)
    ]
    
    llegadas_por_fecha = df_llegadas_detalle.groupby('Fecha de entrega de la línea')['Cantidad'].sum() 
    llegadas_map = llegadas_por_fecha.to_dict()
    
    # --- F. EJECUTAR SIMULACIÓN DÍA A DÍA ---
    
    inventory_level = initial_stock
    history_list = [] 
    date_list = []    

    for day in range(simulation_days):
        current_date = today + pd.Timedelta(days=day)
        
        history_list.append(inventory_level)
        date_list.append(current_date)
        
        inventory_level += llegadas_map.get(current_date, 0)
        
        # MODIFICACIÓN: Lógica de Variabilidad
        # Si el usuario pide randomness, usamos la desviación estándar real. Si no, usamos 0 (línea recta).
        scale_factor = daily_demand_std if use_randomness else 0.0
        if daily_demand_std > 0:
            daily_consumption = np.random.normal(loc=daily_demand_mean, scale=scale_factor)
        else:
            daily_consumption = daily_demand_mean
            
        daily_consumption = max(0, daily_consumption)
        inventory_level -= daily_consumption
        
    df_sim = pd.DataFrame({'NivelInventario': history_list}, index=pd.Index(date_list, name='Fecha'))

    # --- G. EMPAQUETAR RESULTADOS ---
    
    metrics = {
        'initial_stock': initial_stock,
        'monthly_demand_mean': monthly_demand_mean,
        'monthly_demand_std': monthly_demand_std,
        'llegadas_count': len(llegadas_map),
        'safety_stock': safety_stock,
        'reorder_point': reorder_point,
        'demand_M_0': (start_of_current_month, demand_M_0),
        'demand_M_1': (start_of_M_minus_1, demand_M_1),
        'demand_M_2': (start_of_M_minus_2, demand_M_2),
        'demand_M_3': (start_of_M_minus_3, demand_M_3),
        'demand_M_4': (start_of_M_minus_4, demand_M_4),
    }

    return df_sim, metrics, llegadas_map, df_llegadas_detalle



def obtener_stock_historico_con_owtr(sku, fecha_objetivo, df_stock_actual, df_owtr, bodegas_filtro=None):
    # MODIFICACIÓN: Acepta bodegas dinámicas. Si no se pasa nada, usa BF0001 por defecto.
    if bodegas_filtro is None:
        bodegas_filtro = ["BF0001"]
    
    # 1. Stock Hoy (Base)
    stock_hoy = df_stock_actual[
        (df_stock_actual['CodigoArticulo'] == sku) & 
        (df_stock_actual['CodigoBodega'].isin(bodegas_filtro)) # Usamos .isin() para listas
    ]['StockActual'].sum()

    # 2. Filtrar movimientos ocurridos DESPUÉS de la fecha objetivo
    # (Estos son los que vamos a "deshacer")
    fecha_obj_ts = pd.to_datetime(fecha_objetivo)
    
    # Filtramos por SKU y por fecha
    movs_futuros = df_owtr[
        (df_owtr['CodigoArticulo'] == sku) & 
        (df_owtr['FechaSolicitud'] > fecha_obj_ts) # Asumiendo que esta es la fecha de contabilización
    ].copy()

    # 3. Calcular el Efecto Neto para "Reversar"
    # Lógica:
    # - Si salió de BF0001 (Origen), hoy tengo menos. Para volver al pasado, SUMO.
    # - Si entró a BF0001 (Destino), hoy tengo más. Para volver al pasado, RESTO.
    
    suma_salidas = movs_futuros[movs_futuros['BodegaOrigen_Solicitada'].isin(bodegas_filtro)]['CantidadSolicitada'].sum()
    suma_entradas = movs_futuros[movs_futuros['BodegaDestino_Requerida'].isin(bodegas_filtro)]['CantidadSolicitada'].sum()

    # 4. Aplicar Fórmula
    stock_pasado = stock_hoy + suma_salidas - suma_entradas
    
    return stock_pasado