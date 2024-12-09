import pyodbc

def test_sql_server_connection():
    try:
        # Configuración de la conexión a SQL Server
        connection = pyodbc.connect(
            'DRIVER={SQL Server};'
            'SERVER=10.1.200.20;'
            'DATABASE=SAMARACOSMETICS;'
            'UID=SA;'
            'PWD=ofima.sql10;'
        )
        print("Conexión exitosa a SQL Server.")

        # Realiza una consulta básica para verificar la conexión
        cursor = connection.cursor()
        cursor.execute("SELECT TOP 1 nit, nombre FROM MTPROCLI")
        row = cursor.fetchone()
        
        if row:
            print("Consulta exitosa. Primer registro encontrado:")
            print(f"NIT: {row[0]}, Nombre: {row[1]}")
        else:
            print("Consulta ejecutada, pero no se encontraron resultados.")

        # Cierra la conexión
        connection.close()

    except pyodbc.Error as e:
        print("Error al conectar con SQL Server:", e)

# Ejecuta la función
if __name__ == "__main__":
    test_sql_server_connection()
