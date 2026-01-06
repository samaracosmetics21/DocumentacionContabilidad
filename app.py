from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import psycopg2
from db_config import sql_server_connection, postgres_connection
import os
from datetime import datetime
from werkzeug.security import generate_password_hash
from flask import session  
from werkzeug.security import check_password_hash
from functools import wraps
from flask_login import current_user
from pyodbc import Error
from flask import jsonify
import decimal
import json
from email_config import enviar_correo_asignacion


app = Flask(__name__)
app.secret_key = "secret_key_example"
ROOT_FOLDER = os.path.abspath(os.path.dirname(__file__))  # Directorio raíz del proyecto
UPLOAD_FOLDER = os.path.join(ROOT_FOLDER, 'static', "uploads")  # Carpeta principal para archivos
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Asegurar directorio de carga
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ============================================================================
# SISTEMA DE PERMISOS DINÁMICO
# ============================================================================

def obtener_permisos_usuario(usuario_id):
    """
    Obtiene el grupo del usuario basado en su ID
    Retorna el nombre del grupo o None si no se encuentra
    """
    try:
        conn_pg = postgres_connection()
        cursor = conn_pg.cursor()
        
        cursor.execute("""
            SELECT g.grupo 
            FROM usuarios u
            INNER JOIN grupo_aprobacion g ON u.grupo_aprobacion_id = g.id 
            WHERE u.id = %s
        """, (usuario_id,))
        
        grupo = cursor.fetchone()
        cursor.close()
        conn_pg.close()
        
        return grupo[0] if grupo else None
    except Exception as e:
        print(f"Error obteniendo permisos del usuario {usuario_id}: {e}")
        return None

# Diccionario de permisos por módulo
# '*' significa que todos los usuarios pueden acceder
# Lista vacía [] significa que ningún usuario puede acceder
PERMISOS_MODULOS = {
    'grupos': ['Contabilidad', 'Sistemas'],  # Contabilidad y Sistemas pueden gestionar grupos
    'usuarios': ['Contabilidad', 'Sistemas'],  # Contabilidad y Sistemas pueden gestionar usuarios
    'gestion_inicial_mp': ['Compras', 'Sistemas', 'Contabilidad'],  # Compras y Sistemas pueden gestionar órdenes de compra
    'bodega': ['Bodega', 'Sistemas', 'Contabilidad'],  # Bodega y Sistemas pueden aprobar en bodega
    'compras': ['Compras', 'Sistemas', 'Bodega', 'Contabilidad'],  # Compras y Sistemas pueden aprobar en compras
    'servicios': ['Contabilidad', 'Sistemas'],  # Contabilidad y Sistemas pueden asignar servicios
    'asignaciones': ['*'],  # Todos los usuarios pueden ver sus asignaciones
    'pago_servicios': ['jefe_servicios', 'Sistemas', 'Contabilidad'],  # Jefe de servicios y Sistemas pueden aprobar pagos de servicios
    'pago_mp': ['jefe_mp', 'Sistemas', 'Contabilidad'],  # Jefe de MP y Sistemas pueden aprobar pagos de MP
    'gestion_final': ['Contabilidad', 'Sistemas'],  # Contabilidad y Sistemas pueden hacer gestión final
    'tesoreria': ['Contabilidad', 'jefe_servicios', 'jefe_mp', 'tesoreria', 'Sistemas'],  # Múltiples grupos pueden acceder a tesorería
    'facturas_resumen': ['*'],  # Todos los usuarios EXCEPTO Genericos (ver función tiene_permiso)
    'auditor': ['Auditores', 'Sistemas', 'Contabilidad']  # Auditores, Sistemas y Contabilidad pueden acceder a auditoría
}

# Descripciones detalladas de permisos por módulo
DESCRIPCIONES_PERMISOS = {
    'grupos': {
        'nombre': 'Gestión de Grupos',
        'descripcion': 'Crear, editar y eliminar grupos de aprobación. Define los roles del sistema.',
        'acciones': ['Crear grupos', 'Editar grupos', 'Eliminar grupos', 'Asignar permisos']
    },
    'usuarios': {
        'nombre': 'Gestión de Usuarios',
        'descripcion': 'Crear, editar y eliminar usuarios del sistema. Asignar grupos y permisos.',
        'acciones': ['Crear usuarios', 'Editar usuarios', 'Eliminar usuarios', 'Asignar grupos']
    },
    'gestion_inicial_mp': {
        'nombre': 'Gestión Inicial MP',
        'descripcion': 'Registrar y gestionar órdenes de compra de materia prima.',
        'acciones': ['Registrar órdenes', 'Editar órdenes', 'Subir archivos', 'Consultar órdenes']
    },
    'bodega': {
        'nombre': 'Aprobación Bodega',
        'descripcion': 'Aprobar facturas en el módulo de bodega. Validar recepción de mercancía.',
        'acciones': ['Aprobar facturas', 'Asignar lotes', 'Cerrar órdenes', 'Validar recepción']
    },
    'compras': {
        'nombre': 'Aprobación Compras',
        'descripcion': 'Aprobar facturas en el módulo de compras. Validar documentación.',
        'acciones': ['Aprobar facturas', 'Validar remisiones', 'Registrar pagos', 'Gestionar compras']
    },
    'servicios': {
        'nombre': 'Asignación Servicios',
        'descripcion': 'Asignar facturas de servicios a usuarios específicos para su procesamiento.',
        'acciones': ['Asignar facturas', 'Enviar notificaciones', 'Gestionar asignaciones']
    },
    'asignaciones': {
        'nombre': 'Mis Asignaciones',
        'descripcion': 'Ver y gestionar las facturas asignadas al usuario actual.',
        'acciones': ['Ver asignaciones', 'Aprobar facturas', 'Gestionar tareas']
    },
    'pago_servicios': {
        'nombre': 'Pago Servicios',
        'descripcion': 'Aprobar pagos de facturas de servicios. Autorización de jefe de servicios.',
        'acciones': ['Aprobar pagos', 'Autorizar servicios', 'Gestionar pagos']
    },
    'pago_mp': {
        'nombre': 'Pago Materia Prima',
        'descripcion': 'Aprobar pagos de facturas de materia prima. Autorización de jefe de MP.',
        'acciones': ['Aprobar pagos', 'Autorizar MP', 'Gestionar pagos MP']
    },
    'gestion_final': {
        'nombre': 'Gestión Final',
        'descripcion': 'Procesamiento final de facturas. Vinculación automática con SQL Server.',
        'acciones': ['Procesar facturas', 'Vincular documentos', 'Actualizar datos', 'Finalizar proceso']
    },
    'tesoreria': {
        'nombre': 'Tesorería',
        'descripcion': 'Vincular documentos de pago con facturas. Gestión de comprobantes de egreso.',
        'acciones': ['Vincular documentos', 'Subir archivos PDF', 'Gestionar pagos', 'Crear comprobantes']
    },
    'facturas_resumen': {
        'nombre': 'Resumen Facturas',
        'descripcion': 'Ver el estado completo de todas las facturas del sistema.',
        'acciones': ['Consultar facturas', 'Ver estados', 'Exportar datos', 'Generar reportes']
    },
    'auditor': {
        'nombre': 'Auditoría',
        'descripcion': 'Revisar y aprobar facturas desde el punto de vista de auditoría.',
        'acciones': ['Revisar facturas', 'Aprobar auditoría', 'Validar procesos', 'Generar reportes']
    }
}

def tiene_permiso(usuario_id, modulo):
    """
    Verifica si un usuario tiene permiso para acceder a un módulo específico
    """
    grupo_usuario = obtener_permisos_usuario(usuario_id)
    if not grupo_usuario:
        return False
    
    permisos_modulo = PERMISOS_MODULOS.get(modulo, [])
    
    # Si '*' está en los permisos, todos pueden acceder EXCEPTO grupos bloqueados
    if '*' in permisos_modulo:
        # Bloquear acceso a "Resumen Facturas" para usuarios del grupo "Genericos"
        if modulo == 'facturas_resumen' and grupo_usuario == 'Genericos':
            return False
        return True
    
    # Si el grupo del usuario está en los permisos del módulo
    return grupo_usuario in permisos_modulo

# ============================================================================
# FIN SISTEMA DE PERMISOS DINÁMICO
# ============================================================================

def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Por favor, inicia sesión para acceder a esta página.", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapped


@app.route("/buscar_cliente", methods=["GET"])
def buscar_cliente():
    query_param = request.args.get("q", "").upper()  # Convertir el término de búsqueda a mayúsculas
    
    if query_param:
        try:
            conn = sql_server_connection()  # Asegúrate de que la conexión a SQL Server esté funcionando
            if not conn:
                return jsonify({"error": "No se pudo conectar a la base de datos"}), 500
            
            cursor = conn.cursor()

            # Verificar si es un NIT (comprobando si contiene solo números)
            if query_param.isdigit():
                # Buscar por NIT
                query = """
                    SELECT TOP 10 nit, nombre 
                    FROM MTPROCLI 
                    WHERE nit LIKE ?  -- Buscar por NIT
                    ORDER BY nombre
                """
                cursor.execute(query, ('%' + query_param + '%',))
            else:
                # Buscar por nombre
                query = """
                    SELECT TOP 10 nit, nombre 
                    FROM MTPROCLI 
                    WHERE UPPER(nombre) LIKE ?  -- Buscar por nombre
                    ORDER BY nombre
                """
                cursor.execute(query, ('%' + query_param + '%',))
            
            resultados = cursor.fetchall()

            # Formatear los resultados como una lista de diccionarios
            clientes = [{"nit": row[0], "nombre": row[1]} for row in resultados]
            
            return jsonify(clientes)
        
        except Exception as e:
            print(f"Error en la consulta: {str(e)}")
            return jsonify({"error": str(e)}), 500
    else:
        return jsonify([])  # Si no se proporciona un término de búsqueda, devolver lista vacía



