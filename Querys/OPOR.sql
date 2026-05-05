SELECT
    T0."DocNum" AS "Número de documento",        -- Número visible de la Orden de Compra.
    T0."DocDate" AS "Fecha de contabilización" ,       -- Fecha de creación (contabilización).
    T0."CardName" AS "Nombre de cliente/proveedor",      -- Nombre del Proveedor.
    T1."ItemCode" AS "Número de artículo" ,      -- Código del artículo.
    T1."Dscription" AS "Descripción artículo/serv.",    -- Descripción del artículo.
    T2."U_Familia" AS "Familia_Articulo", -- Campo de usuario 'Familia'.
    T2."U_SubFamilia" AS "SubFamilia",
    T1."Quantity" AS "Cantidad",      -- Cantidad total pedida.
    
    -- Campos monetarios
    T1."Price" AS "Precio_Unitario",
    T1."LineTotal" AS "Total_Linea",
    
    T1."OpenQty" AS "Cantidad abierta restante",       -- Cantidad pendiente.
    T1."OpenSum" AS "Total_Pendiente", -- Valor pendiente.
    
    T0."U_EXX_FE_Fecha" AS "Fecha de entrega de la línea", 
    T1."LineStatus",    -- Estado de la línea.
    T3."U_NAME" AS "Creador", 
    LEFT(T0."Comments", 2000) AS "Comentarios"
    
FROM OPOR T0 
    INNER JOIN POR1 T1 ON T0."DocEntry" = T1."DocEntry"
    INNER JOIN OITM T2 ON T1."ItemCode" = T2."ItemCode"
    LEFT JOIN OUSR T3 ON T0."UserSign" = T3."USERID"

WHERE
    -- === NUEVO FILTRO: Excluir las Órdenes de Compra Canceladas ===
    T0."CANCELED" = 'N' 
    -- === NUEVO FILTRO: Exigir que la fecha de entrega exista ===    
    -- AND T0."U_EXX_FE_Fecha" IS NOT NULL

    AND T2."validFor" = 'Y'  -- Filtra solo artículos activos
    AND T2."U_Familia" = 'EQUIPOS PRINCIPALES'
    AND T2."ItemName" NOT LIKE '%Tablero%'
    AND (T1."DocDate" >= ADD_YEARS(CURRENT_DATE, -1) ) -- OC más antigua de un año, sino no aparece
    
ORDER BY 
    "Fecha de entrega de la línea" ASC;