# scripts/set_admin_password.py
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
DB_SSL_CA = os.getenv("DB_SSL_CA")  # ruta a tu .pem

def main():
    # === 1) Cambia aquí la contraseña que quieras para admin ===
    new_plain_password = "Admin123*"  # <-- cámbiala por la que quieras

    # Genera hash con Werkzeug (pbkdf2:sha256)
    new_hash = generate_password_hash(new_plain_password, method="pbkdf2:sha256", salt_length=12)
    print("Hash generado:", new_hash)

    # Conecta a TiDB
    conn = pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        ssl={"ca": DB_SSL_CA}
    )
    try:
        with conn.cursor() as cur:
            # Asegura que exista el usuario admin; si no, lo crea.
            cur.execute("""
                INSERT INTO usuarios (username, password_hash, role, activo)
                VALUES ('admin', %s, 'admin', 1)
                ON DUPLICATE KEY UPDATE password_hash = VALUES(password_hash), role='admin', activo=1
            """, (new_hash,))
        conn.commit()
        print("✅ Contraseña de 'admin' establecida/actualizada.")
        print("➡️  Usuario: admin")
        print("➡️  Contraseña:", new_plain_password)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
