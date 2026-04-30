import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from core import analysis

def cargar_estilos():
    st.markdown("""
        <style>
        .main .block-container { padding-top: 2rem; padding-bottom: 3rem; }
        div[data-testid="stMetric"] {
            background-color: #ffffff;
            padding: 15px;
            border-radius: 8px;
            border: 1px solid #e0e0e0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            border-left: 5px solid #E31C23;
        }
        h3 { color: #333333; font-weight: 600; }
        </style>
        """, unsafe_allow_html=True)

def render_header():
    col_logo, col_title = st.columns([1, 6])
    with col_logo:
        try:
            st.image("assets/COPEC-FLUX.svg", width=True)
        except Exception:
            st.markdown("## 🔴")
    with col_title:
        st.title("Portal de Gestión de Abastecimiento")
        st.caption(f"📅 Actualización: {pd.Timestamp.now().strftime('%d-%m-%Y')} | Panel de Control Centralizado")
    st.markdown("---")

def configurar_sidebar():
    st.sidebar.header("⚙️ Configuración Global")
    
    # Filtro de Familia
    lista_familias = []
    if 'df_stock' in st.session_state and st.session_state.df_stock is not None:
        if 'SubFamilia' in st.session_state.df_stock.columns:
            lista_familias = sorted(st.session_state.df_stock['SubFamilia'].dropna().astype(str).unique())
    
    familia_sel = st.sidebar.selectbox("📂 Filtrar por Familia:", ["Todas"] + lista_familias)
    
    # Filtro de Días
    dias_calc = st.sidebar.slider("📅 Ventana de Análisis (Días):", min_value=30, max_value=360, value=60, step=30)
    
    # Información Footer
    st.sidebar.markdown("---")
    st.sidebar.image("assets/COPEC-FLUX.svg", use_container_width=True)
    st.sidebar.caption("v3.2 | Conectado a SAP Querys")
    
    return familia_sel, dias_calc

def render_kpis_principales(df_s, df_o, df_h, dias_calc):
    st.subheader("📊 Resumen Ejecutivo")
    kpi1, kpi2, kpi3, kpi4, kpi5= st.columns(5)
    
    # --- Cálculos ---
    rot_val, doi_val = 0, 0
    try:
        bodegas_all = df_s['CodigoBodega'].unique().tolist() if 'CodigoBodega' in df_s.columns else []
        
        # Filtramos el historial SOLO para aislar las salidas del KPI
        bodegas_salidas = ['BF0001', 'BF0004', 'BF0008', 'BF0009']
        df_h_salidas = df_h[df_h['CodigoBodega'].isin(bodegas_salidas)] if 'CodigoBodega' in df_h.columns else df_h
        
        df_rep = analysis.generar_reporte_inventario(df_h_salidas, df_s, dias=dias_calc, bodegas=bodegas_all)
        if not df_rep.empty:
            tot_inv = df_rep['Valor_Inventario'].sum()
            tot_sal = df_rep[f'Salidas_{dias_calc}D'].sum()
            if tot_sal > 0:
                doi_val = (tot_inv / tot_sal) * dias_calc
                rot_val = 365 / doi_val if doi_val > 0 else 0
    except Exception:
        pass

    with kpi1:
        st.metric("Rotación Global", f"{rot_val:.1f} x", help=f"Rotación anualizada (base {dias_calc} días)")
    with kpi2:
        st.metric("DOI Global", f"{doi_val:.0f} días", help=f"Días de Inventario promedio considerando los últimos {dias_calc} días")
    with kpi3:
        val_total = df_s['ValorTotalInventario'].sum() if 'ValorTotalInventario' in df_s.columns else 0
        st.metric("Valor Stock Total", f"${val_total:,.0f}")
    with kpi4:
        skus_activos = df_s[df_s['StockActual'] > 0]['CodigoArticulo'].nunique() if 'StockActual' in df_s.columns else 0
        st.metric("SKUs Activos", f"{skus_activos:,.0f}")
    with kpi5:
        col_p, col_doc = "Cantidad abierta restante", "Número de documento"
        ocs_activas = df_o[df_o[col_p] > 0][col_doc].nunique() if col_p in df_o.columns else 0
        st.metric("OCs Pendientes", f"{ocs_activas}", delta="En Tránsito")

