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


app = Flask(__name__)
app.secret_key = "secret_key_example"
ROOT_FOLDER = os.path.abspath(os.path.dirname(__file__))  # Directorio raíz del proyecto
UPLOAD_FOLDER = os.path.join(ROOT_FOLDER, 'static', "uploads")  # Carpeta principal para archivos
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Asegurar directorio de carga
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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
    nombre = request.args.get("q", "").upper()  # Convertir el nombre ingresado a mayúsculas
    
    if nombre:
        try:
            conn = sql_server_connection()  # Asegúrate de que la conexión a SQL Server esté funcionando
            if not conn:
                return jsonify({"error": "No se pudo conectar a la base de datos"}), 500
            
            cursor = conn.cursor()

            # Realizar la consulta, comparando en mayúsculas
            query = """
                SELECT TOP 10 nit, nombre 
                FROM MTPROCLI 
                WHERE UPPER(nombre) LIKE ?  -- Convertir el campo 'nombre' a mayúsculas
                ORDER BY nombre
            """
            cursor.execute(query, ('%' + nombre + '%',))  # Agregar '%' para realizar la búsqueda de substring
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
    if request.method == "POST":
        # Procesar datos del formulario
        nit = request.form.get("nit")
        numero_factura = request.form.get("numero_factura")
        fecha_seleccionada = request.form.get("fecha")
        clasificacion = request.form.get("clasificacion")
        archivo = request.files.get("archivo")
        observaciones = request.form.get("observaciones")

        if not archivo or not archivo.filename:
            flash("Debes subir un archivo", "error")
            return redirect(request.url)

        # Definir clasificación de factura en texto
        clasificacion_texto = "Facturas" if clasificacion == "1" else "Servicios"

        # Crear la jerarquía de directorios: clasificacion/nit/fecha
        fecha_directorio = fecha_seleccionada.replace("-", "")  
        ruta_directorio = os.path.join(
            app.config["UPLOAD_FOLDER"], clasificacion_texto, nit, fecha_directorio
        )
        os.makedirs(ruta_directorio, exist_ok=True)  # Crear directorios si no existen

        # Guardar el archivo en la ruta definida
        archivo_path = os.path.join(ruta_directorio, archivo.filename)
        archivo.save(archivo_path)

        # Calcular la ruta relativa desde el directorio 'static/uploads'
        ruta_relativa = os.path.relpath(archivo_path, app.config["UPLOAD_FOLDER"])

        # Aquí eliminamos el prefijo 'static/' de la ruta relativa
        ruta_relativa = ruta_relativa.replace("static/", "")  # Eliminar la parte 'static/' de la ruta

        # Consultar NIT en SQL Server
        try:
            conn = sql_server_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT nombre FROM MTPROCLI WHERE LTRIM(RTRIM(nit)) = ?", nit.strip())
            row = cursor.fetchone()
            if row:
                nombre = row[0]
            else:
                flash("NIT no encontrado en SQL Server", "error")
                return redirect(request.url)
        except Exception as e:
            flash(f"Error consultando NIT: {str(e)}", "error")
            return redirect(request.url)

        # Guardar datos en PostgreSQL
        try:
            conn_pg = postgres_connection()
            if not conn_pg:
                raise Exception("Conexión a PostgreSQL fallida. Verifica los parámetros de conexión en db_config.py.")
            print("Conexión exitosa a PostgreSQL dentro de Flask")
            cursor_pg = conn_pg.cursor()

            # Verificar si ya existe un registro con el mismo número de factura
            cursor_pg.execute("SELECT COUNT(*) FROM facturas WHERE numero_factura = %s", (numero_factura,))
            count = cursor_pg.fetchone()[0]
            if count > 0:
                flash("La factura con este número ya ha sido registrada", "error")
                return redirect(request.url)
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
            flash("Factura registrada exitosamente", "success")

            # Realizar el SELECT y mostrar en consola
            cursor_pg.execute("SELECT * FROM facturas")
            facturas = cursor_pg.fetchall()
            print("Datos actuales en la tabla 'facturas':")
            for factura in facturas:
                print(factura)
        except Exception as e:
            print("Error al intentar conectarse a PostgreSQL desde Flask:")
            print(e)
            flash(f"Error guardando en PostgreSQL: {str(e)}", "error")
            return redirect(request.url)

    return render_template("index.html")



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

