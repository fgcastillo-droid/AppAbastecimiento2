# --- ARCHIVO: src/limpieza.py ---
import pandas as pd
from src import config

def _convertir_fechas_flexibles(series):
    """
    Función auxiliar robusta para convertir fechas mixtas (Texto y Excel Serial).
    Soluciona el problema de fechas 'basura' (1970) o invertidas.
    """
    if series is None or series.empty:
        return series

    # Asegurar string y quitar espacios
    s_clean = series.astype(str).str.strip()
    
    # 1. Intentar detectar formato numérico (Excel Serial)
    s_num = pd.to_numeric(s_clean, errors='coerce')
    # Rango lógico: 30,000 (año 1982) hasta 90,000 (año 2146)
    mask_excel = s_num.notna() & (s_num > 30000) & (s_num < 90000)
    
    # Inicializar resultado con NaT
    result = pd.Series(pd.NaT, index=series.index)
    
    # A. Convertir Seriales Excel (Números)
    if mask_excel.any():
        result.loc[mask_excel] = pd.to_datetime(s_num[mask_excel], unit='D', origin='1899-12-30')
    
    # B. Convertir Texto (DD/MM/YYYY)
    mask_text = ~mask_excel
    if mask_text.any():
        # dayfirst=True fuerza a leer DD/MM, crucial en Latam
        # Reemplazar guiones por barras ayuda a estandarizar
        txt_vals = s_clean[mask_text].str.replace('-', '/', regex=False)
        # format='mixed' ayuda si tienes Pandas nuevo, pero errors='coerce' es seguro
        try:
            result.loc[mask_text] = pd.to_datetime(txt_vals, dayfirst=True, format='mixed', errors='coerce')
        except ValueError:
            result.loc[mask_text] = pd.to_datetime(txt_vals, dayfirst=True, errors='coerce')
            
    return result

def _convertir_numeros_flexibles(series: pd.Series) -> pd.Series:
    """
    Función auxiliar optimizada y robusta para convertir series de texto
    con formato monetario/numérico latino (ej. "$ 1.234,56") a números.
    """
    if series is None or series.empty:
        return series
    
    # Optimización: Si ya es numérico, solo rellenar nulos y retornar.
    if pd.api.types.is_numeric_dtype(series):
        return series.fillna(0)

    # 1. Asegurar que es texto y quitar espacios iniciales/finales
    s_clean = series.astype(str).str.strip()
    
    # 2. Limpieza y estandarización
    s_clean = (
        s_clean.str.replace(r'[^\d\.,\-]', '', regex=True)  # Limpia símbolos ($ , €, etc)
               .str.replace('.', '', regex=False)           # Quita separador de miles
               .str.replace(',', '.', regex=False)           # Cambia coma decimal a punto
    )
    
    # 3. Forzar a número. Los errores (ej. celdas vacías) se vuelven NaN.
    s_numeric = pd.to_numeric(s_clean, errors='coerce')
    
    # 4. Rellenar los NaN resultantes con 0.
    return s_numeric.fillna(0)

