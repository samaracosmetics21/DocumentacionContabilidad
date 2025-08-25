#!/usr/bin/env python3
"""
Script para verificar si existen facturas con numero_ofimatica específico
"""

from db_config import postgres_connection

def verificar_facturas():
    print("🔍 VERIFICANDO FACTURAS CON NUMERO_OFIMATICA")
    print("=" * 50)
    
    # Conectar a PostgreSQL
    conn_pg = postgres_connection()
    cursor_pg = conn_pg.cursor()
    
    # 1. Verificar si existe la factura específica
    numero_ofimatica_buscar = "21456"
    print(f"1. Buscando factura con numero_ofimatica: '{numero_ofimatica_buscar}'")
    
    cursor_pg.execute("""
        SELECT id, numero_ofimatica, numero_factura, nit, nombre, estado_final
        FROM facturas 
        WHERE numero_ofimatica = %s
    """, (numero_ofimatica_buscar,))
    
    facturas_encontradas = cursor_pg.fetchall()
    
    if facturas_encontradas:
        print(f"✅ Encontradas {len(facturas_encontradas)} factura(s):")
        for factura in facturas_encontradas:
            print(f"  - ID: {factura[0]}, numero_ofimatica: '{factura[1]}', numero_factura: '{factura[2]}', nit: '{factura[3]}', nombre: '{factura[4]}', estado_final: '{factura[5]}'")
    else:
        print(f"❌ No se encontró ninguna factura con numero_ofimatica: '{numero_ofimatica_buscar}'")
    
    # 2. Mostrar todas las facturas con estado_final = 'Aprobado'
    print(f"\n2. Mostrando todas las facturas con estado_final = 'Aprobado':")
    cursor_pg.execute("""
        SELECT id, numero_ofimatica, numero_factura, nit, nombre, estado_final
        FROM facturas 
        WHERE estado_final = 'Aprobado'
        ORDER BY id DESC
        LIMIT 10
    """)
    
    facturas_aprobadas = cursor_pg.fetchall()
    print(f"📋 Facturas aprobadas encontradas: {len(facturas_aprobadas)}")
    for factura in facturas_aprobadas:
        print(f"  - ID: {factura[0]}, numero_ofimatica: '{factura[1]}', numero_factura: '{factura[2]}', nit: '{factura[3]}', nombre: '{factura[4]}', estado_final: '{factura[5]}'")
    
    # 3. Buscar facturas que contengan '32989' en cualquier campo
    print(f"\n3. Buscando facturas que contengan '32989' en cualquier campo:")
    cursor_pg.execute("""
        SELECT id, numero_ofimatica, numero_factura, nit, nombre, estado_final
        FROM facturas 
        WHERE numero_ofimatica LIKE '%21456%' 
           OR numero_factura LIKE '%21456%'
           OR CAST(id AS TEXT) LIKE '%21456%'
        LIMIT 10
    """)
    
    facturas_similares = cursor_pg.fetchall()
    print(f"📋 Facturas similares encontradas: {len(facturas_similares)}")
    for factura in facturas_similares:
        print(f"  - ID: {factura[0]}, numero_ofimatica: '{factura[1]}', numero_factura: '{factura[2]}', nit: '{factura[3]}', nombre: '{factura[4]}', estado_final: '{factura[5]}'")
    
    # 4. Mostrar estadísticas generales
    print(f"\n4. Estadísticas generales:")
    cursor_pg.execute("SELECT COUNT(*) FROM facturas WHERE estado_final = 'Aprobado'")
    total_aprobadas = cursor_pg.fetchone()[0]
    print(f"  - Total facturas aprobadas: {total_aprobadas}")
    
    cursor_pg.execute("SELECT COUNT(*) FROM facturas WHERE numero_ofimatica IS NOT NULL")
    total_con_ofimatica = cursor_pg.fetchone()[0]
    print(f"  - Total facturas con numero_ofimatica: {total_con_ofimatica}")
    
    cursor_pg.execute("SELECT COUNT(*) FROM facturas WHERE numero_ofimatica IS NOT NULL AND estado_final = 'Aprobado'")
    total_aprobadas_con_ofimatica = cursor_pg.fetchone()[0]
    print(f"  - Total facturas aprobadas con numero_ofimatica: {total_aprobadas_con_ofimatica}")
    
    # Cerrar conexión
    cursor_pg.close()
    conn_pg.close()
    
    print(f"\n✅ VERIFICACIÓN COMPLETADA")
    print("=" * 50)

if __name__ == "__main__":
    verificar_facturas() 