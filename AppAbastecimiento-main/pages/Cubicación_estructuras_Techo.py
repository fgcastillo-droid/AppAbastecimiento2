import streamlit as st
import pandas as pd
import io

# --- 1. CLASE DE LÓGICA ---
class GestorAbastecimientoStreamlit:
    def __init__(self, archivo_excel):
        self.archivo_excel = archivo_excel
        self.df_proyectos = None
        self.df_skus = None
        self.resultado_detalle = None
        self.resumen_skus = None
        self.matriz_distribucion = None
        self.viabilidad_proyectos = None
        self.df_evolucion = None

    def cargar_datos(self):
        try:
            self.df_proyectos = pd.read_excel(self.archivo_excel, sheet_name='Necesidad')
            self.df_skus = pd.read_excel(self.archivo_excel, sheet_name='Evolucion')

            # Normalizar columnas
            self.df_proyectos.columns = self.df_proyectos.columns.str.strip()
            self.df_skus.columns = self.df_skus.columns.str.strip()

            # Validación básica
            req_proy = {'Proyecto', 'Kwp'}
            req_sku = {'SKU', 'Desc.', 'Stock', 'Uso'}
            
            if not req_proy.issubset(self.df_proyectos.columns):
                st.error(f"Faltan columnas en 'Necesidad'. Se requiere: {req_proy}")
                return False
            if not req_sku.issubset(self.df_skus.columns):
                st.error(f"Faltan columnas en 'Evolucion'. Se requiere: {req_sku}")
                return False
            
            return True
        except Exception as e:
            st.error(f"Error al leer el Excel: {e}")
            return False

    def calcular_todo(self):
        """Ejecuta toda la lógica de cálculo secuencialmente"""
        
        # 1. Calcular Requerimientos
        df_cross = self.df_proyectos.merge(self.df_skus, how='cross')
        df_cross['Cantidad_Requerida'] = df_cross['Kwp'] * df_cross['Uso']
        self.resultado_detalle = df_cross[df_cross['Cantidad_Requerida'] > 0].copy()
        
        # Reordenamos columnas si existen
        cols_ideales = ['Proyecto', 'Kwp', 'SKU', 'Desc.', 'Uso', 'Cantidad_Requerida', 'Stock']
        cols_existentes = [c for c in cols_ideales if c in self.resultado_detalle.columns]
        self.resultado_detalle = self.resultado_detalle[cols_existentes]

        # 2. Analizar Stock Global
        resumen = self.resultado_detalle.groupby(['SKU', 'Desc.', 'Stock'])['Cantidad_Requerida'].sum().reset_index()
        resumen.rename(columns={'Cantidad_Requerida': 'Demanda_Total'}, inplace=True)
        resumen['Balance'] = resumen['Stock'] - resumen['Demanda_Total']
        resumen['Estado'] = resumen['Balance'].apply(lambda x: 'COMPRAR' if x < 0 else 'OK')
        self.resumen_skus = resumen.sort_values('Estado')

        # 3. Matriz Cruzada
        self.matriz_distribucion = self.resultado_detalle.pivot_table(
            index=['SKU', 'Desc.'], columns='Proyecto', values='Cantidad_Requerida', aggfunc='sum', fill_value=0
        )

        # 4. Viabilidad en Cascada
        stock_virtual = dict(zip(self.df_skus['SKU'], self.df_skus['Stock']))
        historial_stock = []
        
        estado_inicial = stock_virtual.copy()
        estado_inicial['Proyecto'] = '0. STOCK INICIAL'
        estado_inicial['Estado_Asignacion'] = 'Inicio'
        historial_stock.append(estado_inicial)
        
        df_ordenados = self.df_proyectos.sort_values(by='Kwp', ascending=True)
        proyectos_unicos = df_ordenados['Proyecto'].unique()
        
        resultados_simulacion = []

        for proyecto in proyectos_unicos:
            kwp_proyecto = df_ordenados[df_ordenados['Proyecto'] == proyecto]['Kwp'].iloc[0]
            materiales = self.resultado_detalle[self.resultado_detalle['Proyecto'] == proyecto]
            
            es_viable = True
            motivo = ""
            
            for _, row in materiales.iterrows():
                if stock_virtual.get(row['SKU'], 0) < row['Cantidad_Requerida']:
                    es_viable = False
                    motivo = "Genera Saldo Negativo"
                    break 
            
            estado = "VIABLE" if es_viable else "NO VIABLE (Déficit)"

            for _, row in materiales.iterrows():
                stock_virtual[row['SKU']] -= row['Cantidad_Requerida']

            snapshot = stock_virtual.copy()
            snapshot['Proyecto'] = proyecto
            snapshot['Estado_Asignacion'] = estado
            historial_stock.append(snapshot)

            resultados_simulacion.append({
                'Proyecto': proyecto, 'Kwp': kwp_proyecto, 
                'Estado_Simulacion': estado, 'Detalle_Critico': motivo
            })
            
        self.viabilidad_proyectos = pd.DataFrame(resultados_simulacion)
        
        df_temp = pd.DataFrame(historial_stock)
        df_temp.set_index(['Proyecto', 'Estado_Asignacion'], inplace=True)
        df_temp = df_temp.reindex(sorted(df_temp.columns), axis=1)
        
        mapa_desc = dict(zip(self.df_skus['SKU'], self.df_skus['Desc.']))
        nuevos_encabezados = []
        for col in df_temp.columns:
            desc = mapa_desc.get(col, "Sin Desc.")
            nuevos_encabezados.append((desc, col))
        
        df_temp.columns = pd.MultiIndex.from_tuples(nuevos_encabezados)
        self.df_evolucion = df_temp

    def obtener_excel_en_memoria(self):
        output = io.BytesIO()
        # Nota: Si no tienes xlsxwriter instalado, cambia engine='xlsxwriter' por engine='openpyxl'
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            self.resultado_detalle.to_excel(writer, sheet_name='Detalle', index=False)
            self.resumen_skus.to_excel(writer, sheet_name='Analisis_Stock', index=False)
            self.viabilidad_proyectos.to_excel(writer, sheet_name='Viabilidad', index=False)
            self.df_evolucion.to_excel(writer, sheet_name='Evolucion_Saldo')
        return output.getvalue()

