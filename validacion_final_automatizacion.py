#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validación final considerando espacios adicionales en SQL Server
"""

from db_config import sql_server_connection, postgres_connection

def validacion_final_con_espacios():
    """Validación final considerando espacios en SQL Server"""
    print("=" * 60)
    print("VALIDACIÓN FINAL - CONSIDERANDO ESPACIOS")
    print("=" * 60)
    
    try:
        conn_pg = postgres_connection()
        conn_sql = sql_server_connection()
        cursor_pg = conn_pg.cursor()
        cursor_sql = conn_sql.cursor()
        
        # 1. Verificar facturas de PostgreSQL
        print("\n1. FACTURAS EN POSTGRESQL:")
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
                print(f"  ID: {factura[0]}, NIT: {factura[1]}, Factura: '{factura[2]}', Clasificación: {factura[3]}")
        else:
            print("✗ No se encontraron facturas pendientes")
            return
        
        # 2. Buscar coincidencias considerando espacios
        print("\n2. BÚSQUEDA CON LIMPIEZA DE ESPACIOS:")
        print("-" * 50)
        
        coincidencias_encontradas = 0
        total_facturas = 0
        
        for factura in facturas_pg:
            numero_factura = factura[2].strip()  # Limpiar espacios en PostgreSQL
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
            
            # Buscar en SQL Server con limpieza de espacios
            query_sql = """
                SELECT NRODCTO, NIT, TIPODCTO, LTRIM(RTRIM(dctoprv)) as dctoprv_limpio, 
                       BRUTO, IVABRUTO, PASSWORDIN
                FROM TRADE 
                WHERE LTRIM(RTRIM(dctoprv)) = ? AND NIT = ? AND TIPODCTO = ? AND ORIGEN = 'COM'
            """
            
            try:
                cursor_sql.execute(query_sql, (numero_factura, nit, tipodcto))
                resultado = cursor_sql.fetchone()
                
                if resultado:
                    coincidencias_encontradas += 1
                    print(f"  ✓ COINCIDENCIA EXACTA CON ESPACIOS LIMPIOS:")
                    print(f"    PostgreSQL: Factura='{numero_factura}', NIT={nit}")
                    print(f"    SQL Server: DCTOPRV='{resultado[3]}', NIT={resultado[1]}, NRODCTO={resultado[0]}")
                    print(f"    BRUTO={resultado[4]}, IVABRUTO={resultado[5]}, PASSWORDIN={resultado[6]}")
                else:
                    # Buscar coincidencias parciales
                    query_sql_parcial = """
                        SELECT NRODCTO, NIT, TIPODCTO, LTRIM(RTRIM(dctoprv)) as dctoprv_limpio, 
                               BRUTO, IVABRUTO, PASSWORDIN
                        FROM TRADE 
                        WHERE LTRIM(RTRIM(dctoprv)) LIKE ? AND NIT = ? AND TIPODCTO = ? AND ORIGEN = 'COM'
                    """
                    
                    # Buscar por diferentes patrones
                    patrones_busqueda = [
                        f'%{numero_factura}%',
                        f'%{numero_factura.strip()}%',
                        f'%{numero_factura.replace(" ", "")}%'
                    ]
                    
                    coincidencias_parciales = []
                    for patron in patrones_busqueda:
                        cursor_sql.execute(query_sql_parcial, (patron, nit, tipodcto))
                        resultados = cursor_sql.fetchall()
                        if resultados:
                            coincidencias_parciales.extend(resultados)
                    
                    if coincidencias_parciales:
                        print(f"  ⚠ COINCIDENCIAS PARCIALES para '{numero_factura}':")
                        for res in coincidencias_parciales[:3]:  # Mostrar solo las primeras 3
                            print(f"    DCTOPRV='{res[3]}', NRODCTO={res[0]}, BRUTO={res[4]}")
                    else:
                        print(f"  ✗ No coincidencia para: Factura='{numero_factura}', NIT={nit}")
                        
            except Exception as e:
                print(f"  ⚠ Error buscando '{numero_factura}': {e}")
        
        # 3. Estadísticas finales
        print(f"\n3. ESTADÍSTICAS FINALES:")
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
        
        # 4. Verificar si hay algún patrón específico para DUMI
        print(f"\n4. ANÁLISIS ESPECÍFICO PARA DUMI:")
        print("-" * 50)
        
        # Buscar específicamente facturas DUMI
        query_dumi_pg = """
            SELECT id, nit, numero_factura, clasificacion
            FROM facturas 
            WHERE estado_final = 'Pendiente' AND numero_factura LIKE '%DUMI%'
            LIMIT 3
        """
        cursor_pg.execute(query_dumi_pg)
        facturas_dumi = cursor_pg.fetchall()
        
        for factura_dumi in facturas_dumi:
            numero_factura = factura_dumi[2].strip()
            nit = factura_dumi[1]
            
            print(f"  Verificando DUMI: '{numero_factura}', NIT: {nit}")
            
            # Buscar en SQL Server
            query_dumi_sql = """
                SELECT NRODCTO, NIT, TIPODCTO, LTRIM(RTRIM(dctoprv)) as dctoprv_limpio, 
                       BRUTO, IVABRUTO, PASSWORDIN
                FROM TRADE 
                WHERE LTRIM(RTRIM(dctoprv)) LIKE ? AND NIT = ? AND ORIGEN = 'COM'
                AND (TIPODCTO = 'FR' OR TIPODCTO = 'FS')
            """
            
            cursor_sql.execute(query_dumi_sql, (f'%DUMI%', nit))
            resultados_dumi = cursor_sql.fetchall()
            
            if resultados_dumi:
                print(f"    ✓ Encontrados {len(resultados_dumi)} registros DUMI en SQL Server:")
                for res in resultados_dumi[:3]:
                    print(f"      DCTOPRV='{res[3]}', NRODCTO={res[0]}, BRUTO={res[4]}")
            else:
                print(f"    ✗ No se encontraron registros DUMI para NIT {nit}")
        
        cursor_pg.close()
        cursor_sql.close()
        conn_pg.close()
        conn_sql.close()
        
    except Exception as e:
        print(f"✗ Error en validación final: {e}")

def main():
    validacion_final_con_espacios()
    print("\n" + "=" * 60)
    print("FIN DE VALIDACIÓN FINAL")
    print("=" * 60)

if __name__ == "__main__":
    main() 