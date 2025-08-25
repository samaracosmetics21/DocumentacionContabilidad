#!/usr/bin/env python3
"""
Script para probar el sistema de permisos dinámico
"""

from db_config import postgres_connection

def test_permisos():
    print("🧪 PROBANDO SISTEMA DE PERMISOS DINÁMICO")
    print("=" * 50)
    
    # Conectar a PostgreSQL
    conn_pg = postgres_connection()
    cursor_pg = conn_pg.cursor()
    
    # 1. Obtener todos los usuarios y sus grupos
    print("1. Usuarios y sus grupos:")
    cursor_pg.execute("""
        SELECT u.id, u.usuario, u.nombre, u.apellido, g.grupo
        FROM usuarios u
        INNER JOIN grupo_aprobacion g ON u.grupo_aprobacion_id = g.id
        ORDER BY u.id
    """)
    
    usuarios = cursor_pg.fetchall()
    print(f"📋 Total usuarios: {len(usuarios)}")
    for usuario in usuarios:
        print(f"  - ID: {usuario[0]}, Usuario: {usuario[1]}, Nombre: {usuario[2]} {usuario[3]}, Grupo: {usuario[4]}")
    
    # 2. Obtener todos los grupos disponibles
    print(f"\n2. Grupos disponibles:")
    cursor_pg.execute("SELECT id, grupo, descripcion FROM grupo_aprobacion ORDER BY grupo")
    grupos = cursor_pg.fetchall()
    print(f"📋 Total grupos: {len(grupos)}")
    for grupo in grupos:
        print(f"  - ID: {grupo[0]}, Grupo: {grupo[1]}, Descripción: {grupo[2]}")
    
    # 3. Definir permisos por módulo (copiado del código)
    PERMISOS_MODULOS = {
        'grupos': ['Contabilidad'],
        'usuarios': ['Contabilidad'],
        'gestion_inicial_mp': ['Compras'],
        'bodega': ['Bodega'],
        'compras': ['Compras'],
        'servicios': ['Contabilidad'],
        'asignaciones': ['*'],
        'pago_servicios': ['jefe_servicios'],
        'pago_mp': ['jefe_mp'],
        'gestion_final': ['Contabilidad'],
        'tesoreria': ['Contabilidad', 'jefe_servicios', 'jefe_mp', 'tesoreria'],
        'facturas_resumen': ['*'],
        'auditor': ['Auditores']
    }
    
    # 4. Probar permisos para cada usuario
    print(f"\n3. Análisis de permisos por usuario:")
    for usuario in usuarios:
        usuario_id = usuario[0]
        usuario_nombre = usuario[1]
        grupo_usuario = usuario[4]
        
        print(f"\n👤 Usuario: {usuario_nombre} (Grupo: {grupo_usuario})")
        
        modulos_acceso = []
        for modulo, permisos in PERMISOS_MODULOS.items():
            if '*' in permisos or grupo_usuario in permisos:
                modulos_acceso.append(modulo)
        
        print(f"  ✅ Módulos con acceso: {len(modulos_acceso)}")
        for modulo in modulos_acceso:
            print(f"    - {modulo}")
        
        modulos_sin_acceso = [modulo for modulo in PERMISOS_MODULOS.keys() if modulo not in modulos_acceso]
        if modulos_sin_acceso:
            print(f"  ❌ Módulos sin acceso: {len(modulos_sin_acceso)}")
            for modulo in modulos_sin_acceso:
                print(f"    - {modulo}")
    
    # 5. Resumen por grupo
    print(f"\n4. Resumen por grupo:")
    grupos_unicos = list(set([usuario[4] for usuario in usuarios]))
    for grupo in grupos_unicos:
        usuarios_grupo = [u for u in usuarios if u[4] == grupo]
        modulos_grupo = []
        for modulo, permisos in PERMISOS_MODULOS.items():
            if '*' in permisos or grupo in permisos:
                modulos_grupo.append(modulo)
        
        print(f"\n🏷️  Grupo: {grupo} ({len(usuarios_grupo)} usuarios)")
        print(f"  📋 Módulos accesibles: {len(modulos_grupo)}")
        for modulo in modulos_grupo:
            print(f"    - {modulo}")
    
    # Cerrar conexión
    cursor_pg.close()
    conn_pg.close()
    
    print(f"\n✅ PRUEBA COMPLETADA")
    print("=" * 50)

if __name__ == "__main__":
    test_permisos() 