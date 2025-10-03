import os
import pymysql
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash
load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", "4000"))
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME", "sistema_registros")
DB_SSL_CA = os.getenv("DB_SSL_CA")

def main():
    new_plain_password = "Admin123*"
    new_hash = generate_password_hash(new_plain_password, method="pbkdf2:sha256", salt_length=12)
    conn = pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD,
        database=DB_NAME, ssl={"ca": DB_SSL_CA} if DB_SSL_CA else None
    )
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO usuarios (username, password_hash, role, activo)
                VALUES ('admin', %s, 'admin', 1)
                ON DUPLICATE KEY UPDATE password_hash=VALUES(password_hash), role='admin', activo=1
            """, (new_hash,))
        conn.commit()
        print("✅ Admin listo. Usuario: admin / Pass:", new_plain_password)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
