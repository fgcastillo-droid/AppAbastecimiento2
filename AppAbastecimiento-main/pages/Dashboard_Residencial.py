import streamlit as st
import pandas as pd
import sys
from pathlib import Path

# --- Configuración del Path ---
src_path = str(Path(__file__).resolve().parent.parent / "src")
if src_path not in sys.path:
    sys.path.append(src_path)

# Importamos TUS módulos modulares
import ui.ui_helpers as ui_helpers
import data.limpieza as limpieza
import core.analysis as analysis
import ui.charts as charts
import data.data_loader as data_loader

# --- 1. Configuración Global ---
st.set_page_config(layout="wide", page_title="Dashboard Residencial", page_icon="🏡")
ui_helpers.setup_locale()
try: ui_helpers.hide_streamlit_style() 
except: pass

st.title("🏡 Tablero de Control Residencial")
st.markdown("Visión 360° de proyectos: **Ventas, Ingeniería y Operaciones**.")

if 'data_loaded' not in st.session_state or not st.session_state.data_loaded:
    with st.spinner("Cargando datos... por favor, espere."):
        data_loader.load_data_into_session()
        
if 'data_loaded' not in st.session_state or not st.session_state.data_loaded:
    st.error("⚠️ Datos no cargados. Vaya al inicio.")
    st.stop()

# --- VERIFICACIÓN DE DATOS VACÍOS O COLUMNAS FALTANTES ---
if st.session_state.df_residencial.empty:
    st.warning("⚠️ No hay datos de proyectos residenciales disponibles (la API no devolvió registros).")
    st.stop()

if 'fecha_de_ganado' not in st.session_state.df_residencial.columns:
    st.error(f"⚠️ Error de formato: No se encontró la columna 'fecha_de_ganado'. Columnas recibidas desde la API: {list(st.session_state.df_residencial.columns)}")
    st.stop()

# --- 2. Preparación de Datos ---
# Enriquecimiento (Cálculos de Tiempos y Ratios)
df_main = analysis.enriquecer_data_residencial(st.session_state.df_residencial)

# --- 3. Filtros ---
with st.sidebar:
    st.header("🔍 Filtros")
    
    # A. Años
    anos_disp = sorted(df_main['fecha_de_ganado'].dt.year.dropna().unique(), reverse=True)
    sel_anos = st.multiselect("Año de Venta:", anos_disp, default=anos_disp)
    
    # B. Filtro Mes
    mapa_meses = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 
        5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto", 
        9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
    }
    meses_existentes = sorted(df_main['fecha_de_ganado'].dt.month.dropna().unique())
    nombres_meses_disp = [mapa_meses[m] for m in meses_existentes]
    
    sel_nombres_meses = st.multiselect(
        "Mes de Venta:", 
        options=nombres_meses_disp, 
        default=nombres_meses_disp,
        placeholder="Selecciona meses"
    )
    
    # Mapeo inverso Nombre -> Número
    mapa_inv = {v: k for k, v in mapa_meses.items()}
    sel_meses_num = [mapa_inv[nombre] for nombre in sel_nombres_meses]

    # C. Tipo
    tipos_disp = sorted(df_main['tipo_proyecto'].dropna().unique())
    sel_tipos = st.multiselect("Tipo Sistema:", tipos_disp, default=tipos_disp)

    # D. Tecnología
    sel_bat = st.radio("Tecnología:", ["Todos", "Con Batería", "Solo Solar"], index=0)
    st.divider()

# --- LÓGICA DE FILTRADO ---
df_filtrado = analysis.filtrar_residencial(
    df_main, 
    sel_anos, 
    sel_meses_num, 
    sel_tipos, 
    sel_bat
)

if df_filtrado.empty:
    st.warning("No hay datos para la selección actual (revise Años o Meses).")
    st.stop()