@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    # Obtener permisos del usuario para el menú dinámico
    usuario_id = session.get("user_id")
    grupo_usuario = obtener_permisos_usuario(usuario_id)
    
    # Redirigir usuarios según su grupo a su vista específica
    if grupo_usuario:
        if grupo_usuario == 'Auditores':
            return redirect(url_for('auditor'))
        elif grupo_usuario == 'Compras':
            return redirect(url_for('gestion_inicial'))
        elif grupo_usuario == 'Bodega':
            return redirect(url_for('gestion_bodega'))
        elif grupo_usuario == 'jefe_servicios':
            return redirect(url_for('pago_servicios'))
        elif grupo_usuario == 'jefe_mp':
            return redirect(url_for('pago_mp'))
        elif grupo_usuario == 'tesoreria':
            return redirect(url_for('tesoreria'))
        elif grupo_usuario not in ['Contabilidad', 'Sistemas']:
            # Usuarios genéricos van a asignaciones
            return redirect(url_for('gestion_asignaciones'))
    
    if request.method == "POST":
        try:
            # Procesar datos del formulario
            nit = request.form.get("nit")
            numero_factura = request.form.get("numero_factura")
            fecha_seleccionada = request.form.get("fecha")
            clasificacion = request.form.get("clasificacion")
            archivo = request.files.get("archivo")
            observaciones = request.form.get("observaciones")

            # Validar fecha
            if not fecha_seleccionada:
                return jsonify(success=False, message="La fecha es obligatoria"), 400
            
            # Validar que la fecha no sea futura
            from datetime import date
            try:
                fecha_ingresada = datetime.strptime(fecha_seleccionada, '%Y-%m-%d').date()
                fecha_hoy = date.today()
                if fecha_ingresada > fecha_hoy:
                    return jsonify(success=False, message="No se permiten fechas futuras"), 400
            except ValueError:
                return jsonify(success=False, message="Formato de fecha inválido"), 400

            if not archivo or not archivo.filename:
                return jsonify(success=False, message="Debes subir un archivo"), 400

            clasificacion_texto = "Facturas" if clasificacion == "1" else "Servicios"
            fecha_directorio = fecha_seleccionada.replace("-", "")
            ruta_directorio = os.path.join(app.config["UPLOAD_FOLDER"], clasificacion_texto, nit, fecha_directorio)
            os.makedirs(ruta_directorio, exist_ok=True)
            archivo_path = os.path.join(ruta_directorio, archivo.filename)
            archivo.save(archivo_path)
            ruta_relativa = os.path.relpath(archivo_path, app.config["UPLOAD_FOLDER"])
            ruta_relativa = ruta_relativa.replace("static/", "")

            # Consultar NIT en SQL Server
            conn = sql_server_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT nombre FROM MTPROCLI WHERE LTRIM(RTRIM(nit)) = ?", nit.strip())
            row = cursor.fetchone()
            if row:
                nombre = row[0]
            else:
                return jsonify(success=False, message="NIT no encontrado en SQL Server"), 400

            # Guardar datos en PostgreSQL
            conn_pg = postgres_connection()
            if not conn_pg:
                raise Exception("Conexión a PostgreSQL fallida. Verifica los parámetros de conexión en db_config.py.")
            cursor_pg = conn_pg.cursor()

            cursor_pg.execute("SELECT COUNT(*) FROM facturas WHERE numero_factura = %s AND nit = %s", (numero_factura, nit))
            count = cursor_pg.fetchone()[0]
            if count > 0:
                return jsonify(success=False, message="La factura con este número ya ha sido registrada"), 400

            fecha_registro = datetime.now()
            print("Datos a insertar en PostgreSQL:")
            print(f"NIT: {nit}")
            print(f"Nombre: {nombre}")
            print(f"Número de Factura: {numero_factura}")
            print(f"Fecha Seleccionada: {fecha_seleccionada}")
            print(f"Fecha Registro: {fecha_registro}")
            print(f"Clasificación: {clasificacion_texto}")
            print(f"Ruta del Archivo: {ruta_relativa}")
            print(f"Observaciones del registro: {observaciones}")
            query = """
                INSERT INTO facturas (nit, nombre, numero_factura, fecha_seleccionada, 
                fecha_registro, clasificacion, archivo_path, observaciones_regis) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor_pg.execute(query, (
                nit, nombre, numero_factura, fecha_seleccionada,
                fecha_registro, clasificacion_texto, ruta_relativa, observaciones
            ))
            conn_pg.commit()

            return jsonify(success=True)
        
        except Exception as e:
            print("Error durante el POST:", e)
            return jsonify(success=False, message=str(e)), 500

    return render_template("index.html", 
                         grupo_usuario=grupo_usuario,
                         permisos_modulos=PERMISOS_MODULOS)




@app.route("/buscar_nombre", methods=["POST"])
@login_required
def buscar_nombre():
    """
    Endpoint para buscar el nombre del cliente en SQL Server
    basado en el NIT ingresado.
    """
    nit = request.form.get("nit", "").strip()

    if not nit:
        return jsonify({"error": "NIT no proporcionado"}), 400

    try:
        conn = sql_server_connection()
        cursor = conn.cursor()

        # Consulta con LTRIM y RTRIM
        cursor.execute("SELECT nombre FROM MTPROCLI WHERE LTRIM(RTRIM(nit)) = ?", nit)
        row = cursor.fetchone()

        if row:
            return jsonify({"nombre": row[0]})
        else:
            return jsonify({"nombre": None})

    except Exception as e:
        return jsonify({"error": f"Error al buscar el NIT: {str(e)}"}), 500

    finally:
        conn.close()

# endpoint para modulo de editar facturas
@app.route("/buscar_factura", methods=["GET"])
@login_required
def buscar_factura():
    factura_id = request.args.get("id")

    if not factura_id:
        return jsonify({"error": "ID de factura no proporcionado"}), 400

    try:
        conn_pg = postgres_connection()
        cursor_pg = conn_pg.cursor()
        cursor_pg.execute("SELECT id, nit, nombre, numero_factura, fecha_seleccionada, clasificacion, archivo_path, observaciones_regis, nrodcto_oc FROM facturas WHERE id = %s", (factura_id,))
        row = cursor_pg.fetchone()

        if row:
            factura = {
                "id": row[0],
                "nit": row[1],
                "nombre": row[2],
                "numero_factura": row[3],
                "fecha_seleccionada": row[4].strftime("%Y-%m-%d"),
                "clasificacion": row[5],
                "archivo_path": row[6],
                "observaciones_regis": row[7],
                "nrodcto_oc": row[8] if row[8] is not None else None
            }
            return jsonify(factura)
        else:
            return jsonify({"error": "Factura no encontrada"}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===== ENDPOINTS AJAX PARA BODEGA =====

@app.route("/bodega/aprobar", methods=["POST"])
@login_required
def bodega_aprobar_ajax():
    """Endpoint AJAX para aprobar facturas en bodega sin refrescar la página"""
    try:
        data = request.get_json()
        orden_id = data.get('orden_id')
        factura_id = data.get('factura_id')
        referencias = data.get('referencias', [])
        lotes = data.get('lotes', [])
        usuario_id = session.get("user_id")
        
        if not all([orden_id, factura_id, usuario_id]):
            return jsonify({"success": False, "message": "Datos incompletos"}), 400
        
        conn_pg = postgres_connection()
        cursor_pg = conn_pg.cursor()
        
        # Validar permisos
        cursor_pg.execute("""
            SELECT g.grupo 
            FROM usuarios u 
            INNER JOIN grupo_aprobacion g ON u.grupo_aprobacion_id = g.id 
            WHERE u.id = %s AND g.grupo = 'Bodega'
        """, (usuario_id,))
        grupo = cursor_pg.fetchone()
        
        if not grupo:
            return jsonify({"success": False, "message": "No tienes permisos para aprobar facturas en Bodega"}), 403
        
        # Obtener nrodcto_oc
        cursor_pg.execute("SELECT nrodcto_oc FROM ordenes_compras WHERE id = %s", (orden_id,))
        orden = cursor_pg.fetchone()
        
        if not orden:
            return jsonify({"success": False, "message": "Orden de compra no encontrada"}), 404
        
        nrodcto_oc = orden[0]
        
        # Validar factura
        cursor_pg.execute("SELECT id FROM facturas WHERE id = %s AND estado = 'Pendiente'", (factura_id,))
        factura = cursor_pg.fetchone()
        
        if not factura:
            return jsonify({"success": False, "message": "Factura no válida o ya procesada"}), 400
        
        # Procesar lotes
        lotes_oc = []
        for i, referencia in enumerate(referencias):
            if i < len(lotes) and lotes[i]:
                lotes_oc.append(f"{referencia}:{lotes[i]}")
        
        lotes_oc_str = ",".join(lotes_oc) if lotes_oc else None
        
        # Actualizar factura
        hora_aprobacion = datetime.now()
        cursor_pg.execute("""
            UPDATE facturas
            SET 
                hora_aprobacion = %s, 
                aprobado_bodega = %s,
                lotes_oc = %s, 
                nrodcto_oc = %s
            WHERE id = %s
        """, (hora_aprobacion, usuario_id, lotes_oc_str, nrodcto_oc, factura_id))
        
        conn_pg.commit()
        cursor_pg.close()
        conn_pg.close()
        
        return jsonify({
            "success": True, 
            "message": "Factura aprobada exitosamente",
            "hora_aprobacion": hora_aprobacion.strftime("%Y-%m-%d %H:%M:%S")
        })
        
    except Exception as e:
        print(f"Error en bodega_aprobar_ajax: {str(e)}")
        return jsonify({"success": False, "message": f"Error interno: {str(e)}"}), 500


@app.route("/bodega/cerrar_factura", methods=["POST"])
@login_required
def bodega_cerrar_factura_ajax():
    """Endpoint AJAX para cerrar facturas sin refrescar la página"""
    try:
        data = request.get_json()
        factura_id = data.get('factura_id')
        usuario_id = session.get("user_id")
        
        if not all([factura_id, usuario_id]):
            return jsonify({"success": False, "message": "Datos incompletos"}), 400
        
        conn_pg = postgres_connection()
        cursor_pg = conn_pg.cursor()
        
        # Validar factura
        cursor_pg.execute("SELECT id FROM facturas WHERE id = %s AND estado = 'Pendiente'", (factura_id,))
        factura = cursor_pg.fetchone()
        
        if not factura:
            return jsonify({"success": False, "message": "Factura no válida o ya procesada"}), 400
        
        # Cerrar factura
        cursor_pg.execute("UPDATE facturas SET estado = 'Aprobado' WHERE id = %s", (factura_id,))
        conn_pg.commit()
        cursor_pg.close()
        conn_pg.close()
        
        return jsonify({
            "success": True, 
            "message": "Factura cerrada exitosamente"
        })
        
    except Exception as e:
        print(f"Error en bodega_cerrar_factura_ajax: {str(e)}")
        return jsonify({"success": False, "message": f"Error interno: {str(e)}"}), 500


@app.route("/bodega/cerrar_orden", methods=["POST"])
@login_required
def bodega_cerrar_orden_ajax():
    """Endpoint AJAX para cerrar órdenes de compra sin refrescar la página"""
    try:
        data = request.get_json()
        orden_id = data.get('orden_id')
        usuario_id = session.get("user_id")
        
        if not all([orden_id, usuario_id]):
            return jsonify({"success": False, "message": "Datos incompletos"}), 400
        
        conn_pg = postgres_connection()
        cursor_pg = conn_pg.cursor()
        
        # Validar orden
        cursor_pg.execute("SELECT id FROM ordenes_compras WHERE id = %s", (orden_id,))
        orden = cursor_pg.fetchone()
        
        if not orden:
            return jsonify({"success": False, "message": "Orden de compra no encontrada"}), 404
        
        # Cerrar orden
        cursor_pg.execute("UPDATE ordenes_compras SET estado = 'Cerrada' WHERE id = %s", (orden_id,))
        conn_pg.commit()
        cursor_pg.close()
        conn_pg.close()
        
        return jsonify({
            "success": True, 
            "message": "Orden de compra cerrada exitosamente"
        })
        
    except Exception as e:
        print(f"Error en bodega_cerrar_orden_ajax: {str(e)}")
        return jsonify({"success": False, "message": f"Error interno: {str(e)}"}), 500


@app.route("/actualizar_factura", methods=["POST"])
@login_required
def actualizar_factura():
    try:
        factura_id = request.form.get("id")
        nit = request.form.get("nit")
        numero_factura = request.form.get("numero_factura")
        fecha = request.form.get("fecha")
        clasificacion = request.form.get("clasificacion")
        observaciones = request.form.get("observaciones")
        archivo = request.files.get("archivo")
        nrodcto_oc = request.form.get("nrodcto_oc", "").strip()
        
        # Mapear valor numérico a texto de clasificación
        if clasificacion == "1":
            clasificacion_texto = "Facturas"
        elif clasificacion == "2":
            clasificacion_texto = "Servicios"
        else:
            # Fallback: intentar detectar por texto (compatibilidad con datos antiguos)
            if clasificacion and "Servicios" in clasificacion:
                clasificacion_texto = "Servicios"
            else:
                clasificacion_texto = "Facturas"
        
        if not factura_id:
            return jsonify({"error": "ID de factura no proporcionado"}), 400

        # Obtener nombre desde SQL Server
        conn_sql = sql_server_connection()
        cursor_sql = conn_sql.cursor()
        cursor_sql.execute("SELECT nombre FROM MTPROCLI WHERE LTRIM(RTRIM(nit)) = ?", nit.strip())
        row = cursor_sql.fetchone()
        if not row:
            return jsonify({"error": "NIT no encontrado en SQL Server"}), 400
        nombre = row[0]

        # Construir ruta de archivo si se cargó uno nuevo
        ruta_relativa = None
        if archivo and archivo.filename:
            #clasificacion_texto = "Facturas" if clasificacion == "Facturas" else "Servicios"
            fecha_directorio = fecha.replace("-", "")
            ruta_directorio = os.path.join(app.config["UPLOAD_FOLDER"], clasificacion_texto, nit, fecha_directorio)
            os.makedirs(ruta_directorio, exist_ok=True)
            archivo_path = os.path.join(ruta_directorio, archivo.filename)
            archivo.save(archivo_path)
            ruta_relativa = os.path.relpath(archivo_path, app.config["UPLOAD_FOLDER"])
            ruta_relativa = ruta_relativa.replace("static/", "")

        # Actualizar en PostgreSQL
        conn_pg = postgres_connection()
        cursor_pg = conn_pg.cursor()
        
        # Recuperar el valor actual de nrodcto_oc desde la base de datos
        cursor_pg.execute("SELECT nrodcto_oc FROM facturas WHERE id = %s", (factura_id,))
        row_actual = cursor_pg.fetchone()
        nrodcto_oc_actual = row_actual[0] if row_actual and row_actual[0] else None
        
        # Si se proporcionó un nuevo valor en el formulario, usarlo; sino, mantener el actual
        if nrodcto_oc and nrodcto_oc.strip():
            nrodcto_oc_value = nrodcto_oc.strip()
        else:
            # Mantener el valor actual o usar valor por defecto si no existe (NOT NULL constraint)
            nrodcto_oc_value = nrodcto_oc_actual if nrodcto_oc_actual else 'DEFAULT_NRODCTO'

        query = """
            UPDATE facturas
            SET nit = %s, nombre = %s, numero_factura = %s,
                fecha_seleccionada = %s, clasificacion = %s,
                observaciones_regis = %s, nrodcto_oc = %s
                {archivo_sql}
            WHERE id = %s
        """.format(archivo_sql=", archivo_path = %s" if ruta_relativa else "")

        params = [nit, nombre, numero_factura, fecha, clasificacion_texto, observaciones, nrodcto_oc_value]
        if ruta_relativa:
            params.append(ruta_relativa)
        params.append(factura_id)

        cursor_pg.execute(query, tuple(params))
        conn_pg.commit()

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Gestión de Grupos
@app.route("/grupos", methods=["GET", "POST"])
@login_required
def gestion_grupos():
    # Obtener permisos del usuario para el menú dinámico
    usuario_id = session.get("user_id")
    grupo_usuario = obtener_permisos_usuario(usuario_id)
    
    # Verificar si el usuario tiene permiso para acceder a este módulo
    if not tiene_permiso(usuario_id, 'grupos'):
        flash("No tienes permisos para acceder a este módulo.", "error")
        return redirect("/")
    
    if request.method == "POST":
        grupo = request.form.get("grupo")
        descripcion = request.form.get("descripcion")

        try:
            conn_pg = postgres_connection()
            cursor = conn_pg.cursor()

            # Insertar el nuevo grupo en la base de datos
            cursor.execute("INSERT INTO grupo_aprobacion (grupo, descripcion) VALUES (%s, %s)", (grupo, descripcion))
            conn_pg.commit()
            flash("Grupo creado exitosamente", "success")
        except Exception as e:
            flash(f"Error creando grupo: {str(e)}", "error")
        finally:
            if cursor:
                cursor.close()
            if conn_pg:
                conn_pg.close()

    return render_template("grupos.html", 
                         grupo_usuario=grupo_usuario,
                         permisos_modulos=PERMISOS_MODULOS,
                         descripciones_permisos=DESCRIPCIONES_PERMISOS)


# Gestión de Usuarios
@app.route("/usuarios", methods=["GET", "POST"])
@login_required
def gestion_usuarios():
    # Obtener permisos del usuario para el menú dinámico
    usuario_id = session.get("user_id")
    grupo_usuario = obtener_permisos_usuario(usuario_id)
    
    # Verificar si el usuario tiene permiso para acceder a este módulo
    if not tiene_permiso(usuario_id, 'usuarios'):
        flash("No tienes permisos para acceder a este módulo.", "error")
        return redirect("/")
    
    # Establecer la conexión a PostgreSQL
    conn_pg = None
    cursor = None
    print("Iniciando el flujo de gestión de usuarios...")
    try:
        print("Conectando a PostgreSQL...")
        conn_pg = postgres_connection()
        cursor = conn_pg.cursor()
        print("Conexión a PostgreSQL establecida.")

        if request.method == "POST":
            print("Procesando solicitud POST...")
            # Obtener datos del formulario
            nombre = request.form.get("nombre")
            apellido = request.form.get("apellido")
            usuario = request.form.get("usuario")
            correo = request.form.get("correo")
            grupo_id = request.form.get("grupo_aprobacion")
            password = request.form.get("password")

            print("Datos recibidos del formulario:")
            print(f"Nombre: {nombre}, Apellido: {apellido}, Usuario: {usuario}, Correo: {correo}, Grupo ID: {grupo_id}")

            try:
                # VALIDAR SI EL USUARIO YA EXISTE
                print("Validando si el usuario ya existe...")
                cursor.execute("SELECT id FROM usuarios WHERE usuario = %s", (usuario,))
                usuario_existente = cursor.fetchone()
                
                if usuario_existente:
                    print(f"❌ Error: El usuario '{usuario}' ya existe en la base de datos")
                    flash(f"Error: El usuario '{usuario}' ya existe. Por favor, elige otro nombre de usuario.", "error")
                    return redirect("/usuarios")
                
                # VALIDAR SI EL CORREO YA EXISTE
                print("Validando si el correo ya existe...")
                cursor.execute("SELECT id FROM usuarios WHERE correo = %s", (correo,))
                correo_existente = cursor.fetchone()
                
                if correo_existente:
                    print(f"❌ Error: El correo '{correo}' ya existe en la base de datos")
                    flash(f"Error: El correo '{correo}' ya está registrado. Por favor, usa otro correo.", "error")
                    return redirect("/usuarios")
                
                print("✅ Validaciones pasadas: usuario y correo únicos")
                
                # Encriptar la contraseña
                print("Encriptando la contraseña...")
                password_hash = generate_password_hash(password)
                print("Contraseña encriptada correctamente.")

                # Insertar datos en la tabla usuarios
                query = """
                    INSERT INTO usuarios (nombre, apellido, usuario, correo, grupo_aprobacion_id, password_hash)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
                print("Ejecutando consulta para insertar usuario...")
                cursor.execute(query, (nombre, apellido, usuario, correo, grupo_id, password_hash))
                conn_pg.commit()  # Confirmar transacción
                print("Usuario creado exitosamente en la base de datos.")
                flash("Usuario creado exitosamente", "success")
            except Exception as e:
                conn_pg.rollback()  # Revertir la transacción si ocurre un error
                print(f"Error al insertar usuario: {e}")
                flash(f"Error creando usuario: {str(e)}", "error")

        # Consultar los grupos disponibles
        try:
            print("Consultando los grupos disponibles...")
            cursor.execute("SELECT id, grupo FROM grupo_aprobacion")
            grupos = cursor.fetchall()  # Obtener todos los registros (id y nombre del grupo)
            print(f"Grupos obtenidos: {grupos}")
        except Exception as e:
            print(f"Error al consultar grupos: {e}")
            flash(f"Error consultando grupos: {str(e)}", "error")
            grupos = []

        # Consultar usuarios existentes
        try:
            print("Consultando usuarios existentes...")
            cursor.execute("""
                SELECT u.id, u.nombre, u.apellido, u.usuario, u.correo, g.grupo
                FROM usuarios u
                INNER JOIN grupo_aprobacion g ON u.grupo_aprobacion_id = g.id
                ORDER BY u.nombre, u.apellido
            """)
            usuarios_existentes = cursor.fetchall()
            print(f"Usuarios obtenidos: {len(usuarios_existentes)}")
        except Exception as e:
            print(f"Error al consultar usuarios: {e}")
            flash(f"Error consultando usuarios: {str(e)}", "error")
            usuarios_existentes = []

    except Exception as e:
        print(f"Error conectando a la base de datos: {e}")
        flash(f"Error conectando a la base de datos: {str(e)}", "error")
        grupos = []
        usuarios_existentes = []

    finally:
        # Cerrar la conexión y el cursor para evitar problemas de recursos
        if cursor:
            print("Cerrando el cursor...")
            cursor.close()
        if conn_pg:
            print("Cerrando la conexión a PostgreSQL...")
            conn_pg.close()

    print("Renderizando la plantilla 'usuarios.html'.")
    # Renderizar la plantilla con los grupos
    return render_template("usuarios.html", 
                         grupos=grupos,
                         usuarios_existentes=usuarios_existentes,
                         grupo_usuario=grupo_usuario,
                         permisos_modulos=PERMISOS_MODULOS)