def limpiar_ordenes_compra(df_oc: pd.DataFrame) -> pd.DataFrame:
    """Limpia las Órdenes de Compra (OPOR): textos, fechas y montos desde Google Sheets."""
    if df_oc is None or df_oc.empty:
        return pd.DataFrame()
        
    df = df_oc.copy()
    
    # --- OPTIMIZACIÓN: Limpiar y filtrar por fecha PRIMERO ---
    # 1. CONVERSIÓN DE FECHAS
    cols_fecha = ['Fecha de contabilización', 'Fecha de entrega de la línea']
    for col in cols_fecha:
        if col in df.columns:
            df[col] = _convertir_fechas_flexibles(df[col])

    # 2. FILTRO DE TIEMPO (Últimos 12 meses)
    if 'Fecha de contabilización' in df.columns:
        hoy = pd.Timestamp.now()
        hace_12_meses = (hoy - pd.DateOffset(months=12)).replace(day=1)
        df = df[df['Fecha de contabilización'] >= hace_12_meses].copy()

    # --- Limpiezas sobre el DataFrame ya filtrado ---
    # 3. LIMPIEZA DE TEXTOS
    cols_texto = [
        'Número de documento', 'Nombre de cliente/proveedor', 'Número de artículo', 
        'Descripción artículo/serv.', 'Familia_Articulo', 'LineStatus', 'Creador', 'Comentarios'
    ]
    for col in cols_texto:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # ---------------------------------------------------------
    # 3. CONVERSIÓN NUMÉRICA (Cantidades y Dinero)
    # ---------------------------------------------------------
    cols_numericas = [
        'Cantidad', 
        'Precio_Unitario', 
        'Total_Linea', 
        'Cantidad abierta restante', 
        'Total_Pendiente',
        'DocEntry', 
        'LineNum'
    ]
    
    for col in cols_numericas:
        if col in df.columns:
            df[col] = _convertir_numeros_flexibles(df[col])
    
    return df

def limpiar_consumos(df_consumo: pd.DataFrame) -> pd.DataFrame:
    """Limpia los Consumos/Traslados desde Sheets: fechas, números, filtro de 3 meses y mapeo de SKUs."""
    if df_consumo is None or df_consumo.empty:
        return pd.DataFrame()
        
    df = df_consumo.copy()

    # --- OPTIMIZACIÓN: Limpiar y filtrar por fecha PRIMERO ---
    if 'FechaSolicitud' in df.columns:
        df['FechaSolicitud'] = _convertir_fechas_flexibles(df['FechaSolicitud'])
        df = df.dropna(subset=['FechaSolicitud'])
        
        # Filtro de tiempo
        hoy = pd.Timestamp.now()
        hace_12_meses = (hoy - pd.DateOffset(months=12)).replace(day=1)
        df = df[df['FechaSolicitud'] >= hace_12_meses].copy()

    # --- Limpiezas sobre el DataFrame ya filtrado ---
    # 1. LIMPIEZA DE TEXTOS
    cols_texto = [
        'BodegaDestino_Requerida', 'BodegaOrigen_Solicitada', 
        'CodigoArticulo', 'Estado', 'NombreProyecto', 'CodigoProyecto'
    ]
    for col in cols_texto:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # ---------------------------------------------------------
    # 4. CONVERSIÓN NUMÉRICA (Evita los errores de 'str' y 'int')
    # ---------------------------------------------------------
    cols_numericas = [
        'CantidadSolicitada', 
        'StockActual_EnOrigen', 
        'CostoUnitarioEstimado', 
        'ValorTotalSolicitado'
    ]
    
    for col in cols_numericas:
        if col in df.columns:
            df[col] = _convertir_numeros_flexibles(df[col])

    # ---------------------------------------------------------
    # 5. MAPEO DE SKUS
    # ---------------------------------------------------------
    if 'CodigoArticulo' in df.columns:
        df['CodigoArticulo'] = df['CodigoArticulo'].replace(config.MAPEO_SKUS)
        
    return df

