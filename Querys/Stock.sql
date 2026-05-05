SELECT
    
    T1."ItemCode" AS "CodigoArticulo",
    T1."ItemName" AS "NombreArticulo",
    T3."ItmsGrpNam" AS "GrupoArticulo",
    T0."WhsCode" AS "CodigoBodega",
    T2."WhsName" AS "NombreBodega",
    T1."U_Familia" AS "Familia",
    T1."U_SubFamilia" AS "SubFamilia",
    
    T0."OnHand" AS "StockActual",
    T0."IsCommited" AS "Comprometido",
    T0."OnOrder" AS "EnPedido_a_Proveedor",
    (T0."OnHand" - T0."IsCommited") AS "DisponibleParaPrometer",

    
    CASE T1."EvalSystem"
        WHEN 'A' THEN T0."AvgPrice" -- Promedio Móvil (costo por bodega)
        WHEN 'S' THEN T1."AvgPrice" -- Costo Estándar (costo por artículo)
        ELSE 0
    END AS "CostoUnitario",

    (T0."OnHand" *
        CASE T1."EvalSystem"
            WHEN 'A' THEN T0."AvgPrice"
            WHEN 'S' THEN T1."AvgPrice"
            ELSE 0
        END
    ) AS "ValorTotalInventario"


FROM
    OITW AS T0 -- T0: Tabla central de Stock por Bodega (Hechos)
    INNER JOIN OITM AS T1 ON T0."ItemCode" = T1."ItemCode" -- T1: Maestro de Artículos (Dimensión)
    LEFT JOIN OWHS AS T2 ON T0."WhsCode" = T2."WhsCode"    -- T2: Maestro de Bodegas (Dimensión)
    LEFT JOIN OITB AS T3 ON T1."ItmsGrpCod" = T3."ItmsGrpCod"  -- T3: Maestro de Grupos de Artículos (Dimensión)

WHERE
    T1."InvntItem" = 'Y'  -- Muestra solo artículos que son gestionados por inventario (excluye servicios).
    AND T1."ItmsGrpCod" = 112 -- para que solo sean existencias
    AND T0."WhsCode" IN ('BF0001', 'BF0008', 'BF0009', 'BFT0001', 'BF0004') -- Selección de bodegas consideradas para gestión de inventario
ORDER BY
    "ValorTotalInventario" DESC; -- Ordena para mostrar primero dónde tienes más capital invertido.