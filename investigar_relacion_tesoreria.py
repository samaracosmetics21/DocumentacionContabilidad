#!/usr/bin/env python3
"""
Script para investigar la relación real entre SQL Server y PostgreSQL en Tesorería
"""

from db_config import postgres_connection, sql_server_connection

def investigar_relacion():
    print("🔍 INVESTIGANDO RELACIÓN ENTRE SQL SERVER Y POSTGRESQL")
    print("=" * 60)
    
    # 1. Conectar a SQL Server
    print("1. Conectando a SQL Server...")
    conn_sql = sql_server_connection()
    cursor_sql = conn_sql.cursor()
    
    # 2. Obtener datos de ejemplo de SQL Server
    print("\n2. Obteniendo datos de ejemplo de SQL Server...")
    cursor_sql.execute("""
        SELECT TOP 10
            LTRIM(RTRIM(ABOCXP.dcto)) AS dcto,
            LTRIM(RTRIM(ABOCXP.factura)) AS factura,
            LTRIM(RTRIM(ABOCXP.nit)) AS nit,
            LTRIM(RTRIM(mtprocli.nombre)) AS nombre_tercero,
            LTRIM(RTRIM(ABOCXP.PASSWORDIN)) AS PASSWORDIN
        FROM ABOCXP
        INNER JOIN mtprocli ON ABOCXP.nit = mtprocli.NIT
        WHERE ABOCXP.fecha >= DATEADD(DAY, -30, GETDATE())
        AND ABOCXP.tipodcto = 'CE'
        ORDER BY ABOCXP.factura
    """)
    documentos_sql = cursor_sql.fetchall()
    
    print("Documentos de SQL Server:")
    for doc in documentos_sql:
        print(f"  - dcto: '{doc[0]}', factura: '{doc[1]}', nit: '{doc[2]}', nombre: '{doc[3]}', passwordin: '{doc[4]}'")
    
    # 3. Conectar a PostgreSQL
    print("\n3. Conectando a PostgreSQL...")
    conn_pg = postgres_connection()
    cursor_pg = conn_pg.cursor()
    
    # 4. Obtener datos de ejemplo de PostgreSQL
    print("\n4. Obteniendo datos de ejemplo de PostgreSQL...")
    cursor_pg.execute("""
        SELECT id, numero_ofimatica, numero_factura, nit, nombre
        FROM facturas 
        WHERE estado_final = 'Aprobado'
        ORDER BY id DESC
        LIMIT 10
    """)
    facturas_pg = cursor_pg.fetchall()
    
    print("Facturas de PostgreSQL:")
    for factura in facturas_pg:
        print(f"  - ID: {factura[0]}, numero_ofimatica: '{factura[1]}', numero_factura: '{factura[2]}', nit: '{factura[3]}', nombre: '{factura[4]}'")
    
    # 5. Intentar diferentes estrategias de coincidencia
    print("\n5. Probando diferentes estrategias de coincidencia...")
    
    for doc_sql in documentos_sql[:3]:  # Solo los primeros 3
        dcto_sql = doc_sql[0]
        factura_sql = doc_sql[1]
        nit_sql = doc_sql[2]
        passwordin_sql = doc_sql[4]
        
        print(f"\n🔍 Analizando documento SQL: dcto='{dcto_sql}', factura='{factura_sql}', nit='{nit_sql}', passwordin='{passwordin_sql}'")
        
        # Estrategia 1: Buscar por numero_ofimatica
        cursor_pg.execute("""
            SELECT id, numero_ofimatica, numero_factura, nit, nombre
            FROM facturas 
            WHERE numero_ofimatica = %s
        """, (factura_sql,))
        coincidencia_ofimatica = cursor_pg.fetchall()
        print(f"  📋 Coincidencias por numero_ofimatica: {len(coincidencia_ofimatica)}")
        
        # Estrategia 2: Buscar por numero_factura
        cursor_pg.execute("""
            SELECT id, numero_ofimatica, numero_factura, nit, nombre
            FROM facturas 
            WHERE numero_factura = %s
        """, (factura_sql,))
        coincidencia_factura = cursor_pg.fetchall()
        print(f"  📋 Coincidencias por numero_factura: {len(coincidencia_factura)}")
        
        # Estrategia 3: Buscar por NIT
        cursor_pg.execute("""
            SELECT id, numero_ofimatica, numero_factura, nit, nombre
            FROM facturas 
            WHERE nit = %s
        """, (nit_sql,))
        coincidencia_nit = cursor_pg.fetchall()
        print(f"  📋 Coincidencias por NIT: {len(coincidencia_nit)}")
        
        # Estrategia 4: Buscar por passwordin
        cursor_pg.execute("""
            SELECT id, numero_ofimatica, numero_factura, nit, nombre
            FROM facturas 
            WHERE numero_ofimatica = %s
        """, (passwordin_sql,))
        coincidencia_passwordin = cursor_pg.fetchall()
        print(f"  📋 Coincidencias por passwordin como numero_ofimatica: {len(coincidencia_passwordin)}")
        
        # Estrategia 5: Buscar por passwordin como numero_factura
        cursor_pg.execute("""
            SELECT id, numero_ofimatica, numero_factura, nit, nombre
            FROM facturas 
            WHERE numero_factura = %s
        """, (passwordin_sql,))
        coincidencia_passwordin_factura = cursor_pg.fetchall()
        print(f"  📋 Coincidencias por passwordin como numero_factura: {len(coincidencia_passwordin_factura)}")
        
        # Mostrar las coincidencias encontradas
        if coincidencia_ofimatica:
            print(f"    ✅ Coincidencias por numero_ofimatica: {coincidencia_ofimatica}")
        if coincidencia_factura:
            print(f"    ✅ Coincidencias por numero_factura: {coincidencia_factura}")
        if coincidencia_nit:
            print(f"    ✅ Coincidencias por NIT: {coincidencia_nit}")
        if coincidencia_passwordin:
            print(f"    ✅ Coincidencias por passwordin como numero_ofimatica: {coincidencia_passwordin}")
        if coincidencia_passwordin_factura:
            print(f"    ✅ Coincidencias por passwordin como numero_factura: {coincidencia_passwordin_factura}")
    
    # 6. Cerrar conexiones
    print("\n6. Cerrando conexiones...")
    cursor_sql.close()
    conn_sql.close()
    cursor_pg.close()
    conn_pg.close()
    
    print("\n✅ INVESTIGACIÓN COMPLETADA")
    print("=" * 60)

if __name__ == "__main__":
    investigar_relacion() 