def limpiar_stock(df_stock: pd.DataFrame) -> pd.DataFrame:
    """Limpia el Stock de inventario desde Google Sheets: formatea números, fechas y textos."""
    if df_stock is None or df_stock.empty:
        return pd.DataFrame()
        
    df = df_stock.copy()
    
    # ---------------------------------------------------------
    # 1. LIMPIEZA DE TEXTOS (Crucial para el cruce de bodegas y SKUs)
    # ---------------------------------------------------------
    cols_texto = [
        'CodigoArticulo', 
        'NombreArticulo', 
        'GrupoArticulo', 
        'CodigoBodega', 
        'NombreBodega', 
        'Familia', 
        'SubFamilia'
    ]
    
    for col in cols_texto:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # ---------------------------------------------------------
    # 2. CONVERSIÓN NUMÉRICA (Cantidades físicas y Valores monetarios)
    # ---------------------------------------------------------
    cols_numericas = [
        'StockActual', 
        'Comprometido', 
        'EnPedido_a_Proveedor', 
        'DisponibleParaPrometer', 
        'CostoUnitario', 
        'ValorTotalInventario', 
        'NivelMinimo', 
        'NivelMaximo'
    ]
    
    for col in cols_numericas:
            if col in df.columns:
                df[col] = _convertir_numeros_flexibles(df[col])


    # ---------------------------------------------------------
    # 3. CONVERSIÓN DE FECHAS
    # ---------------------------------------------------------
    cols_fecha = [
        'FechaUltimaCompra', 
        'FechaCreacionArticulo'
    ]
    
    for col in cols_fecha:
        if col in df.columns:
            df[col] = _convertir_fechas_flexibles(df[col])
            # NOTA: Aquí NO hacemos dropna() porque es normal tener artículos sin fecha de última compra

    # ---------------------------------------------------------
    # 4. MAPEO DE SKUS (Unifica los códigos para que coincidan con OPOR y Consumos)
    # ---------------------------------------------------------

    col_subfam = 'SubFamilia' if 'SubFamilia' in df.columns else 'Familia'
    if col_subfam in df.columns:
        df[col_subfam] = df[col_subfam].fillna("Sin Subfamilia")
        df[col_subfam] = df[col_subfam].replace("", "Sin Subfamilia")
    return df

def limpiar_movimientos(df_movimientos: pd.DataFrame) -> pd.DataFrame:
    """Limpia la tabla de historial de movimientos de stock (OINM) desde Google Sheets."""
    if df_movimientos is None or df_movimientos.empty:
        return pd.DataFrame()
        
    df = df_movimientos.copy()
    
    # ---------------------------------------------------------
    # 1. LIMPIEZA DE TEXTOS
    # ---------------------------------------------------------
    cols_texto = [
        'Mes', 
        'CodigoArticulo', 
        'NombreArticulo', 
        'Familia', 
        'SubFamilia', 
        'CodigoBodega'
    ]
    
    for col in cols_texto:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

# ---------------------------------------------------------
    # 2. CONVERSIÓN DE FECHAS (Formato Día-Mes-Año)
    # ---------------------------------------------------------
    if 'fecha' in df.columns:
        # Convertimos a string, quitamos espacios y cambiamos guiones en un solo paso
        df['fecha'] = df['fecha'].astype(str).str.strip().str.replace('-', '/')
        # convertimos a fecha oficial de Pandas
        df['fecha'] = pd.to_datetime(df['fecha'], dayfirst=True, errors='coerce')
        # Aquí NO hacemos dropna() de inmediato para no borrar accidentalmente filas 
        # sin avisar, aunque si en tu Radar requieres fechas obligatorias, puedes agregarlo.

    # ---------------------------------------------------------
    # 3. CONVERSIÓN NUMÉRICA (Cantidades y Valores Monetarios)
    # ---------------------------------------------------------
    # Estas son las columnas que tienen formato latino "1.000,00"
    cols_numericas_complejas = [
        'CantidadMovimiento', 
        'ValorMovimiento', 
    ]
    
    for col in cols_numericas_complejas:
        if col in df.columns:
            df[col] = _convertir_numeros_flexibles(df[col])
    return df