# Verificar si un usuario ya existe
@app.route("/verificar_usuario", methods=["POST"])
@login_required
def verificar_usuario():
    """
    Verifica si un nombre de usuario o correo ya existe
    """
    try:
        data = request.get_json()
        usuario = data.get('usuario', '').strip()
        correo = data.get('correo', '').strip()
        
        conn_pg = postgres_connection()
        cursor = conn_pg.cursor()
        
        # Verificar usuario
        usuario_existe = False
        if usuario:
            cursor.execute("SELECT id FROM usuarios WHERE usuario = %s", (usuario,))
            usuario_existe = cursor.fetchone() is not None
        
        # Verificar correo
        correo_existe = False
        if correo:
            cursor.execute("SELECT id FROM usuarios WHERE correo = %s", (correo,))
            correo_existe = cursor.fetchone() is not None
        
        return jsonify({
            'usuario_existe': usuario_existe,
            'correo_existe': correo_existe,
            'disponible': not usuario_existe and not correo_existe
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn_pg:
            conn_pg.close()


# Obtener datos de un usuario específico para edición
@app.route("/obtener_usuario/<int:usuario_id>", methods=["GET"])
@login_required
def obtener_usuario(usuario_id):
    # Verificar permisos
    usuario_actual_id = session.get("user_id")
    if not tiene_permiso(usuario_actual_id, 'usuarios'):
        return jsonify({"error": "No tienes permisos para acceder a esta funcionalidad"}), 403
    
    try:
        conn_pg = postgres_connection()
        cursor = conn_pg.cursor()
        
        cursor.execute("""
            SELECT u.id, u.nombre, u.apellido, u.usuario, u.correo, u.grupo_aprobacion_id, g.grupo
            FROM usuarios u
            INNER JOIN grupo_aprobacion g ON u.grupo_aprobacion_id = g.id
            WHERE u.id = %s
        """, (usuario_id,))
        
        usuario = cursor.fetchone()
        
        if usuario:
            return jsonify({
                "id": usuario[0],
                "nombre": usuario[1],
                "apellido": usuario[2],
                "usuario": usuario[3],
                "correo": usuario[4],
                "grupo_aprobacion_id": usuario[5],
                "grupo": usuario[6]
            })
        else:
            return jsonify({"error": "Usuario no encontrado"}), 404
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn_pg:
            conn_pg.close()


# Actualizar usuario
@app.route("/actualizar_usuario", methods=["POST"])
@login_required
def actualizar_usuario():
    # Verificar permisos
    usuario_actual_id = session.get("user_id")
    if not tiene_permiso(usuario_actual_id, 'usuarios'):
        return jsonify({"error": "No tienes permisos para acceder a esta funcionalidad"}), 403
    
    try:
        # Obtener datos del formulario
        usuario_id = request.form.get("usuario_id")
        nombre = request.form.get("nombre")
        apellido = request.form.get("apellido")
        usuario = request.form.get("usuario")
        correo = request.form.get("correo")
        grupo_id = request.form.get("grupo_aprobacion")
        password = request.form.get("password")
        
        if not usuario_id or not usuario_id.isdigit():
            return jsonify({"error": "ID de usuario no válido"}), 400
        
        conn_pg = postgres_connection()
        cursor = conn_pg.cursor()
        
        # Verificar si el usuario existe
        cursor.execute("SELECT id FROM usuarios WHERE id = %s", (usuario_id,))
        if not cursor.fetchone():
            return jsonify({"error": "Usuario no encontrado"}), 404
        
        # Construir query de actualización
        update_fields = []
        update_values = []
        
        if nombre:
            update_fields.append("nombre = %s")
            update_values.append(nombre)
        
        if apellido:
            update_fields.append("apellido = %s")
            update_values.append(apellido)
        
        if usuario:
            update_fields.append("usuario = %s")
            update_values.append(usuario)
        
        if correo:
            update_fields.append("correo = %s")
            update_values.append(correo)
        
        if grupo_id:
            update_fields.append("grupo_aprobacion_id = %s")
            update_values.append(grupo_id)
        
        if password:
            password_hash = generate_password_hash(password)
            update_fields.append("password_hash = %s")
            update_values.append(password_hash)
        
        if not update_fields:
            return jsonify({"error": "No se proporcionaron datos para actualizar"}), 400
        
        # Agregar ID al final para el WHERE
        update_values.append(usuario_id)
        
        query = f"UPDATE usuarios SET {', '.join(update_fields)} WHERE id = %s"
        cursor.execute(query, update_values)
        conn_pg.commit()
        
        return jsonify({"success": True, "message": "Usuario actualizado exitosamente"})
        
    except Exception as e:
        conn_pg.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn_pg:
            conn_pg.close()


# Eliminar usuario
@app.route("/eliminar_usuario", methods=["POST"])
@login_required
def eliminar_usuario():
    print("🔍 INICIANDO eliminación de usuario")
    print("=" * 50)
    print(f"📥 Método: {request.method}")
    print(f"📥 Headers: {dict(request.headers)}")
    print(f"📥 Form data: {dict(request.form)}")
    print(f"📥 Args: {dict(request.args)}")
    
    # Verificar permisos
    usuario_actual_id = session.get("user_id")
    print(f"Usuario actual: {usuario_actual_id}")
    
    if not tiene_permiso(usuario_actual_id, 'usuarios'):
        print("❌ Usuario sin permisos")
        return jsonify({"error": "No tienes permisos para acceder a esta funcionalidad"}), 403
    
    try:
        usuario_id = request.form.get("usuario_id")
        print(f"ID de usuario a eliminar: {usuario_id}")
        
        if not usuario_id or not usuario_id.isdigit():
            print("❌ ID de usuario no válido")
            return jsonify({"error": "ID de usuario no válido"}), 400
        
        # No permitir que un usuario se elimine a sí mismo
        if int(usuario_id) == int(usuario_actual_id):
            print("❌ Intento de auto-eliminación")
            return jsonify({"error": "No puedes eliminar tu propia cuenta"}), 400
        
        conn_pg = postgres_connection()
        cursor = conn_pg.cursor()
        print("✅ Conexión a base de datos establecida")
        
        # Verificar si el usuario existe
        cursor.execute("SELECT id, usuario FROM usuarios WHERE id = %s", (usuario_id,))
        usuario = cursor.fetchone()
        print(f"Usuario encontrado: {usuario}")
        
        if not usuario:
            print("❌ Usuario no encontrado")
            return jsonify({"error": "Usuario no encontrado"}), 404
        
        # Eliminar usuario
        print(f"🗑️ Eliminando usuario {usuario[1]} (ID: {usuario[0]})")
        cursor.execute("DELETE FROM usuarios WHERE id = %s", (usuario_id,))
        conn_pg.commit()
        print("✅ Usuario eliminado exitosamente")
        
        return jsonify({"success": True, "message": f"Usuario {usuario[1]} eliminado exitosamente"})
        
    except Exception as e:
        print(f"❌ Error eliminando usuario: {e}")
        if 'conn_pg' in locals():
            conn_pg.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn_pg' in locals():
            conn_pg.close()
        print("🔒 Conexiones cerradas")



@app.route("/bodega", methods=["GET", "POST"])
@login_required
def gestion_bodega():
    # Obtener permisos del usuario para el menú dinámico
    usuario_id = session.get("user_id")
    grupo_usuario = obtener_permisos_usuario(usuario_id)
    
    # Verificar si el usuario tiene permiso para acceder a este módulo
    if not tiene_permiso(usuario_id, 'bodega'):
        flash("No tienes permisos para acceder a este módulo.", "error")
        return redirect("/")
    
    conn_pg = postgres_connection()  # Conexión a PostgreSQL
    conn_sql = sql_server_connection()  # Conexión a SQL Server
    cursor_pg = conn_pg.cursor()
    cursor_sql = conn_sql.cursor()
    ordenes_compras = []
    facturas_pendientes = {}
    referencias_dict = {}

    try:
        if request.method == "POST":
            # Obtener datos del formulario
            usuario_id = request.form.get("usuario_id")

            accion = request.form.get("accion")
            if accion:
                if accion.startswith("aprobar_"):
                    orden_id = accion.split("_")[1]  # Obtener el ID de la orden de compra

                    # Obtener el valor de nrodcto_oc de las órdenes de compra
                    cursor_pg.execute("""
                        SELECT nrodcto_oc FROM ordenes_compras WHERE id = %s
                    """, (orden_id,))
                    orden = cursor_pg.fetchone()

                    if orden:
                        nrodcto_oc = orden[0]  # Asignar nrodcto_oc con el valor obtenido de la base de datos
                    else:
                        flash("Orden de compra no encontrada.", "error")
                        return redirect("/bodega")

                    # Continuar con el flujo de aprobación de la factura
                    factura_id = request.form.get(f"factura_id_{orden_id}")
                    if factura_id:
                        # Validar factura_id
                        if not factura_id.isdigit():
                            print(f"ID de factura inválido: {factura_id}") 
                            flash("El ID de la factura no es válido.", "error")
                            return redirect("/bodega")

                        # Verificar si la factura existe y está pendiente
                        cursor_pg.execute("""
                            SELECT id FROM facturas WHERE id = %s AND estado = 'Pendiente'
                        """, (factura_id,))
                        factura = cursor_pg.fetchone()

                        if not factura:
                            flash("El ID de la factura no es válido o no está pendiente.", "error")
                            return redirect("/bodega")

                        # Validar si el usuario pertenece al grupo de aprobadores de bodega
                        cursor_pg.execute("""
                            SELECT g.grupo 
                            FROM usuarios u 
                            INNER JOIN grupo_aprobacion g ON u.grupo_aprobacion_id = g.id 
                            WHERE u.id = %s AND g.grupo = 'Bodega'
                        """, (usuario_id,))
                        grupo = cursor_pg.fetchone()

                        if not grupo:
                            flash("No tienes permisos para aprobar facturas en Bodega", "error")
                            return redirect("/bodega")

                        # Recoger lotes para cada referencia seleccionada
                        lotes_oc = []
                        referencias_seleccionadas = request.form.getlist(f"referencias_oc_{orden_id}")
                        for referencia_numero in referencias_seleccionadas:
                            lote = request.form.get(f"lotes_{orden_id}_{referencia_numero}")
                            if lote:
                                lotes_oc.append(f"{referencia_numero}:{lote}")

                        # Unir los lotes seleccionados con comas
                        lotes_oc_str = ",".join(lotes_oc) if lotes_oc else None

                        # Actualizar el estado de la factura a 'Aprobado' y registrar los lotes  estado = 'Aprobado',
                        hora_aprobacion = datetime.now()
                        cursor_pg.execute("""
                            UPDATE facturas
                            SET 
                                hora_aprobacion = %s, 
                                aprobado_bodega = %s,
                                lotes_oc = %s, 
                                nrodcto_oc = %s
                            WHERE id = %s
                        """, (hora_aprobacion, usuario_id, lotes_oc_str, nrodcto_oc, factura_id))
                        conn_pg.commit()
                        flash("Factura aprobada exitosamente", "success")
                    else:
                        flash("Debe seleccionar una factura para aprobar", "error")


                elif accion.startswith("cerrar_orden_"):
                    orden_id = accion.split("_")[2]  # Obtener el ID de la orden de compra

                    # Cerrar la orden de compra (actualizar estado a 'Aprobado')
                    cursor_pg.execute("""
                        UPDATE ordenes_compras
                        SET estado = 'Aprobado'
                        WHERE id = %s
                    """, (orden_id,))
                    conn_pg.commit()
                    flash("Orden de compra cerrada exitosamente", "success")

                elif accion.startswith("c"):
                    factura_id = accion.split("_")[2]  # Obtener el ID de la factura

                    # Validar que el ID de la factura sea numérico
                    if not factura_id.isdigit():
                        print(f"ID de factura inválido: {factura_id}") 
                        flash("El ID de la factura no es válido.", "error")
                        return redirect("/bodega")

                    # Verificar si la factura existe y está en estado 'Pendiente'
                    cursor_pg.execute("""
                        SELECT id FROM facturas WHERE id = %s AND estado = 'Pendiente'
                    """, (factura_id,))
                    factura = cursor_pg.fetchone()

                    if not factura:
                        flash("La factura no es válida o ya fue aprobada.", "error")
                        return redirect("/bodega")

                    # Cerrar la factura cambiando su estado a 'Aprobado'
                    cursor_pg.execute("""
                        UPDATE facturas
                        SET estado = 'Aprobado'
                        WHERE id = %s
                    """, (factura_id,))
                    conn_pg.commit()

                    flash("Factura cerrada exitosamente.", "success")

        # Consultar órdenes de compra aprobadas desde SQL Server (trade)
        print("Consultando órdenes de compra aprobadas desde SQL Server...")
        cursor_sql.execute("""
            SELECT NRODCTO 
            FROM trade
            WHERE origen = 'COM' 
            AND TIPODCTO = 'OC' 
            AND TRIM(autorizpor) = 'NCARDONA' OR TRIM(autorizpor) = 'BMONTOYA' OR TRIM(autorizpor) = 'MCARDONA' OR TRIM(autorizpor) = 'DESTRADA' OR TRIM(autorizpor) = 'ACONTABLE'
        """)
        ordenes_aprobadas_sql = cursor_sql.fetchall()

        print(f"Órdenes de compra aprobadas encontradas: {len(ordenes_aprobadas_sql)} registros.")

        if not ordenes_aprobadas_sql:
            print("No se encontraron órdenes aprobadas en SQL Server.")
            return render_template("bodega.html", 
                                 ordenes_compras=[], 
                                 facturas_pendientes={}, 
                                 referencias={},
                                 grupo_usuario=grupo_usuario,
                                 permisos_modulos=PERMISOS_MODULOS)

        nrodcto_aprobadas = [orden[0].strip() for orden in ordenes_aprobadas_sql]

        # Consultar las órdenes de compra en PostgreSQL que estén pend>CTO aprobados en SQL Server
        print("Consultando órdenes de compra pendientes en PostgreSQL...")
        cursor_pg.execute("""
            SELECT 
                oc.id AS orden_compra_id, 
                oc.nit_oc, 
                oc.nrodcto_oc, 
                oc.nombre_cliente_oc, 
                oc.cantidad_oc, 
                oc.estado AS estado_oc,
                oc.archivo_path_oc
            FROM ordenes_compras oc
            WHERE oc.estado = 'Pendiente' 
            AND oc.nrodcto_oc IN %s
            ORDER BY oc.nrodcto_oc ASC
        """, (tuple(nrodcto_aprobadas),))
        ordenes_compras = cursor_pg.fetchall()

        print(f"Órdenes de compra pendientes obtenidas: {len(ordenes_compras)} registros.")

        facturas_pendientes = {}
        referencias_dict = {}

        for orden in ordenes_compras:
            nit_oc = orden[1]  # Extraer el NIT de la orden de compra
            nrodcto_oc = orden[2]  # Extraer el NRODCTO de la orden de compra
            print(f"Consultando facturas para NIT: {nit_oc} en PostgreSQL...")

            cursor_pg.execute("""
                SELECT fac.id, fac.numero_factura, fac.fecha_seleccionada
                    FROM facturas fac
                    INNER JOIN ordenes_compras oc ON TRIM(oc.nit_oc) = TRIM(fac.nit)
                    WHERE fac.estado = 'Pendiente' 
                        AND oc.estado = 'Pendiente' 
                        AND oc.nit_oc = %s
                        AND oc.nrodcto_oc = %s
                    ORDER BY fac.fecha_seleccionada ASC
            """, (nit_oc, nrodcto_oc))
            facturas_pg = cursor_pg.fetchall()

            print(f"Facturas encontradas para NIT {nit_oc} en Postgresql: {len(facturas_pg)} registros.")

            facturas_dict = {}
            for fac in facturas_pg:
                facturas_dict[fac[0]] = fac
                #facturas_pendientes[orden[0]] = facturas_pg
            facturas_pendientes[orden[0]] = list(facturas_dict.values())
            #else:
                #print(f"No se encontraron facturas para NIT {nit_oc} en PostgreSQL.")

            # Obtener las referencias dinámicamente para el nrodcto_oc específico
            print(f"Obteniendo las referencias para el NRODCTO {nrodcto_oc} desde PostgreSQL...")
            cursor_pg.execute("""
                SELECT numero_referencia_oc, nombre_referencia_oc 
                FROM ordenes_compras
                WHERE nrodcto_oc = %s
                ORDER BY numero_referencia_oc
            """, (nrodcto_oc,))
            referencias = cursor_pg.fetchall()

            print(f"Referencias obtenidas para NRODCTO {nrodcto_oc}: {len(referencias)} registros.")

            # Asegurarse de que las referencias se gestionen correctamente para cada orden
            referencias_dict[nrodcto_oc] = {}
            for referencia in referencias:
                numeros_referencia = referencia[0].split(",")  # Separar las referencias por coma
                nombres_referencia = referencia[1].split(",")  # Separar los nombres por coma
                for num, nombre in zip(numeros_referencia, nombres_referencia):
                    referencias_dict[nrodcto_oc][num.strip()] = nombre.strip()

            print(f"Referencias para NRODCTO {nrodcto_oc} procesadas.")

    except Exception as e:
        print(f"Error en la gestión de bodega: {str(e)}")
        flash(f"Error en la gestión de bodega: {str(e)}", "error")

    finally:
        if cursor_pg:
            cursor_pg.close()
        if cursor_sql:
            cursor_sql.close()
        if conn_pg:
            conn_pg.close()
        if conn_sql:
            conn_sql.close()

    return render_template(
        "bodega.html", 
        ordenes_compras=ordenes_compras, 
        facturas_pendientes=facturas_pendientes, 
        referencias=referencias_dict,
        grupo_usuario=grupo_usuario,
        permisos_modulos=PERMISOS_MODULOS
    )






@app.route("/compras", methods=["GET", "POST"])
@login_required
def gestion_compras():
    # Obtener permisos del usuario para el menú dinámico
    usuario_id = session.get("user_id")
    grupo_usuario = obtener_permisos_usuario(usuario_id)
    
    # Verificar si el usuario tiene permiso para acceder a este módulo
    if not tiene_permiso(usuario_id, 'compras'):
        flash("No tienes permisos para acceder a este módulo.", "error")
        return redirect("/")
    
    # Conexión a la base de datos PostgreSQL
    conn_pg = postgres_connection()
    cursor = conn_pg.cursor()
    print("Conexión exitosa a PostgreSQL")

    try:
        if request.method == "POST":
            # Obtener datos del formulario
            usuario_id = request.form.get("usuario_id")
            factura_id = request.form.get("factura_id")
            remision = request.form.get("remision")
            # El archivo de remisión ya fue subido anteriormente, no se necesita en este formulario

            # Log de datos recibidos
            print(f"Datos recibidos: usuario_id={usuario_id}, factura_id={factura_id}, remision={remision}")

            # Validar campos
            if not usuario_id or not usuario_id.isdigit():
                print("Error: El ID del usuario no es válido.")
                flash("El ID del usuario no es válido.", "error")
                return redirect("/compras")

            if not factura_id or not factura_id.isdigit():
                print("Error: El ID de la factura no es válido.")
                flash("El ID de la factura no es válido.", "error")
                return redirect("/compras")

            if not remision:  # Solo verificamos que no esté vacío
                print("Error: La remisión no puede estar vacía.")
                flash("La remisión no puede estar vacía.", "error")
                return redirect("/compras")

            # Validar si el usuario pertenece al grupo de aprobadores de compras
            print("Consultando si el usuario pertenece al grupo de Compras...")
            cursor.execute("""
                SELECT g.grupo 
                FROM usuarios u 
                INNER JOIN grupo_aprobacion g ON u.grupo_aprobacion_id = g.id 
                WHERE u.id = %s AND g.grupo = 'Compras'
            """, (usuario_id,))
            grupo = cursor.fetchone()
            print(f"Resultado de grupo: {grupo}")

            if not grupo:
                print("Error: El usuario no pertenece al grupo de Compras.")
                flash("No tienes permisos para aprobar facturas en Compras", "error")
                return redirect("/compras")

            # Consultar información de la factura
            print("Consultando información de la factura...")
            cursor.execute("""
                SELECT nit, fecha_seleccionada, clasificacion
                FROM facturas
                WHERE id = %s
            """, (factura_id,))
            factura_info = cursor.fetchone()
            print(f"Información de factura: {factura_info}")

            if not factura_info:
                print("Error: Factura no encontrada.")
                flash("Factura no encontrada.", "error")
                return redirect("/compras")

            nit, fecha_seleccionada, clasificacion = factura_info
            # Convertir fecha_seleccionada a cadena antes de usar replace
            fecha_directorio = str(fecha_seleccionada).replace("-", "")  # Formato YYYYMMDD
            clasificacion_texto = "Facturas" if clasificacion == "Facturas" else "Servicios"
            print(f"Datos procesados: nit={nit}, fecha={fecha_seleccionada}, clasificación={clasificacion_texto}")

    
            # Aprobar la factura y registrar información
            try:
                hora_aprobacion_compras = datetime.now()
                print("Aprobando factura en la base de datos...")

                # Elimina la parte que se encargaba de guardar el archivo de remisión
                cursor.execute("""
                    UPDATE facturas
                    SET estado_compras = 'Aprobado', 
                        hora_aprobacion_compras = %s, 
                        aprobado_compras = %s,
                        remision = %s
                    WHERE id = %s
                """, (hora_aprobacion_compras, usuario_id, remision, factura_id))
                conn_pg.commit()
                print("Factura aprobada exitosamente.")
                flash("Factura aprobada exitosamente en Compras", "success")
            except Exception as e:
                conn_pg.rollback()
                print(f"Error al aprobar la factura: {e}")
                flash(f"Error aprobando factura en Compras: {str(e)}", "error")
                return redirect("/compras")

        # Consultar facturas pendientes en compras
        print("Consultando facturas pendientes en Compras...")
        cursor.execute("""
            SELECT 
                f.id, 
                f.nit, 
                f.numero_factura, 
                f.fecha_seleccionada, 
                f.clasificacion, 
                f.archivo_path, 
                f.estado_compras, 
                f.hora_aprobacion_compras, 
                f.lotes_oc, 
                oc.archivo_path_oc,
                f.nombre  
            FROM facturas f
            JOIN ordenes_compras oc ON f.nrodcto_oc = oc.nrodcto_oc 
            WHERE f.clasificacion = 'Facturas' 
            AND f.estado_compras = 'Pendiente'
            ORDER BY f.fecha_seleccionada ASC;
        """)
        facturas = cursor.fetchall()
        print(f"Facturas pendientes: {len(facturas)} facturas encontradas")

    except Exception as e:
        print(f"Error general en gestión_compras: {e}")
        flash(f"Error en la gestión de compras: {str(e)}", "error")
        facturas = []

    finally:
        if cursor:
            cursor.close()
        if conn_pg:
            conn_pg.close()
            print("Conexión cerrada")

    # Renderizar el HTML
    return render_template("compras.html", 
                         facturas=facturas,
                         grupo_usuario=grupo_usuario,
                         permisos_modulos=PERMISOS_MODULOS)



@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("usuario")
        password = request.form.get("password")

        try:
            conn_pg = postgres_connection()
            cursor = conn_pg.cursor()

            # Consultar usuario en la base de datos
            cursor.execute("SELECT id, password_hash FROM usuarios WHERE usuario = %s", (usuario,))
            user = cursor.fetchone()

            if user and check_password_hash(user[1], password):  # Verificar contraseña
                session["user_id"] = user[0]  # Almacenar el ID del usuario en la sesión
                session["usuario"] = usuario
                flash("Inicio de sesión exitoso", "success")
                return redirect(url_for("index"))  # Redirigir a la página principal
            else:
                flash("Usuario o contraseña incorrectos", "error")
        except Exception as e:
            flash(f"Error al iniciar sesión: {str(e)}", "error")

    return render_template("login.html")


@app.route("/cambiar_password", methods=["POST"])
def cambiar_password():
    """
    Endpoint para cambiar la contraseña de un usuario.
    Valida la contraseña actual antes de permitir el cambio.
    """
    try:
        usuario = request.form.get("usuario")
        password_actual = request.form.get("password_actual")
        password_nueva = request.form.get("password_nueva")
        password_confirmar = request.form.get("password_confirmar")
        
        # Validaciones básicas
        if not all([usuario, password_actual, password_nueva, password_confirmar]):
            return jsonify({"success": False, "message": "Todos los campos son requeridos"}), 400
        
        if password_nueva != password_confirmar:
            return jsonify({"success": False, "message": "Las contraseñas nuevas no coinciden"}), 400
        
        if len(password_nueva) < 6:
            return jsonify({"success": False, "message": "La contraseña debe tener al menos 6 caracteres"}), 400
        
        # Conectar a la base de datos
        conn_pg = postgres_connection()
        cursor = conn_pg.cursor()
        
        # Verificar que el usuario existe y obtener su contraseña actual
        cursor.execute("SELECT id, password_hash FROM usuarios WHERE usuario = %s", (usuario,))
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            conn_pg.close()
            return jsonify({"success": False, "message": "Usuario no encontrado"}), 404
        
        user_id = user[0]
        password_hash_actual = user[1]
        
        # Verificar que la contraseña actual sea correcta 1
        if not check_password_hash(password_hash_actual, password_actual):
            cursor.close()
            conn_pg.close()
            return jsonify({"success": False, "message": "La contraseña actual es incorrecta"}), 401
        
        # Generar hash de la nueva contraseña
        nuevo_password_hash = generate_password_hash(password_nueva)
        
        # Actualizar la contraseña en la base de datos 1
        cursor.execute("""
            UPDATE usuarios 
            SET password_hash = %s 
            WHERE id = %s
        """, (nuevo_password_hash, user_id))
        
        conn_pg.commit()
        cursor.close()
        conn_pg.close()
        
        print(f"✅ Contraseña cambiada exitosamente para el usuario: {usuario}")
        
        return jsonify({
            "success": True, 
            "message": "Contraseña cambiada exitosamente. Ya puedes iniciar sesión con tu nueva contraseña."
        }), 200
        
    except Exception as e:
        print(f"❌ Error al cambiar contraseña: {str(e)}")
        return jsonify({"success": False, "message": f"Error al cambiar la contraseña: {str(e)}"}), 500


@app.route("/servicios", methods=["GET", "POST"])
@login_required
def gestion_servicios():
    # Obtener permisos del usuario para el menú dinámico
    usuario_id = session.get("user_id")
    grupo_usuario = obtener_permisos_usuario(usuario_id)
    
    # Verificar si el usuario tiene permiso para acceder a este módulo
    if not tiene_permiso(usuario_id, 'servicios'):
        flash("No tienes permisos para acceder a este módulo.", "error")
        return redirect("/")
    
    conn_pg = postgres_connection()
    cursor = conn_pg.cursor()

    try:
        if request.method == "POST":
            # Obtener datos del formulario
            usuario_id = request.form.get("usuario_id")
            factura_id = request.form.get("factura_id")
            usuario_asignado = request.form.get("usuario_asignado")  # Nuevo campo para asignar el usuario

            # Imprimir valores obtenidos para verificar
            print("Datos recibidos:")
            print(f"usuario_id: {usuario_id}")
            print(f"factura_id: {factura_id}")
            print(f"usuario_asignado: {usuario_asignado}")

            # Validar usuario_id y factura_id
            if not usuario_id or not usuario_id.isdigit():
                flash("El ID del usuario no es válido.", "error")
                print("Error: usuario_id no es válido.")
                return redirect("/servicios")

            if not factura_id or not factura_id.isdigit():
                flash("El ID de la factura no es válido.", "error")
                print("Error: factura_id no es válido.")
                return redirect("/servicios")

            if not usuario_asignado or not usuario_asignado.isdigit():
                flash("El ID del usuario asignado no es válido.", "error")
                print("Error: usuario_asignado no es válido.")
                return redirect("/servicios")

            # Validar si el usuario pertenece al grupo de Contabilidad
            cursor.execute("""
                SELECT g.grupo 
                FROM usuarios u 
                INNER JOIN grupo_aprobacion g ON u.grupo_aprobacion_id = g.id 
                WHERE u.id = %s AND g.grupo = 'Contabilidad'
            """, (usuario_id,))
            grupo = cursor.fetchone()

            print("Grupo obtenido:", grupo)

            if not grupo:
                flash("No tienes permisos para asignar facturas en Servicios.", "error")
                print("Error: usuario no pertenece al grupo de Contabilidad.")
                return redirect("/servicios")

            # Aprobar la factura y asignar al usuario
            try:
                hora_aprobacion = datetime.now()
                print("Hora de aprobación:", hora_aprobacion)

                cursor.execute("""
                    UPDATE facturas
                    SET estado = 'Aprobado', 
                        hora_aprobacion = %s, 
                        aprobado_servicios = %s,
                        usuario_asignado_servicios = %s
                    WHERE id = %s
                """, (hora_aprobacion, usuario_id, usuario_asignado, factura_id))
                conn_pg.commit()
                print("Factura actualizada exitosamente en la base de datos.")
                
                # ENVIAR CORREO DE NOTIFICACIÓN
                try:
                    # Obtener datos del usuario asignado
                    cursor.execute("""
                        SELECT nombre, apellido, correo 
                        FROM usuarios 
                        WHERE id = %s
                    """, (usuario_asignado,))
                    usuario_asignado_data = cursor.fetchone()
                    
                    # Obtener datos del usuario que asignó
                    cursor.execute("""
                        SELECT nombre, apellido 
                        FROM usuarios 
                        WHERE id = %s
                    """, (usuario_id,))
                    usuario_asignador_data = cursor.fetchone()
                    
                    # Obtener datos completos de la factura
                    cursor.execute("""
                        SELECT id, nit, nombre, numero_factura, fecha_seleccionada, clasificacion
                        FROM facturas 
                        WHERE id = %s
                    """, (factura_id,))
                    factura_data = cursor.fetchone()
                    
                    if usuario_asignado_data and usuario_asignador_data and factura_data:
                        # Preparar datos para el correo
                        destinatario_email = usuario_asignado_data[2]  # correo
                        destinatario_nombre = f"{usuario_asignado_data[0]} {usuario_asignado_data[1]}"
                        usuario_asignador_nombre = f"{usuario_asignador_data[0]} {usuario_asignador_data[1]}"
                        
                        factura_info = {
                            'id': factura_data[0],
                            'nit': factura_data[1],
                            'nombre': factura_data[2],
                            'numero_factura': factura_data[3],
                            'fecha_seleccionada': factura_data[4].strftime('%d/%m/%Y') if factura_data[4] else 'N/A',
                            'clasificacion': factura_data[5]
                        }
                        
                        # Enviar correo
                        if enviar_correo_asignacion(destinatario_email, destinatario_nombre, factura_info, usuario_asignador_nombre):
                            print(f"✅ Correo de notificación enviado a {destinatario_email}")
                            flash("Factura asignada y notificación enviada por correo", "success")
                        else:
                            print(f"⚠️ Error enviando correo a {destinatario_email}")
                            flash("Factura asignada, pero hubo un problema enviando la notificación por correo", "warning")
                    else:
                        print("⚠️ No se pudieron obtener todos los datos para el correo")
                        flash("Factura asignada exitosamente", "success")
                        
                except Exception as email_error:
                    print(f"⚠️ Error en el proceso de envío de correo: {email_error}")
                    flash("Factura asignada exitosamente", "success")
                
            except Exception as e:
                conn_pg.rollback()
                print("Error durante la actualización de la factura:", e)
                flash(f"Error aprobando y asignando factura: {str(e)}", "error")

        # Consultar facturas pendientes
        consulta_servicios = """
            SELECT 
                id, 
                nit, 
                numero_factura, 
                TO_CHAR(fecha_seleccionada, 'YYYY-MM-DD') AS fecha_seleccionada, 
                clasificacion, 
                archivo_path, 
                estado, 
                nombre 
            FROM facturas
            WHERE clasificacion = 'Servicios' AND estado = 'Pendiente'
            ORDER BY fecha_seleccionada ASC
        """
        print("/servicios -> Ejecutando consulta:\n", consulta_servicios)
        cursor.execute(consulta_servicios)
        facturas = cursor.fetchall()
        print(f"/servicios -> Filas obtenidas: {len(facturas)}")
        if facturas:
            print("/servicios -> Primera fila (muestra):", facturas[0])

        # Consultar usuarios disponibles para asignar
        cursor.execute("""
            SELECT id, nombre, apellido, usuario, correo
            FROM usuarios
        """)
        usuarios = cursor.fetchall()
        print("Usuarios disponibles para asignar:", usuarios)

    except Exception as e:
        print("Error general:", e)
        flash(f"Error en la gestión de servicios: {str(e)}", "error")
        facturas = []
        usuarios = []

    finally:
        if cursor:
            cursor.close()
        if conn_pg:
            conn_pg.close()

    return render_template("servicios.html", 
                         facturas=facturas, 
                         usuarios=usuarios,
                         grupo_usuario=grupo_usuario,
                         permisos_modulos=PERMISOS_MODULOS)


@app.route("/asignaciones", methods=["GET", "POST"])
@login_required
def gestion_asignaciones():
    print("Iniciando gestión de asignaciones...")

    # Obtener permisos del usuario para el menú dinámico
    usuario_id = session.get("user_id")
    grupo_usuario = obtener_permisos_usuario(usuario_id)
    
    # Verificar si el usuario tiene permiso para acceder a este módulo
    if not tiene_permiso(usuario_id, 'asignaciones'):
        flash("No tienes permisos para acceder a este módulo.", "error")
        return redirect("/")

    conn_pg = postgres_connection()
    print("Conexión a la base de datos establecida.")
    cursor = conn_pg.cursor()

    # Obtener el ID del usuario autenticado desde la sesión
    usuario_actual_id = session.get("user_id")
    print(f"Usuario autenticado: {usuario_actual_id}")

    if not usuario_actual_id:
        flash("Tu sesión ha expirado o no has iniciado sesión.", "error")
        print("Error: sesión no válida o usuario no autenticado.")
        return redirect(url_for("login"))

    try:
        if request.method == "POST":
            print("Método POST recibido.")

            # Obtener datos del formulario
            factura_id = request.form.get("factura_id")
            accion = request.form.get("accion", "aprobar").lower()
            print(f"Factura recibida: {factura_id} | Acción solicitada: {accion}")

            if not factura_id or not factura_id.isdigit():
                flash("El ID de la factura no es válido.", "error")
                print("Error: factura_id no es válido.")
                return redirect("/asignaciones")

            if accion not in ["aprobar", "rechazar"]:
                flash("Acción no reconocida para la factura seleccionada.", "error")
                print(f"Error: acción '{accion}' no válida.")
                return redirect("/asignaciones")

            # Validar que la factura pertenece al usuario actual
            print("Validando si la factura pertenece al usuario actual...")
            cursor.execute("""
                SELECT id, estado_usuario_asignado, estado, hora_aprobacion, aprobado_servicios
                FROM facturas
                WHERE id = %s AND usuario_asignado_servicios = %s
            """, (factura_id, usuario_actual_id))
            factura = cursor.fetchone()
            print(f"Resultado de la validación de factura: {factura}")

            if not factura:
                flash("No tienes permiso para gestionar esta factura.", "error")
                print("Error: factura no encontrada o no pertenece al usuario.")
                return redirect("/asignaciones")

            estado_actual = factura[1]

            if accion == "aprobar":
                # Validar que la factura no esté ya aprobada
                if estado_actual == 'Aprobado':
                    flash("La factura ya ha sido aprobada anteriormente.", "warning")
                    print("Advertencia: la factura ya estaba aprobada.")
                    return redirect("/asignaciones")

                # Aprobar la factura y registrar la hora de aprobación
                # Nota: Corregida indentación del bloque try-except (líneas 1806-1828)
                try:
                    hora_actual = datetime.now()
                    print(f"Hora de aprobación: {hora_actual}")

                    cursor.execute("""
                        UPDATE facturas
                        SET estado_usuario_asignado = 'Aprobado',
                            hora_aprobacion_asignado = %s
                        WHERE id = %s AND usuario_asignado_servicios = %s
                    """, (hora_actual, factura_id, usuario_actual_id))
                    conn_pg.commit()
                    print(f"Factura aprobada. Filas afectadas: {cursor.rowcount}")

                    if cursor.rowcount == 0:
                        flash("No se pudo actualizar la factura. Verifica tus permisos.", "error")
                        print("Error: actualización de factura fallida, fila no afectada.")
                    else:
                        flash("Factura aprobada exitosamente.", "success")
                        print("Factura aprobada con éxito.")
                except Exception as e:
                    conn_pg.rollback()
                    print(f"Error durante la aprobación de la factura: {e}")
                    flash(f"Error aprobando factura: {str(e)}", "error")

            elif accion == "rechazar":
                # Revertir la aprobación y liberar la factura para reasignación
                try:
                    cursor.execute("""
                        UPDATE facturas
                        SET estado_usuario_asignado = 'Pendiente',
                            hora_aprobacion_asignado = NULL,
                            usuario_asignado_servicios = NULL,
                            estado = 'Pendiente',
                            hora_aprobacion = NULL,
                            aprobado_servicios = NULL
                        WHERE id = %s AND usuario_asignado_servicios = %s
                    """, (factura_id, usuario_actual_id))
                    conn_pg.commit()
                    print(f"Factura rechazada. Filas afectadas: {cursor.rowcount}")

                    if cursor.rowcount == 0:
                        flash("No fue posible rechazar la factura. Verifica tus permisos.", "error")
                        print("Error: rechazo de factura fallido, fila no afectada.")
                    else:
                        flash("Factura rechazada y devuelta para reasignación.", "success")
                        print("Factura rechazada y devuelta a Servicios.")
                except Exception as e:
                    conn_pg.rollback()
                    print(f"Error durante el rechazo de la factura: {e}")
                    flash(f"Error al rechazar la factura: {str(e)}", "error")

        # Consultar facturas asignadas al usuario actual
        print("Consultando facturas asignadas al usuario actual...")
        consulta_asignaciones = """
            SELECT 
                id, 
                nit, 
                numero_factura, 
                TO_CHAR(fecha_seleccionada, 'YYYY-MM-DD') AS fecha_seleccionada, 
                clasificacion, 
                archivo_path, 
                estado_usuario_asignado, 
                estado_usuario_asignado, 
                TO_CHAR(hora_aprobacion_asignado, 'YYYY-MM-DD HH24:MI:SS') AS hora_aprobacion_asignado, 
                nombre
            FROM facturas
            WHERE usuario_asignado_servicios = %s
            ORDER BY 
                CASE 
                    WHEN estado_usuario_asignado = 'Pendiente' THEN 1 
                    WHEN estado_usuario_asignado = 'Aprobado' THEN 2 
                    ELSE 3 
                END,
                fecha_seleccionada ASC
        """
        print("/asignaciones -> Ejecutando consulta:\n", consulta_asignaciones)
        cursor.execute(consulta_asignaciones, (usuario_actual_id,))
        facturas_asignadas = cursor.fetchall()
        print(f"/asignaciones -> Filas obtenidas: {len(facturas_asignadas)}")
        if facturas_asignadas:
            print("/asignaciones -> Primera fila (muestra):", facturas_asignadas[0])

    except Exception as e:
        print(f"Error general en /asignaciones: {e}")
        flash(f"Error al gestionar asignaciones: {str(e)}", "error")
        facturas_asignadas = []

    finally:
        if cursor:
            cursor.close()
            print("Cursor de base de datos cerrado.")
        if conn_pg:
            conn_pg.close()
            print("Conexión a la base de datos cerrada.")

    print("Renderizando la plantilla asignaciones.html...")
    return render_template("asignaciones.html", 
                         facturas=facturas_asignadas,
                         grupo_usuario=grupo_usuario,
                         permisos_modulos=PERMISOS_MODULOS)


@app.route("/pago_servicios", methods=["GET", "POST"])
@login_required
def pago_servicios():
    print("Iniciando vista de pago de servicios...")

    # Obtener permisos del usuario para el menú dinámico
    usuario_id = session.get("user_id")
    grupo_usuario = obtener_permisos_usuario(usuario_id)
    
    # Verificar si el usuario tiene permiso para acceder a este módulo
    if not tiene_permiso(usuario_id, 'pago_servicios'):
        flash("No tienes permisos para acceder a este módulo.", "error")
        return redirect("/")

    conn_pg = postgres_connection()
    cursor = conn_pg.cursor()

    print(f"Usuario autenticado: {usuario_id}")

    try:
        if request.method == "POST":
            print("Método POST recibido.")
            
            # Obtener el ID de la factura a aprobar
            factura_id = request.form.get("factura_id")
            print(f"Factura para pago servicios: {factura_id}")

            if not factura_id or not factura_id.isdigit():
                flash("El ID de la factura no es válido.", "error")
                print("Error: factura_id no es válido.")
                return redirect("/pago_servicios")

            # Validar que la factura está aprobada y lista para pago de servicios
            print("Validando estado de la factura para pago de servicios...")
            cursor.execute("""
                SELECT id, pago_servicios
                FROM facturas
                WHERE id = %s AND estado_usuario_asignado = 'Aprobado'
            """, (factura_id,))
            factura = cursor.fetchone()
            print(f"Resultado de la validación de factura: {factura}")

            if not factura:
                flash("No se encontró la factura o no está en estado Aprobado.", "error")
                print("Error: factura no encontrada o no válida para pago de servicios.")
                return redirect("/pago_servicios")

            if factura[1] == 'Aprobado':
                flash("La factura ya ha sido aprobada para pago de servicios.", "warning")
                print("Advertencia: la factura ya está aprobada para pago de servicios.")
                return redirect("/pago_servicios")

            # Aprobar la factura para pago de servicios y registrar hora de aprobación
            try:
                hora_actual = datetime.now()
                print(f"Hora de aprobación para pago servicios: {hora_actual}")

                cursor.execute("""
                    UPDATE facturas
                    SET pago_servicios = 'Aprobado',
                        hora_aprobacion_pago_servicio = %s
                    WHERE id = %s
                """, (hora_actual, factura_id))
                conn_pg.commit()
                print(f"Factura aprobada para pago servicios. Filas afectadas: {cursor.rowcount}")

                if cursor.rowcount == 0:
                    flash("No se pudo aprobar la factura para pago de servicios.", "error")
                    print("Error: actualización fallida, fila no afectada.")
                else:
                    flash("Factura aprobada exitosamente para pago de servicios.", "success")
                    print("Factura aprobada con éxito para pago de servicios.")
            except Exception as e:
                conn_pg.rollback()
                print(f"Error durante la aprobación de la factura para pago servicios: {e}")
                flash(f"Error aprobando factura para pago de servicios: {str(e)}", "error")

        # Consultar facturas aprobadas y pendientes de pago de servicios
        print("Consultando facturas aprobadas para pago de servicios...")
        cursor.execute("""
            SELECT fac.id, fac.nit, fac.numero_factura, fac.fecha_seleccionada, fac.clasificacion, fac.archivo_path, fac.pago_servicios, 
            fac.hora_aprobacion_pago_servicio, fac.nombre, us.usuario
            FROM facturas fac
			inner join usuarios us on fac.usuario_asignado_servicios=us.id
            WHERE fac.estado_usuario_asignado = 'Aprobado' and fac.pago_servicios = 'Pendiente'
            ORDER BY fac.fecha_seleccionada ASC
        """)
        facturas_aprobadas = cursor.fetchall()
        print(f"Facturas aprobadas para pago de servicios obtenidas: {facturas_aprobadas}")

    except Exception as e:
        print(f"Error general en /pago_servicios: {e}")
        flash(f"Error al gestionar pago de servicios: {str(e)}", "error")
        facturas_aprobadas = []

    finally:
        if cursor:
            cursor.close()
            print("Cursor de base de datos cerrado.")
        if conn_pg:
            conn_pg.close()
            print("Conexión a la base de datos cerrada.")

    print("Renderizando la plantilla pago_servicios.html...")
    return render_template("pago_servicios.html", 
                         facturas=facturas_aprobadas,
                         grupo_usuario=grupo_usuario,
                         permisos_modulos=PERMISOS_MODULOS)

#-------------Pago MP
@app.route("/pago_mp", methods=["GET", "POST"])
@login_required
def pago_mp():
    print("Iniciando vista de pago de MP...")

    # Obtener permisos del usuario para el menú dinámico
    usuario_id = session.get("user_id")
    grupo_usuario = obtener_permisos_usuario(usuario_id)
    
    # Verificar si el usuario tiene permiso para acceder a este módulo
    if not tiene_permiso(usuario_id, 'pago_mp'):
        flash("No tienes permisos para acceder a este módulo.", "error")
        return redirect("/")

    conn_pg = postgres_connection()
    cursor = conn_pg.cursor()

    print(f"Usuario autenticado: {usuario_id}")

    try:

        if request.method == "POST":
            print("Método POST recibido.")

            # Obtener el ID de la factura a aprobar
            factura_id = request.form.get("factura_id")
            print(f"Factura para pago MP: {factura_id}")

            if not factura_id or not factura_id.isdigit():
                flash("El ID de la factura no es válido.", "error")
                print("Error: factura_id no es válido.")
                return redirect("/pago_mp")

            # Validar que la factura está aprobada y lista para pago de servicios
            print("Validando estado de la factura para pago de servicios...")
            cursor.execute("""
                SELECT id, pago_mp
                FROM facturas
                WHERE id = %s AND estado_compras = 'Aprobado' 
            """, (factura_id,))
            factura = cursor.fetchone()
            print(f"Resultado de la validación de factura: {factura}")

            if not factura:
                flash("No se encontró la factura o no está en estado Aprobado.", "error")
                print("Error: factura no encontrada o no válida para pago de MP.")
                return redirect("/pago_mp")

            if factura[1] == 'Aprobado':
                flash("La factura ya ha sido aprobada para pago de MP.", "warning")
                print("Advertencia: la factura ya está aprobada para pago de MP.")
                return redirect("/pago_mp")

            # Aprobar la factura para pago de MP y registrar hora de aprobación
            try:
                hora_actual = datetime.now()
                print(f"Hora de aprobación para pago MP: {hora_actual}")

                cursor.execute("""
                    UPDATE facturas
                    SET pago_mp = 'Aprobado',
                        hora_aprobacion_pago_mp = %s
                    WHERE id = %s
                """, (hora_actual, factura_id))
                conn_pg.commit()
                print(f"Factura aprobada para pago MP. Filas afectadas: {cursor.rowcount}")

                if cursor.rowcount == 0:
                    flash("No se pudo aprobar la factura para pago de MP.", "error")
                    print("Error: actualización fallida, fila no afectada.")
                else:
                    flash("Factura aprobada exitosamente para pago de MP.", "success")
                    print("Factura aprobada con éxito para pago de MP.")
            except Exception as e:
                conn_pg.rollback()
                print(f"Error durante la aprobación de la factura para pago MP: {e}")
                flash(f"Error aprobando factura para pago de MP: {str(e)}", "error")

        # Consultar facturas aprobadas y pendientes de pago de MP
        print("Consultando facturas aprobadas para pago de MP...")
        cursor.execute("""
            SELECT id, nit, numero_factura, fecha_seleccionada, clasificacion, archivo_path, pago_mp, hora_aprobacion_pago_mp, archivo_remision, remision
            FROM facturas
            WHERE estado_compras = 'Aprobado' and pago_mp = 'Pendiente'
            ORDER BY fecha_seleccionada ASC
        """)
        facturas_aprobadas = cursor.fetchall()
        print(f"Facturas aprobadas para pago de MP obtenidas: {facturas_aprobadas}")

    except Exception as e:
        print(f"Error general en /pago_mp: {e}")
        flash(f"Error al gestionar pago de MP: {str(e)}", "error")
        facturas_aprobadas = []

    finally:
        if cursor:
            cursor.close()
            print("Cursor de base de datos cerrado.")
        if conn_pg:
            conn_pg.close()
            print("Conexión a la base de datos cerrada.")

    print("Renderizando la plantilla pago_mp.html...")
    return render_template("pago_mp.html", 
                         facturas=facturas_aprobadas,
                         grupo_usuario=grupo_usuario,
                         permisos_modulos=PERMISOS_MODULOS)


# FUNCIÓN ORIGINAL COMENTADA - VERSIÓN MANUAL
# @app.route("/gestion_final", methods=["GET", "POST"])
# def gestion_final():
#     print("Iniciando vista de gestión final...")
# 
#     conn_pg = postgres_connection()
#     cursor_pg = conn_pg.cursor()
# 
#     # Obtener el ID del usuario autenticado desde la sesión
#     usuario_id = session.get("user_id")
#     print(f"Usuario autenticado: {usuario_id}")
# 
#     if not usuario_id:
#         flash("Tu sesión ha expirado o no has iniciado sesión.", "error")
#         print("Error: sesión no válida o usuario no autenticado.")
#         return redirect(url_for("login"))
# 
#     # Conexión a PostgreSQL
#     conn_pg = postgres_connection()
#     cursor_pg = conn_pg.cursor()
# 
#     if request.method == "POST":
#         # Recoger los valores enviados desde el formulario
#         factura_id = request.form.get("factura_id")
#         numero_ofimatica = request.form.get("numero_ofimatica")
#         password_in = request.form.get("password_in")
#         bruto = request.form.get("bruto")
#         iva_bruto = request.form.get("iva_bruto")
#         vl_retfte = request.form.get("vl_retfte")
#         v_retica = request.form.get("v_retica")
#         v_reteniva = request.form.get("v_reteniva")
#         subtotal = request.form.get("subtotal")
#         total = request.form.get("total")
#         clasificacion_final = request.form.get("clasificacion_final")
#         abonos = request.form.get("abonos")
#         retenciones = request.form.get("retenciones")
#         valor_pagar = request.form.get("valor_pagar")
#         estado_final = 'Aprobado'
# 
#         print(f"Facture ID: {factura_id}, Numero Ofimatica: {numero_ofimatica}, Abonos: {abonos}, Retenciones: {retenciones}, Valor a Pagar: {valor_pagar}")
# 
#         try:
#             # Definir la consulta SQL para la actualización de la factura
#             update_query = """
#                 UPDATE facturas
#                 SET numero_ofimatica = %s,
#                     password_in = %s,
#                     bruto = %s,
#                     iva_bruto = %s,
#                     vl_retfte = %s,
#                     v_retica = %s,
#                     v_reteniva = %s,
#                     subtotal = %s,
#                     total = %s,
#                     clasificacion_final = %s,
#                     abonos = %s,
#                     retenciones = %s,
#                     valor_pagar = %s,
#                     estado_final = %s,
#                     usuario_update_final = %s,
#                     hora_actualizacion_final = CURRENT_TIMESTAMP
#                 WHERE id = %s
#             """
# 
#             # Ejecutar la consulta SQL con los valores recibidos desde el formulario
#             cursor_pg.execute(update_query, (
#                 numero_ofimatica, password_in, bruto, iva_bruto, vl_retfte, v_retica, v_reteniva, subtotal, total, clasificacion_final, abonos, retenciones, valor_pagar, estado_final, usuario_id, factura_id
#             ))
# 
#             print("Consulta SQL:", "UPDATE facturas SET estado = %s WHERE id = %s")
#             print("Parámetros:", (estado_final, factura_id))
# 
#             # Confirmar los cambios en la base de datos
#             conn_pg.commit()
#             flash("Factura actualizada exitosamente.", "success")
#             print(f"Factura {factura_id} actualizada correctamente.")
# 
#         except Exception as e:
#             # En caso de error, mostrar mensaje y hacer rollback
#             flash(f"Hubo un error al actualizar la factura: {e}", "error")
#             conn_pg.rollback()
#             print(f"Error al actualizar la factura: {e}")
# 
#     cursor_sql = None  # Inicializar cursor_sql antes de usarlo
#     conn_sql = None  # Inicializar conn_sql antes de usarlo
# 
#     # Diccionario para almacenar los datos de ofimatica
#     ofimatica_data = {}
# 
#     if request.method == "POST":
#         print("Método POST detectado. Procesando facturas...")
# 
#         # Conectamos a SQL Server una vez antes de procesar todas las facturas
#         conn_sql = sql_server_connection()
#         cursor_sql = conn_sql.cursor()
# 
#         # Procesar el número de ofimática de cada factura
#         for factura in request.form.getlist("factura_id"):  # Iterar sobre las facturas
#             numero_ofimatica = request.form.get(f"numero_ofimatica_{factura}")
#             print(f"Número de ofimatica recibido para la factura {factura}: {numero_ofimatica}")
# 
#             if numero_ofimatica:
#                 try:
#                     # Primero consultar en PostgreSQL la clasificación de la factura
#                     query_clasificacion = """
#                         SELECT clasificacion
#                         FROM facturas
#                         WHERE id = %s
#                     """
#                     print(f"Consulta en PostgreSQL para obtener clasificación de la factura con ID {factura}.")
#                     cursor_pg.execute(query_clasificacion, (factura,))
#                     clasificacion = cursor_pg.fetchone()
#                     print(f"Clasificación obtenida: {clasificacion}")
# 
#                     if clasificacion:
#                         clasificacion = clasificacion[0]  # 'Facturas' o 'Servicios'
#                         if clasificacion == 'Facturas':
#                             # Es una factura MP (FR)
#                             sql_server_query = """
#                                 SELECT 
#                                     NRODCTO, 
#                                     PASSWORDIN, 
#                                     BRUTO, 
#                                     IVABRUTO, 
#                                     VLRETFTE, 
#                                     VRETICA, 
#                                     VRETENIVA, 
#                                     (bruto + IVABRUTO) AS SUBTOTAL, 
#                                     ((bruto + IVABRUTO) - VLRETFTE - VRETICA - VRETENIVA) AS TOTAL
#                                 FROM TRADE
#                                 WHERE NRODCTO = ? AND ORIGEN='COM' AND TIPODCTO='FR'
#                             """
#                             print(f"Consulta SQL que se ejecutará para Factura MP: {sql_server_query}")
#                             cursor_sql.execute(sql_server_query, (numero_ofimatica,))
#                         elif clasificacion == 'Servicios':
#                             # Es una factura de Servicios (FS) AND TIPODCTO='FS'
#                             sql_server_query = """
#                                 SELECT 
#                                     NRODCTO, 
#                                     PASSWORDIN, 
#                                     BRUTO, 
#                                     IVABRUTO, 
#                                     VLRETFTE, 
#                                     VRETICA, 
#                                     VRETENIVA, 
#                                     (bruto + IVABRUTO) AS SUBTOTAL, 
#                                     ((bruto + IVABRUTO) - VLRETFTE - VRETICA - VRETENIVA) AS TOTAL
#                                 FROM TRADE
#                                 WHERE NRODCTO = ? AND ORIGEN='COM' -- AND TIPODCTO='FS'
#                             """
#                             print(f"Consulta SQL que se ejecutará para Factura de Servicios: {sql_server_query}")
#                             cursor_sql.execute(sql_server_query, (numero_ofimatica,))
#                         else:
#                             print(f"Clasificación no válida para la factura {factura}: {clasificacion}")
#                             continue  # Si la clasificación no es válida, continuar con la siguiente factura
# 
#                         # Ejecutar la consulta en SQL Server
#                         ofimatica_result = cursor_sql.fetchone()
#                         print(f"Datos obtenidos de SQL Server: {ofimatica_result}")
# 
#                         if ofimatica_result:
#                             # Si se encontraron datos, asignarlos a un diccionario para la factura específica
#                             ofimatica_data[factura] = {
#                                 "numero_ofimatica": ofimatica_result[0],  # NRODCTO
#                                 "passwordin": ofimatica_result[1],        # PASSWORDIN
#                                 "bruto": ofimatica_result[2],             # BRUTO
#                                 "ivabruto": ofimatica_result[3],          # IVABRUTO
#                                 "vlretfte": ofimatica_result[4],          # VLRETFTE
#                                 "vretica": ofimatica_result[5],           # VRETICA
#                                 "vreteniva": ofimatica_result[6],         # VRETENIVA
#                                 "subtotal": ofimatica_result[7],          # SUBTOTAL
#                                 "total": ofimatica_result[8]              # TOTAL
#                             }
#                         else:
#                             flash(f"No se encontró la factura con el número de ofimática {numero_ofimatica}.", "error")
#                             print(f"No se encontró la factura con el número de ofimática {numero_ofimatica}.")
#                     else:
#                         print(f"No se encontró clasificación para la factura {factura}.")
#                         continue  # Si no se encuentra clasificación, pasar a la siguiente factura
# 
#                 except (psycopg2.Error, pyodbc.Error) as e:
#                     print(f"Error al consultar la base de datos: {e}")
#                     flash("Ocurrió un error al obtener los datos.", "error")
# 
#     try:
#         # Validar si el usuario pertenece al grupo de contabilidad
#         print("Validando grupo del usuario...")
#         query_validar_grupo = """
#             SELECT g.grupo 
#             FROM usuarios u
#             INNER JOIN grupo_aprobacion g ON u.grupo_aprobacion_id = g.id 
#             WHERE u.id = %s AND g.grupo = 'Contabilidad'
#         """
#         print(f"Consulta SQL que se ejecutará: {query_validar_grupo} con el usuario_id {usuario_id}")
#         
#         cursor_pg.execute(query_validar_grupo, (usuario_id,))
#         grupo = cursor_pg.fetchone()
#         print(f"Resultado de validación de grupo: {grupo}")
# 
#         if not grupo:
#             flash("No tienes permisos para acceder a esta funcionalidad.", "error")
#             print("Error: usuario no pertenece al grupo Contabilidad.")
#             return redirect("/")
# 
#         # Obtener las facturas aprobadas   120225 pago_mp = 'Aprobado' 
#         print("Consultando facturas aprobadas...")
#         query_facturas_aprobadas = """
#             SELECT id, nit, numero_factura, fecha_seleccionada, clasificacion, archivo_path, 
#                 pago_servicios, pago_mp, hora_aprobacion_pago_servicio, hora_aprobacion_pago_mp, nombre
#             FROM facturas
#             WHERE (pago_servicios = 'Aprobado' OR estado_compras = 'Aprobado') 
#             AND estado_final = 'Pendiente'
#             ORDER BY id
#         """
#         print(f"Consulta SQL que se ejecutará: {query_facturas_aprobadas}")
#         
#         cursor_pg.execute(query_facturas_aprobadas)
#         facturas = cursor_pg.fetchall()
#         print(f"Facturas encontradas: {facturas}")
# 
#         # Crear un diccionario de datos para las facturas que se mostrarán en la plantilla
#         facturas_data = []
#         for factura in facturas:
#             facturas_data.append({
#                 "id": factura[0],
#                 "nit": factura[1],
#                 "numero_factura": factura[2],
#                 "fecha_seleccionada": factura[3],
#                 "clasificacion": factura[4],
#                 "archivo_path": factura[5],
#                 "pago_servicios": factura[6],
#                 "pago_mp": factura[7],
#                 "hora_aprobacion_pago_servicio": factura[8],
#                 "hora_aprobacion_pago_mp": factura[9],
#                 "nombre": factura[10],
#                 "ofimatica_data": ofimatica_data.get(factura[0], {})  # Asignar los datos de ofimática a cada factura
#             })
# 
#     except Exception as e:
#         print(f"Error general en /gestion_final: {e}")
#         flash(f"Error al gestionar la vista final: {str(e)}", "error")
#         facturas_data = []
#         ofimatica_data = {}
# 
#     finally:
#         if cursor_pg:
#             cursor_pg.close()
#         if conn_pg:
#             conn_pg.close()
# 
#     print("Renderizando la plantilla gestion_final.html...")
#     return render_template("gestion_final.html", facturas_data=facturas_data, ofimatica_data=ofimatica_data)

# NUEVA FUNCIÓN AUTOMATIZADA
@app.route("/gestion_final", methods=["GET", "POST"])
@login_required
def gestion_final():
    print("Iniciando vista de gestión final AUTOMATIZADA...")

    # Obtener permisos del usuario para el menú dinámico
    usuario_id = session.get("user_id")
    grupo_usuario = obtener_permisos_usuario(usuario_id)
    
    # Verificar si el usuario tiene permiso para acceder a este módulo
    if not tiene_permiso(usuario_id, 'gestion_final'):
        flash("No tienes permisos para acceder a este módulo.", "error")
        return redirect("/")

    print(f"Usuario autenticado: {usuario_id}")

    # Conexión a PostgreSQL
    conn_pg = postgres_connection()
    cursor_pg = conn_pg.cursor()

    if request.method == "POST":
        # Recoger los valores enviados desde el formulario
        factura_id = request.form.get("factura_id")
        numero_ofimatica = request.form.get("numero_ofimatica")
        password_in = request.form.get("password_in")
        bruto = request.form.get("bruto")
        iva_bruto = request.form.get("iva_bruto")
        vl_retfte = request.form.get("vl_retfte")
        v_retica = request.form.get("v_retica")
        v_reteniva = request.form.get("v_reteniva")
        subtotal = request.form.get("subtotal")
        total = request.form.get("total")
        clasificacion_final = request.form.get("clasificacion_final")
        abonos = request.form.get("abonos")
        retenciones = request.form.get("retenciones")
        valor_pagar = request.form.get("valor_pagar")
        estado_final = 'Aprobado'

        print(f"Factura ID: {factura_id}, Numero Ofimatica: {numero_ofimatica}")

        try:
            # Validar y convertir campos numéricos antes de enviar a la base de datos
            def convertir_campo_numerico(valor):
                if not valor or valor == '' or valor == 'None':
                    return None
                try:
                    valor_float = float(valor)
                    # Si el valor es 0, también retornar None para campos opcionales
                    if valor_float == 0:
                        return None
                    return valor_float
                except (ValueError, TypeError):
                    return None
            
            # Convertir campos numéricos
            bruto_conv = convertir_campo_numerico(bruto)
            iva_bruto_conv = convertir_campo_numerico(iva_bruto)
            vl_retfte_conv = convertir_campo_numerico(vl_retfte)
            v_retica_conv = convertir_campo_numerico(v_retica)
            v_reteniva_conv = convertir_campo_numerico(v_reteniva)
            subtotal_conv = convertir_campo_numerico(subtotal)
            total_conv = convertir_campo_numerico(total)
            abonos_conv = convertir_campo_numerico(abonos)
            retenciones_conv = convertir_campo_numerico(retenciones)
            valor_pagar_conv = convertir_campo_numerico(valor_pagar)
            
            # Definir la consulta SQL para la actualización de la factura
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
                    clasificacion_final = %s,
                    abonos = %s,
                    retenciones = %s,
                    valor_pagar = %s,
                    estado_final = %s,
                    usuario_update_final = %s,
                    hora_actualizacion_final = CURRENT_TIMESTAMP
                WHERE id = %s
            """

            # Ejecutar la consulta SQL con los valores convertidos
            cursor_pg.execute(update_query, (
                numero_ofimatica, password_in, bruto_conv, iva_bruto_conv, vl_retfte_conv, v_retica_conv, v_reteniva_conv, subtotal_conv, total_conv, clasificacion_final, abonos_conv, retenciones_conv, valor_pagar_conv, estado_final, usuario_id, factura_id
            ))

            # Confirmar los cambios en la base de datos
            conn_pg.commit()
            flash("Factura actualizada exitosamente.", "success")
            print(f"Factura {factura_id} actualizada correctamente.")

        except Exception as e:
            # En caso de error, mostrar mensaje y hacer rollback
            flash(f"Hubo un error al actualizar la factura: {e}", "error")
            conn_pg.rollback()
            print(f"Error al actualizar la factura: {e}")

    try:
        # Validar si el usuario pertenece al grupo de contabilidad
        print("Validando grupo del usuario...")
        query_validar_grupo = """
            SELECT g.grupo 
            FROM usuarios u
            INNER JOIN grupo_aprobacion g ON u.grupo_aprobacion_id = g.id 
            WHERE u.id = %s AND g.grupo = 'Contabilidad'
        """
        
        cursor_pg.execute(query_validar_grupo, (usuario_id,))
        grupo = cursor_pg.fetchone()
        print(f"Resultado de validación de grupo: {grupo}")

        if not grupo:
            flash("No tienes permisos para acceder a esta funcionalidad.", "error")
            print("Error: usuario no pertenece al grupo Contabilidad.")
            return redirect("/")

        # Obtener las facturas aprobadas
        print("Consultando facturas aprobadas...")
        query_facturas_aprobadas = """
            SELECT 
                id, 
                nit, 
                numero_factura, 
                TO_CHAR(fecha_seleccionada, 'YYYY-MM-DD') AS fecha_seleccionada, 
                clasificacion, 
                archivo_path, 
                pago_servicios, 
                pago_mp, 
                TO_CHAR(hora_aprobacion_pago_servicio, 'YYYY-MM-DD HH24:MI:SS') AS hora_aprobacion_pago_servicio, 
                TO_CHAR(hora_aprobacion_pago_mp, 'YYYY-MM-DD HH24:MI:SS') AS hora_aprobacion_pago_mp, 
                nombre
            FROM facturas
            WHERE (estado_usuario_asignado = 'Aprobado' OR estado_compras = 'Aprobado') 
            AND estado_final = 'Pendiente'
            ORDER BY id
        """
        print("/gestion_final -> Ejecutando consulta:\n", query_facturas_aprobadas)
        cursor_pg.execute(query_facturas_aprobadas)
        facturas = cursor_pg.fetchall()
        print(f"/gestion_final -> Filas obtenidas: {len(facturas)}")
        if facturas:
            print("/gestion_final -> Primera fila (muestra):", facturas[0])

        # BÚSQUEDA AUTOMÁTICA EN SQL SERVER
        print("Iniciando búsqueda automática en SQL Server...")
        conn_sql = sql_server_connection()
        cursor_sql = conn_sql.cursor()
        
        facturas_data = []
        ofimatica_data = {}
        
        # Contadores para estadísticas
        auto_actualizadas = 0
        requieren_manual = 0
        errores_actualizacion = 0
        
        for factura in facturas:
            factura_id = factura[0]
            nit = factura[1]
            numero_factura = factura[2].strip()  # Limpiar espacios
            clasificacion = factura[4]
            
            # Determinar tipo de documento
            def determinar_tipo_documento(clasificacion):
                mapeo_tipos = {
                    'Facturas': 'FR',
                    'Servicios': 'FS',
                    'Facturas Genericas': 'FG',
                    'Notas Credito': 'DP',
                    'Documento Soporte': 'DN',
                    'Caja Menor': 'CM'
                }
                return mapeo_tipos.get(clasificacion, 'FS')  # Default a FS si no se encuentra
            
            tipodcto = determinar_tipo_documento(clasificacion)
            if not tipodcto:
                print(f"  ⚠ Clasificación no válida para la factura {factura_id}: {clasificacion}")
                continue
            
            print(f"Buscando automáticamente: NIT={nit}, Factura='{numero_factura}', Tipo={tipodcto} ({clasificacion})")
            
            # Logging especial para CM
            if tipodcto == 'CM':
                print(f"  🔍 [CM] Iniciando búsqueda para Caja Menor")
                print(f"  🔍 [CM] Parámetros: dctoprv='{numero_factura}', NIT='{nit}', TIPODCTO='CM'")
            
            # Generar consulta adaptativa según el tipo de documento
            def generar_consulta_sql(tipodcto):
                if tipodcto in ['FR', 'FS', 'FG']:
                    # Documentos con estructura completa (facturas)
                    return """
                SELECT 
                    NRODCTO, 
                    PASSWORDIN, 
                    BRUTO, 
                    IVABRUTO, 
                    VLRETFTE, 
                    VRETICA, 
                    VRETENIVA, 
                            (BRUTO + ISNULL(IVABRUTO, 0)) AS SUBTOTAL, 
                            ((BRUTO + ISNULL(IVABRUTO, 0)) - ISNULL(VLRETFTE, 0) - ISNULL(VRETICA, 0) - ISNULL(VRETENIVA, 0)) AS TOTAL
                        FROM TRADE
                        WHERE LTRIM(RTRIM(dctoprv)) = ? AND NIT = ? AND TIPODCTO = ? AND ORIGEN = 'COM'
                    """
                elif tipodcto == 'DP':
                    # Notas crédito (estructura intermedia)
                    return """
                        SELECT 
                            NRODCTO, 
                            PASSWORDIN, 
                            BRUTO, 
                            ISNULL(IVABRUTO, 0) AS IVABRUTO, 
                            ISNULL(VLRETFTE, 0) AS VLRETFTE, 
                            ISNULL(VRETICA, 0) AS VRETICA, 
                            ISNULL(VRETENIVA, 0) AS VRETENIVA, 
                            BRUTO AS SUBTOTAL, 
                            (BRUTO - ISNULL(VLRETFTE, 0) - ISNULL(VRETICA, 0) - ISNULL(VRETENIVA, 0)) AS TOTAL
                        FROM TRADE
                        WHERE LTRIM(RTRIM(dctoprv)) = ? AND NIT = ? AND TIPODCTO = ? AND ORIGEN = 'COM'
                    """
                elif tipodcto == 'DN':
                    # Documentos soporte (estructura simplificada)
                    return """
                        SELECT 
                            NRODCTO, 
                            PASSWORDIN, 
                            BRUTO, 
                            0 AS IVABRUTO, 
                            0 AS VLRETFTE, 
                            0 AS VRETICA, 
                            0 AS VRETENIVA, 
                            BRUTO AS SUBTOTAL, 
                            BRUTO AS TOTAL
                        FROM TRADE
                        WHERE LTRIM(RTRIM(dctoprv)) = ? AND NIT = ? AND TIPODCTO = ? AND ORIGEN = 'COM'
                        ORDER BY NRODCTO DESC
                    """
                elif tipodcto == 'CM':
                    # Caja menor (estructura con IVA real)
                    return """
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
                else:
                    # Default a la consulta original
                    return """
                        SELECT 
                            NRODCTO, 
                            PASSWORDIN, 
                            BRUTO, 
                            IVABRUTO, 
                            VLRETFTE, 
                            VRETICA, 
                            VRETENIVA, 
                            (BRUTO + ISNULL(IVABRUTO, 0)) AS SUBTOTAL, 
                            ((BRUTO + ISNULL(IVABRUTO, 0)) - ISNULL(VLRETFTE, 0) - ISNULL(VRETICA, 0) - ISNULL(VRETENIVA, 0)) AS TOTAL
                FROM TRADE
                WHERE LTRIM(RTRIM(dctoprv)) = ? AND NIT = ? AND TIPODCTO = ? AND ORIGEN = 'COM'
            """
            
            # Búsqueda automática en SQL Server usando dctoprv
            query_auto = generar_consulta_sql(tipodcto)
            
            try:
                # Logging especial para CM antes de ejecutar
                if tipodcto == 'CM':
                    print(f"  🔍 [CM] Ejecutando consulta con parámetros: ('{numero_factura}', '{nit}', 'CM')")
                    print(f"  🔍 [CM] Query: {query_auto[:200]}...")  # Primeros 200 caracteres
                
                cursor_sql.execute(query_auto, (numero_factura, nit, tipodcto))
                resultados_auto = cursor_sql.fetchall()
                
                # Logging especial para CM después de ejecutar
                if tipodcto == 'CM':
                    print(f"  🔍 [CM] Resultados encontrados: {len(resultados_auto)}")
                    if resultados_auto:
                        print(f"  🔍 [CM] Primer resultado: NRODCTO={resultados_auto[0][0]}, BRUTO={resultados_auto[0][2]}, IVABRUTO={resultados_auto[0][3]}")
                    else:
                        print(f"  ❌ [CM] No se encontraron resultados para dctoprv='{numero_factura}', NIT='{nit}'")
                
                if resultados_auto:
                    # Si hay múltiples resultados, validar antes de seleccionar
                    if len(resultados_auto) > 1:
                        print(f"  ⚠️ MÚLTIPLES COINCIDENCIAS encontradas para factura {factura_id}: {len(resultados_auto)} registros")
                        print(f"  📋 Opciones disponibles:")
                        
                        # Mostrar todas las opciones para validación
                        for i, resultado in enumerate(resultados_auto):
                            print(f"    {i+1}. NRODCTO: {resultado[0]}, PASSWORDIN: {resultado[1]}, BRUTO: {resultado[2]}")
                        
                        # Para DN, validar que el BRUTO coincida aproximadamente con el valor esperado
                        if tipodcto == 'DN':
                            # Buscar el resultado con BRUTO más cercano al valor esperado
                            valor_esperado = float(factura[5]) if len(factura) > 5 and factura[5] else 0
                            if valor_esperado > 0:
                                mejor_resultado = None
                                menor_diferencia = float('inf')
                                
                                for resultado in resultados_auto:
                                    bruto_resultado = float(resultado[2]) if resultado[2] else 0
                                    diferencia = abs(bruto_resultado - valor_esperado)
                                    
                                    if diferencia < menor_diferencia:
                                        menor_diferencia = diferencia
                                        mejor_resultado = resultado
                                
                                if mejor_resultado:
                                    resultado_auto = mejor_resultado
                                    print(f"  🎯 Para DN: Seleccionando por coincidencia de BRUTO (diferencia: {menor_diferencia:.2f})")
                                else:
                                    resultado_auto = resultados_auto[0]
                                    print(f"  ⚠️ Para DN: No se pudo validar BRUTO, seleccionando el más reciente")
                            else:
                                resultado_auto = resultados_auto[0]
                                print(f"  ⚠️ Para DN: No hay valor esperado para validar, seleccionando el más reciente")
                        else:
                            # Para otros tipos, seleccionar el más reciente
                            resultado_auto = resultados_auto[0]
                            print(f"  ✅ Seleccionando automáticamente: NRODCTO {resultado_auto[0]}, PASSWORDIN: {resultado_auto[1]}")
                    else:
                        resultado_auto = resultados_auto[0]
                    print(f"  ✓ COINCIDENCIA AUTOMÁTICA ENCONTRADA para factura {factura_id}")
                    
                    # Cargar datos para el frontend
                    ofimatica_data[factura_id] = {
                        "numero_ofimatica": str(resultado_auto[0]),  # NRODCTO
                        "passwordin": str(resultado_auto[1]),        # PASSWORDIN
                        "bruto": float(resultado_auto[2]) if resultado_auto[2] else 0,             # BRUTO
                        "ivabruto": float(resultado_auto[3]) if resultado_auto[3] else 0,          # IVABRUTO
                        "vlretfte": float(resultado_auto[4]) if resultado_auto[4] else 0,          # VLRETFTE
                        "vretica": float(resultado_auto[5]) if resultado_auto[5] else 0,           # VRETICA
                        "vreteniva": float(resultado_auto[6]) if resultado_auto[6] else 0,         # VRETENIVA
                        "subtotal": float(resultado_auto[7]) if resultado_auto[7] else 0,          # SUBTOTAL
                        "total": float(resultado_auto[8]) if resultado_auto[8] else 0,             # TOTAL
                        "auto_cargado": True,                    # Marcar como cargado automáticamente
                        "actualizado_auto": False                # Inicialmente no actualizado
                    }
                    
                    # EJECUTAR UPDATE AUTOMÁTICO INMEDIATO
                    try:
                        # Definir la consulta SQL para la actualización automática
                        update_query_auto = """
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
                                clasificacion_final = %s,
                                abonos = %s,
                                retenciones = %s,
                                valor_pagar = %s,
                                estado_final = %s,
                                usuario_update_final = %s,
                                hora_actualizacion_final = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """
                        
                        # Determinar clasificación final basada en el tipo de documento
                        def determinar_clasificacion_final(tipodcto):
                            mapeo_clasificacion = {
                                'FR': 'FR',
                                'FS': 'FS', 
                                'FG': 'FG',
                                'DP': 'DP',
                                'DN': 'DN',
                                'CM': 'CM'
                            }
                            return mapeo_clasificacion.get(tipodcto, 'FS')
                        
                        clasificacion_final = determinar_clasificacion_final(tipodcto)
                        
                        # Calcular valores adicionales con manejo robusto de nulos
                        def convertir_valor_seguro(valor, default=None):
                            if valor is None or valor == '':
                                return default
                            try:
                                valor_float = float(valor)
                                return valor_float if valor_float != 0 else default
                            except (ValueError, TypeError):
                                return default
                        
                        abonos = None  # NULL en lugar de 0 para campos vacíos
                        retenciones = convertir_valor_seguro(resultado_auto[4])  # VLRETFTE
                        valor_pagar = convertir_valor_seguro(resultado_auto[8])  # TOTAL
                        
                        # Validar y truncar valores numéricos para evitar desbordamiento
                        def validar_valor_numerico(valor, max_valor=99999999.99):
                            if valor is None or valor == '':
                                return 0
                            try:
                                valor_float = float(valor)
                                # Truncar a 2 decimales y limitar el valor máximo
                                valor_truncado = round(valor_float, 2)
                                if valor_truncado > max_valor:
                                    print(f"  ⚠️ Valor {valor_truncado} truncado a {max_valor}")
                                    return max_valor
                                return valor_truncado
                            except (ValueError, TypeError):
                                return 0
                        
                        # Ejecutar UPDATE automático con valores validados
                        cursor_pg.execute(update_query_auto, (
                            str(resultado_auto[0]),  # numero_ofimatica
                            str(resultado_auto[1]),  # password_in
                            validar_valor_numerico(resultado_auto[2]),  # bruto
                            validar_valor_numerico(resultado_auto[3]),  # iva_bruto
                            validar_valor_numerico(resultado_auto[4]),  # vl_retfte
                            validar_valor_numerico(resultado_auto[5]),  # v_retica
                            validar_valor_numerico(resultado_auto[6]),  # v_reteniva
                            validar_valor_numerico(resultado_auto[7]),  # subtotal
                            validar_valor_numerico(resultado_auto[8]),  # total
                            clasificacion_final,  # clasificacion_final
                            abonos,  # abonos
                            validar_valor_numerico(retenciones),  # retenciones
                            validar_valor_numerico(valor_pagar),  # valor_pagar
                            'Aprobado',  # estado_final
                            usuario_id,  # usuario_update_final
                            factura_id   # WHERE id
                        ))
                        
                        conn_pg.commit()
                        print(f"  ✅ UPDATE AUTOMÁTICO EXITOSO para factura {factura_id}")
                        
                        # Marcar como actualizado automáticamente
                        ofimatica_data[factura_id]["actualizado_auto"] = True
                        auto_actualizadas += 1
                        
                    except Exception as e:
                        print(f"  ❌ ERROR en UPDATE automático para factura {factura_id}: {e}")
                        conn_pg.rollback()
                        errores_actualizacion += 1
                        ofimatica_data[factura_id]["error_actualizacion"] = str(e)
                        
                else:
                    print(f"  ✗ No se encontró coincidencia automática para factura {factura_id}")
                    # Buscar múltiples registros para mostrar opciones (consulta adaptativa)
                    def generar_consulta_multiple(tipodcto):
                        if tipodcto in ['FR', 'FS', 'FG']:
                            return """
                        SELECT TOP 5
                            NRODCTO, 
                            PASSWORDIN, 
                            BRUTO, 
                            IVABRUTO, 
                            VLRETFTE, 
                            VRETICA, 
                            VRETENIVA, 
                                    (BRUTO + ISNULL(IVABRUTO, 0)) AS SUBTOTAL, 
                                    ((BRUTO + ISNULL(IVABRUTO, 0)) - ISNULL(VLRETFTE, 0) - ISNULL(VRETICA, 0) - ISNULL(VRETENIVA, 0)) AS TOTAL,
                                    LTRIM(RTRIM(dctoprv)) as dctoprv_limpio
                                FROM TRADE
                                WHERE NIT = ? AND TIPODCTO = ? AND ORIGEN = 'COM'
                                ORDER BY NRODCTO
                            """
                        elif tipodcto == 'DP':
                            return """
                                SELECT TOP 5
                                    NRODCTO, 
                                    PASSWORDIN, 
                                    BRUTO, 
                                    ISNULL(IVABRUTO, 0) AS IVABRUTO, 
                                    ISNULL(VLRETFTE, 0) AS VLRETFTE, 
                                    ISNULL(VRETICA, 0) AS VRETICA, 
                                    ISNULL(VRETENIVA, 0) AS VRETENIVA, 
                                    BRUTO AS SUBTOTAL, 
                                    (BRUTO - ISNULL(VLRETFTE, 0) - ISNULL(VRETICA, 0) - ISNULL(VRETENIVA, 0)) AS TOTAL,
                                    LTRIM(RTRIM(dctoprv)) as dctoprv_limpio
                                FROM TRADE
                                WHERE NIT = ? AND TIPODCTO = ? AND ORIGEN = 'COM'
                                ORDER BY NRODCTO
                            """
                        elif tipodcto == 'DN':
                            return """
                                SELECT TOP 5
                                    NRODCTO, 
                                    PASSWORDIN, 
                                    BRUTO, 
                                    0 AS IVABRUTO, 
                                    0 AS VLRETFTE, 
                                    0 AS VRETICA, 
                                    0 AS VRETENIVA, 
                                    BRUTO AS SUBTOTAL, 
                                    BRUTO AS TOTAL,
                                    LTRIM(RTRIM(dctoprv)) as dctoprv_limpio
                                FROM TRADE
                                WHERE NIT = ? AND TIPODCTO = ? AND ORIGEN = 'COM'
                                ORDER BY NRODCTO
                            """
                        elif tipodcto == 'CM':
                            return """
                                SELECT TOP 5
                                    NRODCTO, 
                                    PASSWORDIN, 
                                    BRUTO, 
                                    ISNULL(IVABRUTO, 0) AS IVABRUTO, 
                                    ISNULL(VLRETFTE, 0) AS VLRETFTE, 
                                    ISNULL(VRETICA, 0) AS VRETICA, 
                                    ISNULL(VRETENIVA, 0) AS VRETENIVA, 
                                    (BRUTO + ISNULL(IVABRUTO, 0)) AS SUBTOTAL, 
                                    ((BRUTO + ISNULL(IVABRUTO, 0)) - ISNULL(VLRETFTE, 0) - ISNULL(VRETICA, 0) - ISNULL(VRETENIVA, 0)) AS TOTAL,
                                    LTRIM(RTRIM(dctoprv)) as dctoprv_limpio
                                FROM TRADE
                                WHERE NIT = ? AND TIPODCTO = ? AND ORIGEN = 'COM'
                                ORDER BY NRODCTO
                            """
                        else:
                            return """
                                SELECT TOP 5
                                    NRODCTO, 
                                    PASSWORDIN, 
                                    BRUTO, 
                                    IVABRUTO, 
                                    VLRETFTE, 
                                    VRETICA, 
                                    VRETENIVA, 
                                    (BRUTO + ISNULL(IVABRUTO, 0)) AS SUBTOTAL, 
                                    ((BRUTO + ISNULL(IVABRUTO, 0)) - ISNULL(VLRETFTE, 0) - ISNULL(VRETICA, 0) - ISNULL(VRETENIVA, 0)) AS TOTAL,
                            LTRIM(RTRIM(dctoprv)) as dctoprv_limpio
                        FROM TRADE
                        WHERE NIT = ? AND TIPODCTO = ? AND ORIGEN = 'COM'
                        ORDER BY NRODCTO
                    """
                    
                    query_multiple = generar_consulta_multiple(tipodcto)
                    
                    # Búsqueda de opciones múltiples para selección manual
                    # Nota: Corregida indentación del bloque try-except (líneas 2928-2967)
                    try:
                        cursor_sql.execute(query_multiple, (nit, tipodcto))
                        resultados_multiple = cursor_sql.fetchall()
                        
                        if resultados_multiple:
                            print(f"  ⚠ Encontrados {len(resultados_multiple)} registros para selección manual")
                            requieren_manual += 1
                            # Convertir a lista de diccionarios para JSON
                            opciones_list = []
                            for resultado in resultados_multiple:
                                opciones_list.append({
                                    "nrodcto": str(resultado[0]),
                                    "passwordin": str(resultado[1]),
                                    "bruto": float(resultado[2]) if resultado[2] else 0,
                                    "ivabruto": float(resultado[3]) if resultado[3] else 0,
                                    "vlretfte": float(resultado[4]) if resultado[4] else 0,
                                    "vretica": float(resultado[5]) if resultado[5] else 0,
                                    "vreteniva": float(resultado[6]) if resultado[6] else 0,
                                    "subtotal": float(resultado[7]) if resultado[7] else 0,
                                    "total": float(resultado[8]) if resultado[8] else 0,
                                    "dctoprv": str(resultado[9]) if resultado[9] else ""
                                })
                            ofimatica_data[factura_id] = {
                                "opciones_multiple": opciones_list,
                                "auto_cargado": False
                            }
                        else:
                            print(f"  ✗ No se encontraron registros para factura {factura_id}")
                            requieren_manual += 1
                            ofimatica_data[factura_id] = {
                                "auto_cargado": False,
                                "sin_registros": True
                            }
                    except Exception as e:
                        print(f"  ⚠ Error en búsqueda de opciones múltiples para factura {factura_id}: {e}")
                        requieren_manual += 1
                        ofimatica_data[factura_id] = {
                            "auto_cargado": False,
                            "error_opciones": str(e)
                        }
                        
            except Exception as e:
                print(f"  ⚠ Error en búsqueda automática para factura {factura_id}: {e}")
                requieren_manual += 1
                ofimatica_data[factura_id] = {
                    "auto_cargado": False,
                    "error_busqueda": str(e)
                }
            
            # Crear datos de factura para la plantilla
            facturas_data.append({
                "id": factura[0],
                "nit": factura[1],
                "numero_factura": factura[2],
                "fecha_seleccionada": factura[3],
                "clasificacion": factura[4],
                "archivo_path": factura[5],
                "pago_servicios": factura[6],
                "pago_mp": factura[7],
                "hora_aprobacion_pago_servicio": factura[8],
                "hora_aprobacion_pago_mp": factura[9],
                "nombre": factura[10],
                "ofimatica_data": ofimatica_data.get(factura[0], {})
            })
        
        # Estadísticas finales de automatización
        total_facturas = len(facturas_data)
        print(f"\n📊 ESTADÍSTICAS DE AUTOMATIZACIÓN:")
        print(f"  Total facturas: {total_facturas}")
        print(f"  ✅ Actualizadas automáticamente: {auto_actualizadas}")
        print(f"  ⚠ Requieren intervención manual: {requieren_manual}")
        print(f"  ❌ Errores de actualización: {errores_actualizacion}")
        if total_facturas > 0:
            porcentaje_exito = (auto_actualizadas / total_facturas) * 100
            print(f"  🎯 Porcentaje de éxito: {porcentaje_exito:.1f}%")
            
            if porcentaje_exito >= 70:
                print("  🎉 EXCELENTE - Alta automatización lograda!")
            elif porcentaje_exito >= 50:
                print("  👍 BUENO - Automatización moderada")
            else:
                print("  ⚠️ MEJORABLE - Baja automatización")
        
        if auto_actualizadas > 0:
            flash(f"✅ {auto_actualizadas} facturas actualizadas automáticamente", "success")
        if errores_actualizacion > 0:
            flash(f"⚠️ {errores_actualizacion} errores en actualizaciones automáticas", "warning")

    except Exception as e:
        print(f"Error general en /gestion_final: {e}")
        flash(f"Error al gestionar la vista final: {str(e)}", "error")
        facturas_data = []
        ofimatica_data = {}

    finally:
        if cursor_pg:
            cursor_pg.close()
        if conn_pg:
            conn_pg.close()
        if 'cursor_sql' in locals():
            cursor_sql.close()
        if 'conn_sql' in locals():
            conn_sql.close()

    print("Renderizando la plantilla gestion_final.html...")
    return render_template("gestion_final.html", 
                         facturas_data=facturas_data, 
                         ofimatica_data=ofimatica_data,
                         grupo_usuario=grupo_usuario,
                         permisos_modulos=PERMISOS_MODULOS)


# Ruta para buscar datos de la base de datos
def obtener_factura(numero_ofimatica):
    print(f"Buscando datos para la factura con número de ofimatica: {numero_ofimatica}")
    
    # Conexión con la base de datos SQL Server
    conn = sql_server_connection()
    cursor = conn.cursor()

    # Consulta para buscar el número de ofimatica en la base de datos
    query = f"""
        SELECT NRODCTO, PASSWORDIN, BRUTO, IVABRUTO, VLRETFTE, VRETICA, VRETENIVA,
               (BRUTO + IVABRUTO) AS SUBTOTAL,
               ((BRUTO + IVABRUTO) - VLRETFTE - VRETICA - VRETENIVA) AS TOTAL
        FROM TRADE
        WHERE NRODCTO = ? AND ORIGEN='COM'
    """
    print(f"Consulta SQL que se ejecutará: {query}")
    
    cursor.execute(query, (numero_ofimatica,))  # Añadimos el '%' para el LIKE
    #cursor.execute(query, (numero_ofimatica,))
    result = cursor.fetchone()

    cursor.close()
    conn.close()

    # Si se encontró un resultado, lo devolvemos
    if result:
        print(f"Factura encontrada: {result}")
        return {
            "nro_dcto": result[0].strip() if result[0] else "",
            "passwordin": result[1].strip() if result[1] else "",
            "bruto": str(result[2]),
            "ivabruto": str(result[3]),
            "vlretfte": str(result[4]),
            "vretica": str(result[5]),
            "vreteniva": str(result[6]),
            "subtotal": str(result[7]),
            "total": str(result[8]),
            # Campos adicionales calculados
            "retenciones": str(result[4]),  # VLRETFTE como 'retenciones'
            "valor_pagar": str(result[5]),  # Un valor arbitrario, por ejemplo
            "abonos": str(result[6]),  # Otro valor arbitrario
            "saldos": str(result[7]),  # Un valor calculado arbitrario
            "clasificacion_final": 'FS'  # Puedes mantener esto como un valor fijo
        }
    else:
        print(f"No se encontró factura con número de ofimatica {numero_ofimatica}.")
        return None

    


def convertir_decimal_a_float(dato):
    """Convierte cualquier valor Decimal a float recursivamente en diccionarios o listas."""
    if isinstance(dato, decimal.Decimal):
        return float(dato)
    elif isinstance(dato, dict):
        return {key: convertir_decimal_a_float(value) for key, value in dato.items()}
    elif isinstance(dato, list):
        return [convertir_decimal_a_float(item) for item in dato]
    else:
        return dato

@app.route('/buscar_ofimatica/<numero_ofimatica>', methods=['GET'])
def buscar_ofimatica(numero_ofimatica):
    try:
        # Consulta a la base de datos
        factura = obtener_factura(numero_ofimatica)

        # Imprimir la factura para depuración
        print(f"Factura recibida: {factura}")

        # Verificar si la factura se ha encontrado
        if factura:
            # Convertir todos los valores de Decimal a float de manera recursiva
            factura = convertir_decimal_a_float(factura)

            # Devolver la respuesta como JSON
            return jsonify(factura)
        else:
            return jsonify({"error": "Factura no encontrada."}), 404

    except Exception as e:
        # Manejo de excepciones en caso de error en la consulta o en el proceso
        print(f"Error al procesar la factura: {e}")
        return jsonify({"error": "Error interno al procesar la solicitud."}), 500
    
@app.route("/autocomplete_ofimatica")
def autocomplete_ofimatica():
    term = request.args.get("term")

    query = """
    SELECT DISTINCT TOP 30 
        NRODCTO, PASSWORDIN, BRUTO, IVABRUTO, VLRETFTE, VRETICA, VRETENIVA,
        (BRUTO + IVABRUTO) AS SUBTOTAL,
        ((BRUTO + IVABRUTO) - VLRETFTE - VRETICA - VRETENIVA) AS TOTAL
    FROM TRADE
    WHERE NRODCTO LIKE ? AND ORIGEN='COM'
    """


    conn = sql_server_connection()  
    cursor = conn.cursor()          
    cursor.execute(query, (f"%{term}%",))
    rows = cursor.fetchall()

    suggestions = []
    for row in rows:
        suggestions.append({
            "nro_dcto": row[0].strip() if row[0] else '',
            "passwordin": row[1].strip() if row[1] else '',
            "bruto": str(row[2]) if row[2] is not None else '0.00',
            "ivabruto": str(row[3]) if row[3] is not None else '0.00',
            "vlretfte": str(row[4]) if row[4] is not None else '0.00',
            "vretica": str(row[5]) if row[5] is not None else '0.00',
            "vreteniva": str(row[6]) if row[6] is not None else '0.00',
            "subtotal": str(row[7]) if row[7] is not None else '0.00',
            "total": str(row[8]) if row[8] is not None else '0.00',
        })


    conn.close()  
    return jsonify(suggestions)





@app.route("/tesoreria", methods=["GET", "POST"])
@login_required
def tesoreria():
    print("Iniciando vista para vincular documentos a un archivo PDF...")

    # Obtener el ID del usuario autenticado desde la sesión
    usuario_id = session.get("user_id")
    if not usuario_id:
        flash("Tu sesión ha expirado o no has iniciado sesión.", "error")
        return redirect(url_for("login"))

    # Obtener permisos del usuario para el menú dinámico
    grupo_usuario = obtener_permisos_usuario(usuario_id)
    
    # Verificar si el usuario tiene permiso para acceder a este módulo
    if not tiene_permiso(usuario_id, 'tesoreria'):
        flash("No tienes permisos para acceder a Tesorería.", "error")
        print("Error: usuario no tiene permisos para Tesorería.")
        return redirect("/")

    if request.method == "POST":
        archivo_pdf = request.files.get("archivo_pdf")

        # Validar si se ha subido un archivo PDF
        if not archivo_pdf:
            flash("Por favor, sube un archivo PDF.", "error")
            return render_template("tesoreria.html", 
                                 grupo_usuario=grupo_usuario,
                                 permisos_modulos=PERMISOS_MODULOS)

        print(f"Archivo recibido: {archivo_pdf.filename}")

        # Guardar el archivo PDF
        directorio_base = os.path.join(app.config['UPLOAD_FOLDER'], 'Pagos')
        if not os.path.exists(directorio_base):
            os.makedirs(directorio_base)

        # Guardar el archivo PDF en la nueva carpeta "Pagos"
        archivo_nombre = archivo_pdf.filename  # Nombre del archivo (ej. archivo.pdf)
        archivo_path = os.path.join('Pagos', archivo_nombre)  # Guardar solo la ruta relativa
        archivo_pdf.save(os.path.join(directorio_base, archivo_nombre))
        print(f"Archivo guardado en: {archivo_path}")

        try:
            # Conexión a SQL Server para buscar los documentos de los últimos 30 días
            conn_sql_server = sql_server_connection()
            cursor_sql_server = conn_sql_server.cursor()

            # Consultar los documentos de los últimos 45 días
            query_sql_server = """
                 SELECT
                    LTRIM(RTRIM(ABOCXP.dcto)) AS dcto,
                    LTRIM(RTRIM(ABOCXP.fecha)) AS fecha,
                    LTRIM(RTRIM(ABOCXP.cheque)) AS cheque,
                    LTRIM(RTRIM(ABOCXP.nit)) AS nit,
                    LTRIM(RTRIM(ABOCXP.PASSWORDIN)) AS PASSWORDIN,
                    ISNULL(FORMAT(CAST(ABOCXP.valor AS MONEY), 'N0', 'es-CO'), '0') AS valor,
                    LTRIM(RTRIM(ABOCXP.tipodcto)) AS tipodcto,
                    LTRIM(RTRIM(ABOCXP.factura)) AS factura,
                    LTRIM(RTRIM(mtprocli.nombre)) AS nombre_tercero
                FROM ABOCXP
                INNER JOIN mtprocli ON ABOCXP.nit = mtprocli.NIT
                WHERE fecha >= DATEADD(DAY, -365, GETDATE())
                AND tipodcto = 'CE'
                ORDER BY factura;
            """
            print(f"Ejecutando consulta SQL Server: {query_sql_server}")
            cursor_sql_server.execute(query_sql_server)
            documentos = cursor_sql_server.fetchall()

            # Si no se encontraron documentos, mostrar mensaje
            if not documentos:
                flash("No se encontraron documentos en los últimos 30 días.", "error")
                return render_template("tesoreria.html", 
                                     grupo_usuario=grupo_usuario,
                                     permisos_modulos=PERMISOS_MODULOS)

            print(f"Documentos encontrados: {len(documentos)}")

            # Procesamos los documentos y los agrupamos por mes/año
            documentos_por_mes = {}
            meses_espanol = {
                1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
                5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
                9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
            }
            
            for dcto, fecha, cheque, nit, passwordin, valor, tipodcto, factura, nombre_tercero in documentos:
                # Crear objeto documento
                documento = {
                    "dcto": dcto,
                    "fecha": fecha,
                    "cheque": cheque,
                    "nit": nit,
                    "passwordin": passwordin,
                    "valor": valor,
                    "tipodcto": tipodcto,
                    "factura": factura,
                    "nombre_tercero": nombre_tercero
                }
                
                # Parsear la fecha para obtener mes y año
                try:
                    # La fecha puede venir como string o como objeto datetime desde SQL Server
                    fecha_parseada = None
                    if isinstance(fecha, str):
                        # Intentar diferentes formatos de fecha comunes en SQL Server
                        fecha_limpia = fecha.strip()
                        
                        # Intentar primero con dateutil.parser que es más flexible (maneja mayúsculas/minúsculas)
                        try:
                            from dateutil import parser
                            fecha_parseada = parser.parse(fecha_limpia)
                        except:
                            # Si dateutil no está disponible o falla, intentar formatos específicos
                            formatos_fecha = [
                                '%b %d %Y %I:%M:%S %p',  # Dec 27 2024 12:00:00 AM (con segundos)
                                '%b %d %Y %I:%M%p',      # Dec 27 2024 12:00AM (sin segundos)
                                '%b %d %Y',              # Dec 27 2024 (sin hora)
                                '%Y-%m-%d',              # 2024-11-15
                                '%Y-%m-%d %H:%M:%S',     # 2024-11-15 10:30:00
                                '%d/%m/%Y',              # 15/11/2024
                                '%Y/%m/%d',              # 2024/11/15
                                '%m/%d/%Y',              # 11/15/2024
                                '%d-%m-%Y',              # 15-11-2024
                            ]
                            
                            # Intentar con el string original y también con el mes en minúsculas
                            fecha_parseada = None
                            for fmt in formatos_fecha:
                                try:
                                    fecha_parseada = datetime.strptime(fecha_limpia, fmt)
                                    break
                                except:
                                    # Intentar con el mes en minúsculas (para formatos con %b)
                                    if '%b' in fmt:
                                        try:
                                            # Convertir el mes a minúsculas (ej: "Dec" -> "dec")
                                            partes = fecha_limpia.split()
                                            if len(partes) > 0:
                                                partes[0] = partes[0].lower()
                                                fecha_lower = ' '.join(partes)
                                                fecha_parseada = datetime.strptime(fecha_lower, fmt)
                                                break
                                        except:
                                            continue
                                    continue
                            
                            if not fecha_parseada:
                                # Si no se puede parsear, usar fecha actual como fallback
                                print(f"⚠️ No se pudo parsear fecha: {fecha}, usando fecha actual")
                                fecha_parseada = datetime.now()
                    elif hasattr(fecha, 'year') and hasattr(fecha, 'month'):
                        # Si ya es un objeto datetime
                        fecha_parseada = fecha
                    else:
                        # Fallback a fecha actual
                        print(f"⚠️ Formato de fecha desconocido: {type(fecha)}, usando fecha actual")
                        fecha_parseada = datetime.now()
                    
                    año = fecha_parseada.year
                    mes = fecha_parseada.month
                    clave_mes = f"{año}-{mes:02d}"
                    nombre_mes = f"{meses_espanol[mes]} {año}"
                    
                    # Agrupar por mes
                    if clave_mes not in documentos_por_mes:
                        documentos_por_mes[clave_mes] = {
                            "mes": nombre_mes,
                            "clave": clave_mes,
                            "documentos": []
                        }
                    
                    documentos_por_mes[clave_mes]["documentos"].append(documento)
                    
                except Exception as e:
                    print(f"Error parseando fecha {fecha}: {e}")
                    # Si hay error, poner en un mes "Sin fecha"
                    clave_mes = "sin-fecha"
                    if clave_mes not in documentos_por_mes:
                        documentos_por_mes[clave_mes] = {
                            "mes": "Sin fecha",
                            "clave": clave_mes,
                            "documentos": []
                        }
                    documentos_por_mes[clave_mes]["documentos"].append(documento)

            # Ordenar los meses de más reciente a más antiguo
            meses_ordenados = sorted(documentos_por_mes.keys(), reverse=True)
            documentos_ordenados = {clave: documentos_por_mes[clave] for clave in meses_ordenados if clave != "sin-fecha"}
            if "sin-fecha" in documentos_por_mes:
                documentos_ordenados["sin-fecha"] = documentos_por_mes["sin-fecha"]

            # Calcular total de documentos
            total_documentos = sum(len(grupo["documentos"]) for grupo in documentos_ordenados.values())

            # Mostrar los documentos encontrados antes de enviarlos
            print(f"Documentos procesados: {total_documentos} en {len(documentos_ordenados)} meses")

            # Asegurarse de que la respuesta sea un JSON
            return jsonify({
                "documentos_por_mes": documentos_ordenados,
                "archivo_path": archivo_path,
                "num_documentos": total_documentos,
                "num_meses": len(documentos_ordenados)
            })

        except Exception as e:
            flash(f"Ocurrió un error al buscar los documentos: {e}", "error")
            print(f"Error en la consulta SQL Server: {e}")

        finally:
            if cursor_sql_server:
                cursor_sql_server.close()
            if conn_sql_server:
                conn_sql_server.close()

    return render_template("tesoreria.html", 
                         grupo_usuario=grupo_usuario,
                         permisos_modulos=PERMISOS_MODULOS)


@app.route("/guardar_documentos", methods=["POST"])
def guardar_documentos():
    print("🔍 INICIANDO guardar_documentos")
    print("=" * 50)
    
    try:
        # Obtener la ruta del archivo y los documentos seleccionados
        archivo_path = request.form.get("archivo_path")
        print(f'📁 Ruta del archivo recibida: {archivo_path}')
        
        selected_documents_json = request.form.get("selectedDocuments")
        print(f'📦 JSON recibido: {selected_documents_json}')

        if not selected_documents_json:
            print("❌ No se recibieron documentos seleccionados")
            return jsonify({"success": False, "message": "No se recibieron documentos seleccionados"}), 400

        # Deserializar el JSON
        selected_documents = json.loads(selected_documents_json)
        print(f"📋 Documentos deserializados: {selected_documents}")

        # Conexión a PostgreSQL
        conn_pg = postgres_connection()
        cursor_pg = conn_pg.cursor()

        actualizados = 0
        errores = 0

        # Iterar sobre los documentos seleccionados
        for doc in selected_documents:
            dcto = doc['dcto']
            factura = doc['factura']
            print(f'🔄 Procesando: Dcto={dcto}, Factura={factura}')

            try:
                # PRIMERO: Verificar si la factura existe por numero_ofimatica
                # El campo 'factura' de SQL Server corresponde al 'numero_ofimatica' de PostgreSQL
                # Usar LTRIM(RTRIM()) para manejar espacios en blanco
                check_query = """
                    SELECT id, numero_ofimatica, numero_factura 
                    FROM facturas 
                    WHERE LTRIM(RTRIM(numero_ofimatica)) = %s
                """
                cursor_pg.execute(check_query, (str(factura),))  # Usar factura en lugar de dcto
                factura_encontrada = cursor_pg.fetchone()
                
                if factura_encontrada:
                    print(f"✅ Factura encontrada por numero_ofimatica: ID={factura_encontrada[0]}, numero_ofimatica='{factura_encontrada[1]}', numero_factura='{factura_encontrada[2]}'")
                    
                    # Realizar el UPDATE en la tabla facturas usando numero_ofimatica
                    update_query = """
                        UPDATE facturas
                        SET dctos = %s, archivo_pdf = %s
                        WHERE LTRIM(RTRIM(numero_ofimatica)) = %s
                    """
                    print(f"🔧 Ejecutando query: {update_query}")
                    print(f"📝 Parámetros: dcto={dcto}, archivo_path={archivo_path}, numero_ofimatica={factura}")
                    
                    cursor_pg.execute(update_query, (dcto, archivo_path, str(factura)))
                    
                    if cursor_pg.rowcount > 0:
                        actualizados += 1
                        print(f"✅ Actualizado: factura numero_ofimatica {factura} con dcto {dcto} - {cursor_pg.rowcount} fila(s) afectada(s)")
                    else:
                        errores += 1
                        print(f"❌ Error en UPDATE para factura numero_ofimatica {factura}")
                else:
                    errores += 1
                    print(f"❌ No se encontró factura con numero_ofimatica: {factura}")
                    
                    # Mostrar algunas facturas para debugging
                    cursor_pg.execute("SELECT id, numero_ofimatica, numero_factura FROM facturas LIMIT 5")
                    ejemplos = cursor_pg.fetchall()
                    print(f"📋 Ejemplos de facturas en BD: {ejemplos}")
                    
            except Exception as e:
                errores += 1
                print(f"❌ Error actualizando factura {factura}: {e}")

        # Confirmar los cambios
        conn_pg.commit()
        print(f"💾 Commit realizado")

        mensaje = f"✅ {actualizados} documentos vinculados correctamente"
        if errores > 0:
            mensaje += f", ❌ {errores} errores"

        print(f"📊 Resultado final: {mensaje}")
        return jsonify({
            "success": True, 
            "message": mensaje,
            "actualizados": actualizados,
            "errores": errores
        })

    except Exception as e:
        print(f"❌ Error general en guardar_documentos: {e}")
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500

    finally:
        if cursor_pg:
            cursor_pg.close()
        if conn_pg:
            conn_pg.close()


@app.route("/facturas_resumen", methods=["GET"])
@login_required
def facturas_servicios():
    # Obtener permisos del usuario para el menú dinámico
    usuario_id = session.get("user_id")
    grupo_usuario = obtener_permisos_usuario(usuario_id)
    
    # Verificar si el usuario tiene permiso para acceder a este módulo
    if not tiene_permiso(usuario_id, 'facturas_resumen'):
        flash("No tienes permisos para acceder a este módulo.", "error")
        print("/facturas_resumen -> Acceso denegado para usuario:", usuario_id)
        return redirect("/")
    
    print("/facturas_resumen -> Usuario:", usuario_id, "Grupo:", grupo_usuario)
    
    # Obtener parámetros de fecha
    fecha_desde = request.args.get('fecha_desde')
    fecha_hasta = request.args.get('fecha_hasta')
    
    print(f"/facturas_resumen -> Parámetros: fecha_desde={fecha_desde}, fecha_hasta={fecha_hasta}")
    
    # Si no hay fechas, mostrar formulario vacío (sin tabla)
    if not fecha_desde or not fecha_hasta:
        print("/facturas_resumen -> Sin fechas, mostrando formulario")
        return render_template("facturas_servicios.html", 
                             facturas=None,  # Indicador para mostrar formulario
                             fecha_desde=None,
                             fecha_hasta=None,
                             grupo_usuario=grupo_usuario,
                             permisos_modulos=PERMISOS_MODULOS)
    
    conn_pg = postgres_connection()
    cursor = conn_pg.cursor()

    try:
        consulta = """
            SELECT 
                f.nit, 
                f.nombre, 
                f.numero_factura,
                TO_CHAR(f.fecha_seleccionada, 'YYYY-MM-DD') AS fecha_seleccionada,
                TO_CHAR(f.fecha_registro, 'YYYY-MM-DD HH24:MI:SS') AS fecha_registro,
                f.clasificacion, 
                f.archivo_path,
                TO_CHAR(f.hora_aprobacion, 'YYYY-MM-DD HH24:MI:SS') as aprobacion_bodega, 
                f.estado as estado_aprobacion_bodega, 
                COALESCE(u.usuario, '') as usuario_aprueba_bodega,
                f.estado_compras,
                TO_CHAR(f.hora_aprobacion_compras, 'YYYY-MM-DD HH24:MI:SS') as hora_aprobacion_compras,
                COALESCE(u1.usuario, '') as usuario_aprueba_compras, 
                f.remision,
                f.nrodcto_oc as orden_compra,
                f.pago_mp as estado_aprobacion_jefe_mp, 
                f.estado_final as estado_final_contabilizado,
                f.archivo_pdf as archivo_pago_banco, 
                f.dctos as comprobantes_egresos, 
                COALESCE(u3.usuario, '') as usuario_asignado_servicios, 
                COALESCE(u2.usuario, '') as usuario_asigno_contabilidad,
                f.estado_usuario_asignado as estado_aprobacion_user_servi,
                TO_CHAR(f.hora_aprobacion_asignado, 'YYYY-MM-DD HH24:MI:SS') as hora_aprobacion_user_servicio, 
                f.pago_servicios as aprobacion_jefe_servicios,
                TO_CHAR(f.hora_aprobacion_pago_servicio, 'YYYY-MM-DD HH24:MI:SS') as hora_aprobacion_jefe_servicio,
                f.valor_pagar,
                f.observaciones_regis, 
                f.aproba_auditor,
                f.id       
            FROM facturas f
            LEFT JOIN usuarios u ON f.aprobado_bodega = u.id  
            LEFT JOIN usuarios u1 ON f.aprobado_compras = u1.id  
            LEFT JOIN usuarios u2 ON f.aprobado_servicios = u2.id 
            LEFT JOIN usuarios u3 ON f.usuario_asignado_servicios = u3.id 
            WHERE f.fecha_seleccionada BETWEEN %s AND %s
            ORDER BY f.fecha_seleccionada DESC
        """
        
        print(f"/facturas_resumen -> Ejecutando consulta con rango: {fecha_desde} - {fecha_hasta}")

        cursor.execute(consulta, (fecha_desde, fecha_hasta))
        facturas = cursor.fetchall()

        print(f"✅ /facturas_resumen -> Facturas encontradas: {len(facturas)}")
        if facturas and len(facturas) > 0:
            print(f"/facturas_resumen -> Primera fila (muestra): ID={facturas[0][-1]}, NIT={facturas[0][0]}")

    except Exception as e:
        print(f"❌ /facturas_resumen -> Error en consulta: {e}")
        flash(f"Error al consultar las facturas: {str(e)}", "error")
        facturas = []

    finally:
        if cursor:
            cursor.close()
        if conn_pg:
            conn_pg.close()
        print("/facturas_resumen -> Conexiones cerradas")

    print(f"/facturas_resumen -> Renderizando plantilla con {len(facturas)} facturas")
    return render_template("facturas_servicios.html", 
                         facturas=facturas,
                         fecha_desde=fecha_desde,
                         fecha_hasta=fecha_hasta,
                         grupo_usuario=grupo_usuario,
                         permisos_modulos=PERMISOS_MODULOS)


@app.route('/buscar_orden', methods=['GET'])
def buscar_orden():
    query = request.args.get('q', '')  
    if query:
        try:
            conn = sql_server_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    trade.nrodcto, 
                    trade.NIT, 
                    mtprocli.nombre AS nombre_cliente
                FROM 
                    trade
                INNER JOIN 
                    mtprocli ON trade.nit = mtprocli.nit
                WHERE 
                    trade.nrodcto LIKE ?
                    AND trade.ORIGEN = 'COM' 
                    AND trade.tipodcto = 'OC'
            """, ('%' + query + '%',))  # Buscar coincidencias
            results = cursor.fetchall()
            
            ordenes = [{
                'nrodcto': row[0],
                'nit': row[1],
                'nombre_cliente': row[2]
            } for row in results]

            return jsonify(ordenes)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return jsonify([])  
 


@app.route("/gestion_inicial_mp", methods=["GET", "POST"]) 
@login_required
def gestion_inicial():
    # Obtener permisos del usuario para el menú dinámico
    usuario_id = session.get("user_id")
    grupo_usuario = obtener_permisos_usuario(usuario_id)
    
    # Verificar si el usuario tiene permiso para acceder a este módulo
    if not tiene_permiso(usuario_id, 'gestion_inicial_mp'):
        flash("No tienes permisos para acceder a este módulo.", "error")
        return redirect("/")

    # Inicializar conexiones fuera del bloque POST para que estén disponibles en toda la función
    conn_pg = postgres_connection()
    cursor_pg = conn_pg.cursor()

    if request.method == "POST":
        # Procesar los datos del formulario y eliminar espacios de las variables
        nrodcto_oc = request.form.get("nrodcto", "").strip() or "Valor por defecto"
        nit_oc = request.form.get("nit", "").strip() or "0000000000"
        nombre_cliente_oc = request.form.get("nombre_cliente", "").strip() or "Cliente Desconocido"
        cantidad_oc = request.form.get("cantidad", "").strip() or 0
        archivo = request.files.get("orden_compra")
        print(f"Datos recibidos: nrodcto_oc={nrodcto_oc}, nit_oc={nit_oc}, nombre_cliente_oc={nombre_cliente_oc}, "
              f"cantidad_oc={cantidad_oc}")

        # Validación del archivo
        if not archivo or not archivo.filename:
            flash("Debes subir un archivo PDF", "error")
            return redirect(request.url)

        # Consultar si ya existe un nrodcto_oc duplicado
        try:
            cursor_pg.execute("""
                SELECT COUNT(*) 
                FROM ordenes_compras 
                WHERE nrodcto_oc = %s
            """, (nrodcto_oc,))
            count = cursor_pg.fetchone()[0]

            if count > 0:
                flash("El número de orden de compra ya existe en el sistema.", "error")
                return redirect(request.url)
        
        except Exception as e:
            flash(f"Error al verificar el duplicado en PostgreSQL: {str(e)}", "error")
            return redirect(request.url)

        # Crear la jerarquía de directorios: clasificacion/nit/fecha
        fecha_directorio = datetime.now().strftime("%Y%m%d")
        ruta_directorio = os.path.join(app.config["UPLOAD_FOLDER"], nit_oc, fecha_directorio)
        os.makedirs(ruta_directorio, exist_ok=True)
        print(f"Ruta del directorio creada: {ruta_directorio}")

        # Guardar el archivo en la ruta definida
        archivo_path = os.path.join(ruta_directorio, archivo.filename)
        archivo.save(archivo_path)
        print(f"Archivo guardado en: {archivo_path}")

        # Calcular la ruta relativa desde el directorio 'static/uploads'
        ruta_relativa_oc = os.path.relpath(archivo_path, app.config["UPLOAD_FOLDER"])
        print(f"Ruta relativa del archivo: {ruta_relativa_oc}")

        # Consultar datos del número de orden en SQL Server
        try:
            conn_sql = sql_server_connection()
            cursor_sql = conn_sql.cursor()
            cursor_sql.execute("""
                SELECT 
                    trade.nrodcto, 
                    trade.bruto, 
                    trade.IVABRUTO, 
                    trade.NIT, 
                    mtprocli.nombre, 
                    mvtrade.CANTIDAD, 
                    mvtrade.nombre AS nombre_referencia, 
                    mvtrade.producto AS numero_referencia
                FROM 
                    trade
                INNER JOIN 
                    mvtrade ON trade.nrodcto = mvtrade.nrodcto
                INNER JOIN 
                    mtprocli ON trade.nit = mtprocli.nit
                WHERE 
                    trade.nrodcto = ? 
                    AND trade.ORIGEN = 'COM' 
                    AND trade.tipodcto = 'OC' 
                    AND mvtrade.ORIGEN = 'COM' 
                    AND mvtrade.tipodcto = 'OC'
            """, (nrodcto_oc,))
            rows = cursor_sql.fetchall()

            if rows:
                # Desestructurar el primer resultado
                nrodcto, bruto_oc, ivabruto_oc, nit_oc, nombre_cliente_oc, cantidad_oc, nombre_referencia_oc, numero_referencia_oc = rows[0]

                # Unir las referencias con coma y quitar espacios
                nombre_referencia_oc = ",".join([row[6].strip() for row in rows if row[6]]) 
                numero_referencia_oc = ",".join([str(row[7]).strip() for row in rows if row[7]])

                # Mostrar las referencias concatenadas
                print(f"Nombre referencias: {nombre_referencia_oc}")
                print(f"Número referencias: {numero_referencia_oc}")
            else:
                flash("No se encontró la orden de compra en SQL Server", "error")
                return redirect(request.url)
        except Exception as e:
            flash(f"Error consultando la orden en SQL Server: {str(e)}", "error")
            return redirect(request.url)

        # Guardar datos en PostgreSQL
        try:
            # Obtener la hora actual
            hora_actual_oc = datetime.now()

            cursor_pg.execute("""
                INSERT INTO ordenes_compras (nrodcto_oc, bruto_oc, ivabruto_oc, nit_oc, nombre_cliente_oc, 
                                            cantidad_oc, nombre_referencia_oc, numero_referencia_oc, archivo_path_oc, 
                                            hora_registro_oc, usuario_id_oc) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                nrodcto_oc, bruto_oc, ivabruto_oc, nit_oc, nombre_cliente_oc, cantidad_oc, 
                nombre_referencia_oc, numero_referencia_oc, ruta_relativa_oc, hora_actual_oc, usuario_id
            ))

            conn_pg.commit()
            flash("Orden de compra registrada exitosamente", "success")
        except Exception as e:
            flash(f"Error al guardar en PostgreSQL: {str(e)}", "error")
            return redirect(request.url)
        
    # Consultar las órdenes de compra para mostrar en la plantilla
    # Nota: Corregida indentación del bloque try-except-finally (líneas 3665-3678)
    try:
        cursor_pg.execute("SELECT id, nrodcto_oc, nit_oc, nombre_cliente_oc, hora_registro_oc, estado FROM ordenes_compras ORDER BY hora_registro_oc DESC")
        ordenes = [dict(zip([d[0] for d in cursor_pg.description], row)) for row in cursor_pg.fetchall()]
    except Exception as e:
        print(f"Error consultando órdenes de compra: {e}")
        flash(f"Error al consultar las órdenes de compra: {str(e)}", "error")
        ordenes = []
    finally:
        # Cerrar conexiones
        if cursor_pg:
            cursor_pg.close()
        if conn_pg:
            conn_pg.close()

    return render_template("gestion_inicial.html", 
                         ordenes=ordenes,
                         grupo_usuario=grupo_usuario,
                         permisos_modulos=PERMISOS_MODULOS)