# Gestión de Grupos
@app.route("/grupos", methods=["GET", "POST"])
@login_required
def gestion_grupos():
    if request.method == "POST":
        grupo = request.form.get("grupo")
        descripcion = request.form.get("descripcion")
        usuario_id = session.get("user_id")  # Obtener el ID del usuario desde la sesión

        try:
            conn_pg = postgres_connection()
            cursor = conn_pg.cursor()

            # Validar si el usuario pertenece al grupo de Contabilidad
            print("Validando grupo del usuario...")
            query_validar_grupo = """
                SELECT g.grupo 
                FROM usuarios u
                INNER JOIN grupo_aprobacion g ON u.grupo_aprobacion_id = g.id 
                WHERE u.id = %s AND g.grupo = 'Contabilidad'
            """
            cursor.execute(query_validar_grupo, (usuario_id,))
            grupo_usuario = cursor.fetchone()

            print("Grupo obtenido:", grupo_usuario)

            if not grupo_usuario:
                flash("No tienes permisos para gestionar grupos.", "error")
                print("Error: usuario no pertenece al grupo de Contabilidad.")
                return redirect("/grupos")

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

    return render_template("grupos.html")


# Gestión de Usuarios
@app.route("/usuarios", methods=["GET", "POST"])
@login_required
def gestion_usuarios():
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
            usuario_id = session.get("user_id")  # Obtener el ID del usuario desde la sesión

            print("Datos recibidos del formulario:")
            print(f"Nombre: {nombre}, Apellido: {apellido}, Usuario: {usuario}, Correo: {correo}, Grupo ID: {grupo_id}")

            # Validar si el usuario pertenece al grupo de Contabilidad
            print("Validando grupo del usuario...")
            query_validar_grupo = """
                SELECT g.grupo 
                FROM usuarios u
                INNER JOIN grupo_aprobacion g ON u.grupo_aprobacion_id = g.id 
                WHERE u.id = %s AND g.grupo = 'Contabilidad'
            """
            cursor.execute(query_validar_grupo, (usuario_id,))
            grupo_usuario = cursor.fetchone()

            print("Grupo obtenido:", grupo_usuario)

            if not grupo_usuario:
                flash("No tienes permisos para gestionar usuarios.", "error")
                print("Error: usuario no pertenece al grupo de Contabilidad.")
                return redirect("/usuarios")

            try:
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

    except Exception as e:
        print(f"Error conectando a la base de datos: {e}")
        flash(f"Error conectando a la base de datos: {str(e)}", "error")
        grupos = []

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
    return render_template("usuarios.html", grupos=grupos)



@app.route("/bodega", methods=["GET", "POST"])
@login_required
def gestion_bodega():
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

                    # Obtener la factura_id para esta orden de compra específica
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

                        # Actualizar el estado de la factura a 'Aprobado' y registrar los lotes
                        hora_aprobacion = datetime.now()
                        cursor_pg.execute("""
                            UPDATE facturas
                            SET estado = 'Aprobado', 
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

        # Consultar órdenes de compra aprobadas desde SQL Server (trade)
        print("Consultando órdenes de compra aprobadas desde SQL Server...")
        cursor_sql.execute("""
            SELECT NRODCTO 
            FROM trade
            WHERE origen = 'COM' 
            AND TIPODCTO = 'OC' 
            AND TRIM(autorizpor) = 'RRQ07'
        """)
        ordenes_aprobadas_sql = cursor_sql.fetchall()

        print(f"Órdenes de compra aprobadas encontradas: {len(ordenes_aprobadas_sql)} registros.")
        
        if not ordenes_aprobadas_sql:
            print("No se encontraron órdenes aprobadas en SQL Server.")
            return render_template("bodega.html", ordenes_compras=[], facturas_pendientes={}, referencias={})

        nrodcto_aprobadas = [orden[0].strip() for orden in ordenes_aprobadas_sql]

        # Consultar las órdenes de compra en PostgreSQL que estén pendientes y coincidan con los NRODCTO aprobados en SQL Server
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
                WHERE fac.estado = 'Pendiente' AND oc.estado = 'Pendiente' AND oc.nit_oc = %s
                ORDER BY fac.fecha_seleccionada ASC
            """, (nit_oc,))
            facturas_pg = cursor_pg.fetchall()

            print(f"Facturas encontradas para NIT {nit_oc} en Postgresql: {len(facturas_pg)} registros.")

            if facturas_pg:
                facturas_pendientes[orden[0]] = facturas_pg
            else:
                print(f"No se encontraron facturas para NIT {nit_oc} en PostgreSQL.")

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
        referencias=referencias_dict
    )