def render_kpis_consumo_equipos(df_c, df_s):
    st.subheader("⚡ Consumo Equipos Principales (Últimos 12 Meses)")
    c1, c2, c3 = st.columns(3)
    
    if df_c is None or df_c.empty:
        c1.metric("☀️ Paneles Solares", "0 Uds")
        c2.metric("🔌 Inversores", "0 Uds")
        c3.metric("🔋 Baterías", "0 Uds")
        return
        
    df_calc = df_c.copy()
    
    # Enriquecer con SubFamilia desde Stock si no existe directamente en Consumo
    if 'SubFamilia' not in df_calc.columns and df_s is not None and not df_s.empty and 'CodigoArticulo' in df_s.columns:
        df_s_unique = df_s.drop_duplicates(subset=['CodigoArticulo'])
        if 'SubFamilia' in df_s_unique.columns:
            df_calc = df_calc.merge(df_s_unique[['CodigoArticulo', 'SubFamilia']], on='CodigoArticulo', how='left')
            
    subfam_col = df_calc['SubFamilia'].fillna('').astype(str).str.upper() if 'SubFamilia' in df_calc.columns else pd.Series([''] * len(df_calc))
    nombre_col = df_calc['NombreArticulo'].fillna('').astype(str).str.upper() if 'NombreArticulo' in df_calc.columns else pd.Series([''] * len(df_calc))
    
    # Filtros para identificar productos independientemente de si la familia viene sucia
    mask_paneles = subfam_col.str.contains('PANELES')
    mask_inversores = subfam_col.str.contains('INVERSOR')
    mask_baterias = subfam_col.str.contains('BATE')
    
    cant_paneles = df_calc.loc[mask_paneles, 'CantidadSolicitada'].sum() if 'CantidadSolicitada' in df_calc.columns else 0
    cant_inversores = df_calc.loc[mask_inversores, 'CantidadSolicitada'].sum() if 'CantidadSolicitada' in df_calc.columns else 0
    cant_baterias = df_calc.loc[mask_baterias, 'CantidadSolicitada'].sum() if 'CantidadSolicitada' in df_calc.columns else 0
    
    c1.metric("☀️ Paneles Solares", f"{cant_paneles:,.0f} Uds")
    c2.metric("🔌 Inversores", f"{cant_inversores:,.0f} Uds")
    c3.metric("🔋 Baterías", f"{cant_baterias:,.0f} Uds")

    # --- Gráfico de Tendencia Mensual ---
    if 'CantidadSolicitada' in df_calc.columns and 'FechaSolicitud' in df_calc.columns:
        df_calc['CategoriaEquipo'] = np.select(
            [mask_paneles, mask_inversores, mask_baterias],
            ['Paneles Solares', 'Inversores', 'Baterías'],
            default='Otros'
        )
        
        df_grafico = df_calc[df_calc['CategoriaEquipo'] != 'Otros'].copy()
        
        if not df_grafico.empty:
            df_grafico['FechaSolicitud'] = pd.to_datetime(df_grafico['FechaSolicitud'], errors='coerce')
            df_grafico = df_grafico.dropna(subset=['FechaSolicitud'])
            df_grafico['Mes'] = df_grafico['FechaSolicitud'].dt.strftime('%Y-%m')
            
            df_agrupado = df_grafico.groupby(['Mes', 'CategoriaEquipo'])['CantidadSolicitada'].sum().reset_index()
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("##### 📊 Consumo Mensual por Categoría")
            
            cg1, cg2, cg3 = st.columns(3)
            
            config_graficos = [
                ('Paneles Solares', '#f1c40f', cg1),
                ('Inversores', '#e74c3c', cg2),
                ('Baterías', '#2ecc71', cg3)
            ]
            
            for cat, color_hex, col in config_graficos:
                df_cat = df_agrupado[df_agrupado['CategoriaEquipo'] == cat]
                with col:
                    if not df_cat.empty:
                        base = alt.Chart(df_cat).encode(
                            x=alt.X('Mes:O', title=None, axis=alt.Axis(labelAngle=-45))
                        )
                        barras = base.mark_bar(color=color_hex).encode(
                            y=alt.Y('CantidadSolicitada:Q', title='Unidades Consumidas'),
                            tooltip=[alt.Tooltip('Mes:O', title='Mes'), alt.Tooltip('CantidadSolicitada:Q', title='Unidades', format=',.0f')]
                        )
                        etiquetas = base.mark_text(dy=-10, color='black', clip=False).encode(
                            y=alt.Y('CantidadSolicitada:Q'),
                            text=alt.Text('CantidadSolicitada:Q', format=',.0f')
                        )
                        chart = (barras + etiquetas).properties(title=cat, height=250)
                        st.altair_chart(chart, use_container_width=True)
                    else:
                        st.info(f"Sin consumos de {cat}")

