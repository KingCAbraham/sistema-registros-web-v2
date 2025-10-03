# services/base_general_loader.py
import pandas as pd
from db import SessionLocal
from models import BaseGeneral

def load_base_general_xlsx(file_like) -> dict:
    """
    Lee un .xlsx desde un BytesIO o ruta y upsert a base_general.
    Devuelve: {"inserted": X, "updated": Y, "skipped": Z}
    """
    df = pd.read_excel(file_like, dtype=str).fillna("")
    cols = {"CLIENTE_UNICO", "NOMBRE_CTE", "GERENCIA", "PRODUCTO", "FIDIAPAGO", "GESTION_DESC"}
    missing = cols - set(df.columns.str.upper())
    if missing:
        raise ValueError(f"Faltan columnas: {', '.join(sorted(missing))}")

    inserted = updated = skipped = 0
    with SessionLocal() as db:
        for _, row in df.iterrows():
            cu = str(row["CLIENTE_UNICO"]).strip()
            if not cu:
                skipped += 1
                continue
            item = db.query(BaseGeneral).filter(BaseGeneral.cliente_unico == cu).first()
            if not item:
                item = BaseGeneral(
                    cliente_unico=cu,
                    nombre_cte=row["NOMBRE_CTE"],
                    gerencia=row["GERENCIA"],
                    producto=row["PRODUCTO"],
                    fidiapago=row["FIDIAPAGO"],
                    gestion_desc=row["GESTION_DESC"],
                )
                db.add(item)
                inserted += 1
            else:
                # upsert “suave”
                item.nombre_cte = row["NOMBRE_CTE"]
                item.gerencia = row["GERENCIA"]
                item.producto = row["PRODUCTO"]
                item.fidiapago = row["FIDIAPAGO"]
                item.gestion_desc = row["GESTION_DESC"]
                updated += 1
        db.commit()

    return {"inserted": inserted, "updated": updated, "skipped": skipped}
