# --- ARCHIVO: src/config.py ---
# (El contenido es el mismo, solo cambia su ubicación)

import pandas as pd
import os


BASE_URL = "https://data-api-f7y55nboxq-uc.a.run.app"
CLIENT_ID = os.getenv("API_CLIENT_ID", "abastecimiento_app")
CLIENT_SECRET = os.getenv("API_CLIENT_SECRET", "") # ⚠️ Evitar hardcodear contraseñas


# --- Constantes Globales ---
AVERAGE_DAYS_PER_MONTH = 30.4375
LOCALE_ES = 'es_ES.UTF-8' # Para nombres de meses en español
LOCALE_ES_FALLBACK = 'Spanish_Spain.1252'

# --- Parámetros de Simulación ---
Z_SCORE_MAP = {
    "90%": 1.28, 
    "95%": 1.65, 
    "98%": 2.05, 
    "99%": 2.33
}

# --- Mapeo de SKUs (Homogenización) ---
MAPEO_SKUS = {
    # Grupo 1 (SKUs -> EXI-009231) Inversores 1P5kw Hibrido
    'EXI-008656': 'EXI-009231', #5K ANTERIOR POR EL NUEVO
    #'EXI-008391': 'EXI-009231', # de 3.6 por 5k
    'EXI-008391': 'EXI-009287', # 3.6 POR 3.6 NUEVO
    #'EXI-009287': 'EXI-009231', # de 3.6k por 5k
    
    ######################### Paneles ##########################################
    # Grupo 2 (SKUs -> EXI-009545) Paneles black
    'EXI-008842': 'EXI-008805',
    'EXI-008844': 'EXI-008805',
    'EXI-008805': 'EXI-009545',
    # Panel 650 BIFACIAL EXI-009392
    'EXI-009168': 'EXI-009392',
    'EXI-009275': 'EXI-009392',
    'EXI-008870': 'EXI-009392',
    'EXI-009158': 'EXI-009392',
    'EXI-009477': 'EXI-009392',
    'EXI-008853': 'EXI-009392',
    'EXI-008848': 'EXI-009392',
    'EXI-008853': 'EXI-009392',
    #'EXI-008852': 'EXI-009392', # 570 bifa a 650
    'EXI-008851': 'EXI-009392',
    # (SKUs -> EXI-009672) Paneles blue 595 bifaciales
    'EXI-008854': 'EXI-009672', # de 580
    'EXI-008854': 'EXI-009672', # de 580
    'EXI-009216': 'EXI-009672', # 595 monofaciales

    ################### Inversores #################################################
    # inversores ongrid 1p5kw solis EXI-008660 
    'EXI-007037': 'EXI-008660', # huawei anterior 5Kw
    #Inversores 25KTL HUAWEI C&I
    'EXI-006082': 'EXI-009219', # huawei anterior 25Kw
    # Inversores 8k hibridos monofasicos
    'EXI-008657': 'EXI-009234', # sku anterior
    'EXI-008381': 'EXI-009234', # sku anterior
    #Inversores 6k 008525
    'EXI-008655': 'EXI-009233', # solis 6k
    'EXI-006043': 'EXI-009233', # solis 6k
    #Inversor 10k hibrido trifásico
    'EXI-008389' :'EXI-009288',
    'EXI-008940': 'EXI-008659', # Inversores OnGrid 3.6 Solis
    #Inversores Solis Ongrid a Huawei solicitado por fernando
    #'EXI-008659':'EXI-008567',   # 3.6k / 4k
    #'EXI-008658': 'EXI-007645',  # 3k
    #'EXI-008660': 'EXI-007037', # 5k
    #'EXI-008661': 'EXI-008525',# 6k

    ############################## Baterias ####################################### 
    # 5wkp Soluna
    'EXI-006594': 'EXI-009496', # huawei anterior 5Kw


    # Estructuras techo residencial
    'EXI-003415': 'EXI-009538', #Hp Kit De Grapa Final/Intermedia 28-40Mm, Ult
    'EXI-003417': 'EXI-009536', # Conector para perfil
    'EXI-003418': 'EXI-009540', # Grapa para perfil
    'EXI-003419': 'EXI-009535', # Perfil
    'EXI-003423': 'EXI-009539', # placa puesta a tierra
    'EXI-004010': 'EXI-009537',  # gancho tipo L
    'EXI-003421': 'EXI-009533', # Sistema inclinado
    'EXI-003422': 'EXI-009534', # Terminal
    'EXI-007214': 'EXI-009542', # grapa fijación emballetado 01
    'EXI-009107': 'EXI-009538' # Hp Kit De Grapa Final/Intermedia 28-40Mm, Ult
}



#cambio de skus para los stocks
#SOLUNA PANAMA
MAPEO_SKUS_STOCK = {"EXI-006594": "EXI-009496", # sku soluna 5k
                    "EXI-008940": "EXI-008659",
                    'EXI-009216': 'EXI-009672' # 595 MONO POR BIFACIAL 
                    }

# --- Metas de KPIs ---
KPI_TARGETS = {
    "FILL_RATE": 95.0,
    "MIN_WEEKS_SUPPLY": 4.0, # Lead time de seguridad
    "MAX_WEEKS_SUPPLY": 24.0 # Medio año
}

# --- Columnas Clave (Para estandarizar nombres) ---
COLS = {
    "SKU": "CodigoArticulo",
    "STOCK": "OnHand",
    "REQ_QTY": "Cantidad",
    "OPEN_QTY": "CantidadPendiente",
    "OWTQ": "Nº Solicitud"
}

# --- Identificadores de Google Sheets ---
GSHEET_IDS = {
    "RESIDENCIAL": "1pbRdmdZugz48B8jmI4Rjr6po31UNSqzj5vQdqW2lHpc",
    "CONSUMO": "1GiUDz80vKFz5rpJQUR-prtL_pDjiVXv8mU725tFmNFw",
    "STOCK": "111m-HitHGo-24wMFqGBbX1chtJ6RnPv27xP08PRYx9w",
    "OINM": "1Kgj6cDs7CaEXGgxhVnQxgDuIK4TQbYkDjy7RNFVlfUE",
    "LLEGADAS": "1PLJAYSXQEIVxNcTw25uGEjbC2sLhM7SaWilmKi_Wdl4",
    "ST": "1Sai0UH9kiQpcfcOA4ovPHLyt1xoN7JeT2UHQQ0-SGm4",
    "REQUERIMIENTOS": "12e1yaBaQG1LZ2xl9CxkurKSTF5iaHgQ7NlxE7hp_Eh0",
    "CI": "1bKqzpCvjlPD5pNROqR4JBeBEMX6SI7ebI7kobQL2OtE"
}