@app.route("/compras", methods=["GET", "POST"])
@login_required
def gestion_compras():
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
                oc.archivo_path_oc  
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
    return render_template("compras.html", facturas=facturas)



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

@app.route("/servicios", methods=["GET", "POST"])
@login_required
def gestion_servicios():
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
                flash("Factura asignada y aprobada exitosamente", "success")
            except Exception as e:
                conn_pg.rollback()
                print("Error durante la actualización de la factura:", e)
                flash(f"Error aprobando y asignando factura: {str(e)}", "error")

        # Consultar facturas pendientes
        cursor.execute("""
            SELECT id, nit, numero_factura, fecha_seleccionada, clasificacion, archivo_path, estado, nombre 
            FROM facturas
            WHERE clasificacion = 'Servicios' AND estado = 'Pendiente'
            ORDER BY fecha_seleccionada ASC
        """)
        facturas = cursor.fetchall()
        print("Facturas pendientes obtenidas:", facturas)

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

    return render_template("servicios.html", facturas=facturas, usuarios=usuarios)


@app.route("/asignaciones", methods=["GET", "POST"])
@login_required
def gestion_asignaciones():
    print("Iniciando gestión de asignaciones...")

    conn_pg = postgres_connection()
    print("Conexión a la base de datos establecida.")
    cursor = conn_pg.cursor()

    # Obtener el ID del usuario autenticado desde la sesións
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
            print(f"Factura recibida para aprobación: {factura_id}")

            if not factura_id or not factura_id.isdigit():
                flash("El ID de la factura no es válido.", "error")
                print("Error: factura_id no es válido.")
                return redirect("/asignaciones")

            # Validar que la factura pertenece al usuario actual y está pendiente
            print("Validando si la factura pertenece al usuario actual...")
            cursor.execute("""
                SELECT id, estado_usuario_asignado
                FROM facturas
                WHERE id = %s AND usuario_asignado_servicios = %s
            """, (factura_id, usuario_actual_id))
            factura = cursor.fetchone()
            print(f"Resultado de la validación de factura: {factura}")

            if not factura:
                flash("No tienes permiso para aprobar esta factura o ya ha sido aprobada.", "error")
                print("Error: factura no encontrada o no pertenece al usuario.")
                return redirect("/asignaciones")

            if factura[1] == 'Aprobado':
                flash("La factura ya ha sido aprobada anteriormente.", "warning")
                print("Advertencia: la factura ya estaba aprobada.")
                return redirect("/asignaciones")

            # Aprobar la factura y registrar la hora de aprobación
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

        # Consultar facturas asignadas al usuario actual
        print("Consultando facturas asignadas al usuario actual...")
        cursor.execute("""
            SELECT id, nit, numero_factura, fecha_seleccionada, clasificacion, archivo_path, estado_usuario_asignado, estado_usuario_asignado, hora_aprobacion_asignado
            FROM facturas
            WHERE usuario_asignado_servicios = %s
            ORDER BY fecha_seleccionada ASC
        """, (usuario_actual_id,))
        facturas_asignadas = cursor.fetchall()
        print(f"Facturas asignadas obtenidas: {facturas_asignadas}")

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
    return render_template("asignaciones.html", facturas=facturas_asignadas)


