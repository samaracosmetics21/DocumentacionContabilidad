#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de validación para automatización de búsqueda de registros
entre PostgreSQL y SQL Server en el módulo de gestión final.
"""

from db_config import sql_server_connection, postgres_connection
import psycopg2
from pyodbc import Error

def validar_estructura_postgresql():
    """Validar estructura de datos en PostgreSQL"""
    print("=" * 60)
    print("VALIDACIÓN DE ESTRUCTURA EN POSTGRESQL")
    print("=" * 60)
    
    try:
        conn_pg = postgres_connection()
        cursor_pg = conn_pg.cursor()
        
        # Consulta 1: Verificar facturas pendientes en gestión final
        print("\n1. FACTURAS PENDIENTES EN GESTIÓN FINAL:")
        print("-" * 40)
        query1 = """
            SELECT id, nit, numero_factura, nombre, fecha_seleccionada, clasificacion 
            FROM facturas 
            WHERE estado_final = 'Pendiente' 
            LIMIT 5
        """
        cursor_pg.execute(query1)
        facturas = cursor_pg.fetchall()
        
        if facturas:
            print("✓ Se encontraron facturas pendientes:")
            for factura in facturas:
                print(f"  ID: {factura[0]}, NIT: {factura[1]}, Factura: {factura[2]}, Nombre: {factura[3]}, Fecha: {factura[4]}, Clasificación: {factura[5]}")
        else:
            print("✗ No se encontraron facturas pendientes")
        
        # Consulta 2: Verificar tipos de datos de campos clave
        print("\n2. ESTRUCTURA DE CAMPOS CLAVE:")
        print("-" * 40)
        query2 = """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'facturas' 
            AND column_name IN ('nit', 'numero_factura', 'clasificacion')
            ORDER BY column_name
        """
        cursor_pg.execute(query2)
        campos = cursor_pg.fetchall()
        
        for campo in campos:
            print(f"  Campo: {campo[0]}, Tipo: {campo[1]}, Nullable: {campo[2]}")
        
        # Consulta 3: Verificar valores únicos de clasificación
        print("\n3. VALORES DE CLASIFICACIÓN:")
        print("-" * 40)
        query3 = """
            SELECT DISTINCT clasificacion, COUNT(*) as cantidad
            FROM facturas 
            GROUP BY clasificacion
        """
        cursor_pg.execute(query3)
        clasificaciones = cursor_pg.fetchall()
        
        for clasif in clasificaciones:
            print(f"  Clasificación: '{clasif[0]}', Cantidad: {clasif[1]}")
        
        cursor_pg.close()
        conn_pg.close()
        
    except Exception as e:
        print(f"✗ Error en PostgreSQL: {e}")

def validar_estructura_sqlserver():
    """Validar estructura de datos en SQL Server"""
    print("\n" + "=" * 60)
    print("VALIDACIÓN DE ESTRUCTURA EN SQL SERVER")
    print("=" * 60)
    
    try:
        conn_sql = sql_server_connection()
        cursor_sql = conn_sql.cursor()
        
        # Consulta 1: Verificar estructura de TRADE
        print("\n1. ESTRUCTURA DE TABLA TRADE:")
        print("-" * 40)
        query1 = """
            SELECT TOP 5 
                NRODCTO, 
                NIT, 
                TIPODCTO, 
                ORIGEN,
                BRUTO,
                IVABRUTO,
                PASSWORDIN
            FROM TRADE 
            WHERE ORIGEN = 'COM' 
            AND (TIPODCTO = 'FR' OR TIPODCTO = 'FS')
            ORDER BY NRODCTO
        """
        cursor_sql.execute(query1)
        registros = cursor_sql.fetchall()
        
        if registros:
            print("✓ Se encontraron registros en TRADE:")
            for registro in registros:
                print(f"  NRODCTO: {registro[0]}, NIT: {registro[1]}, TIPODCTO: {registro[2]}, ORIGEN: {registro[3]}, BRUTO: {registro[4]}, IVABRUTO: {registro[5]}, PASSWORDIN: {registro[6]}")
        else:
            print("✗ No se encontraron registros en TRADE")
        
        # Consulta 2: Verificar tipos de documento disponibles
        print("\n2. TIPOS DE DOCUMENTO DISPONIBLES:")
        print("-" * 40)
        query2 = """
            SELECT DISTINCT TIPODCTO, COUNT(*) as cantidad
            FROM TRADE 
            WHERE ORIGEN = 'COM'
            GROUP BY TIPODCTO
            ORDER BY TIPODCTO
        """
        cursor_sql.execute(query2)
        tipos = cursor_sql.fetchall()
        
        for tipo in tipos:
            print(f"  Tipo: '{tipo[0]}', Cantidad: {tipo[1]}")
        
        # Consulta 3: Verificar estructura de MTPROCLI
        print("\n3. ESTRUCTURA DE MTPROCLI:")
        print("-" * 40)
        query3 = """
            SELECT TOP 3 nit, nombre
            FROM MTPROCLI
            ORDER BY nit
        """
        cursor_sql.execute(query3)
        clientes = cursor_sql.fetchall()
        
        for cliente in clientes:
            print(f"  NIT: {cliente[0]}, Nombre: {cliente[1]}")
        
        cursor_sql.close()
        conn_sql.close()
        
    except Exception as e:
        print(f"✗ Error en SQL Server: {e}")

def validar_correlacion_datos():
    """Validar si hay correlación entre los datos de ambas bases"""
    print("\n" + "=" * 60)
    print("VALIDACIÓN DE CORRELACIÓN ENTRE BASES DE DATOS")
    print("=" * 60)
    
    try:
        # Conectar a ambas bases
        conn_pg = postgres_connection()
        conn_sql = sql_server_connection()
        cursor_pg = conn_pg.cursor()
        cursor_sql = conn_sql.cursor()
        
        # Consulta 1: Obtener algunos NITs de PostgreSQL
        print("\n1. NITs EN POSTGRESQL:")
        print("-" * 40)
        query_pg = """
            SELECT DISTINCT nit, COUNT(*) as cantidad_facturas
            FROM facturas 
            WHERE estado_final = 'Pendiente'
            GROUP BY nit
            LIMIT 5
        """
        cursor_pg.execute(query_pg)
        nits_pg = cursor_pg.fetchall()
        
        if nits_pg:
            print("✓ NITs encontrados en PostgreSQL:")
            for nit_pg in nits_pg:
                print(f"  NIT: {nit_pg[0]}, Cantidad facturas: {nit_pg[1]}")
                
                # Buscar este NIT en SQL Server
                query_sql = """
                    SELECT COUNT(*) as cantidad_registros
                    FROM TRADE 
                    WHERE NIT = ? AND ORIGEN = 'COM'
                """
                cursor_sql.execute(query_sql, (nit_pg[0],))
                resultado_sql = cursor_sql.fetchone()
                
                if resultado_sql and resultado_sql[0] > 0:
                    print(f"    ✓ Encontrado en SQL Server: {resultado_sql[0]} registros")
                else:
                    print(f"    ✗ No encontrado en SQL Server")
        else:
            print("✗ No se encontraron NITs en PostgreSQL")
        
        # Consulta 2: Verificar si hay coincidencias por NIT y número de factura
        print("\n2. VERIFICACIÓN DE COINCIDENCIAS:")
        print("-" * 40)
        query_coincidencias = """
            SELECT nit, numero_factura, clasificacion
            FROM facturas 
            WHERE estado_final = 'Pendiente'
            LIMIT 3
        """
        cursor_pg.execute(query_coincidencias)
        facturas_pg = cursor_pg.fetchall()
        
        for factura in facturas_pg:
            nit = factura[0]
            numero_factura = factura[1]
            clasificacion = factura[2]
            
            print(f"\n  Verificando NIT: {nit}, Factura: {numero_factura}, Clasificación: {clasificacion}")
            
            # Buscar en SQL Server
            if clasificacion == 'Facturas':
                tipodcto = 'FR'
            elif clasificacion == 'Servicios':
                tipodcto = 'FS'
            else:
                tipodcto = None
            
            if tipodcto:
                query_sql = """
                    SELECT NRODCTO, NIT, TIPODCTO, BRUTO, IVABRUTO, PASSWORDIN
                    FROM TRADE 
                    WHERE NIT = ? AND NRODCTO = ? AND TIPODCTO = ? AND ORIGEN = 'COM'
                """
                cursor_sql.execute(query_sql, (nit, numero_factura, tipodcto))
                resultado = cursor_sql.fetchone()
                
                if resultado:
                    print(f"    ✓ COINCIDENCIA ENCONTRADA:")
                    print(f"      NRODCTO: {resultado[0]}, NIT: {resultado[1]}, TIPODCTO: {resultado[2]}")
                    print(f"      BRUTO: {resultado[3]}, IVABRUTO: {resultado[4]}, PASSWORDIN: {resultado[5]}")
                else:
                    print(f"    ✗ No se encontró coincidencia")
            else:
                print(f"    ⚠ Clasificación no reconocida: {clasificacion}")
        
        cursor_pg.close()
        cursor_sql.close()
        conn_pg.close()
        conn_sql.close()
        
    except Exception as e:
        print(f"✗ Error en validación de correlación: {e}")

def main():
    """Función principal de validación"""
    print("INICIO DE VALIDACIÓN PARA AUTOMATIZACIÓN")
    print("=" * 60)
    
    # Validar estructura de PostgreSQL
    validar_estructura_postgresql()
    
    # Validar estructura de SQL Server
    validar_estructura_sqlserver()
    
    # Validar correlación entre bases
    validar_correlacion_datos()
    
    print("\n" + "=" * 60)
    print("FIN DE VALIDACIÓN")
    print("=" * 60)

if __name__ == "__main__":
    main() 