def render_analisis_historico(df_h):
    st.subheader("📉 Evolución Histórica (Últimos 12 Meses)")
    
    if df_h.empty:
        st.info("⚠️ No hay historial suficiente para calcular la evolución.")
        return

    try:
        # Preparación de datos (Copia local)
        df_local = df_h.copy()
        if not pd.api.types.is_datetime64_any_dtype(df_local['fecha']):
            df_local['fecha'] = pd.to_datetime(df_local['fecha'])
        
        df_local['Mes'] = df_local['fecha'].dt.to_period('M')
        
        # Agrupación y Cálculos
        df_mensual = df_local.groupby('Mes').agg(
            Salidas=('ValorMovimiento', lambda x: x[x < 0].sum()),
            MovimientoNeto=('ValorMovimiento', 'sum')
        )
        df_mensual['Salidas'] = df_mensual['Salidas'].abs()
        df_mensual['StockFin'] = df_mensual['MovimientoNeto'].cumsum()
        
        # Filtro de 12 meses cerrados
        hoy = pd.Timestamp.now().normalize()
        mes_actual = hoy.to_period('M')
        df_final = df_mensual.loc[mes_actual - 12 : mes_actual - 1].copy()
        
        # Cálculo DOI
        df_final['DiasMes'] = df_final.index.days_in_month
        df_final['DOI'] = np.where(
            df_final['Salidas'] > 0, 
            (df_final['StockFin'] / df_final['Salidas']) * df_final['DiasMes'], 
            np.nan 
        )
        
        # Limpieza visual
        df_final['StockFin'] = df_final['StockFin'].round(0)
        
        # Visualización
        df_chart = df_final.reset_index()
        df_chart['MesStr'] = df_chart['Mes'].astype(str)
        
        col_graf1, col_graf2 = st.columns(2)

        with col_graf1:
            st.markdown("##### 💰 Valor Inventario ($)")
            base_val = alt.Chart(df_chart).encode(
                x=alt.X('MesStr', title='Mes', sort=None),
                y=alt.Y('StockFin:Q', title='Valor Stock ($)', axis=alt.Axis(format='$,.0f'), scale=alt.Scale(zero=False))
            )
            linea_val = base_val.mark_line(point=True, color='#2980b9').encode(
                tooltip=[alt.Tooltip('MesStr', title='Mes'), alt.Tooltip('StockFin', format='$,.0f', title='Valor Stock')]
            )
            textos_val = base_val.mark_text(dy=-10, color='black').encode(
                text=alt.Text('StockFin:Q', format='$,.0f')
            )
            st.altair_chart((linea_val + textos_val).properties(height=300), use_container_width=True)

        with col_graf2:
            st.markdown("##### 🔄 Días de Inventario (DOI)")
            base_doi = alt.Chart(df_chart).encode(
                x=alt.X('MesStr', title='Mes', sort=None),
                y=alt.Y('DOI', title='Días de Inventario (DOI)')
            )
            linea_doi = base_doi.mark_line(point=True, color='#E31C23').encode(
                tooltip=[alt.Tooltip('MesStr'), alt.Tooltip('DOI', format=',.1f')]
            )
            etiquetas_doi = base_doi.mark_text(dy=-10, color='#333333').encode(
                text=alt.Text('DOI:Q', format='.1f')
            )
            st.altair_chart((linea_doi + etiquetas_doi).properties(height=300), use_container_width=True)

    except Exception as e:
        st.error(f"No se pudo generar el gráfico de evolución: {e}")

