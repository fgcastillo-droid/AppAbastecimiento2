import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import sys
from pathlib import Path

src_path = str(Path(__file__).resolve().parent.parent / "src")
if src_path not in sys.path:
    sys.path.append(src_path)

import ui.ui_helpers as ui_helpers
import core.analysis as analysis # Importamos tus nuevas funciones

# --- Configuración Global ---
st.set_page_config(layout="wide", page_title="Rotación de Inventario", page_icon="🔄")
ui_helpers.setup_locale()

st.title("🔄 Análisis de Rotación y DOI")
st.markdown("Identifica el capital inmovilizado y la velocidad a la que se mueve tu inventario.")

# --- 1. CONSTANTES Y CONFIGURACIÓN ---

SALUD_CATEGORIES = {
    "1. Rápida (<30d)": (0, 30),
    "2. Normal (30-90d)": (30, 90),
    "3. Lenta (90-180d)": (90, 180),
    "4. Inmovilizado (>180d o Sin Mov.)": (180, np.inf)
}

SALUD_COLORS = {
    "1. Rápida (<30d)": "#2ecc71",
    "2. Normal (30-90d)": "#3498db",
    "3. Lenta (90-180d)": "#f1c40f",
    "4. Inmovilizado (>180d o Sin Mov.)": "#e74c3c"
}

DEFAULT_BODEGAS = ["BF0001", "BFT0001", "BF0004", "BF0006", "BF0008"]

# --- 2. FUNCIONES AUXILIARES (Lógica y UI) ---

def render_sidebar(df_stock):
    """Renderiza la barra lateral y devuelve un diccionario con las selecciones."""
    with st.sidebar:
        st.header("⚙️ Configuración de Análisis")
        dias_analisis = st.select_slider(
            "Ventana de Análisis (Días Históricos):",
            options=[30, 60, 90, 180, 365], value=60,
            help="Cuántos días hacia atrás miraremos para calcular la rotación."
        )

        bodegas_disponibles = sorted(df_stock['CodigoBodega'].dropna().unique())
        # Lógica de default robusta: solo usa los defaults que existen en los datos
        defaults_validos = [b for b in DEFAULT_BODEGAS if b in bodegas_disponibles]
        bodegas_sel = st.multiselect("Bodegas a analizar:", options=bodegas_disponibles, default=defaults_validos)

        familias_disponibles = sorted(df_stock['Familia'].dropna().unique())
        familias_sel = st.multiselect("Filtrar por Familia:", options=familias_disponibles)

        df_subfam = df_stock[df_stock['Familia'].isin(familias_sel)] if familias_sel else df_stock
        subfamilias_disponibles = sorted(df_subfam['SubFamilia'].dropna().unique())
        subfamilias_sel = st.multiselect("Filtrar por Subfamilia:", options=subfamilias_disponibles)

        st.divider()
        st.header("🔬 Filtros Visuales")
        salud_options = ["Todas"] + list(SALUD_CATEGORIES.keys())
        salud_sel = st.selectbox("Filtrar por Salud:", salud_options, help="Filtra los gráficos y la tabla por la categoría de rotación.")

    return {
        "dias": dias_analisis,
        "bodegas": bodegas_sel,
        "familias": familias_sel,
        "subfamilias": subfamilias_sel,
        "salud": salud_sel
    }

def categorizar_salud(doi):
    """Asigna una categoría de salud basada en los Días de Inventario (DOI)."""
    for categoria, (min_d, max_d) in SALUD_CATEGORIES.items():
        if min_d <= doi < max_d:
            return categoria
    return "4. Inmovilizado (>180d o Sin Mov.)"