def limpiar_residencial(df):
    """
    Limpia y tipifica el maestro de proyectos Residencial.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    df_out = df.copy()

    # 1. Identificadores (Texto)
    if 'ceco' in df_out.columns:
        df_out['ceco'] = df_out['ceco'].astype(str).str.strip().str.upper()
    
    if 'tipo_proyecto' in df_out.columns:
        # Limpieza para estandarizar categorías como 'Híbrido' y 'Hibrido'
        df_out['tipo_proyecto'] = df_out['tipo_proyecto'].astype(str).str.strip()
        # Convertimos a minúsculas y reemplazamos la tilde para unificar
        df_out['tipo_proyecto'] = df_out['tipo_proyecto'].str.lower().str.replace('í', 'i', regex=False)
        # Finalmente, capitalizamos para un formato limpio (ej: 'Hibrido')
        df_out['tipo_proyecto'] = df_out['tipo_proyecto'].str.title()

    # 2. Métricas Numéricas (Manejo de Nulos)
    # kWp y Paneles: Si es nulo, es 0.
    for col in ['kwp', 'cantidad_de_paneles', 'kwh']:
        if col in df_out.columns:
            df_out[col] = _convertir_numeros_flexibles(df_out[col])
            
            # Evitar números negativos por error de dedo
            df_out[col] = df_out[col].clip(lower=0)
            

    # 3. Fechas (Strict Date)
    cols_fecha = ['fecha_de_ganado', 'fecha_de_inicio_de_instalacion_real', 'fecha_de_termino_de_instalacion_real']
    for col in cols_fecha:
        if col in df_out.columns:
            df_out[col] = _convertir_fechas_flexibles(df_out[col])

    return df_out


def limpiar_solicitudes(df):
    """
    Limpia OWTQ incluyendo ahora costos y valores monetarios.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    df_out = df.copy()

    # 1. Estandarizar columnas (quitar espacios extra)
    df_out.columns = df_out.columns.str.strip()

    # --- OPTIMIZACIÓN: Filtrar por fecha primero ---
    if 'Fecha Contab.' in df_out.columns:
        df_out['Fecha Contab.'] = _convertir_fechas_flexibles(df_out['Fecha Contab.'])
        # Podríamos agregar un filtro de tiempo aquí si fuera necesario, por ejemplo:
        # hoy = pd.Timestamp.now()
        # hace_X_meses = (hoy - pd.DateOffset(months=24)).replace(day=1)
        # df_out = df_out[df_out['Fecha Contab.'] >= hace_X_meses].copy()


    # --- Limpiezas sobre el DataFrame filtrado ---
    # Forzar Textos (Strings)
    cols_texto = ['Nombre Proyecto', 'Código Artículo', 'Almacén Origen', 'Almacén Destino', 'Descripción', 'Nº Solicitud']
    for col in cols_texto:
        if col in df_out.columns:
            # Convertir a string y limpiar nulos
            df_out[col] = df_out[col].astype(str).str.strip().replace('nan', '')

    # 4. Asegurar Numéricos (Cantidades y DINERO)
    # Agregamos las nuevas columnas financieras aquí
    cols_num = ['Cant. Pendiente', 'Costo Unitario', 'Valor Pendiente Total']
    
    for col in cols_num:
            if col in df_out.columns:
                df_out[col] = _convertir_numeros_flexibles(df_out[col])

    return df_out

def limpiar_requerimientos(df: pd.DataFrame) -> pd.DataFrame:
    """
    Limpia la tabla de Requerimientos de Salidas Futuras.
    Columnas esperadas: sku, desc., cantidad, fecha, proyecto, enviado, firmado, comentarios
    """
    if df is None or df.empty:
        return pd.DataFrame()
    df_out = df.copy()
    
    # Normalizamos las columnas actuales para facilitar el mapeo
    df_out.columns = [c.strip() for c in df_out.columns]
    # Renombramos usando el mapa (ignorando case)

    # 2. Limpieza de Texto
    cols_texto = ['sku', 'desc.', 'proyecto', 'enviado', 'estado comercial (won,open)', 'comentarios', 'estado global', 'Abastecimiento (orgánico - calzado)', 'Subfamilia']
    for col in cols_texto:
        if col in df_out.columns:
            df_out[col] = df_out[col].astype(str).str.strip()

    # 3. Fechas
    cols_fecha = ['fecha tentativa','fecha firma','fecha en proyecto segun gantt','fecha real de llegada a proyecto' ]
    for col in cols_fecha:
        df_out[col] = _convertir_fechas_flexibles(df_out[col])

    # 4. Cantidades
    if 'cantidad' in df_out.columns:
        df_out['cantidad'] = _convertir_numeros_flexibles(df_out['cantidad'])

    return df_out