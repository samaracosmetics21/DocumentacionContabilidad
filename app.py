from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from db_config import sql_server_connection, postgres_connection
import os
from datetime import datetime
from werkzeug.security import generate_password_hash
from flask import session  
from werkzeug.security import check_password_hash
from functools import wraps
from flask_login import current_user


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
        fecha_directorio = fecha_seleccionada.replace("-", "")  # Fecha en formato YYYYMMDD
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
        try:
            conn_pg = postgres_connection()
            cursor = conn_pg.cursor()
            cursor.execute("INSERT INTO grupo_aprobacion (grupo, descripcion) VALUES (%s, %s)", (grupo, descripcion))
            conn_pg.commit()
            flash("Grupo creado exitosamente", "success")
        except Exception as e:
            flash(f"Error creando grupo: {str(e)}", "error")
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

            print("Datos recibidos del formulario:")
            print(f"Nombre: {nombre}, Apellido: {apellido}, Usuario: {usuario}, Correo: {correo}, Grupo ID: {grupo_id}")

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
    conn_pg = postgres_connection()
    cursor = conn_pg.cursor()

    try:
        if request.method == "POST":
            # Obtener datos del formulario
            usuario_id = request.form.get("usuario_id")
            factura_id = request.form.get("factura_id")

            # Validar usuario_id y factura_id
            if not usuario_id or not usuario_id.isdigit():
                flash("El ID del usuario no es válido.", "error")
                return redirect("/bodega")

            if not factura_id or not factura_id.isdigit():
                flash("El ID de la factura no es válido.", "error")
                return redirect("/bodega")

            # Validar si el usuario pertenece al grupo de aprobadores de bodega
            cursor.execute("""
                SELECT g.grupo 
                FROM usuarios u 
                INNER JOIN grupo_aprobacion g ON u.grupo_aprobacion_id = g.id 
                WHERE u.id = %s AND g.grupo = 'Bodega'
            """, (usuario_id,))
            grupo = cursor.fetchone()

            if not grupo:
                flash("No tienes permisos para aprobar facturas en Bodega", "error")
                return redirect("/bodega")

            # Aprobar la factura y actualizar la hora de aprobación
            try:
                hora_aprobacion = datetime.now()
                cursor.execute("""
                    UPDATE facturas
                    SET estado = 'Aprobado', hora_aprobacion = %s, aprobado_bodega = %s
                    WHERE id = %s
                """, (hora_aprobacion, usuario_id, factura_id))
                conn_pg.commit()
                flash("Factura aprobada exitosamente", "success")
            except Exception as e:
                conn_pg.rollback()
                flash(f"Error aprobando factura: {str(e)}", "error")

        # Consultar facturas pendientes
        cursor.execute("""
            SELECT id, nit, numero_factura, fecha_seleccionada, clasificacion, archivo_path, estado 
            FROM facturas
            WHERE clasificacion = 'Facturas' AND estado = 'Pendiente'
            ORDER BY fecha_seleccionada ASC
        """)
        facturas = cursor.fetchall()

    except Exception as e:
        flash(f"Error en la gestión de bodega: {str(e)}", "error")
        facturas = []

    finally:
        if cursor:
            cursor.close()
        if conn_pg:
            conn_pg.close()

    return render_template("bodega.html", facturas=facturas)

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
            archivo_remision = request.files.get("archivo_remision")

            # Log de datos recibidos
            print(f"Datos recibidos: usuario_id={usuario_id}, factura_id={factura_id}, remision={remision}, archivo_remision={archivo_remision.filename if archivo_remision else 'No file'}")

            # Validar campos
            if not usuario_id or not usuario_id.isdigit():
                print("Error: El ID del usuario no es válido.")
                flash("El ID del usuario no es válido.", "error")
                return redirect("/compras")

            if not factura_id or not factura_id.isdigit():
                print("Error: El ID de la factura no es válido.")
                flash("El ID de la factura no es válido.", "error")
                return redirect("/compras")

            if not remision or not remision.isalnum():
                print("Error: La remisión debe ser un valor alfanumérico.")
                flash("La remisión debe ser un valor alfanumérico.", "error")
                return redirect("/compras")

            if not archivo_remision or not archivo_remision.filename:
                print("Error: No se ha subido un archivo de remisión.")
                flash("Debes subir un archivo de remisión.", "error")
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

            # Crear directorio para guardar el archivo
            ruta_directorio = os.path.join(
                app.config["UPLOAD_FOLDER"], clasificacion_texto, nit, fecha_directorio
            )
            os.makedirs(ruta_directorio, exist_ok=True)
            print(f"Directorio creado o existente: {ruta_directorio}")

            # Guardar el archivo
            archivo_path = os.path.join(ruta_directorio, archivo_remision.filename)
            archivo_remision.save(archivo_path)
            print(f"Archivo guardado en: {archivo_path}")

            # Calcular ruta relativa para almacenamiento en la base de datos
            ruta_relativa = os.path.relpath(archivo_path, app.config["UPLOAD_FOLDER"])
            ruta_relativa = ruta_relativa.replace("static/", "")  # Eliminar prefijo 'static/'
            print(f"Ruta relativa del archivo: {ruta_relativa}")

            # Aprobar la factura y registrar información
            try:
                hora_aprobacion_compras = datetime.now()
                print("Aprobando factura en la base de datos...")
                cursor.execute("""
                    UPDATE facturas
                    SET estado_compras = 'Aprobado', 
                        hora_aprobacion_compras = %s, 
                        aprobado_compras = %s,
                        remision = %s,
                        archivo_remision = %s
                    WHERE id = %s
                """, (hora_aprobacion_compras, usuario_id, remision, ruta_relativa, factura_id))
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
            SELECT id, nit, numero_factura, fecha_seleccionada, clasificacion, archivo_path, estado_compras, hora_aprobacion_compras
            FROM facturas
            WHERE clasificacion = 'Facturas' AND estado_compras = 'Pendiente'
            ORDER BY fecha_seleccionada ASC
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
            SELECT id, nit, numero_factura, fecha_seleccionada, clasificacion, archivo_path, estado 
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
            WHERE estado_usuario_asignado = 'Aprobado'
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
            SELECT id, nit, numero_factura, fecha_seleccionada, clasificacion, archivo_path, pago_mp, hora_aprobacion_pago_mp
            FROM facturas
            WHERE estado_compras = 'Aprobado'
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
    cursor = conn_pg.cursor()

    # Obtener el ID del usuario autenticado desde la sesión
    usuario_id = session.get("user_id")
    print(f"Usuario autenticado: {usuario_id}")

    if not usuario_id:
        flash("Tu sesión ha expirado o no has iniciado sesión.", "error")
        print("Error: sesión no válida o usuario no autenticado.")
        return redirect(url_for("login"))

    try:
        # Validar si el usuario pertenece al grupo de contabilidad
        print("Validando grupo del usuario...")
        cursor.execute("""
            SELECT g.grupo 
            FROM usuarios u
            INNER JOIN grupo_aprobacion g ON u.grupo_aprobacion_id = g.id 
            WHERE u.id = %s AND g.grupo = 'Contabilidad'
        """, (usuario_id,))
        grupo = cursor.fetchone()
        print(f"Resultado de validación de grupo: {grupo}")

        if not grupo:
            flash("No tienes permisos para acceder a esta funcionalidad.", "error")
            print("Error: usuario no pertenece al grupo Contabilidad.")
            return redirect("/")

        if request.method == "POST":
            print("Método POST recibido.")

            # Obtener los valores del formulario
            factura_id = request.form.get("factura_id")
            numero_ofimatica = request.form.get("numero_ofimatica")  # Obligatorio
            retenciones = request.form.get("retenciones")  # Opcional
            valor_pagar = request.form.get("valor_pagar")  # Opcional
            abonos = request.form.get("abonos")  # Opcional
            saldos = request.form.get("saldos")  # Opcional
            clasificacion_final = request.form.get("clasificacion_final")  # Obligatorio

            print(f"Factura ID: {factura_id}, Clasificación: {clasificacion_final}, Ofimática: {numero_ofimatica}")

            if not numero_ofimatica:
                flash("El número de ofimática es obligatorio.", "error")
                return redirect("/gestion_final")

            # Convertir campos opcionales a None si están vacíos
            retenciones = float(retenciones) if retenciones else None
            valor_pagar = float(valor_pagar) if valor_pagar else None
            abonos = float(abonos) if abonos else None
            saldos = float(saldos) if saldos else None

            try:
                # Actualizar la factura con la información del formulario
                cursor.execute("""
                    UPDATE facturas
                    SET numero_ofimatica = %s,
                        retenciones = %s,
                        valor_pagar = %s,
                        abonos = %s,
                        saldos = %s,
                        clasificacion_final = %s,
                        estado_final = 'Aprobado'  -- Cambiar a Aprobado cuando se complete
                    WHERE id = %s
                """, (numero_ofimatica, retenciones, valor_pagar, abonos, saldos, clasificacion_final, factura_id))
                conn_pg.commit()

                if cursor.rowcount == 0:
                    flash("No se pudo actualizar la factura.", "error")
                else:
                    flash("Factura actualizada y aprobada exitosamente.", "success")
            except Exception as e:
                conn_pg.rollback()
                print(f"Error al actualizar la factura: {e}")
                flash(f"Error al actualizar la factura: {str(e)}", "error")

        # Consultar facturas con estado 'Aprobado' para pago de servicios o MP
        print("Consultando facturas para gestión final...")
        cursor.execute("""
            SELECT id, nit, numero_factura, fecha_seleccionada, clasificacion, archivo_path, 
                   pago_servicios, pago_mp, hora_aprobacion_pago_servicio, hora_aprobacion_pago_mp
            FROM facturas
            WHERE pago_servicios = 'Aprobado' OR pago_mp = 'Aprobado'
        """)
        facturas_gestion_final = cursor.fetchall()
        print(f"Facturas obtenidas: {facturas_gestion_final}")

    except Exception as e:
        print(f"Error general en /gestion_final: {e}")
        flash(f"Error al gestionar la vista final: {str(e)}", "error")
        facturas_gestion_final = []

    finally:
        if cursor:
            cursor.close()
        if conn_pg:
            conn_pg.close()

    print("Renderizando la plantilla gestion_final.html...")
    return render_template("gestion_final.html", facturas=facturas_gestion_final)







@app.route("/logout")
def logout():
    session.clear()  
    flash("Sesión cerrada exitosamente", "success")
    return redirect(url_for("login"))



if __name__ == "__main__":
    app.run(host='0.0.0.0', port=2837, debug=True)
