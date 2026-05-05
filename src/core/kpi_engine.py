# --- ARCHIVO: src/kpi_engine.py ---
import pandas as pd
import numpy as np

def calcular_fill_rate_proyectos(df_solicitudes):
    """
    Calcula el Fill Rate (OTIF Volumen) basado en Solicitudes de Traslado (OWTQ).
    Fórmula: (Cantidad Solicitada - Cantidad Pendiente) / Cantidad Solicitada
    """
    df = df_solicitudes.copy()
    
    # Asegurar numéricos
    cols = ['Cantidad', 'CantidadPendiente'] # Ajusta a tus nombres reales de columnas en ST_OWTQ
    for col in cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Calcular Cantidad Entregada
    df['CantidadEntregada'] = df['Cantidad'] - df['CantidadPendiente']
    
    # Agrupar por Mes y (opcional) Familia/Item
    # Asumiendo que tienes una columna de fecha 'FechaContabilizacion'
    df['Mes'] = pd.to_datetime(df['FechaContabilizacion']).dt.to_period('M')
    
    kpi_mensual = df.groupby('Mes').agg(
        Total_Solicitado=('Cantidad', 'sum'),
        Total_Entregado=('CantidadEntregada', 'sum')
    ).reset_index()
    
    kpi_mensual['FillRate'] = (kpi_mensual['Total_Entregado'] / kpi_mensual['Total_Solicitado']) * 100
    
    # Fill Rate Global actual
    fill_rate_total = (df['CantidadEntregada'].sum() / df['Cantidad'].sum()) * 100
    
    return kpi_mensual, fill_rate_total

def calcular_cobertura_semanal(df_stock, df_consumo):
    """
    Calcula semanas de inventario (Weeks of Supply).
    Coverage = Stock Actual / Demanda Promedio Semanal (últimos 3 meses)
    """
    # 1. Calcular Demanda Promedio Semanal por SKU basándonos en TS_OWTR (Traslados Reales)
    # Filtramos últimos 90 días
    fecha_corte = pd.Timestamp.now() - pd.DateOffset(days=90)
    df_cons_recent = df_consumo[pd.to_datetime(df_consumo['FechaSolicitud']) >= fecha_corte].copy()
    
    demanda_sku = df_cons_recent.groupby('CodigoArticulo')['Cantidad'].sum().reset_index()
    demanda_sku['PromedioSemanal'] = demanda_sku['Cantidad'] / 12 # 12 semanas aprox en 3 meses
    
    # 2. Unir con Stock Actual
    # Agrupar stock por SKU (por si está en múltiples bodegas, filtramos bodegas de 'basura' si es necesario)
    stock_sku = df_stock.groupby('CodigoArticulo')['OnHand'].sum().reset_index()
    
    df_kpi = pd.merge(stock_sku, demanda_sku[['CodigoArticulo', 'PromedioSemanal']], on='CodigoArticulo', how='left')
    df_kpi['PromedioSemanal'] = df_kpi['PromedioSemanal'].fillna(0)
    
    # Evitar división por cero
    df_kpi['SemanasCobertura'] = np.where(
        df_kpi['PromedioSemanal'] > 0,
        df_kpi['OnHand'] / df_kpi['PromedioSemanal'],
        999 # Si no hay demanda, técnicamente la cobertura es infinita (o stock muerto)
    )
    
    return df_kpi

def analizar_quiebres(df_quiebres):
    """
    Analiza la tabla de solicitudes de compra generadas por urgencia (OPRQ).
    """
    # Asumiendo df_quiebres es tu archivo Quiebres.xlsx o una vista de OPRQ
    df = df_quiebres.copy()
    if 'Fecha' in df.columns:
        df['Mes'] = pd.to_datetime(df['Fecha']).dt.to_period('M')
        tendencia = df.groupby('Mes').size().reset_index(name='Num_Quiebres')
        return tendencia
    return pd.DataFrame()