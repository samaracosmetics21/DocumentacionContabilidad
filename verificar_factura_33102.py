#!/usr/bin/env python3
"""
Script para verificar específicamente la factura con numero_ofimatica 33102
"""

from db_config import postgres_connection

def verificar_factura_33102():
    print("🔍 VERIFICANDO FACTURA CON NUMERO_OFIMATICA 33102")
    print("=" * 50)
    
    # Conectar a PostgreSQL
    conn_pg = postgres_connection()
    cursor_pg = conn_pg.cursor()
    
    # 1. Buscar exactamente la factura 33102
    numero_ofimatica_buscar = "33102"
    print(f"1. Buscando factura con numero_ofimatica: '{numero_ofimatica_buscar}'")
    
    cursor_pg.execute("""
        SELECT id, numero_ofimatica, numero_factura, nit, nombre, estado_final
        FROM facturas 
        WHERE LTRIM(RTRIM(numero_ofimatica)) = %s
    """, (numero_ofimatica_buscar,))
    
    facturas_encontradas = cursor_pg.fetchall()
    
    if facturas_encontradas:
        print(f"✅ Encontradas {len(facturas_encontradas)} factura(s):")
        for factura in facturas_encontradas:
            print(f"  - ID: {factura[0]}, numero_ofimatica: '{factura[1]}', numero_factura: '{factura[2]}', nit: '{factura[3]}', nombre: '{factura[4]}', estado_final: '{factura[5]}'")
    else:
        print(f"❌ No se encontró ninguna factura con numero_ofimatica: '{numero_ofimatica_buscar}'")
    
    # 2. Buscar facturas que contengan '33102' en cualquier campo
    print(f"\n2. Buscando facturas que contengan '33102' en cualquier campo:")
    cursor_pg.execute("""
        SELECT id, numero_ofimatica, numero_factura, nit, nombre, estado_final
        FROM facturas 
        WHERE LTRIM(RTRIM(numero_ofimatica)) LIKE '%33102%' 
           OR LTRIM(RTRIM(numero_factura)) LIKE '%33102%'
           OR CAST(id AS TEXT) LIKE '%33102%'
        LIMIT 10
    """)
    
    facturas_similares = cursor_pg.fetchall()
    print(f"📋 Facturas similares encontradas: {len(facturas_similares)}")
    for factura in facturas_similares:
        print(f"  - ID: {factura[0]}, numero_ofimatica: '{factura[1]}', numero_factura: '{factura[2]}', nit: '{factura[3]}', nombre: '{factura[4]}', estado_final: '{factura[5]}'")
    
    # 3. Mostrar facturas con estado_final = 'Aprobado' que tengan numero_ofimatica
    print(f"\n3. Mostrando facturas aprobadas con numero_ofimatica:")
    cursor_pg.execute("""
        SELECT id, numero_ofimatica, numero_factura, nit, nombre, estado_final
        FROM facturas 
        WHERE estado_final = 'Aprobado' 
        AND numero_ofimatica IS NOT NULL
        ORDER BY id DESC
        LIMIT 10
    """)
    
    facturas_aprobadas = cursor_pg.fetchall()
    print(f"📋 Facturas aprobadas con numero_ofimatica: {len(facturas_aprobadas)}")
    for factura in facturas_aprobadas:
        print(f"  - ID: {factura[0]}, numero_ofimatica: '{factura[1]}', numero_factura: '{factura[2]}', nit: '{factura[3]}', nombre: '{factura[4]}', estado_final: '{factura[5]}'")
    
    # 4. Verificar si hay facturas con numero_ofimatica similar
    print(f"\n4. Verificando facturas con numero_ofimatica que empiecen con '331':")
    cursor_pg.execute("""
        SELECT id, numero_ofimatica, numero_factura, nit, nombre, estado_final
        FROM facturas 
        WHERE LTRIM(RTRIM(numero_ofimatica)) LIKE '331%'
        ORDER BY numero_ofimatica
        LIMIT 10
    """)
    
    facturas_331 = cursor_pg.fetchall()
    print(f"📋 Facturas con numero_ofimatica que empiecen con '331': {len(facturas_331)}")
    for factura in facturas_331:
        print(f"  - ID: {factura[0]}, numero_ofimatica: '{factura[1]}', numero_factura: '{factura[2]}', nit: '{factura[3]}', nombre: '{factura[4]}', estado_final: '{factura[5]}'")
    
    # Cerrar conexión
    cursor_pg.close()
    conn_pg.close()
    
    print(f"\n✅ VERIFICACIÓN COMPLETADA")
    print("=" * 50)

if __name__ == "__main__":
    verificar_factura_33102() 