@app.route("/pago_servicios", methods=["GET", "POST"])
def pago_servicios():
    print("Iniciando vista de pago de servicios...")

    conn_pg = postgres_connection()
    cursor = conn_pg.cursor()

    # Obtener el ID del usuario autenticado desde la sesión
    usuario_id = session.get("user_id")
    print(f"Usuario autenticado: {usuario_id}")

    if not usuario_id:
        flash("Tu sesión ha expirado o no has iniciado sesión.", "error")
        print("Error: sesión no válida o usuario no autenticado.")
        return redirect(url_for("login"))

    try:
        # Validar si el usuario pertenece al grupo de jefe_servicios
        print("Validando grupo del usuario...")
        cursor.execute("""
            SELECT g.grupo 
            FROM usuarios u 
            INNER JOIN grupo_aprobacion g ON u.grupo_aprobacion_id = g.id 
            WHERE u.id = %s AND g.grupo = 'jefe_servicios'
        """, (usuario_id,))
        grupo = cursor.fetchone()
        print(f"Resultado de validación de grupo: {grupo}")

        if not grupo:
            flash("No tienes permisos para acceder a esta funcionalidad.", "error")
            print("Error: usuario no pertenece al grupo jefe_servicios.")
            return redirect("/")

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
            SELECT id, nit, numero_factura, fecha_seleccionada, clasificacion, archivo_path, pago_servicios, hora_aprobacion_pago_servicio
            FROM facturas
            WHERE estado_usuario_asignado = 'Aprobado' and pago_servicios = 'Pendiente'
            ORDER BY fecha_seleccionada ASC
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
    return render_template("pago_servicios.html", facturas=facturas_aprobadas)

#-------------Pago MP
@app.route("/pago_mp", methods=["GET", "POST"])
def pago_mp():
    print("Iniciando vista de pago de MP...")

    conn_pg = postgres_connection()
    cursor = conn_pg.cursor()

    # Obtener el ID del usuario autenticado desde la sesión
    usuario_id = session.get("user_id")
    print(f"Usuario autenticado: {usuario_id}")

    if not usuario_id:
        flash("Tu sesión ha expirado o no has iniciado sesión.", "error")
        print("Error: sesión no válida o usuario no autenticado.")
        return redirect(url_for("login"))

    try:
        # Validar si el usuario pertenece al grupo de jefe_servicios
        print("Validando grupo del usuario...")
        cursor.execute("""
            SELECT g.grupo 
            FROM usuarios u 
            INNER JOIN grupo_aprobacion g ON u.grupo_aprobacion_id = g.id 
            WHERE u.id = %s AND g.grupo = 'jefe_mp'
        """, (usuario_id,))
        grupo = cursor.fetchone()
        print(f"Resultado de validación de grupo: {grupo}")

        if not grupo:
            flash("No tienes permisos para acceder a esta funcionalidad.", "error")
            print("Error: usuario no pertenece al grupo jefe_mp.")
            return redirect("/")

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
    return render_template("pago_mp.html", facturas=facturas_aprobadas)


