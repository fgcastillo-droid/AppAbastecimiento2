# **Documentación Técnica: AppAbastecimiento**

Versión: 1.0.0  
Tecnología: Python 3.13+, Streamlit, Pandas  
Propósito: Herramienta de Planificación de Abastecimiento (Supply Planning) y Gestión de Inventario.

## **1\. Visión General del Proyecto**

La **AppAbastecimiento** es una solución analítica interactiva diseñada para optimizar la gestión de inventarios. Su objetivo principal es transformar datos transaccionales (Stock, Consumo Histórico, Órdenes de Compra) en indicadores clave de desempeño (KPIs) accionables para prevenir quiebres de stock y sobre-stock.

### **Funcionalidades Principales**

* **Radar de Inventario:** Detección masiva de SKUs críticos basada en proyecciones de demanda y tiempos de entrega (Lead Time).  
* **Carga Centralizada de Datos:** Ingesta y limpieza automatizada de archivos Excel maestros.  
* **Simulación de Escenarios:** Ajuste dinámico de parámetros de negocio (Nivel de Servicio, Lead Time) en tiempo real.

## **2\. Arquitectura del Sistema**

La aplicación sigue una arquitectura modular basada en **Streamlit Multipage Apps**, separando claramente la interfaz de usuario (Frontend) de la lógica de negocio (Backend).

### **Estructura de Directorios**

AppAbastecimiento/  
├── Menu.py                  \# Punto de entrada principal (Landing Page).  
├── pages/                   \# Módulos de Interfaz de Usuario (Vistas).  
│   ├── radar.py             \# Vista del Radar de Inventario.  
│   ├── Simulador.py         \# Vista de Simulación de compras.  
│   ├── ConsultaStock.py     \# Consulta rápida de disponibilidad.  
│   └── ...  
├── src/                     \# Lógica de Negocio y Procesamiento de Datos.  
│   ├── radar\_engine.py      \# Motor matemático de cálculo de KPIs.  
│   ├── data\_loader.py       \# ETL: Extracción, Transformación y Carga.  
│   ├── config.py            \# Constantes globales y parámetros de configuración.  
│   └── ui\_helpers.py        \# Componentes visuales reutilizables.  
└── data/                    \# Almacenamiento de fuentes de datos (Excel/CSV).

## **3\. Módulos del Sistema**

### **3.1. Motor de Datos (src/data\_loader.py)**

Este módulo es responsable de la integridad de los datos. Utiliza el decorador @st.cache\_data para optimizar el rendimiento, cargando los datos en memoria solo una vez.

* **Fuentes de Datos:**  
  * Stock.xlsx: Inventario físico actual.  
  * ST\_OWTR.xlsx: Historial de traslados/consumo.  
  * OPOR.xlsx: Órdenes de compra (tránsito).  
* **Procesos de Limpieza:**  
  * Conversión de fechas al formato datetime estándar.  
  * Filtrado de registros históricos obsoletos (\> 5 meses).  
  * Homologación de SKUs antiguos a nuevos utilizando mapas de reemplazo definidos en config.py.

### **3.2. Motor de Radar (src/radar\_engine.py)**

Es el núcleo analítico de la aplicación. Procesa cada SKU individualmente para calcular su salud de inventario.

**Algoritmos Clave:**

1. Días de Cobertura (DOS):  
   $$DOS = \frac{\text{Stock Actual}}{\text{Demanda Promedio Diaria}}$$  

2. Stock de Seguridad (SS):  
   Calculado bajo un modelo de distribución normal para cubrir la variabilidad de la demanda durante el tiempo de entrega.  
   $$SS \= Z \\times \\sigma\_d \\times \\sqrt{LT}$$  
   * $Z$: Factor de servicio (ej. 1.65 para 95%).  
   * $\\sigma\_d$: Desviación estándar de la demanda diaria.  
   * $LT$: Lead Time (tiempo de entrega) en días.  
3. Punto de Reorden (ROP):  
   $$ROP \= (\\text{Demanda Promedio} \\times LT) \+ SS$$  
4. Stock Proyectado:  
   Simula el nivel de inventario futuro al momento de llegada de una nueva orden si se pidiera hoy.  
   $$\\text{Proyección} \= \\text{Stock Actual} \+ \\text{Tránsito (en LT)} \- \\text{Demanda (en LT)}$$

### **3.3. Configuración Global (src/config.py)**

Centraliza las reglas de negocio para facilitar cambios sin tocar el código fuente.

* **Mapeo de Z-Score:** Define los valores estadísticos para niveles de servicio del 90% al 99%.  
* **Homologación de SKUs:** Diccionarios para unificar códigos de productos que han cambiado de nombre.

## **4\. Guía de Instalación y Despliegue**

### **Requisitos Previos**

* Python 3.10 o superior.  
* Bibliotecas listadas en requirements.txt (pandas, streamlit, numpy, openpyxl).

### **Pasos para Ejecutar**

1. **Clonar el repositorio** o descargar el código fuente.  
2. **Instalar dependencias:**  
   pip install \-r requirements.txt

3. Preparar Datos:  
   Asegurar que los archivos Excel fuente (Stock.xlsx, OPOR.xlsx, etc.) estén ubicados en la carpeta data/.  
4. **Iniciar la Aplicación:**  
   streamlit run Menu.py

## **5\. Flujo de Trabajo del Usuario (Radar)**

1. Selección de Parámetros:  
   El usuario selecciona una familia de productos (ej. "Inversores"), define el Lead Time (días proveedor) y el Nivel de Servicio deseado en la barra lateral o panel superior.  
2. Procesamiento:  
   El sistema ejecuta run\_full\_radar\_analysis, iterando sobre los SKUs filtrados.  
3. Análisis Visual:  
   Se presenta una tabla interactiva con alertas visuales:  
   * 🔴 **Alerta Crítica:** Stock Proyectado \< ROP (Riesgo inminente de quiebre).  
   * 🟢 **Saludable:** Niveles óptimos de inventario.  
4. Exportación:  
   Los resultados calculados se pueden descargar en formato CSV para gestión de compras en el ERP.

Autoría: Generado automáticamente para el proyecto AppAbastecimiento.  
Fecha: Noviembre 2025\.