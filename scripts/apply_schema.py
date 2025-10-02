# scripts/apply_schema.py
import os
from dotenv import load_dotenv
import pymysql

load_dotenv()

conn = pymysql.connect(
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT", "4000")),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME"),
    ssl={"ca": os.getenv("DB_SSL_CA")},
    autocommit=False,
)

def split_sql(sql_text: str):
    # Split simple por ';' cuidando líneas en blanco y comentarios básicos.
    # Esto funciona bien para DDL sencillo (CREATE TABLE, INDEX, etc.).
    stmts, buff = [], []
    for line in sql_text.splitlines():
        l = line.strip()
        if not l or l.startswith("--"):
            continue
        buff.append(line)
        if l.endswith(";"):
            stmts.append("\n".join(buff).rstrip(" ;\n\r\t"))
            buff = []
    if buff:
        stmts.append("\n".join(buff).rstrip(" ;\n\r\t"))
    return [s for s in stmts if s]

with conn.cursor() as cur:
    with open("sql/init_schema.sql", "r", encoding="utf-8") as f:
        sql = f.read()
    for stmt in split_sql(sql):
        cur.execute(stmt)
conn.commit()
conn.close()
print("Schema aplicado OK (sentencia por sentencia).")
