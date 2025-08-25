#!/usr/bin/env python3
"""
Script para verificar específicamente la factura con numero_ofimatica 21456
"""

from db_config import postgres_connection

def verificar_factura_21456():
    print("🔍 VERIFICANDO FACTURA CON NUMERO_OFIMATICA 21456")
    print("=" * 50)
    
    # Conectar a PostgreSQL
    conn_pg = postgres_connection()
    cursor_pg = conn_pg.cursor()
    
    # 1. Buscar exactamente la factura 21456
    numero_ofimatica_buscar = "21456"
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
    
    # Cerrar conexión
    cursor_pg.close()
    conn_pg.close()
    
    print(f"\n✅ VERIFICACIÓN COMPLETADA")
    print("=" * 50)

if __name__ == "__main__":
    verificar_factura_21456() 