@app.route("/gestion_final", methods=["GET", "POST"])
def gestion_final():
    print("Iniciando vista de gestión final...")

    conn_pg = postgres_connection()
    cursor_pg = conn_pg.cursor()

    # Obtener el ID del usuario autenticado desde la sesión
    usuario_id = session.get("user_id")
    print(f"Usuario autenticado: {usuario_id}")

    if not usuario_id:
        flash("Tu sesión ha expirado o no has iniciado sesión.", "error")
        print("Error: sesión no válida o usuario no autenticado.")
        return redirect(url_for("login"))

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

        # Establecer el estado final a 'Aprobado'
        estado_final = 'Aprobado'

        print(f"Facture ID: {factura_id}, Numero Ofimatica: {numero_ofimatica}, Abonos: {abonos}, Retenciones: {retenciones}, Valor a Pagar: {valor_pagar}")

        try:
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

            # Ejecutar la consulta SQL con los valores recibidos desde el formulario
            cursor_pg.execute(update_query, (
                numero_ofimatica, password_in, bruto, iva_bruto, vl_retfte, v_retica, v_reteniva, subtotal, total, clasificacion_final, abonos, retenciones, valor_pagar, estado_final, usuario_id, factura_id
            ))

            print("Consulta SQL:", "UPDATE facturas SET estado = %s WHERE id = %s")
            print("Parámetros:", (estado_final, factura_id))

            # Confirmar los cambios en la base de datos
            conn_pg.commit()
            flash("Factura actualizada exitosamente.", "success")
            print(f"Factura {factura_id} actualizada correctamente.")

        except Exception as e:
            # En caso de error, mostrar mensaje y hacer rollback
            flash(f"Hubo un error al actualizar la factura: {e}", "error")
            conn_pg.rollback()
            print(f"Error al actualizar la factura: {e}")

    cursor_sql = None  # Inicializar cursor_sql antes de usarlo
    conn_sql = None  # Inicializar conn_sql antes de usarlo

    # Diccionario para almacenar los datos de ofimatica
    ofimatica_data = {}

    if request.method == "POST":
        print("Método POST detectado. Procesando facturas...")

        # Conectamos a SQL Server una vez antes de procesar todas las facturas
        conn_sql = sql_server_connection()
        cursor_sql = conn_sql.cursor()

        # Procesar el número de ofimática de cada factura
        for factura in request.form.getlist("factura_id"):  # Iterar sobre las facturas
            numero_ofimatica = request.form.get(f"numero_ofimatica_{factura}")
            print(f"Número de ofimatica recibido para la factura {factura}: {numero_ofimatica}")

            if numero_ofimatica:
                try:
                    # Primero consultar en PostgreSQL la clasificación de la factura
                    query_clasificacion = """
                        SELECT clasificacion
                        FROM facturas
                        WHERE id = %s
                    """
                    print(f"Consulta en PostgreSQL para obtener clasificación de la factura con ID {factura}.")
                    cursor_pg.execute(query_clasificacion, (factura,))
                    clasificacion = cursor_pg.fetchone()
                    print(f"Clasificación obtenida: {clasificacion}")

                    if clasificacion:
                        clasificacion = clasificacion[0]  # 'Facturas' o 'Servicios'
                        if clasificacion == 'Facturas':
                            # Es una factura MP (FR)
                            sql_server_query = """
                                SELECT 
                                    NRODCTO, 
                                    PASSWORDIN, 
                                    BRUTO, 
                                    IVABRUTO, 
                                    VLRETFTE, 
                                    VRETICA, 
                                    VRETENIVA, 
                                    (bruto + IVABRUTO) AS SUBTOTAL, 
                                    ((bruto + IVABRUTO) - VLRETFTE - VRETICA - VRETENIVA) AS TOTAL
                                FROM TRADE
                                WHERE NRODCTO = ? AND ORIGEN='COM' AND TIPODCTO='FR'
                            """
                            print(f"Consulta SQL que se ejecutará para Factura MP: {sql_server_query}")
                            cursor_sql.execute(sql_server_query, (f"%{numero_ofimatica}%",))
                        elif clasificacion == 'Servicios':
                            # Es una factura de Servicios (FS)
                            sql_server_query = """
                                SELECT 
                                    NRODCTO, 
                                    PASSWORDIN, 
                                    BRUTO, 
                                    IVABRUTO, 
                                    VLRETFTE, 
                                    VRETICA, 
                                    VRETENIVA, 
                                    (bruto + IVABRUTO) AS SUBTOTAL, 
                                    ((bruto + IVABRUTO) - VLRETFTE - VRETICA - VRETENIVA) AS TOTAL
                                FROM TRADE
                                WHERE NRODCTO = ? AND ORIGEN='COM' AND TIPODCTO='FS'
                            """
                            print(f"Consulta SQL que se ejecutará para Factura de Servicios: {sql_server_query}")
                            cursor_sql.execute(sql_server_query, (f"%{numero_ofimatica}%",))
                        else:
                            print(f"Clasificación no válida para la factura {factura}: {clasificacion}")
                            continue  # Si la clasificación no es válida, continuar con la siguiente factura

                        # Ejecutar la consulta en SQL Server
                        ofimatica_result = cursor_sql.fetchone()
                        print(f"Datos obtenidos de SQL Server: {ofimatica_result}")

                        if ofimatica_result:
                            # Si se encontraron datos, asignarlos a un diccionario para la factura específica
                            ofimatica_data[factura] = {
                                "numero_ofimatica": ofimatica_result[0],  # NRODCTO
                                "passwordin": ofimatica_result[1],        # PASSWORDIN
                                "bruto": ofimatica_result[2],             # BRUTO
                                "ivabruto": ofimatica_result[3],          # IVABRUTO
                                "vlretfte": ofimatica_result[4],          # VLRETFTE
                                "vretica": ofimatica_result[5],           # VRETICA
                                "vreteniva": ofimatica_result[6],         # VRETENIVA
                                "subtotal": ofimatica_result[7],          # SUBTOTAL
                                "total": ofimatica_result[8]              # TOTAL
                            }
                        else:
                            flash(f"No se encontró la factura con el número de ofimática {numero_ofimatica}.", "error")
                            print(f"No se encontró la factura con el número de ofimática {numero_ofimatica}.")
                    else:
                        print(f"No se encontró clasificación para la factura {factura}.")
                        continue  # Si no se encuentra clasificación, pasar a la siguiente factura

                except (psycopg2.Error, pyodbc.Error) as e:
                    print(f"Error al consultar la base de datos: {e}")
                    flash("Ocurrió un error al obtener los datos.", "error")

    try:
        # Validar si el usuario pertenece al grupo de contabilidad
        print("Validando grupo del usuario...")
        query_validar_grupo = """
            SELECT g.grupo 
            FROM usuarios u
            INNER JOIN grupo_aprobacion g ON u.grupo_aprobacion_id = g.id 
            WHERE u.id = %s AND g.grupo = 'Contabilidad'
        """
        print(f"Consulta SQL que se ejecutará: {query_validar_grupo} con el usuario_id {usuario_id}")
        
        cursor_pg.execute(query_validar_grupo, (usuario_id,))
        grupo = cursor_pg.fetchone()
        print(f"Resultado de validación de grupo: {grupo}")

        if not grupo:
            flash("No tienes permisos para acceder a esta funcionalidad.", "error")
            print("Error: usuario no pertenece al grupo Contabilidad.")
            return redirect("/")

        # Obtener las facturas aprobadas   120225 pago_mp = 'Aprobado' 
        print("Consultando facturas aprobadas...")
        query_facturas_aprobadas = """
            SELECT id, nit, numero_factura, fecha_seleccionada, clasificacion, archivo_path, 
                   pago_servicios, pago_mp, hora_aprobacion_pago_servicio, hora_aprobacion_pago_mp
            FROM facturas
            WHERE pago_servicios = 'Aprobado' OR estado_compras = 'Aprobado' and estado_final = 'Pendiente' order by id
        """
        print(f"Consulta SQL que se ejecutará: {query_facturas_aprobadas}")
        
        cursor_pg.execute(query_facturas_aprobadas)
        facturas = cursor_pg.fetchall()
        print(f"Facturas encontradas: {facturas}")

        # Crear un diccionario de datos para las facturas que se mostrarán en la plantilla
        facturas_data = []
        for factura in facturas:
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
                "ofimatica_data": ofimatica_data.get(factura[0], {})  # Asignar los datos de ofimática a cada factura
            })

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

    print("Renderizando la plantilla gestion_final.html...")
    return render_template("gestion_final.html", facturas_data=facturas_data, ofimatica_data=ofimatica_data)


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
        WHERE NRODCTO LIKE ? AND ORIGEN='COM'
    """
    print(f"Consulta SQL que se ejecutará: {query}")
    
    cursor.execute(query, ('%' + numero_ofimatica + '%',))  # Añadimos el '%' para el LIKE
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


@app.route("/tesoreria", methods=["GET", "POST"])
@login_required
def tesoreria():
    print("Iniciando vista para vincular documentos a un archivo PDF...")

    # Obtener el ID del usuario autenticado desde la sesión
    usuario_id = session.get("user_id")
    if not usuario_id:
        flash("Tu sesión ha expirado o no has iniciado sesión.", "error")
        return redirect(url_for("login"))

    # Validar si el usuario pertenece al grupo de Contabilidad o Jefe_MP
    try:
        conn_pg = postgres_connection()
        cursor = conn_pg.cursor()

        print("Validando grupo del usuario...")
        query_validar_grupo = """
            SELECT g.grupo 
            FROM usuarios u
            INNER JOIN grupo_aprobacion g ON u.grupo_aprobacion_id = g.id 
            WHERE u.id = %s AND (g.grupo = 'Contabilidad' OR g.grupo = 'jefe_servicios' or g.grupo = 'jefe_mp' or g.grupo = 'tesoreria')
        """
        cursor.execute(query_validar_grupo, (usuario_id,))
        grupo_usuario = cursor.fetchone()

        print("Grupo obtenido:", grupo_usuario)

        if not grupo_usuario:
            flash("No tienes permisos para acceder a Tesorería.", "error")
            print("Error: usuario no pertenece al grupo de Contabilidad o Jefe_MP.")
            return redirect("/")

    except Exception as e:
        flash(f"Error al validar el grupo del usuario: {e}", "error")
        print(f"Error al validar el grupo del usuario: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn_pg:
            conn_pg.close()

    if request.method == "POST":
        archivo_pdf = request.files.get("archivo_pdf")

        # Validar si se ha subido un archivo PDF
        if not archivo_pdf:
            flash("Por favor, sube un archivo PDF.", "error")
            return render_template("tesoreria.html")

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
                LTRIM(RTRIM(dcto)) AS dcto,
                LTRIM(RTRIM(fecha)) AS fecha,
                LTRIM(RTRIM(cheque)) AS cheque,
                LTRIM(RTRIM(nit)) AS nit,
                LTRIM(RTRIM(PASSWORDIN)) AS PASSWORDIN,
                LTRIM(RTRIM(valor)) AS valor,
                LTRIM(RTRIM(tipodcto)) AS tipodcto,
                LTRIM(RTRIM(factura)) AS factura
            FROM ABOCXP
            WHERE fecha >= DATEADD(DAY, -30, GETDATE()) AND tipodcto='CE' 
            ORDER BY factura
            """
            print(f"Ejecutando consulta SQL Server: {query_sql_server}")
            cursor_sql_server.execute(query_sql_server)
            documentos = cursor_sql_server.fetchall()

            # Si no se encontraron documentos, mostrar mensaje
            if not documentos:
                flash("No se encontraron documentos en los últimos 30 días.", "error")
                return render_template("tesoreria.html")

            print(f"Documentos encontrados: {len(documentos)}")

            # Procesamos los documentos para pasarlos a la plantilla
            documentos_encontrados = [{
                "dcto": dcto,
                "fecha": fecha,
                "cheque": cheque,
                "nit": nit,
                "passwordin": passwordin,
                "valor": valor,
                "tipodcto": tipodcto,
                "factura": factura
            } for dcto, fecha, cheque, nit, passwordin, valor, tipodcto, factura in documentos]

            # Mostrar los documentos encontrados antes de enviarlos
            print(f"Documentos procesados para plantilla: {len(documentos_encontrados)}")

            # Asegurarse de que la respuesta sea un JSON
            return jsonify({
                "documentos": documentos_encontrados,
                "archivo_path": archivo_path,
                "num_documentos": len(documentos_encontrados)
            })

        except Exception as e:
            flash(f"Ocurrió un error al buscar los documentos: {e}", "error")
            print(f"Error en la consulta SQL Server: {e}")

        finally:
            if cursor_sql_server:
                cursor_sql_server.close()
            if conn_sql_server:
                conn_sql_server.close()

    return render_template("tesoreria.html")


