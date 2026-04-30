SELECT
    T0."DocNum" AS "Nº Solicitud",
    T0."DocDate" AS "Fecha Solicitud",
    T0."DocDueDate" AS "Fecha Necesaria",
    
    -- ACTORES
    T0."ReqName" AS "Solicitante",
    T4."U_NAME" AS "Usuario Creador",

    -- DETALLE
    T1."ItemCode" AS "Código Artículo",
    T1."Dscription" AS "Descripción",
    T5."ItmsGrpNam" AS "Grupo Artículo", -- Ahora sí traerá el dato correcto

    -- CANTIDADES
    T1."Quantity" AS "Cant. Original",
    T1."OpenQty" AS "Cant. Pendiente",

    -- DINERO
    T1."Price" AS "Precio Estimado",
    T1."Currency" AS "Moneda",
    (T1."OpenQty" * T1."Price") AS "Monto Pendiente Estimado",

    -- CONTEXTO
    T6."PrjName" AS "Proyecto",
    T0."Comments" AS "Comentarios"

FROM "OPRQ" T0
INNER JOIN "PRQ1" T1 ON T0."DocEntry" = T1."DocEntry"
LEFT JOIN "OCRD" T3 ON T1."LineVendor" = T3."CardCode"
INNER JOIN "OUSR" T4 ON T0."UserSign" = T4."USERID"

LEFT JOIN "OITM" T7 ON T1."ItemCode" = T7."ItemCode"
LEFT JOIN "OITB" T5 ON T7."ItmsGrpCod" = T5."ItmsGrpCod" 

LEFT JOIN "OPRJ" T6 ON T1."Project" = T6."PrjCode"

WHERE T1."LineStatus" = 'O'
ORDER BY T0."DocNum" DESC