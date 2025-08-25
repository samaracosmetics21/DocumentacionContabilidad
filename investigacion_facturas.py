#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de investigación adicional para entender la relación entre números de factura
"""

from db_config import sql_server_connection, postgres_connection

def investigar_numeros_factura():
    """Investigar la relación entre números de factura"""
    print("=" * 60)
    print("INVESTIGACIÓN DE NÚMEROS DE FACTURA")
    print("=" * 60)
    
    try:
        conn_pg = postgres_connection()
        conn_sql = sql_server_connection()
        cursor_pg = conn_pg.cursor()
        cursor_sql = conn_sql.cursor()
        
        # Obtener facturas de PostgreSQL con diferentes patrones
        print("\n1. PATRONES DE NÚMEROS DE FACTURA EN POSTGRESQL:")
        print("-" * 50)
        query_pg = """
            SELECT DISTINCT numero_factura, clasificacion, COUNT(*) as cantidad
            FROM facturas 
            WHERE estado_final = 'Pendiente'
            GROUP BY numero_factura, clasificacion
            ORDER BY numero_factura
            LIMIT 10
        """
        cursor_pg.execute(query_pg)
        facturas_pg = cursor_pg.fetchall()
        
        for factura in facturas_pg:
            print(f"  Factura: '{factura[0]}', Clasificación: {factura[1]}, Cantidad: {factura[2]}")
            
            # Buscar en SQL Server por diferentes criterios
            numero_factura = factura[0]
            clasificacion = factura[1]
            
            if clasificacion == 'Facturas':
                tipodcto = 'FR'
            elif clasificacion == 'Servicios':
                tipodcto = 'FS'
            else:
                continue
            
            # Buscar por número exacto
            query_sql_exacto = """
                SELECT NRODCTO, NIT, TIPODCTO, BRUTO, IVABRUTO, PASSWORDIN
                FROM TRADE 
                WHERE NRODCTO = ? AND TIPODCTO = ? AND ORIGEN = 'COM'
            """
            cursor_sql.execute(query_sql_exacto, (numero_factura, tipodcto))
            resultado_exacto = cursor_sql.fetchone()
            
            if resultado_exacto:
                print(f"    ✓ COINCIDENCIA EXACTA: NRODCTO={resultado_exacto[0]}, NIT={resultado_exacto[1]}")
            else:
                # Buscar por número parcial
                query_sql_parcial = """
                    SELECT TOP 3 NRODCTO, NIT, TIPODCTO, BRUTO, IVABRUTO, PASSWORDIN
                    FROM TRADE 
                    WHERE NRODCTO LIKE ? AND TIPODCTO = ? AND ORIGEN = 'COM'
                """
                cursor_sql.execute(query_sql_parcial, (f'%{numero_factura}%', tipodcto))
                resultados_parciales = cursor_sql.fetchall()
                
                if resultados_parciales:
                    print(f"    ⚠ COINCIDENCIAS PARCIALES:")
                    for res in resultados_parciales:
                        print(f"      NRODCTO={res[0]}, NIT={res[1]}")
                else:
                    print(f"    ✗ No se encontraron coincidencias")
        
        # Investigar si hay algún campo adicional que pueda servir como identificador
        print("\n2. INVESTIGACIÓN DE CAMPOS ADICIONALES:")
        print("-" * 50)
        
        # Verificar si hay campos como 'factura' en SQL Server
        query_campos_sql = """
            SELECT TOP 5 
                NRODCTO, 
                NIT, 
                TIPODCTO, 
                BRUTO,
                IVABRUTO,
                PASSWORDIN
            FROM TRADE 
            WHERE ORIGEN = 'COM' AND (TIPODCTO = 'FR' OR TIPODCTO = 'FS')
            ORDER BY NRODCTO
        """
        cursor_sql.execute(query_campos_sql)
        campos_sql = cursor_sql.fetchall()
        
        print("  Campos disponibles en SQL Server:")
        for campo in campos_sql:
            print(f"    NRODCTO: {campo[0]} (tipo: {type(campo[0])}), NIT: {campo[1]}, TIPODCTO: {campo[2]}")
        
        # Verificar si hay algún patrón en los números de factura de PostgreSQL
        print("\n3. ANÁLISIS DE PATRONES:")
        print("-" * 50)
        
        query_patrones = """
            SELECT 
                CASE 
                    WHEN numero_factura ~ '^[0-9]+$' THEN 'Solo números'
                    WHEN numero_factura ~ '^[A-Z]+[0-9]+$' THEN 'Letras + números'
                    WHEN numero_factura ~ '^[0-9]+[A-Z]+$' THEN 'Números + letras'
                    ELSE 'Otro patrón'
                END as patron,
                COUNT(*) as cantidad
            FROM facturas 
            WHERE estado_final = 'Pendiente'
            GROUP BY 
                CASE 
                    WHEN numero_factura ~ '^[0-9]+$' THEN 'Solo números'
                    WHEN numero_factura ~ '^[A-Z]+[0-9]+$' THEN 'Letras + números'
                    WHEN numero_factura ~ '^[0-9]+[A-Z]+$' THEN 'Números + letras'
                    ELSE 'Otro patrón'
                END
        """
        cursor_pg.execute(query_patrones)
        patrones = cursor_pg.fetchall()
        
        for patron in patrones:
            print(f"  Patrón: {patron[0]}, Cantidad: {patron[1]}")
        
        cursor_pg.close()
        cursor_sql.close()
        conn_pg.close()
        conn_sql.close()
        
    except Exception as e:
        print(f"✗ Error en investigación: {e}")

def main():
    investigar_numeros_factura()
    print("\n" + "=" * 60)
    print("FIN DE INVESTIGACIÓN")
    print("=" * 60)

if __name__ == "__main__":
    main() 