def display_summary_kpis(df_reporte, dias_analisis):
    """Calcula y muestra los KPIs ejecutivos en la parte superior."""
    st.subheader("📊 Resumen Ejecutivo")
    col_salidas = f'Salidas_{dias_analisis}D'
    inv_total = df_reporte['Valor_Inventario'].sum()
    salidas_totales = df_reporte[col_salidas].sum()
    
    doi_general = (inv_total / salidas_totales) * dias_analisis if salidas_totales > 0 else 0
    rotacion_anual = 365 / doi_general if doi_general > 0 else 0

    limite_inmovilizado = SALUD_CATEGORIES["4. Inmovilizado (>180d o Sin Mov.)"][0]
    inv_inmovilizado = df_reporte[df_reporte['DOI'] >= limite_inmovilizado]['Valor_Inventario'].sum()
    pct_inmovilizado = (inv_inmovilizado / inv_total) * 100 if inv_total > 0 else 0

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Capital Invertido", f"${inv_total:,.0f}")
    k2.metric(f"Salidas ({dias_analisis}d)", f"${salidas_totales:,.0f}")
    k3.metric("DOI General", f"{doi_general:,.1f} días", help="Días que duraría el inventario actual a este ritmo.")
    k4.metric("Rotación Anual", f"{rotacion_anual:,.1f} v", help="Cuántas veces al año se renueva el inventario completo.")
    k5.metric("% Capital Inmovilizado", f"{pct_inmovilizado:.1f}%",
               help=f"Porcentaje del valor total del inventario que no ha rotado en {limite_inmovilizado}+ días.",
               delta_color="inverse")
    st.divider()

def render_visuals_tab(df_show):
    """Renderiza la pestaña de gráficos ejecutivos."""
    # FILA 1 DE GRÁFICOS
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("**Salud del Capital Invertido**")
        # Agrupamos el valor del inventario por estado de salud
        df_salud = df_show.groupby('Salud')['Valor_Inventario'].sum().reset_index()
        fig_pie = px.pie(
            df_salud, 
            values='Valor_Inventario', 
            names='Salud', hole=0.4, color='Salud',
            color_discrete_map=SALUD_COLORS
        )
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        fig_pie.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig_pie, use_container_width=True)
        st.caption("Distribución del dinero ($) según la velocidad de salida de los productos.")

    with c2:
        st.markdown("**Top 10 Artículos con Capital Inmovilizado**")
        limite_lento = SALUD_CATEGORIES["3. Lenta (90-180d)"][0]
        df_lentos = df_show[df_show['DOI'] >= limite_lento].nlargest(10, 'Valor_Inventario')
        
        if not df_lentos.empty:
            fig_bar = px.bar(
                df_lentos, 
                x='Valor_Inventario', 
                y='NombreArticulo', 
                orientation='h',
                text_auto='.2s',
                color='DOI',
                color_continuous_scale='Reds',
                hover_data={
                    "CodigoArticulo": True,
                    "Valor_Inventario": ":,.0f",
                    "DOI": ":.1f",
                    "Ultima_Salida": True
                }
            )
            fig_bar.update_layout(yaxis={'categoryorder':'total ascending'}, margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig_bar, use_container_width=True)
            st.caption("Productos de lenta rotación que retienen la mayor cantidad de capital.")
        else:
            st.success("¡Excelente! No tienes productos inmovilizados con alto valor.")

    st.divider()

    # FILA 2 DE GRÁFICOS
    st.markdown("**Matriz de Riesgo: Capital vs Días de Inventario (DOI)**")
    
    # Para el gráfico, limitamos el DOI a 365 días para que los "infinitos" no rompan la escala visual
    df_plot = df_show.copy()
    df_plot['DOI_Grafico'] = df_plot['DOI'].clip(upper=365)
    
    fig_scatter = px.scatter(
        df_plot[df_plot['Valor_Inventario'] > 0], # Solo mostramos los que tienen stock
        x='DOI_Grafico', 
        y='Valor_Inventario',
        color='Salud',
        size='Valor_Inventario', # El tamaño de la burbuja representa su valor
        hover_name='NombreArticulo', # El nombre aparece al pasar el mouse
        hover_data={'Valor_Inventario': ':,.0f', 'DOI': True, 'DOI_Grafico': False, 'Salud': False},
        color_discrete_map=SALUD_COLORS
    )
    
    # Añadimos líneas de referencia que dividen los cuadrantes
    promedio_inv = df_plot['Valor_Inventario'].mean()
    fig_scatter.add_hline(y=promedio_inv, line_dash="dot", annotation_text="Promedio Capital", annotation_position="top right")
    fig_scatter.add_vline(x=90, line_dash="dot", annotation_text="Límite Sano (90d)", annotation_position="top right")
    
    fig_scatter.update_layout(
        xaxis_title="Días de Inventario (DOI) - Tope visual en 365d",
        yaxis_title="Capital Invertido ($)",
        margin=dict(t=20, b=0, l=0, r=0)
    )
    st.plotly_chart(fig_scatter, use_container_width=True)
    st.info("💡 **Cómo leer la matriz:** Fíjate en el **Cuadrante Superior Derecho**. Son productos con MUCHO dinero invertido y MUCHOS días sin salir. ¡Ahí están las oportunidades de descuento o liquidación!")

