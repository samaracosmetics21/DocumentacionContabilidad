#!/usr/bin/env python3
"""
Script de prueba SOLO LECTURA para verificar el problema con la actualización de documentos en Tesorería
NO MODIFICA DATOS EN LA BASE DE DATOS
"""

from db_config import postgres_connection, sql_server_connection

def test_tesoreria_solo_lectura():
    print("🔍 INICIANDO PRUEBA DE SOLO LECTURA - TESORERÍA")
    print("=" * 60)
    
    # 1. Conectar a PostgreSQL
    print("1. Conectando a PostgreSQL...")
    conn_pg = postgres_connection()
    cursor_pg = conn_pg.cursor()
    
    # 2. Verificar estructura de la tabla facturas
    print("\n2. Verificando estructura de tabla facturas...")
    cursor_pg.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'facturas' 
        AND column_name IN ('id', 'numero_ofimatica', 'numero_factura', 'dctos', 'archivo_pdf')
        ORDER BY column_name
    """)
    columnas = cursor_pg.fetchall()
    print("Columnas relevantes:")
    for col in columnas:
        print(f"  - {col[0]}: {col[1]}")
    
    # 3. Verificar datos de ejemplo en facturas (SOLO LECTURA)
    print("\n3. Verificando datos de ejemplo en facturas...")
    cursor_pg.execute("""
        SELECT id, numero_ofimatica, numero_factura, dctos, archivo_pdf
        FROM facturas 
        WHERE estado_final = 'Aprobado'
        LIMIT 5
    """)
    facturas_ejemplo = cursor_pg.fetchall()
    print("Facturas de ejemplo:")
    for factura in facturas_ejemplo:
        print(f"  - ID: {factura[0]}, numero_ofimatica: '{factura[1]}', numero_factura: '{factura[2]}', dctos: '{factura[3]}', archivo_pdf: '{factura[4]}'")
    
    # 4. Conectar a SQL Server
    print("\n4. Conectando a SQL Server...")
    conn_sql = sql_server_connection()
    cursor_sql = conn_sql.cursor()
    
    # 5. Verificar datos de ejemplo en ABOCXP (SOLO LECTURA)
    print("\n5. Verificando datos de ejemplo en ABOCXP...")
    cursor_sql.execute("""
        SELECT TOP 5
            LTRIM(RTRIM(ABOCXP.dcto)) AS dcto,
            LTRIM(RTRIM(ABOCXP.factura)) AS factura,
            LTRIM(RTRIM(ABOCXP.nit)) AS nit,
            LTRIM(RTRIM(mtprocli.nombre)) AS nombre_tercero
        FROM ABOCXP
        INNER JOIN mtprocli ON ABOCXP.nit = mtprocli.NIT
        WHERE ABOCXP.fecha >= DATEADD(DAY, -30, GETDATE())
        AND ABOCXP.tipodcto = 'CE'
        ORDER BY ABOCXP.factura
    """)
    documentos_ejemplo = cursor_sql.fetchall()
    print("Documentos de ejemplo de SQL Server:")
    for doc in documentos_ejemplo:
        print(f"  - dcto: '{doc[0]}', factura: '{doc[1]}', nit: '{doc[2]}', nombre: '{doc[3]}'")
    
    # 6. SIMULAR el proceso de actualización (SIN MODIFICAR DATOS)
    print("\n6. SIMULANDO proceso de actualización (SIN MODIFICAR DATOS)...")
    if documentos_ejemplo:
        # Tomar el primer documento como ejemplo
        doc_ejemplo = documentos_ejemplo[0]
        dcto_ejemplo = doc_ejemplo[0]
        factura_ejemplo = doc_ejemplo[1]
        archivo_path_ejemplo = "Pagos/test.pdf"
        
        print(f"  Simulando actualización:")
        print(f"    - dcto: '{dcto_ejemplo}'")
        print(f"    - factura: '{factura_ejemplo}'")
        print(f"    - archivo_path: '{archivo_path_ejemplo}'")
        
        # Buscar la factura en PostgreSQL (SOLO LECTURA)
        cursor_pg.execute("""
            SELECT id, numero_ofimatica, numero_factura, dctos, archivo_pdf
            FROM facturas 
            WHERE numero_ofimatica = %s OR numero_factura = %s
        """, (factura_ejemplo, factura_ejemplo))
        factura_encontrada = cursor_pg.fetchone()
        
        if factura_encontrada:
            print(f"  ✅ Factura encontrada:")
            print(f"    - ID: {factura_encontrada[0]}")
            print(f"    - numero_ofimatica: '{factura_encontrada[1]}'")
            print(f"    - numero_factura: '{factura_encontrada[2]}'")
            print(f"    - dctos actual: '{factura_encontrada[3]}'")
            print(f"    - archivo_pdf actual: '{factura_encontrada[4]}'")
            
            print(f"  📝 SIMULACIÓN DE UPDATE (NO SE EJECUTA):")
            print(f"    UPDATE facturas SET dctos = '{dcto_ejemplo}', archivo_pdf = '{archivo_path_ejemplo}' WHERE id = {factura_encontrada[0]}")
            print(f"  ✅ Esta consulta SIMULADA actualizaría la factura correctamente")
        else:
            print(f"  ❌ No se encontró factura con numero_ofimatica o numero_factura: '{factura_ejemplo}'")
            
            # Mostrar algunas facturas para debugging
            cursor_pg.execute("SELECT id, numero_ofimatica, numero_factura FROM facturas LIMIT 5")
            ejemplos = cursor_pg.fetchall()
            print(f"  📋 Ejemplos de facturas en BD:")
            for ej in ejemplos:
                print(f"    - ID: {ej[0]}, numero_ofimatica: '{ej[1]}', numero_factura: '{ej[2]}'")
    
    # 7. Verificar si hay problemas de coincidencia
    print("\n7. Verificando posibles problemas de coincidencia...")
    if documentos_ejemplo:
        print("  Comparando campos de SQL Server vs PostgreSQL:")
        for i, doc in enumerate(documentos_ejemplo[:3]):  # Solo los primeros 3
            factura_sql = doc[1]
            print(f"    Documento {i+1}: factura SQL Server = '{factura_sql}'")
            
            # Buscar en PostgreSQL
            cursor_pg.execute("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN numero_ofimatica = %s THEN 1 ELSE 0 END) as match_ofimatica,
                       SUM(CASE WHEN numero_factura = %s THEN 1 ELSE 0 END) as match_factura
                FROM facturas
            """, (factura_sql, factura_sql))
            resultado = cursor_pg.fetchone()
            
            print(f"      - Total facturas: {resultado[0]}")
            print(f"      - Coincidencias en numero_ofimatica: {resultado[1]}")
            print(f"      - Coincidencias en numero_factura: {resultado[2]}")
    
    # 8. Cerrar conexiones
    print("\n8. Cerrando conexiones...")
    cursor_pg.close()
    conn_pg.close()
    cursor_sql.close()
    conn_sql.close()
    
    print("\n✅ PRUEBA DE SOLO LECTURA COMPLETADA")
    print("=" * 60)
    print("📝 RESUMEN:")
    print("  - Este script SOLO LEE datos, NO modifica nada")
    print("  - Ayuda a identificar problemas de coincidencia")
    print("  - Muestra qué consultas se ejecutarían")

if __name__ == "__main__":
    test_tesoreria_solo_lectura() 