@app.route("/guardar_documentos", methods=["POST"])
def guardar_documentos():
    try:
        # Obtener la ruta del archivo y los documentos seleccionados
        archivo_path = request.form.get("archivo_path")
        print(f'ruta del archivo jesus: {archivo_path}')
        selected_documents_json = request.form.get("selectedDocuments")  # Obtener los documentos seleccionados (en formato JSON)

        # Deserializar el JSON
        if selected_documents_json:
            selected_documents = json.loads(selected_documents_json)

        print(f"Ruta del archivo: {archivo_path}")
        print(f"Documentos seleccionados: {selected_documents}")

        # Conexión a PostgreSQL
        conn_pg = postgres_connection()
        cursor_pg = conn_pg.cursor()

        # Iterar sobre los documentos seleccionados
        for doc in selected_documents:
            dcto = doc['dcto']
            factura = doc['factura']
            print(f'Dcto: {dcto}, Factura: {factura}')

            # Realizar el UPDATE en la tabla facturas (con los valores correctos de 'dcto' y 'factura')
            update_query = """
                UPDATE facturas
                SET dctos = %s, archivo_pdf = %s
                WHERE numero_ofimatica = %s
            """
            cursor_pg.execute(update_query, (dcto, archivo_path, str(factura)))

        # Confirmar los cambios
        conn_pg.commit()

        flash("Documentos vinculados correctamente a las facturas.", "success")
        return redirect(url_for("tesoreria"))

    except Exception as e:
        flash(f"Ocurrió un error al guardar los documentos: {e}", "error")
        print(f"Error: {e}")

    finally:
        if cursor_pg:
            cursor_pg.close()
        if conn_pg:
            conn_pg.close()

    return render_template("tesoreria.html")