@app.route("/get_orden")
@login_required
def get_orden():
    id_oc = request.args.get("id")
    if not id_oc:
        return jsonify(error="ID no proporcionado"), 400
    conn_pg = postgres_connection()
    cursor_pg = conn_pg.cursor()

    cursor_pg.execute("SELECT id, nrodcto_oc, nit_oc, nombre_cliente_oc, estado FROM ordenes_compras WHERE id=%s", (id_oc,))
    row = cursor_pg.fetchone()
    if not row:
        return jsonify(error="Orden no encontrada"), 404
    return jsonify(dict(zip([d[0] for d in cursor_pg.description], row)))

@app.route("/editar_orden", methods=["POST"])
@login_required
def editar_orden():
    id_oc = request.form.get("id_oc")
    nit = request.form.get("nit_oc").strip()
    nombre = request.form.get("nombre_cliente_oc").strip()
    estado = request.form.get("estado", "Pendiente").strip()
    archivo = request.files.get("orden_compra")

    conn_pg = postgres_connection()
    cursor_pg = conn_pg.cursor()

    if archivo and archivo.filename:
        fecha_directorio = datetime.now().strftime("%Y%m%d")
        ruta_directorio = os.path.join(app.config["UPLOAD_FOLDER"], nit, fecha_directorio)
        os.makedirs(ruta_directorio, exist_ok=True)
        archivo_path = os.path.join(ruta_directorio, archivo.filename)
        archivo.save(archivo_path)
        ruta_relativa = os.path.relpath(archivo_path, app.config["UPLOAD_FOLDER"])
        ruta_relativa = ruta_relativa.replace("static/", "")
        cursor_pg.execute("UPDATE ordenes_compras SET nit_oc=%s, nombre_cliente_oc=%s, archivo_path_oc=%s, estado=%s WHERE id=%s",
                          (nit, nombre, ruta_relativa, estado, id_oc))
    else:
        cursor_pg.execute("UPDATE ordenes_compras SET nit_oc=%s, nombre_cliente_oc=%s, estado=%s WHERE id=%s",
                          (nit, nombre, estado, id_oc))
    conn_pg.commit()
    flash("Orden actualizada exitosamente", "success")
    return redirect(url_for('gestion_inicial'))



