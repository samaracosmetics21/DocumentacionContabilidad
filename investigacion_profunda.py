#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Investigación profunda para encontrar patrones de coincidencia entre las bases de datos
"""

from db_config import sql_server_connection, postgres_connection

def investigacion_profunda():
    """Investigación profunda de patrones de coincidencia"""
    print("=" * 60)
    print("INVESTIGACIÓN PROFUNDA DE PATRONES")
    print("=" * 60)
    
    try:
        conn_pg = postgres_connection()
        conn_sql = sql_server_connection()
        cursor_pg = conn_pg.cursor()
        cursor_sql = conn_sql.cursor()
        
        # 1. Verificar si hay algún patrón en los números de factura
        print("\n1. ANÁLISIS DE PATRONES EN NÚMEROS DE FACTURA:")
        print("-" * 50)
        
        query_patrones = """
            SELECT 
                numero_factura,
                LENGTH(numero_factura) as longitud,
                CASE 
                    WHEN numero_factura ~ '^[0-9]+$' THEN 'Solo números'
                    WHEN numero_factura ~ '^[A-Z]+[0-9]+$' THEN 'Letras + números'
                    WHEN numero_factura ~ '^[0-9]+[A-Z]+$' THEN 'Números + letras'
                    WHEN numero_factura ~ '^[A-Z]+$' THEN 'Solo letras'
                    ELSE 'Otro patrón'
                END as tipo_patron
            FROM facturas 
            WHERE estado_final = 'Pendiente'
            ORDER BY numero_factura
            LIMIT 15
        """
        cursor_pg.execute(query_patrones)
        patrones = cursor_pg.fetchall()
        
        for patron in patrones:
            print(f"  Factura: '{patron[0]}', Longitud: {patron[1]}, Tipo: {patron[2]}")
        
        # 2. Verificar si hay algún campo adicional en SQL Server que pueda contener el número de factura
        print("\n2. CAMPOS ADICIONALES EN SQL SERVER:")
        print("-" * 50)
        
        # Buscar campos que puedan contener información de factura
        query_campos_sql = """
            SELECT TOP 10 
                NRODCTO, 
                NIT, 
                TIPODCTO, 
                dctoprv,
                BRUTO,
                IVABRUTO,
                PASSWORDIN,
                -- Verificar si hay otros campos que puedan contener el número de factura
                CAST(NRODCTO AS VARCHAR) as nrodcto_str,
                LEN(dctoprv) as longitud_dctoprv
            FROM TRADE 
            WHERE ORIGEN = 'COM' AND (TIPODCTO = 'FR' OR TIPODCTO = 'FS')
            ORDER BY NRODCTO
        """
        
        try:
            cursor_sql.execute(query_campos_sql)
            campos_sql = cursor_sql.fetchall()
            
            print("  Campos en SQL Server:")
            for campo in campos_sql:
                print(f"    NRODCTO: {campo[0]}, DCTOPRV: '{campo[3]}', Longitud DCTOPRV: {campo[8]}")
                
        except Exception as e:
            print(f"  Error al consultar campos adicionales: {e}")
        
        # 3. Buscar coincidencias por NIT y ver qué registros están disponibles
        print("\n3. BÚSQUEDA POR NIT ESPECÍFICO:")
        print("-" * 50)
        
        # Tomar un NIT específico y ver todos sus registros
        nit_ejemplo = "830000167-2"  # NIT de INVIMA que apareció en los resultados
        
        query_nit_sql = """
            SELECT TOP 10 
                NRODCTO, 
                NIT, 
                TIPODCTO, 
                dctoprv,
                BRUTO,
                IVABRUTO,
                PASSWORDIN
            FROM TRADE 
            WHERE NIT = ? AND ORIGEN = 'COM' AND (TIPODCTO = 'FR' OR TIPODCTO = 'FS')
            ORDER BY NRODCTO
        """
        
        cursor_sql.execute(query_nit_sql, (nit_ejemplo,))
        registros_nit = cursor_sql.fetchall()
        
        print(f"  Registros para NIT {nit_ejemplo} en SQL Server:")
        for registro in registros_nit:
            print(f"    NRODCTO: {registro[0]}, DCTOPRV: '{registro[3]}', TIPODCTO: {registro[2]}")
        
        # 4. Verificar si hay algún patrón en los dctoprv
        print("\n4. ANÁLISIS DE PATRONES EN DCTOPRV:")
        print("-" * 50)
        
        query_patrones_dctoprv = """
            SELECT TOP 10 
                dctoprv,
                LEN(dctoprv) as longitud,
                CASE 
                    WHEN dctoprv LIKE '%[0-9]%' THEN 'Contiene números'
                    WHEN dctoprv LIKE '%[A-Z]%' THEN 'Contiene letras'
                    ELSE 'Otro'
                END as tipo_contenido
            FROM TRADE 
            WHERE ORIGEN = 'COM' AND (TIPODCTO = 'FR' OR TIPODCTO = 'FS')
            AND dctoprv IS NOT NULL
            ORDER BY dctoprv
        """
        
        cursor_sql.execute(query_patrones_dctoprv)
        patrones_dctoprv = cursor_sql.fetchall()
        
        for patron in patrones_dctoprv:
            print(f"  DCTOPRV: '{patron[0]}', Longitud: {patron[1]}, Tipo: {patron[2]}")
        
        # 5. Verificar si hay algún campo que contenga información de factura
        print("\n5. BÚSQUEDA DE CAMPOS CON INFORMACIÓN DE FACTURA:")
        print("-" * 50)
        
        # Buscar si hay algún campo que contenga números de factura similares
        query_buscar_factura = """
            SELECT TOP 5 
                NRODCTO, 
                NIT, 
                TIPODCTO, 
                dctoprv,
                BRUTO,
                IVABRUTO,
                PASSWORDIN
            FROM TRADE 
            WHERE ORIGEN = 'COM' AND (TIPODCTO = 'FR' OR TIPODCTO = 'FS')
            AND (dctoprv LIKE '%DUMI%' OR dctoprv LIKE '%ITA%' OR dctoprv LIKE '%LI%')
            ORDER BY dctoprv
        """
        
        cursor_sql.execute(query_buscar_factura)
        facturas_encontradas = cursor_sql.fetchall()
        
        if facturas_encontradas:
            print("  Facturas encontradas con patrones similares:")
            for factura in facturas_encontradas:
                print(f"    NRODCTO: {factura[0]}, DCTOPRV: '{factura[3]}', NIT: {factura[1]}")
        else:
            print("  No se encontraron facturas con patrones similares")
        
        cursor_pg.close()
        cursor_sql.close()
        conn_pg.close()
        conn_sql.close()
        
    except Exception as e:
        print(f"✗ Error en investigación profunda: {e}")

def main():
    investigacion_profunda()
    print("\n" + "=" * 60)
    print("FIN DE INVESTIGACIÓN PROFUNDA")
    print("=" * 60)

if __name__ == "__main__":
    main() 