#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de validación para verificar la relación entre numero_factura (PostgreSQL) 
y dctoprv (SQL Server)
"""

from db_config import sql_server_connection, postgres_connection

def validar_relacion_dctoprv():
    """Validar la relación entre numero_factura y dctoprv"""
    print("=" * 60)
    print("VALIDACIÓN DE RELACIÓN: numero_factura ↔ dctoprv")
    print("=" * 60)
    
    try:
        conn_pg = postgres_connection()
        conn_sql = sql_server_connection()
        cursor_pg = conn_pg.cursor()
        cursor_sql = conn_sql.cursor()
        
        # Consulta 1: Verificar si existe el campo dctoprv en SQL Server
        print("\n1. VERIFICACIÓN DE CAMPO DCTOPRV EN SQL SERVER:")
        print("-" * 50)
        
        # Primero verificar si el campo existe
        query_verificar_campo = """
            SELECT TOP 5 
                NRODCTO, 
                NIT, 
                TIPODCTO, 
                ORIGEN,
                BRUTO,
                IVABRUTO,
                PASSWORDIN,
                dctoprv
            FROM TRADE 
            WHERE ORIGEN = 'COM' 
            AND (TIPODCTO = 'FR' OR TIPODCTO = 'FS')
            ORDER BY NRODCTO
        """
        
        try:
            cursor_sql.execute(query_verificar_campo)
            registros_sql = cursor_sql.fetchall()
            
            if registros_sql:
                print("✓ Campo dctoprv encontrado en SQL Server:")
                for registro in registros_sql:
                    print(f"  NRODCTO: {registro[0]}, NIT: {registro[1]}, TIPODCTO: {registro[2]}, DCTOPRV: {registro[7]}")
            else:
                print("✗ No se encontraron registros con dctoprv")
                
        except Exception as e:
            print(f"✗ Error al consultar dctoprv: {e}")
            print("  El campo dctoprv podría no existir o tener otro nombre")
            return
        
        # Consulta 2: Obtener facturas de PostgreSQL para comparar
        print("\n2. FACTURAS EN POSTGRESQL PARA COMPARACIÓN:")
        print("-" * 50)
        
        query_pg = """
            SELECT id, nit, numero_factura, clasificacion, nombre
            FROM facturas 
            WHERE estado_final = 'Pendiente'
            ORDER BY numero_factura
            LIMIT 10
        """
        cursor_pg.execute(query_pg)
        facturas_pg = cursor_pg.fetchall()
        
        if facturas_pg:
            print("✓ Facturas encontradas en PostgreSQL:")
            for factura in facturas_pg:
                print(f"  ID: {factura[0]}, NIT: {factura[1]}, Factura: '{factura[2]}', Clasificación: {factura[3]}, Nombre: {factura[4]}")
        else:
            print("✗ No se encontraron facturas pendientes")
            return
        
        # Consulta 3: Buscar coincidencias exactas
        print("\n3. BÚSQUEDA DE COINCIDENCIAS EXACTAS:")
        print("-" * 50)
        
        coincidencias_encontradas = 0
        total_facturas = 0
        
        for factura in facturas_pg:
            numero_factura = factura[2]
            nit = factura[1]
            clasificacion = factura[3]
            
            # Determinar tipo de documento
            if clasificacion == 'Facturas':
                tipodcto = 'FR'
            elif clasificacion == 'Servicios':
                tipodcto = 'FS'
            else:
                continue
            
            total_facturas += 1
            
            # Buscar en SQL Server por dctoprv
            query_sql = """
                SELECT NRODCTO, NIT, TIPODCTO, dctoprv, BRUTO, IVABRUTO, PASSWORDIN
                FROM TRADE 
                WHERE dctoprv = ? AND NIT = ? AND TIPODCTO = ? AND ORIGEN = 'COM'
            """
            
            try:
                cursor_sql.execute(query_sql, (numero_factura, nit, tipodcto))
                resultado = cursor_sql.fetchone()
                
                if resultado:
                    coincidencias_encontradas += 1
                    print(f"  ✓ COINCIDENCIA EXACTA:")
                    print(f"    PostgreSQL: Factura='{numero_factura}', NIT={nit}")
                    print(f"    SQL Server: DCTOPRV='{resultado[3]}', NIT={resultado[1]}, NRODCTO={resultado[0]}")
                    print(f"    BRUTO={resultado[4]}, IVABRUTO={resultado[5]}, PASSWORDIN={resultado[6]}")
                else:
                    print(f"  ✗ No coincidencia para: Factura='{numero_factura}', NIT={nit}, Clasificación={clasificacion}")
                    
            except Exception as e:
                print(f"  ⚠ Error buscando '{numero_factura}': {e}")
        
        # Consulta 4: Estadísticas de coincidencias
        print(f"\n4. ESTADÍSTICAS DE COINCIDENCIAS:")
        print("-" * 50)
        print(f"  Total facturas verificadas: {total_facturas}")
        print(f"  Coincidencias exactas encontradas: {coincidencias_encontradas}")
        if total_facturas > 0:
            porcentaje = (coincidencias_encontradas / total_facturas) * 100
            print(f"  Porcentaje de éxito: {porcentaje:.1f}%")
            
            if porcentaje >= 80:
                print("  ✅ ALTA VIABILIDAD PARA AUTOMATIZACIÓN")
            elif porcentaje >= 50:
                print("  ⚠ VIABILIDAD MODERADA - REQUIERE VALIDACIÓN MANUAL")
            else:
                print("  ❌ BAJA VIABILIDAD - MANTENER BÚSQUEDA MANUAL")
        
        # Consulta 5: Verificar si hay múltiples registros para el mismo NIT
        print(f"\n5. VERIFICACIÓN DE MÚLTIPLES REGISTROS:")
        print("-" * 50)
        
        for factura in facturas_pg[:3]:  # Solo verificar las primeras 3
            nit = factura[1]
            clasificacion = factura[3]
            
            if clasificacion == 'Facturas':
                tipodcto = 'FR'
            elif clasificacion == 'Servicios':
                tipodcto = 'FS'
            else:
                continue
            
            query_multiple = """
                SELECT COUNT(*) as cantidad
                FROM TRADE 
                WHERE NIT = ? AND TIPODCTO = ? AND ORIGEN = 'COM'
            """
            
            cursor_sql.execute(query_multiple, (nit, tipodcto))
            cantidad = cursor_sql.fetchone()[0]
            
            print(f"  NIT: {nit}, Tipo: {tipodcto}, Registros en SQL Server: {cantidad}")
        
        cursor_pg.close()
        cursor_sql.close()
        conn_pg.close()
        conn_sql.close()
        
    except Exception as e:
        print(f"✗ Error general en validación: {e}")

def main():
    validar_relacion_dctoprv()
    print("\n" + "=" * 60)
    print("FIN DE VALIDACIÓN")
    print("=" * 60)

if __name__ == "__main__":
    main() 