@app.route("/aprobar_factura/<int:id_factura>", methods=["POST"])
@login_required
def aprobar_factura(id_factura):
    conn_pg = None
    cursor = None
    usuario = session.get("user_id")  

    try:
        conn_pg = postgres_connection()
        cursor = conn_pg.cursor()

        cursor.execute("""
            SELECT g.grupo
            FROM usuarios u
            INNER JOIN grupo_aprobacion g ON u.grupo_aprobacion_id = g.id
            WHERE u.id = %s AND g.grupo = 'Auditores'
        """, (usuario,))
        grupo_usuario = cursor.fetchone()

        if not grupo_usuario:
            return jsonify({"success": False, "message": "No tienes permisos para aprobar facturas."}), 403

        cursor.execute("""
            UPDATE facturas
            SET
                aproba_auditor = 'Aprobado', 
                hora_aproba_auditor = CURRENT_TIMESTAMP, 
                usuario_auditor = %s
            WHERE id = %s AND aproba_auditor = 'Pendiente'
        """, (usuario, id_factura))

        conn_pg.commit()
        return jsonify({"success": True, "message": "Factura aprobada exitosamente"}), 200

    except Exception as e:
        conn_pg.rollback()
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500

    finally:
        if cursor:
            cursor.close()
        if conn_pg:
            conn_pg.close()



