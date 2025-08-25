#!/usr/bin/env python3
"""
Script de prueba para verificar el problema con la actualización de documentos en Tesorería
"""

import json
from db_config import postgres_connection, sql_server_connection

def test_tesoreria_update():
    print("🔍 INICIANDO PRUEBA DE TESORERÍA")
    print("=" * 50)
    
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
    
    # 3. Verificar datos de ejemplo en facturas
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
    
    # 5. Verificar datos de ejemplo en ABOCXP
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
    
    # 6. Simular el proceso de actualización
    print("\n6. Simulando proceso de actualización...")
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
        
        # Buscar la factura en PostgreSQL
        cursor_pg.execute("""
            SELECT id, numero_ofimatica, numero_factura 
            FROM facturas 
            WHERE numero_ofimatica = %s OR numero_factura = %s
        """, (factura_ejemplo, factura_ejemplo))
        factura_encontrada = cursor_pg.fetchone()
        
        if factura_encontrada:
            print(f"  ✅ Factura encontrada: ID={factura_encontrada[0]}, numero_ofimatica='{factura_encontrada[1]}', numero_factura='{factura_encontrada[2]}'")
            
            # Simular UPDATE
            update_query = """
                UPDATE facturas
                SET dctos = %s, archivo_pdf = %s
                WHERE id = %s
            """
            cursor_pg.execute(update_query, (dcto_ejemplo, archivo_path_ejemplo, factura_encontrada[0]))
            
            if cursor_pg.rowcount > 0:
                print(f"  ✅ UPDATE simulado exitoso: {cursor_pg.rowcount} fila(s) afectada(s)")
                # Revertir el cambio para no afectar datos reales
                cursor_pg.execute("UPDATE facturas SET dctos = NULL, archivo_pdf = NULL WHERE id = %s", (factura_encontrada[0],))
                conn_pg.commit()
                print(f"  🔄 Cambios revertidos")
            else:
                print(f"  ❌ UPDATE simulado falló: 0 filas afectadas")
        else:
            print(f"  ❌ No se encontró factura con numero_ofimatica o numero_factura: '{factura_ejemplo}'")
    
    # 7. Cerrar conexiones
    print("\n7. Cerrando conexiones...")
    cursor_pg.close()
    conn_pg.close()
    cursor_sql.close()
    conn_sql.close()
    
    print("\n✅ PRUEBA COMPLETADA")
    print("=" * 50)

if __name__ == "__main__":
    test_tesoreria_update() 