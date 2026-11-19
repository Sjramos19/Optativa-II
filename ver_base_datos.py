"""Script interactivo de consola para inspeccionar techstore.db y su estructura durante la sustentación."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

# Asegurar codificación UTF-8 en consola de Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "data" / "techstore.db"
SCHEMA_FILE = APP_DIR / "schema.sql"


def linea(char: str = "=", n: int = 75) -> None:
    print(char * n)


def mostrar_esquema_ddl(conn: sqlite3.Connection) -> None:
    linea("=")
    print(" 1. COMO ESTA CREADA LA BASE DE DATOS (ESTRUCTURA SQL / DDL)")
    linea("=")
    cursor = conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type IN ('table', 'index') AND name NOT LIKE 'sqlite_%' ORDER BY type DESC, name"
    )
    for nombre, sql in cursor.fetchall():
        linea("-")
        print(f"TABLA / INDICE: {nombre.upper()}")
        linea("-")
        print(sql.strip() if sql else "N/A")
        print()


def mostrar_resumen_tablas(conn: sqlite3.Connection) -> None:
    linea("=")
    print(" 2. TABLAS Y CONTEO ACTUAL DE REGISTROS")
    linea("=")
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    for row in cursor.fetchall():
        tabla = row[0]
        total = conn.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
        print(f"  * Tabla '{tabla}': {total} registros guardados")
    print()


def consultar(conn: sqlite3.Connection, titulo: str, query: str, limit: int = 10) -> None:
    linea("-")
    print(f" {titulo} (primeros {limit} registros):")
    linea("-")
    cursor = conn.execute(query)
    columnas = [d[0] for d in cursor.description]
    print(" | ".join(f"{c:<14}" for c in columnas))
    print("-" * (len(columnas) * 17))
    rows = cursor.fetchmany(limit)
    for r in rows:
        print(" | ".join(f"{str(v):<14}" for v in r))
    print()


def main() -> None:
    if not DB_PATH.exists():
        print(f"No se encontro la base en: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    linea("=")
    print("           TECHSTORE - INSPECTOR COMPLETO DE BASE DE DATOS SQLITE")
    print(f" Archivo BD:     {DB_PATH}")
    print(f" Archivo Esquema: {SCHEMA_FILE}")
    linea("=")
    print()

    # 1. Cómo está creada (DDL)
    mostrar_esquema_ddl(conn)

    # 2. Tablas y conteo
    mostrar_resumen_tablas(conn)

    # 3. Datos de ejemplo
    consultar(
        conn,
        "PRODUCTOS Y STOCK ACTUAL",
        "SELECT producto_id, nombre, precio, stock FROM productos",
        limit=10,
    )

    consultar(
        conn,
        "RECHAZOS DE CARGA (AUDITORIA DE RECHAZOS Y PED-1025)",
        "SELECT rechazo_id, fila_origen, pedido_id, motivo FROM rechazos_carga",
        limit=5,
    )

    consultar(
        conn,
        "ULTIMOS PEDIDOS REGISTRADOS",
        "SELECT pedido_id, cliente_id, producto_id, cantidad, valor_total, estado, tiempo_entrega_dias FROM pedidos ORDER BY fecha_pedido DESC",
        limit=5,
    )

    conn.close()
    linea("=")
    print(" Demostracion de base de datos lista. Presione cualquier tecla para salir.")
    linea("=")


if __name__ == "__main__":
    main()