@app.route("/auditor", methods=["GET"])
@login_required
def auditor():
    # Obtener permisos del usuario para el menú dinámico
    usuario_id = session.get("user_id")
    grupo_usuario = obtener_permisos_usuario(usuario_id)
    
    # Verificar si el usuario tiene permiso para acceder a este módulo
    if not tiene_permiso(usuario_id, 'auditor'):
        flash("No tienes permisos para acceder a este módulo.", "error")
        return redirect("/")
    
    conn_pg = postgres_connection()
    cursor = conn_pg.cursor()

    try:
        consulta_auditor = """
            SELECT 
                id,
                numero_ofimatica,
                nit,
                nombre,
                numero_factura,
                TO_CHAR(fecha_seleccionada,'YYYY-MM-DD') AS fecha_seleccionada,
                nrodcto_oc,
                archivo_path,
                bruto,
                iva_bruto,
                vl_retfte,
                v_retica,
                v_reteniva,
                subtotal,
                total
            FROM facturas 
            WHERE aproba_auditor='Pendiente'
        """
        print("/auditor -> Ejecutando consulta:\n", consulta_auditor)
        cursor.execute(consulta_auditor)
        facturas = cursor.fetchall()
        print(f"/auditor -> Filas obtenidas: {len(facturas)}")
        if facturas:
            print("/auditor -> Primera fila (muestra):", facturas[0])

    except Exception as e:
        flash(f"Error al consultar las facturas: {str(e)}", "error")
        facturas = []

    finally:
        if cursor:
            cursor.close()
        if conn_pg:
            conn_pg.close()

    return render_template("auditor.html", 
                         facturas=facturas,
                         grupo_usuario=grupo_usuario,
                         permisos_modulos=PERMISOS_MODULOS)




