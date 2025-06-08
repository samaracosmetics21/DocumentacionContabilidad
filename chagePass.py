import psycopg2
from werkzeug.security import generate_password_hash

def actualizar_password_usuario(usuario_id, nueva_contraseña):
    try:
        # Conectar a la base de datos PostgreSQL
        conn_pg = psycopg2.connect(
             dbname="contabilidad",
            user="postgres",
            password="$amara%21.",
            host="127.0.0.1",
            port="5432"
        )
        cursor = conn_pg.cursor()

        # Generar el nuevo password_hash
        nuevo_password_hash = generate_password_hash(nueva_contraseña)
        print(f"Nuevo password_hash generado: {nuevo_password_hash}")

        # Actualizar el password_hash en la base de datos para el usuario específico
        update_query = """
        UPDATE usuarios
        SET password_hash = %s
        WHERE id = %s
        """
        cursor.execute(update_query, (nuevo_password_hash, usuario_id))
        conn_pg.commit()

        print(f"Contraseña actualizada exitosamente para el usuario con ID: {usuario_id}")

    except Exception as e:
        print(f"Error al actualizar la contraseña: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn_pg:
            conn_pg.close()


usuario_id = 19  
nueva_contraseña = "Nueva contraseña"  
actualizar_password_usuario(usuario_id, nueva_contraseña)
