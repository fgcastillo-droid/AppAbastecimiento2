SELECT
    -- TIEMPO
    TO_VARCHAR(T0."DocDate", 'YYYY-MM-DD') AS "fecha",

    -- ARTÍCULO
    T0."ItemCode" AS "CodigoArticulo",
    T0."Dscription" AS "NombreArticulo",
    T1."U_Familia" AS "Familia",       
    T1."U_SubFamilia" AS "SubFamilia",  
    
    -- UBICACIÓN
    T0."Warehouse" AS "CodigoBodega",

    -- MOVIMIENTOS
    SUM(T0."InQty" - T0."OutQty") AS "CantidadMovimiento",
    SUM(T0."TransValue") AS "ValorMovimiento"

FROM 
    OINM T0
    INNER JOIN OITM T1 ON T0."ItemCode" = T1."ItemCode"

WHERE
    -- === EL FILTRO DE TUS BODEGAS ESPECÍFICAS ===
    T0."Warehouse" IN ('BF0001', 'BF0008', 'BF0009', 'BFT0001', 'BF0004')
    AND T1."ItmsGrpCod" = 112 -- para que solo sean existencias
    
    AND T0."DocDate" >= ADD_YEARS(CURRENT_DATE, -4) -- Son los últimos 4 años de historia, pero puede generar problemas a futuro si se filtra después del inicio de SAP

GROUP BY
    TO_VARCHAR(T0."DocDate", 'YYYY-MM'),
    YEAR(T0."DocDate"),
    MONTH(T0."DocDate"),
    T0."ItemCode",
    T0."Dscription",
    T1."U_Familia",
    T1."U_SubFamilia",
    T0."Warehouse",
    T0."DocDate"

ORDER BY
    "fecha" ASC