@app.route("/facturas_resumen", methods=["GET"])
@login_required
def facturas_servicios():
    conn_pg = postgres_connection()
    cursor = conn_pg.cursor()

    try:
        # Ejecutar la consulta para obtener las facturas con los campos especificados
        cursor.execute("""
            SELECT 
                f.nit, 
                f.nombre, 
                f.numero_factura,
                f.fecha_seleccionada, 
                f.fecha_registro, 
                f.clasificacion, 
                f.archivo_path,
                f.hora_aprobacion as aprobacion_bodega, 
                f.estado as estado_aprobacion_bodega, 
                COALESCE(u.usuario, '') as usuario_aprueba_bodega,  -- Si no hay nombre de usuario, muestra vacío
                f.estado_compras,
                f.hora_aprobacion_compras,
                COALESCE(u1.usuario, '') as usuario_aprueba_compras, 
                f.remision,
                f.archivo_remision as orden_compra,
                f.pago_mp as estado_aprobacion_jefe_mp, 
                f.estado_final as estado_final_contabilizado,
                f.archivo_pdf as archivo_pago_banco, 
                f.dctos as comprobantes_egresos, 
                COALESCE(u3.usuario, '') as usuario_asignado_servicios, 
                COALESCE(u2.usuario, '') as usuario_asigno_contabilidad,
                f.estado_usuario_asignado as estado_aprobacion_user_servi,
                f.hora_aprobacion_asignado as hora_aprobacion_user_servicio, 
                f.pago_servicios as aprobacion_jefe_servicios,
                f.hora_aprobacion_pago_servicio as hora_aprobacion_jefe_servicio,
                f.valor_pagar
            FROM facturas f
            LEFT JOIN usuarios u ON f.aprobado_bodega = u.id  
            LEFT JOIN usuarios u1 ON f.aprobado_compras = u1.id  
            LEFT JOIN usuarios u2 ON f.aprobado_servicios = u2.id 
            LEFT JOIN usuarios u3 ON f.usuario_asignado_servicios = u3.id 
            --WHERE clasificacion = 'Servicios' AND estado = 'Pendiente'
            --ORDER BY fecha_seleccionada ASC
        """)
        facturas = cursor.fetchall()

    except Exception as e:
        flash(f"Error al consultar las facturas: {str(e)}", "error")
        facturas = []

    finally:
        if cursor:
            cursor.close()
        if conn_pg:
            conn_pg.close()

    return render_template("facturas_servicios.html", facturas=facturas)


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
def gestion_inicial():
    # Verificar si el usuario está logueado y pertenece al grupo "Compras"
    usuario_id = session.get("user_id")
    if not usuario_id:
        flash("Tu sesión ha expirado o no has iniciado sesión.", "error")
        return redirect(url_for("login"))

    try:
        # Conectar a la base de datos PostgreSQL para validar el grupo
        conn_pg = postgres_connection()
        cursor_pg = conn_pg.cursor()

        cursor_pg.execute("""
            SELECT g.grupo
            FROM usuarios u
            INNER JOIN grupo_aprobacion g ON u.grupo_aprobacion_id = g.id
            WHERE u.id = %s AND g.grupo = 'Compras'
        """, (usuario_id,))
        grupo = cursor_pg.fetchone()

        if not grupo:
            flash("No tienes permisos para acceder a esta funcionalidad. Debes ser parte del grupo 'Compras'.", "error")
            return redirect("/")

    except Exception as e:
        flash(f"Error al verificar el grupo del usuario: {str(e)}", "error")
        return redirect(request.url)

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

    return render_template("gestion_inicial.html")






        
@app.route("/logout")
def logout():
    session.clear()  
    flash("Sesión cerrada exitosamente", "success")
    return redirect(url_for("login"))



if __name__ == "__main__":
    app.run(host='10.1.200.11', port=2837, debug=True)