@app.route("/debug/automatizar_cm", methods=["GET", "POST"])
@login_required
def debug_automatizar_cm():
    """Endpoint de debugging para probar automatización de documentos CM"""
    if request.method == "POST":
        factura_id = request.form.get("factura_id")
        numero_factura = request.form.get("numero_factura")
        nit = request.form.get("nit")
        
        if not factura_id or not numero_factura or not nit:
            return jsonify({"error": "Faltan parámetros: factura_id, numero_factura, nit"}), 400
        
        try:
            # Conectar a SQL Server
            conn_sql = sql_server_connection()
            cursor_sql = conn_sql.cursor()
            
            # Consulta para CM
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
            
            cursor_sql.execute(query_cm, (numero_factura, nit, 'CM'))
            resultados = cursor_sql.fetchall()
            
            cursor_sql.close()
            conn_sql.close()
            
            if resultados:
                resultado = resultados[0]
                return jsonify({
                    "success": True,
                    "encontrado": True,
                    "datos": {
                        "nrodcto": str(resultado[0]),
                        "passwordin": str(resultado[1]),
                        "bruto": float(resultado[2]) if resultado[2] else 0,
                        "ivabruto": float(resultado[3]) if resultado[3] else 0,
                        "subtotal": float(resultado[7]) if resultado[7] else 0,
                        "total": float(resultado[8]) if resultado[8] else 0
                    },
                    "total_resultados": len(resultados)
                })
            else:
                return jsonify({
                    "success": True,
                    "encontrado": False,
                    "mensaje": f"No se encontraron resultados para dctoprv='{numero_factura}', NIT='{nit}', TIPODCTO='CM'"
                })
                
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    # GET: Mostrar formulario de prueba
    return """
    <html>
    <head><title>Debug Automatización CM</title></head>
    <body>
        <h1>Debug Automatización CM</h1>
        <form method="POST">
            <label>Factura ID: <input type="text" name="factura_id" required></label><br>
            <label>Número Factura (dctoprv): <input type="text" name="numero_factura" required></label><br>
            <label>NIT: <input type="text" name="nit" required></label><br>
            <button type="submit">Probar Consulta</button>
        </form>
    </body>
    </html>
    """
        
@app.route("/logout")
def logout():
    session.clear()  
    flash("Sesión cerrada exitosamente", "success")
    return redirect(url_for("login"))



if __name__ == "__main__":
    app.run(host='10.1.200.11', port=2837, debug=True)