def render_detail_tab(df_show, df_reporte, dias_analisis):
    """Renderiza la pestaña con la tabla de datos detallada."""
    st.info(f"Mostrando {len(df_show):,} de {len(df_reporte):,} artículos totales.")

    # Definir columnas dinámicamente
    col_salidas = f'Salidas_{dias_analisis}D'
    col_rotacion = f'Rotacion_{dias_analisis}D'

    st.dataframe(df_show,
                   column_config={
                       "CodigoArticulo": st.column_config.TextColumn("SKU", width="medium"),
                       "NombreArticulo": st.column_config.TextColumn("Artículo", width="large"),
                       "SubFamilia": st.column_config.TextColumn("Subfamilia"),
                       "Valor_Inventario": st.column_config.NumberColumn("Inventario ($)", format="$ %d"),
                       col_salidas: st.column_config.NumberColumn(f"Salidas {dias_analisis}d ($)", format="$ %d"),
                       col_rotacion: st.column_config.NumberColumn("Rotación", format="%.2f"),
                       "Rotacion_Anualizada": st.column_config.NumberColumn("Rot. Anual", format="%.2f"),
                       "DOI": st.column_config.NumberColumn("DOI (Días)", format="%.1f"),
                       "Ultima_Salida": st.column_config.DateColumn("Última Salida", format="DD/MM/YYYY"),
                       "Salud": st.column_config.TextColumn("Estado de Salud")
                   },
                   use_container_width=True, hide_index=True, height=500)

    csv = df_show.to_csv(index=False).encode('utf-8')
    st.download_button("💾 Descargar Reporte CSV", csv, "reporte_rotacion.csv", "text/csv")

def main():
    """Función principal que ejecuta la aplicación Streamlit."""
    # --- Validación de Datos ---
    if 'df_stock' not in st.session_state or 'df_historia_full' not in st.session_state:
        st.error("⚠️ Faltan datos (Stock o Movimientos). Asegúrate de cargarlos en el inicio.")
        st.stop()

    # --- Renderizar UI y obtener filtros ---
    params = render_sidebar(st.session_state.df_stock)

    if not params["bodegas"]:
        st.warning("👈 Selecciona al menos una bodega para analizar.")
        st.stop()

    # --- Filtrado de datos previo a la ejecución del motor ---
    df_stock_filtrado = st.session_state.df_stock
    df_historia_filtrado = st.session_state.df_historia_full

    if params["familias"]:
        df_stock_filtrado = df_stock_filtrado[df_stock_filtrado['Familia'].isin(params["familias"])]
        df_historia_filtrado = df_historia_filtrado[df_historia_filtrado['Familia'].isin(params["familias"])]

    if params["subfamilias"]:
        df_stock_filtrado = df_stock_filtrado[df_stock_filtrado['SubFamilia'].isin(params["subfamilias"])]
        df_historia_filtrado = df_historia_filtrado[df_historia_filtrado['SubFamilia'].isin(params["subfamilias"])]

    # --- Ejecución del motor de análisis ---
    with st.spinner("Calculando velocidad de inventario..."):
        df_reporte = analysis.generar_reporte_inventario(
            df_historia_filtrado,
            df_stock_filtrado,
            dias=params["dias"],
            bodegas=params["bodegas"]
        )

    # --- Preparación de datos para visualización ---
    df_show = df_reporte.copy()
    df_show['DOI'] = df_show['DOI'].replace(np.inf, 9999) # Reemplaza infinitos para graficar
    df_show['Salud'] = df_show['DOI'].apply(categorizar_salud)

    if params["salud"] != "Todas":
        df_show = df_show[df_show['Salud'] == params["salud"]]

    # --- Renderizado del cuerpo principal ---
    display_summary_kpis(df_show, params["dias"])

    tab_graficos, tab_tabla = st.tabs(["📈 Dashboard Ejecutivo", "📋 Detalle por Artículo"])

    with tab_graficos:
        render_visuals_tab(df_show)

    with tab_tabla:
        render_detail_tab(df_show, df_reporte, params["dias"])

if __name__ == "__main__":
    main()