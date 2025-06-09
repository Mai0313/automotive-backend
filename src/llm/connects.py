import os
import psycopg2


PG_HOST = os.getenv("POSTGRES_HOST")
PG_PORT = os.getenv("POSTGRES_PORT")
PG_DBNAME = os.getenv("POSTGRES_DBNAME")
PG_USER = os.getenv("POSTGRES_USER")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD")


def pg_connect(conn_string=f"host={PG_HOST} user={PG_USER} dbname={PG_DBNAME} password={PG_PASSWORD} port={PG_PORT}"):
    conn = psycopg2.connect(conn_string)
    return conn.cursor()


if __name__ == "__main__":
    cur = pg_connect()
    cur.execute("UPDATE ac_settings SET temperature = 25")
    cur.connection.commit()
    cur.close()
