import pyodbc
import psycopg2
from psycopg2 import OperationalError

# Conexión a SQL Server
def sql_server_connection():
    conn = pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=10.1.200.20;"
        "DATABASE=SAMARACOSMETICS;"
        "UID=SA;"
        "PWD=ofima.sql10"
    )
    return conn

# Conexión a PostgreSQL
def postgres_connection():
    try:
        conn = psycopg2.connect(
            dbname="contabilidad",
            user="postgres",
            password="$amara%21.",
            host="127.0.0.1",
            port="5432"
        )
        print("Conexión exitosa a PostgreSQL")
        return conn
    except OperationalError as e:
        print("Error al conectar con PostgreSQL:")
        print(e)
        return None
