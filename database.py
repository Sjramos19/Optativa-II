"""Conexión, esquema, migraciones y seed de TechStore ERP."""

from __future__ import annotations

import hashlib
import os
import sqlite3
from contextlib import closing
from pathlib import Path


APP_DIR         = Path(__file__).resolve().parent
DEFAULT_DB_PATH = Path(os.environ.get("TECHSTORE_DB", APP_DIR / "data" / "techstore.db"))
SCHEMA_PATH     = APP_DIR / "schema.sql"


# ---------------------------------------------------------------------------
# Conexión
# ---------------------------------------------------------------------------

def conectar(db_path: str | Path | None = None, *, autocommit: bool = False) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None if autocommit else "")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


# ---------------------------------------------------------------------------
# Esquema + Migraciones
# ---------------------------------------------------------------------------

def crear_esquema(db_path: str | Path | None = None) -> Path:
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with closing(conectar(path)) as conn:
        conn.executescript(schema)
        conn.commit()
    _aplicar_migraciones(path)
    return path


_MIGRACIONES_SQL = [
    # productos — columnas nuevas
    "ALTER TABLE productos ADD COLUMN descripcion  TEXT",
    "ALTER TABLE productos ADD COLUMN activo       INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE productos ADD COLUMN precio_compra REAL   DEFAULT 0",
    "ALTER TABLE productos ADD COLUMN stock_minimo INTEGER DEFAULT 5",
    "ALTER TABLE productos ADD COLUMN sku          TEXT",
    "ALTER TABLE productos ADD COLUMN categoria_id INTEGER",
    # clientes — columnas nuevas
    "ALTER TABLE clientes ADD COLUMN telefono       TEXT",
    "ALTER TABLE clientes ADD COLUMN nit_cc         TEXT",
    "ALTER TABLE clientes ADD COLUMN tipo           TEXT NOT NULL DEFAULT 'natural'",
    "ALTER TABLE clientes ADD COLUMN limite_credito REAL NOT NULL DEFAULT 0",
    "ALTER TABLE clientes ADD COLUMN activo         INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE clientes ADD COLUMN creado_en      TEXT",
]


def _aplicar_migraciones(db_path: str | Path | None = None) -> None:
    """Aplica ALTER TABLE idempotentes; ignora columnas que ya existen."""
    with closing(conectar(db_path)) as conn:
        # 1. Recrear usuarios SIN CHECK constraint en rol
        _migrar_usuarios(conn)
        # 2. Columnas nuevas
        for sql in _MIGRACIONES_SQL:
            try:
                conn.execute(sql)
                conn.commit()
            except Exception:
                pass