# Subsets para operaciones
df_iniciados = df_filtrado.dropna(subset=['Dias_Venta_Inicio'])
df_terminados = df_filtrado.dropna(subset=['Dias_Ejecucion'])

# --- 4. KPIs ---
k1, k2, k3, k4, k5 = st.columns(5)
total_bat = df_filtrado['Tiene_Bateria'].sum()

k1.metric("Proyectos", f"{len(df_filtrado)}")
k2.metric("Potencia Total", f"{df_filtrado['kwp'].sum():,.1f} kWp")
k3.metric("Total Paneles", f"{int(df_filtrado['cantidad_de_paneles'].sum()):,}")
k4.metric("Tasa Baterías", f"{(total_bat / len(df_filtrado) * 100):.1f}%")
k5.metric("Lead Time (Inicio)", f"{df_iniciados['Dias_Venta_Inicio'].mean():.0f} días")

st.divider()

# --- 5. Visualización ---
tab_comercial, tab_tecno, tab_ops, tab_data = st.tabs(["💰 Comercial", "⚡ Ingeniería", "🏗️ Operaciones", "🔎 Explorador"])


with tab_comercial:
    # Fila Superior: Gráfico Combinado y Mapa de Calor
    c1, c2 = st.columns([2, 1])
    
    with c1:
        st.subheader("Volumen de Proyectos y Potencia")
        st.altair_chart(charts.plot_res_ventas_evolucion(df_filtrado), use_container_width=True)
    
    with c2:
        st.subheader("Intensidad de Venta")
        st.altair_chart(charts.plot_res_heatmap(df_filtrado), use_container_width=True)

    st.divider() # Línea separadora visual

    # Fila Inferior: NUEVO GRÁFICO DE TENDENCIA
    st.subheader("📈 Tendencia de Potencia Vendida (kWp)")
    st.altair_chart(charts.plot_res_tendencia_kwp(df_filtrado), use_container_width=True)


with tab_tecno:
    t1, t2 = st.columns(2)
    with t1:
        st.markdown("**Potencia vs Paneles**")
        st.altair_chart(charts.plot_res_scatter_tecnico(df_filtrado), use_container_width=True)
    with t2:
        st.markdown("**Distribución Baterías**")
        df_bat = df_filtrado[df_filtrado['kwh'] > 0]
        if not df_bat.empty:
            st.altair_chart(charts.plot_res_baterias_hist(df_bat), use_container_width=True)
        else:
            st.info("Sin baterías en la selección.")

