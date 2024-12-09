from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from db_config import sql_server_connection, postgres_connection
import os
from datetime import datetime
from werkzeug.security import generate_password_hash
from flask import session  
from werkzeug.security import check_password_hash
from functools import wraps

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
                return redirect("/compras")

            if not factura_id or not factura_id.isdigit():
                flash("El ID de la factura no es válido.", "error")
                return redirect("/compras")

            # Validar si el usuario pertenece al grupo de aprobadores de compras
            cursor.execute("""
                SELECT g.grupo 
                FROM usuarios u 
                INNER JOIN grupo_aprobacion g ON u.grupo_aprobacion_id = g.id 
                WHERE u.id = %s AND g.grupo = 'Compras'
            """, (usuario_id,))
            grupo = cursor.fetchone()

            if not grupo:
                flash("No tienes permisos para aprobar facturas en Compras", "error")
                return redirect("/compras")

            # Aprobar la factura, registrar la hora de aprobación y el usuario que aprobó
            try:
                hora_aprobacion_compras = datetime.now()
                cursor.execute("""
                    UPDATE facturas
                    SET estado_compras = 'Aprobado', hora_aprobacion_compras = %s, aprobado_compras = %s
                    WHERE id = %s
                """, (hora_aprobacion_compras, usuario_id, factura_id))
                conn_pg.commit()
                flash("Factura aprobada exitosamente en Compras", "success")
            except Exception as e:
                conn_pg.rollback()
                flash(f"Error aprobando factura en Compras: {str(e)}", "error")

        # Consultar facturas pendientes en compras
        cursor.execute("""
            SELECT id, nit, numero_factura, fecha_seleccionada, clasificacion, archivo_path, estado_compras 
            FROM facturas
            WHERE clasificacion = 'Facturas' AND estado = 'Aprobado'
            ORDER BY fecha_seleccionada ASC
        """)
        facturas = cursor.fetchall()

    except Exception as e:
        flash(f"Error en la gestión de compras: {str(e)}", "error")
        facturas = []

    finally:
        if cursor:
            cursor.close()
        if conn_pg:
            conn_pg.close()

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


@app.route("/logout")
def logout():
    session.clear()  
    flash("Sesión cerrada exitosamente", "success")
    return redirect(url_for("login"))



if __name__ == "__main__":
    app.run(host='0.0.0.0', port=2837, debug=True)