def _migrar_usuarios(conn: sqlite3.Connection) -> None:
    """Elimina el CHECK constraint de rol en la tabla usuarios si existe."""
    try:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='usuarios'"
        ).fetchone()
        if row and "ck_usuario_rol" in str(row[0]):
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS _usuarios_new (
                    usuario_id    INTEGER PRIMARY KEY AUTOINCREMENT,
                    username      TEXT    NOT NULL UNIQUE,
                    password_hash TEXT    NOT NULL,
                    nombre        TEXT    NOT NULL,
                    email         TEXT    NOT NULL UNIQUE,
                    rol           TEXT    NOT NULL DEFAULT 'vendedor',
                    activo        INTEGER NOT NULL DEFAULT 1,
                    creado_en     TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                INSERT OR IGNORE INTO _usuarios_new
                SELECT usuario_id, username, password_hash, nombre, email, rol, activo, creado_en
                FROM usuarios
            """)
            conn.execute("DROP TABLE usuarios")
            conn.execute("ALTER TABLE _usuarios_new RENAME TO usuarios")
            conn.commit()
            conn.execute("PRAGMA foreign_keys = ON")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Hash de contraseñas
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Seed de datos iniciales
# ---------------------------------------------------------------------------

ROLES_VALIDOS = {"superadmin", "admin", "supervisor", "vendedor", "cajero",
                 "bodeguero", "contador", "consultor"}

USUARIOS_SEED = [
    {"username": "superadmin",  "password": "super123",  "nombre": "Super Administrador",   "email": "super@techstore.co",    "rol": "superadmin"},
    {"username": "admin",       "password": "admin123",  "nombre": "Administrador",          "email": "admin@techstore.co",    "rol": "admin"},
    {"username": "supervisor1", "password": "super123",  "nombre": "Laura Supervisora",      "email": "super1@techstore.co",   "rol": "supervisor"},
    {"username": "vendedor1",   "password": "vend123",   "nombre": "Carlos Vendedor",        "email": "vend1@techstore.co",    "rol": "vendedor"},
    {"username": "cajero1",     "password": "caj123",    "nombre": "María Cajera",           "email": "caj1@techstore.co",     "rol": "cajero"},
    {"username": "bodeguero1",  "password": "bod123",    "nombre": "Pedro Bodeguero",        "email": "bod1@techstore.co",     "rol": "bodeguero"},
    {"username": "contador1",   "password": "cont123",   "nombre": "Ana Contadora",          "email": "cont1@techstore.co",    "rol": "contador"},
    {"username": "consultor1",  "password": "cons123",   "nombre": "Jorge Consultor",        "email": "cons1@techstore.co",    "rol": "consultor"},
]

CATEGORIAS_SEED = [
    ("Laptops",        "Computadoras portátiles"),
    ("Smartphones",    "Teléfonos inteligentes"),
    ("Accesorios",     "Periféricos y accesorios"),
    ("Monitores",      "Pantallas y monitores"),
    ("Almacenamiento", "Discos duros, SSD y memorias"),
    ("Redes",          "Equipos de red y conectividad"),
    ("Componentes",    "Piezas para ensamble"),
]

CONFIG_SEED = [
    ("empresa_nombre",   "TechStore Colombia",   "Nombre del negocio"),
    ("empresa_nit",      "900.123.456-7",         "NIT de la empresa"),
    ("empresa_ciudad",   "Medellín",              "Ciudad principal"),
    ("empresa_telefono", "+57 300 000 0000",      "Teléfono de contacto"),
    ("empresa_email",    "info@techstore.co",     "Correo de contacto"),
    ("empresa_direccion","Calle 50 # 10-20",      "Dirección física"),
    ("moneda",           "COP",                   "Moneda del sistema"),
    ("iva_porcentaje",   "19",                    "Porcentaje de IVA"),
    ("stock_minimo",     "5",                     "Alerta de stock mínimo"),
    ("venta_sin_stock",  "0",                     "Permitir venta sin stock"),
]


def sembrar_datos(db_path: str | Path | None = None) -> None:
    with closing(conectar(db_path)) as conn:
        # Usuarios
        for u in USUARIOS_SEED:
            if not conn.execute("SELECT 1 FROM usuarios WHERE username=?", (u["username"],)).fetchone():
                conn.execute(
                    "INSERT INTO usuarios (username,password_hash,nombre,email,rol) VALUES (?,?,?,?,?)",
                    (u["username"], hash_password(u["password"]), u["nombre"], u["email"], u["rol"]),
                )
        # Categorías
        for nombre, desc in CATEGORIAS_SEED:
            if not conn.execute("SELECT 1 FROM categorias WHERE nombre=?", (nombre,)).fetchone():
                conn.execute("INSERT INTO categorias (nombre,descripcion) VALUES (?,?)", (nombre, desc))
        # Configuración
        for clave, valor, desc in CONFIG_SEED:
            if not conn.execute("SELECT 1 FROM configuracion WHERE clave=?", (clave,)).fetchone():
                conn.execute("INSERT INTO configuracion (clave,valor,descripcion) VALUES (?,?,?)", (clave, valor, desc))
        conn.commit()


def inicializar_db(db_path: str | Path | None = None) -> Path:
    """Idempotente: crea esquema + migraciones + seed."""
    path = crear_esquema(db_path)
    sembrar_datos(db_path)
    return path
