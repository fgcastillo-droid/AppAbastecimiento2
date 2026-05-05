SELECT
    T0."DocNum" AS "Nº Solicitud",
    T0."DocDate" AS "Fecha Contab.",
    T4."U_NAME" AS "Solicitado Por",
    T0."Filler" AS "Almacén Origen",
    T0."ToWhsCode" AS "Almacén Destino",
    T1."ItemCode" AS "Código Artículo",
    T1."Dscription" AS "Descripción",
    T1."Project" AS "Código Proyecto",
    T3."PrjName" AS "Nombre Proyecto",
    T1."OpenQty" AS "Cant. Pendiente",
    T2."AvgPrice" AS "Costo Unitario",
    (T1."OpenQty" * T2."AvgPrice") AS "Valor Pendiente Total",
    T0."Comments" AS "Comentarios" 
FROM "OWTQ" T0
INNER JOIN "WTQ1" T1 ON T0."DocEntry" = T1."DocEntry"
INNER JOIN "OITW" T2 ON T1."ItemCode" = T2."ItemCode" AND T0."Filler" = T2."WhsCode" -- se conecta con las bodegas para ver el nombre
LEFT JOIN "OPRJ" T3 ON T1."Project" = T3."PrjCode"
INNER JOIN "OUSR" T4 ON T0."UserSign" = T4."USERID"
WHERE T0."DocStatus" = 'O' 
AND T1."OpenQty" > 0
ORDER BY T0."DocNum" DESC