def render_tarjetas_navegacion():
    st.subheader("📌 Herramientas de Gestión")
    
    # Helper para tarjetas limpias
    def tarjeta(col, titulo, icono, desc, link, label_btn):
        with col:
            with st.container(border=True):
                st.markdown(f"### {icono} {titulo}")
                st.caption(desc)
                st.page_link(link, label=label_btn, use_container_width=True)

    # --- FILA 1: OPERACIÓN CORE ---
    st.markdown("##### 🚀 Operación y Abastecimiento")
    c1, c2, c3, c4 = st.columns(4)
    tarjeta(c1, "Simulador", "📈", "Cálculo de compras y stock.", "pages/Simulador_de_inventario_por_SKU.py", "Abrir Simulador")
    tarjeta(c2, "Llegadas", "📦", "Tracking de Órdenes (OC).", "pages/Próximas_Llegadas.py", "Ver Llegadas")
    tarjeta(c3, "Radar", "📡", "Alertas de quiebre y riesgo.", "pages/Radar_de_Inventario.py", "Ver Radar")
    tarjeta(c4, "Consulta", "🔍", "Buscador rápido de items.", "pages/Consulta_de_Stock.py", "Buscar Item")

    # --- FILA 2: ANÁLISIS ESTRATÉGICO ---
    st.markdown("##### 📊 Análisis y Finanzas")
    c5, c6, c7, c8 = st.columns(4)
    tarjeta(c5, "Valorización", "💰", "KPIs financieros y cierres.", "pages/KPIs_de_Inventario.py", "Ver Finanzas")
    tarjeta(c6, "Rotación", "🔄", "Análisis de DOI y Salud.", "pages/Rotación_de_Inventario.py", "Ver Rotación")
    tarjeta(c7, "Evolución", "📅", "Historia diaria (Kardex).", "pages/Evolución_de_Stock.py", "Ver Historia")
    tarjeta(c8, "Compradores", "💼", "Desempeño del equipo.", "pages/KPIs_de_Compradores.py", "Ver Gestión")

    # --- FILA 3: VERTICALES Y LOGÍSTICA ---
    st.markdown("##### 🏗️ Verticales y Logística")
    c9, c10, c11, c12 = st.columns(4)
    tarjeta(c9, "Residencial", "🏠", "Control proyectos solar.", "pages/Dashboard_Residencial.py", "Ir a Residencial")
    tarjeta(c10, "Traslados", "🚛", "Solicitudes pendientes.", "pages/ST_Pendientes.py", "Ver Traslados")
    tarjeta(c11, "Eq. Principal", "💡", "Stock crítico equipos.", "pages/Análisis_Equipos_Principales.py", "Ver Equipos")
    tarjeta(c12, "Predicción", "🔮", "Forecast (Prophet).", "pages/Prediccion_de_Ventas_Residencial.py", "Ver Predicción")
    
    with st.expander("🛠️ Herramientas de Planificación Avanzada"):
        st.page_link("pages/Cubicación_estructuras_Techo.py", label="🏭 Simulador de Planificación (Techos)", icon="🏭")
