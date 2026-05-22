"""
Script independiente para automatizar documentos CM (Caja Menor)
Ejecutar: python automatizar_cm.py
"""

import sys
from datetime import datetime
from db_config import postgres_connection, sql_server_connection

def automatizar_documentos_cm():
    """Automatiza todos los documentos CM pendientes"""
    
    print("=" * 60)
    print("AUTOMATIZACIÓN DE DOCUMENTOS CM (CAJA MENOR)")
    print("=" * 60)
    
    # Conectar a PostgreSQL
    conn_pg = postgres_connection()
    cursor_pg = conn_pg.cursor()
    
    # Conectar a SQL Server
    conn_sql = sql_server_connection()
    cursor_sql = conn_sql.cursor()
    
    try:
        # Consultar facturas CM pendientes
        print("\n📋 Consultando facturas CM pendientes...")
        cursor_pg.execute("""
            SELECT 
                id, 
                nit, 
                numero_factura, 
                clasificacion,
                estado_final
            FROM facturas
            WHERE clasificacion = 'Servicios' 
              AND estado_final = 'Pendiente'
            ORDER BY id
        """)
        
        facturas_cm = cursor_pg.fetchall()
        print(f"✅ Encontradas {len(facturas_cm)} facturas CM pendientes\n")
        
        if not facturas_cm:
            print("No hay facturas CM pendientes para automatizar.")
            return
        
        # Consulta SQL para CM
        query_cm = """
            SELECT 
                NRODCTO, 
                PASSWORDIN, 
                BRUTO, 
                ISNULL(IVABRUTO, 0) AS IVABRUTO, 
                ISNULL(VLRETFTE, 0) AS VLRETFTE, 
                ISNULL(VRETICA, 0) AS VRETICA, 
                ISNULL(VRETENIVA, 0) AS VRETENIVA, 
                (BRUTO + ISNULL(IVABRUTO, 0)) AS SUBTOTAL, 
                ((BRUTO + ISNULL(IVABRUTO, 0)) - ISNULL(VLRETFTE, 0) - ISNULL(VRETICA, 0) - ISNULL(VRETENIVA, 0)) AS TOTAL
            FROM TRADE
            WHERE LTRIM(RTRIM(dctoprv)) = ? AND NIT = ? AND TIPODCTO = ? AND ORIGEN = 'COM'
        """
        
        actualizadas = 0
        no_encontradas = 0
        errores = 0
        
        # Crear archivo de respaldo con timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archivo_respaldo = f"ids_actualizados_cm_{timestamp}.txt"
        ids_actualizados = []
        
        print(f"📝 Archivo de respaldo: {archivo_respaldo}\n")
        
        for factura in facturas_cm:
            factura_id = factura[0]
            nit = factura[1]
            numero_factura = factura[2].strip()
            clasificacion = factura[3]
            
            print(f"\n🔍 Procesando factura ID: {factura_id}")
            print(f"   NIT: {nit}")
            print(f"   Número Factura: {numero_factura}")
            print(f"   Clasificación: {clasificacion}")
            
            try:
                # Buscar en SQL Server
                cursor_sql.execute(query_cm, (numero_factura, nit, 'CM'))
                resultados = cursor_sql.fetchall()
                
                if resultados:
                    resultado = resultados[0]
                    print(f"   ✅ Encontrado en SQL Server")
                    print(f"      NRODCTO: {resultado[0]}")
                    print(f"      BRUTO: {resultado[2]}")
                    print(f"      IVABRUTO: {resultado[3]}")
                    print(f"      TOTAL: {resultado[8]}")
                    
                    # Actualizar en PostgreSQL
                    update_query = """
                        UPDATE facturas
                        SET numero_ofimatica = %s,
                            password_in = %s,
                            bruto = %s,
                            iva_bruto = %s,
                            vl_retfte = %s,
                            v_retica = %s,
                            v_reteniva = %s,
                            subtotal = %s,
                            total = %s,
                            clasificacion_final = 'CM',
                            valor_pagar = %s,
                            estado_final = 'Aprobado',
                            hora_actualizacion_final = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """
                    
                    cursor_pg.execute(update_query, (
                        str(resultado[0]),  # numero_ofimatica
                        str(resultado[1]),  # password_in
                        float(resultado[2]) if resultado[2] else 0,  # bruto
                        float(resultado[3]) if resultado[3] else 0,  # iva_bruto
                        float(resultado[4]) if resultado[4] else 0,  # vl_retfte
                        float(resultado[5]) if resultado[5] else 0,  # v_retica
                        float(resultado[6]) if resultado[6] else 0,  # v_reteniva
                        float(resultado[7]) if resultado[7] else 0,  # subtotal
                        float(resultado[8]) if resultado[8] else 0,  # total
                        float(resultado[8]) if resultado[8] else 0,  # valor_pagar
                        factura_id
                    ))
                    
                    conn_pg.commit()
                    actualizadas += 1
                    ids_actualizados.append(factura_id)
                    print(f"   ✅ Factura {factura_id} actualizada exitosamente")
                    
                else:
                    no_encontradas += 1
                    print(f"   ❌ No encontrada en SQL Server")
                    print(f"      Parámetros usados: dctoprv='{numero_factura}', NIT='{nit}', TIPODCTO='CM'")
                    
            except Exception as e:
                errores += 1
                print(f"   ❌ Error procesando factura {factura_id}: {str(e)}")
                conn_pg.rollback()
        
        # Guardar IDs actualizados en archivo de respaldo
        if ids_actualizados:
            try:
                with open(archivo_respaldo, 'w', encoding='utf-8') as f:
                    f.write(f"# Respaldo de automatización CM - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"# Total de facturas actualizadas: {len(ids_actualizados)}\n")
                    f.write("# Formato: ID por línea\n\n")
                    for factura_id in ids_actualizados:
                        f.write(f"{factura_id}\n")
                print(f"\n💾 Respaldo guardado: {archivo_respaldo}")
                print(f"   Total de IDs guardados: {len(ids_actualizados)}")
            except Exception as e:
                print(f"\n⚠️  Error al guardar respaldo: {str(e)}")
        else:
            print(f"\n📝 No se generó archivo de respaldo (ninguna factura actualizada)")
        
        # Resumen
        print("\n" + "=" * 60)
        print("RESUMEN DE AUTOMATIZACIÓN")
        print("=" * 60)
        print(f"✅ Facturas actualizadas: {actualizadas}")
        print(f"❌ No encontradas: {no_encontradas}")
        print(f"⚠️  Errores: {errores}")
        print(f"📊 Total procesadas: {len(facturas_cm)}")
        if ids_actualizados:
            print(f"💾 Archivo de respaldo: {archivo_respaldo}")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error general: {str(e)}")
        import traceback
        traceback.print_exc()
        
    finally:
        cursor_pg.close()
        conn_pg.close()
        cursor_sql.close()
        conn_sql.close()
        print("\n✅ Conexiones cerradas")

if __name__ == "__main__":
    automatizar_documentos_cm()