# --- 2. INTERFAZ DE STREAMLIT ---

st.set_page_config(page_title="Simulador de Abastecimiento", layout="wide")

st.title("🏭 Simulador de Stock por Proyectos")
st.markdown("""
Sube tu archivo Excel con las hojas **'Necesidad'** (Proyectos y kWp) y **'Evolucion'** (SKU, Stock y Uso).
El sistema calculará si el stock actual es suficiente para cubrir los proyectos en orden de tamaño.
""")

# A. Carga de Archivo
uploaded_file = st.file_uploader("Cargar Excel de Planificación", type=["xlsx"])

if uploaded_file:
    # Instanciar lógica
    gestor = GestorAbastecimientoStreamlit(uploaded_file)
    
    if gestor.cargar_datos():
        st.success("✅ Datos cargados correctamente.")
        st.markdown("---")
        
        # B. Edición Interactiva (PROYECTOS Y SKUS)
        st.subheader("🛠️ Ajuste de Parámetros")
        
        col_proy, col_sku = st.columns(2)
        
        with col_proy:
            st.markdown("##### 1. Ajustar Proyectos (kWp)")
            st.caption("Modifica la potencia de los proyectos aquí:")
            # Editor para la tabla de Proyectos
            gestor.df_proyectos = st.data_editor(
                gestor.df_proyectos, 
                num_rows="dynamic",
                key="editor_proyectos"
            )
            
        with col_sku:
            st.markdown("##### 2. Ajustar Materiales (Uso y Stock)")
            st.caption("Modifica el ratio de 'Uso' o el 'Stock' inicial:")
            # Editor para la tabla de SKUs (Materiales)
            gestor.df_skus = st.data_editor(
                gestor.df_skus, 
                num_rows="dynamic",
                key="editor_skus"
            )

        st.markdown("---")

        # C. Botón de Simulación
        if st.button("🚀 Ejecutar Simulación de Stock", type="primary"):
            with st.spinner("Calculando viabilidad y matrices..."):
                gestor.calcular_todo()
            
            # D. Mostrar Resultados en Pestañas
            tab1, tab2, tab3, tab4 = st.tabs(["🚦 Viabilidad Proyectos", "📉 Evolución Stock", "📦 Resumen SKUs", "🔍 Detalle Cálculo"])
            
            with tab1:
                st.subheader("Resultado de Viabilidad (Ordenado por kWp)")
                def color_viabilidad(val):
                    color = '#ffc9c9' if 'NO VIABLE' in str(val) else '#c9ffc9'
                    return f'background-color: {color}'
                
                st.dataframe(gestor.viabilidad_proyectos.style.applymap(color_viabilidad, subset=['Estado_Simulacion']), use_container_width=True)
                
                metricas = gestor.viabilidad_proyectos['Estado_Simulacion'].value_counts()
                col1, col2 = st.columns(2)
                col1.metric("Proyectos Viables", metricas.get("VIABLE", 0))
                col2.metric("Proyectos con Déficit", metricas.get("NO VIABLE (Déficit)", 0))

            with tab2:
                st.subheader("Evolución del Stock (Cascada)")
                st.caption("Muestra cómo queda el stock de cada SKU después de asignar cada proyecto.")
                st.dataframe(gestor.df_evolucion, height=400, use_container_width=True)

            with tab3:
                st.subheader("Análisis Global de Materiales")
                comprar = gestor.resumen_skus[gestor.resumen_skus['Estado'] == 'COMPRAR']
                if not comprar.empty:
                    st.warning(f"⚠️ Se requiere comprar {len(comprar)} SKUs distintos.")
                    st.dataframe(comprar, use_container_width=True)
                else:
                    st.success("El stock cubre toda la demanda global.")
                
                with st.expander("Ver todos los materiales"):
                    st.dataframe(gestor.resumen_skus, use_container_width=True)

            with tab4:
                st.dataframe(gestor.resultado_detalle, use_container_width=True)

            # E. Botón de Descarga
            st.markdown("---")
            excel_data = gestor.obtener_excel_en_memoria()
            st.download_button(
                label="📥 Descargar Reporte Completo en Excel",
                data=excel_data,
                file_name="Simulacion_Abastecimiento.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )