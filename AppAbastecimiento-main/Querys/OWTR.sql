SELECT
    -- 1. INFORMACIÓN DEL DOCUMENTO DE SOLICITUD
    T0."DocNum" AS "NumSolicitud",
    T0."DocDate" AS "FechaSolicitud",
    T8."U_NAME" AS "SolicitadoPor",
    

    -- 3. DETALLE DEL ARTÍCULO SOLICITADO
    T1."ItemCode" AS "CodigoArticulo",
    T2."ItemName" AS "NombreArticulo",
    T3."ItmsGrpNam" AS "GrupoArticulo",
    
    -- === CAMBIO 2: CAMPO U_Familia ===
    T2."U_Familia" AS "Familia_Articulo", -- Campo 'Familia' del maestro de artículos.
    T2."U_SubFamilia" AS "SubFamilia",

    -- 4. DETALLE DEL MOVIMIENTO REQUERIDO
    T1."Quantity" AS "CantidadSolicitada",
    T4."WhsName" AS "BodegaOrigen_Solicitada",
    T5."WhsName" AS "BodegaDestino_Requerida",

    -- 5. VALORIZACIÓN ESTIMADA DE LA SOLICITUD
    CASE T2."EvalSystem"
        WHEN 'A' THEN T_StockOrigen."AvgPrice" -- Promedio Móvil (de OITW Origen)
        WHEN 'S' THEN T2."AvgPrice"            -- Costo Estándar (de OITM)
        ELSE 0
    END AS "CostoUnitarioEstimado",

    (T1."Quantity" *
        CASE T2."EvalSystem"
            WHEN 'A' THEN T_StockOrigen."AvgPrice"
            WHEN 'S' THEN T2."AvgPrice"
            ELSE 0
        END
    ) AS "ValorTotalSolicitado",

    -- 6. DIMENSIONES DE NEGOCIO (PROYECTO Y UNIDAD DE NEGOCIO)
    T1."Project" AS "CodigoProyecto",
    T6."PrjName" AS "NombreProyecto",
    T1."OcrCode" AS "CodigoUnidadNegocio",
    T7."OcrName" AS "NombreUnidadNegocio"

FROM
    WTR1 AS T1 -- T1: Líneas de la Solicitud de Traslado (el corazón)
    INNER JOIN OWTR AS T0 ON T1."DocEntry" = T0."DocEntry"      -- T0: Cabecera de la Solicitud
    
    -- Se cambió a INNER JOIN para asegurar que solo se procesen líneas
    -- con artículos que existen y sobre los cuales podemos filtrar.
    INNER JOIN OITM AS T2 ON T1."ItemCode" = T2."ItemCode"      -- T2: Maestro de Artículos
    
    LEFT JOIN OITB AS T3 ON T2."ItmsGrpCod" = T3."ItmsGrpCod"  -- T3: Grupos de Artículos
    LEFT JOIN OWHS AS T4 ON T1."FromWhsCod" = T4."WhsCode"      -- T4: Nombres de Bodega Origen
    LEFT JOIN OWHS AS T5 ON T1."WhsCode" = T5."WhsCode"        -- T5: Nombres de Bodega Destino
    LEFT JOIN OPRJ AS T6 ON T1."Project" = T6."PrjCode"        -- T6: Nombres de Proyectos
    LEFT JOIN OOCR AS T7 ON T1."OcrCode" = T7."OcrCode"        -- T7: Nombres de Dimensiones 1 (UN)
    LEFT JOIN OUSR AS T8 ON T0."UserSign" = T8."USERID"        -- T8: Nombres de Usuarios
    
    -- Unión clave para ver el stock actual en la bodega de origen
    LEFT JOIN OITW AS T_StockOrigen ON T1."ItemCode" = T_StockOrigen."ItemCode" AND T1."FromWhsCod" = T_StockOrigen."WhsCode" -- ve el stock actual a día de hoy 

WHERE
    T2."validFor" = 'Y' -- Filtra solo por artículos marcados como 'Activo'
    AND T2."U_Familia" = 'EQUIPOS PRINCIPALES' --Solo los equipos que nos importan
    AND T2."ItemName" NOT LIKE '%Tablero%'
    AND T2."LastPurDat" >= ADD_YEARS(CURRENT_DATE, -1) -- vemos los últimos 12 meses
    AND T4."WhsName" = 'Bodega Fluxsolar'
    AND T5."WhsName" NOT IN ('Bodega Fluxsolar', 'Bodega Liquidación - Flux') -- no vemos las entradas a estas bodegas
ORDER BY
    T0."DocDate" ASC;            -- Dentro de las pendientes, muestra las más antiguas primero