import os, pymysql
from dotenv import load_dotenv

load_dotenv()  # Lee variables de .env

conn = pymysql.connect(
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT")),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME"),
    ssl={'ca': os.getenv("DB_SSL_CA")}
)

with conn.cursor() as cur:
    cur.execute("SELECT VERSION()")
    print("Connected! TiDB version:", cur.fetchone()[0])

conn.close()