with tab_ops:
    # 1. NUEVO GRÁFICO: Evolución de Instalaciones (Timeline)
    st.subheader("✅ Proyectos Instalados (Finalizados)")
    st.markdown("Cantidad de proyectos entregados por mes (según *Fecha de término real*).")
    
    st.altair_chart(
        charts.plot_res_instalados_evolucion(df_filtrado), 
        use_container_width=True
    )
    
    st.divider()

    # 2. NUEVO: Análisis de Eficiencia (Scatter Plot)
    st.subheader("⚡ Eficiencia: Tamaño vs Velocidad")
    col_eff1, col_eff2 = st.columns([2, 1])
    
    with col_eff1:
        if not df_terminados.empty:
            st.altair_chart(charts.plot_res_eficiencia_scatter(df_terminados), use_container_width=True)
            st.caption("La línea roja indica la tendencia promedio. Los puntos muy por encima de la línea son anomalías lentas.")
        else:
            st.info("Faltan datos de proyectos terminados para mostrar el gráfico de eficiencia.")
            
    with col_eff2:
        st.markdown("**⚠️ Alerta: Backlog Sin Inicio (>60 días)**")
        # Calculamos proyectos vendidos pero sin fecha de inicio
        df_pendientes = df_filtrado[df_filtrado['fecha_de_inicio_de_instalacion_real'].isna()].copy()
        if not df_pendientes.empty:
            df_pendientes['Dias_Espera'] = (pd.Timestamp.now() - df_pendientes['fecha_de_ganado']).dt.days
            df_riesgo = df_pendientes[df_pendientes['Dias_Espera'] > 60].sort_values('Dias_Espera', ascending=False)
            
            if not df_riesgo.empty:
                st.dataframe(
                    df_riesgo[['ceco', 'Dias_Espera', 'kwp']].head(10),
                    column_config={"Dias_Espera": st.column_config.NumberColumn("Días Espera", format="%d d")},
                    hide_index=True, use_container_width=True
                )
            else:
                st.success("¡Todo al día! No hay proyectos con >60 días de espera.")
        else:
            st.success("No hay proyectos pendientes de inicio.")

    st.divider()

    # 3. ANÁLISIS DE TIEMPOS (Histogramas)
    st.subheader("⏱️ Análisis de Tiempos (Lead Time)")
    o1, o2 = st.columns(2)
    
    with o1:
        st.markdown("**Tiempo de Espera (Venta → Inicio)**")
        st.altair_chart(
            charts.plot_res_tiempos(df_iniciados, 'Dias_Venta_Inicio', '#2ecc71', 'Días Espera'), 
            use_container_width=True
        )
    with o2:
        st.markdown("**Tiempo de Ejecución (Inicio → Término)**")
        if not df_terminados.empty:
            st.altair_chart(
                charts.plot_res_tiempos(df_terminados, 'Dias_Ejecucion', '#e67e22', 'Días Ejecución'), 
                use_container_width=True
            )
        else:
            st.info("Sin proyectos terminados para calcular ejecución.")

# --- CAMBIOS AQUÍ: TABLA COMPLETA CON TODAS LAS COLUMNAS ---
with tab_data:
    st.subheader("📋 Maestro Detallado")
    
    # Buscador
    search = st.text_input("Buscar ID (CeCo):", "")
    df_show = df_filtrado.copy()
    if search:
        df_show = df_show[df_show['ceco'].str.contains(search, case=False)]

    # Definimos TODAS las columnas que queremos ver (Originales + Calculadas)
    columnas_ordenadas = [
        'ceco', 'tipo_proyecto', 'Status_Bateria',           # Identificación
        'fecha_de_ganado', 'fecha_de_inicio_de_instalacion_real', 'fecha_de_termino_de_instalacion_real', # Fechas
        'kwp', 'cantidad_de_paneles', 'Ratio_Wp_Panel', 'kwh', # Técnicas
        'Dias_Venta_Inicio', 'Dias_Ejecucion'                # KPIs
    ]
    
    # Filtramos solo las que existan para evitar errores
    cols_existentes = [c for c in columnas_ordenadas if c in df_show.columns]
    
    st.dataframe(
        df_show[cols_existentes].sort_values('fecha_de_ganado', ascending=False),
        column_config={
            "ceco": st.column_config.TextColumn("ID Proyecto", pinned=True),
            "kwp": st.column_config.ProgressColumn("kWp", format="%.2f", min_value=0, max_value=float(df_filtrado['kwp'].max())),
            "Ratio_Wp_Panel": st.column_config.NumberColumn("Wp/Panel", format="%.1f W"),
            "kwh": st.column_config.NumberColumn("Batería kWh", format="%.1f"),
            "fecha_de_ganado": st.column_config.DateColumn("F. Venta", format="DD/MM/YYYY"),
            "fecha_de_inicio_de_instalacion_real": st.column_config.DateColumn("F. Inicio", format="DD/MM/YYYY"),
            "fecha_de_termino_de_instalacion_real": st.column_config.DateColumn("F. Término", format="DD/MM/YYYY"),
            "Dias_Venta_Inicio": st.column_config.NumberColumn("Días Espera"),
            "Dias_Ejecucion": st.column_config.NumberColumn("Días Ejec.")
        },
        use_container_width=True,
        height=600,
        hide_index=True
    )