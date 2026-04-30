SELECT
    T0."DocNum" AS "N° Ingreso Mercancía",
    T0."DocDate" AS "Fecha de Contabilización",
    T0."TaxDate" AS "Fecha del Documento",
    T0."CardCode" AS "Código Proveedor",
    T0."CardName" AS "Nombre Proveedor",
    T2."DocNum" AS "N° Orden de Compra Origen",
    T1."ItemCode" AS "Código Artículo",
    T3."ItemName" AS "Nombre del Producto",
    T1."Quantity" AS "Cantidad Recibida",
    T1."Price" AS "Precio por Unidad",
    T1."LineTotal" AS "Total Línea",
    T1."WhsCode" AS "Almacén"

FROM
    OPDN T0 -- Tabla de Ingreso de Mercancías (Cabecera)
    INNER JOIN PDN1 T1 ON T0."DocEntry" = T1."DocEntry" -- Tabla de Ingreso de Mercancías (Líneas)
    LEFT JOIN OITM T3 ON T1."ItemCode" = T3."ItemCode" -- Tabla Maestro de Artículos para obtener el nombre
    LEFT JOIN OPOR T2 ON T1."BaseEntry" = T2."DocEntry" AND T1."BaseType" = 22 -- Une con la Orden de Compra de origen

ORDER BY
    T0."DocDate" DESC,
    T0."DocNum" DESC