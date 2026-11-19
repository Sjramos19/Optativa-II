"""Lógica de negocio TechStore ERP — RBAC, auth, POS, inventario, caja, auditoría."""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import closing
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from database import DEFAULT_DB_PATH, ROLES_VALIDOS, conectar, crear_esquema, hash_password

# ===========================================================================
# EXCEPCIÓN BASE
# ===========================================================================

class ErrorOperacion(ValueError):
    """Error esperado de negocio."""


# ===========================================================================
# RBAC — MATRIZ DE PERMISOS
# ===========================================================================
# True = lectura y escritura | 'r' = solo lectura | None/ausente = sin acceso

_PERMS: dict[str, dict[str, Any]] = {
    "superadmin": {"*": True},
    "admin": {
        "dashboard": True, "ventas": True, "historial": True,
        "productos": True, "inventario": True, "categorias": True,
        "clientes": True, "proveedores": True, "caja": True,
        "finanzas": True, "usuarios": True, "auditoria": "r",
        "reportes": True, "configuracion": True,
    },
    "supervisor": {
        "dashboard": "r", "ventas": "r", "historial": "r",
        "productos": "r", "inventario": "r", "clientes": "r",
        "caja": "r", "finanzas": "r", "auditoria": "r", "reportes": "r",
    },
    "vendedor": {
        "dashboard": "r", "ventas": True, "historial": "r",
        "productos": "r", "clientes": True,
    },
    "cajero": {
        "dashboard": "r", "ventas": "r", "caja": True, "historial": "r",
    },
    "bodeguero": {
        "dashboard": "r", "productos": "r", "inventario": True,
    },
    "contador": {
        "dashboard": "r", "finanzas": True, "ventas": "r",
        "historial": "r", "caja": "r", "reportes": True,
    },
    "consultor": {
        "dashboard": "r", "ventas": "r", "historial": "r",
        "inventario": "r", "finanzas": "r",
        "auditoria": "r", "reportes": "r",
    },
}

PERMS_SIDEBAR: dict[str, list[str]] = {
    "superadmin": [
        "dashboard","ventas","historial","productos","inventario",
        "categorias","clientes","proveedores","caja","finanzas",
        "usuarios","auditoria","reportes","configuracion",
    ],
    "admin": [
        "dashboard","ventas","historial","productos","inventario",
        "categorias","clientes","proveedores","caja","finanzas",
        "usuarios","auditoria","reportes","configuracion",
    ],
    "supervisor": ["dashboard","ventas","historial","productos","inventario","clientes","caja","finanzas","auditoria","reportes"],
    "vendedor":   ["dashboard","ventas","historial","productos","clientes"],
    "cajero":     ["dashboard","ventas","caja","historial"],
    "bodeguero":  ["dashboard","productos","inventario"],
    "contador":   ["dashboard","finanzas","ventas","historial","caja","reportes"],
    "consultor":  ["dashboard","ventas","historial","inventario","finanzas","auditoria","reportes"],
}


def tiene_permiso(rol: str, modulo: str, escritura: bool = False) -> bool:
    if rol == "superadmin":
        return True
    perms = _PERMS.get(rol, {})
    if perms.get("*"):
        return True
    perm = perms.get(modulo)
    if perm is None:
        return False
    if perm == "r":
        return not escritura
    return bool(perm)


def req_perm(rol: str, modulo: str, escritura: bool = False) -> None:
    """Lanza ErrorOperacion si no hay permiso."""
    if not tiene_permiso(rol, modulo, escritura):
        raise ErrorOperacion("Sin permisos para esta operación.")


# ===========================================================================
# HELPERS
# ===========================================================================

def _now() -> str:
    return datetime.now().isoformat(sep="T", timespec="seconds")


def _msg_int(e: sqlite3.IntegrityError) -> str:
    m = str(e)
    if "ck_prod_stock"    in m: return "Stock no puede ser negativo."
    if "UNIQUE"           in m: return "Ya existe un registro con ese valor único."
    if "FOREIGN KEY"      in m: return "Referencia a un registro inexistente."
    if "CHECK"            in m: return f"Valor fuera de rango permitido: {m}"
    return f"Error de base de datos: {m}"


# ===========================================================================
# AUDITORÍA
# ===========================================================================

def audit(uid: int | None, accion: str, modulo: str, desc: str = "",
          db_path: str | Path | None = None) -> None:
    try:
        with closing(conectar(db_path)) as conn:
            conn.execute(
                "INSERT INTO auditoria (usuario_id,accion,modulo,descripcion,fecha) VALUES (?,?,?,?,?)",
                (uid, accion, modulo, desc, _now()),
            )
            conn.commit()
    except Exception:
        pass


def listar_auditoria(limit: int = 100, db_path: str | Path | None = None) -> list[dict]:
    crear_esquema(db_path)
    with closing(conectar(db_path)) as conn:
        rows = conn.execute("""
            SELECT a.audit_id, a.accion, a.modulo, a.descripcion, a.fecha,
                   u.username, u.nombre AS usuario_nombre
              FROM auditoria a
              LEFT JOIN usuarios u ON u.usuario_id = a.usuario_id
             ORDER BY a.audit_id DESC LIMIT ?""", (limit,)).fetchall()
    return [dict(r) for r in rows]


# ===========================================================================
# AUTH & SESIONES
# ===========================================================================

SESSION_TTL = 8  # horas


def autenticar_usuario(username: str, password: str,
                       db_path: str | Path | None = None) -> dict:
    crear_esquema(db_path)
    ph = hash_password(password)
    with closing(conectar(db_path)) as conn:
        row = conn.execute("""
            SELECT usuario_id, username, nombre, email, rol, activo
              FROM usuarios WHERE username=? AND password_hash=?""",
            (username.strip(), ph)).fetchone()
    if row is None:
        raise ErrorOperacion("Usuario o contraseña incorrectos.")
    if not row["activo"]:
        raise ErrorOperacion("Cuenta desactivada. Contacta al administrador.")
    return dict(row)


def crear_sesion(uid: int, db_path: str | Path | None = None) -> str:
    token  = str(uuid.uuid4())
    expira = (datetime.now() + timedelta(hours=SESSION_TTL)).isoformat()
    with closing(conectar(db_path)) as conn:
        conn.execute("DELETE FROM sesiones WHERE usuario_id=? OR expira_en<?", (uid, _now()))
        conn.execute("INSERT INTO sesiones (token,usuario_id,expira_en) VALUES (?,?,?)",
                     (token, uid, expira))
        conn.commit()
    return token


def verificar_sesion(token: str | None,
                     db_path: str | Path | None = None) -> dict | None:
    if not token:
        return None
    with closing(conectar(db_path)) as conn:
        row = conn.execute("""
            SELECT u.usuario_id, u.username, u.nombre, u.email, u.rol
              FROM sesiones s JOIN usuarios u ON u.usuario_id=s.usuario_id
             WHERE s.token=? AND s.expira_en>?""", (token, _now())).fetchone()
    return dict(row) if row else None


def cerrar_sesion(token: str, db_path: str | Path | None = None) -> None:
    with closing(conectar(db_path)) as conn:
        conn.execute("DELETE FROM sesiones WHERE token=?", (token,))
        conn.commit()


# ===========================================================================
# RESUMEN / DASHBOARD
# ===========================================================================

def resumen(db_path: str | Path | None = None) -> dict:
    crear_esquema(db_path)
    hoy = date.today().isoformat()
    with closing(conectar(db_path)) as conn:
        return {
            "clientes":        conn.execute("SELECT COUNT(*) FROM clientes WHERE activo=1").fetchone()[0],
            "productos":       conn.execute("SELECT COUNT(*) FROM productos WHERE activo=1").fetchone()[0],
            "pedidos":         conn.execute("SELECT COUNT(*) FROM pedidos").fetchone()[0],
            "rechazos_carga":  conn.execute("SELECT COUNT(*) FROM rechazos_carga").fetchone()[0],
            "facturas":        conn.execute("SELECT COUNT(*) FROM facturas WHERE estado='pagada'").fetchone()[0],
            "ventas_hoy":      conn.execute("SELECT COALESCE(SUM(total),0) FROM facturas WHERE estado='pagada' AND fecha LIKE ?", (hoy+"%",)).fetchone()[0],
            "stock_bajo":      conn.execute("SELECT COUNT(*) FROM productos WHERE stock<=stock_minimo AND activo=1").fetchone()[0],
            "ventas_mes":      conn.execute("SELECT COALESCE(SUM(total),0) FROM facturas WHERE estado='pagada' AND fecha LIKE ?", (hoy[:7]+"%",)).fetchone()[0],
        }


# ===========================================================================
# CATEGORÍAS
# ===========================================================================

def listar_categorias(db_path: str | Path | None = None) -> list[dict]:
    crear_esquema(db_path)
    with closing(conectar(db_path)) as conn:
        rows = conn.execute("SELECT * FROM categorias ORDER BY nombre").fetchall()
    return [dict(r) for r in rows]


def crear_categoria(nombre: str, descripcion: str = "",
                    db_path: str | Path | None = None) -> dict:
    crear_esquema(db_path)
    with closing(conectar(db_path)) as conn:
        try:
            cur = conn.execute("INSERT INTO categorias (nombre,descripcion) VALUES (?,?)",
                               (nombre.strip(), descripcion.strip()))
            conn.commit()
        except sqlite3.IntegrityError:
            raise ErrorOperacion("Ya existe una categoría con ese nombre.")
    return {"categoria_id": cur.lastrowid, "mensaje": "Categoría creada."}


def editar_categoria(cid: int, nombre: str = None, descripcion: str = None,
                     activo: int = None, db_path: str | Path | None = None) -> dict:
    campos, vals = [], []
    if nombre      is not None: campos.append("nombre=?");      vals.append(nombre.strip())
    if descripcion is not None: campos.append("descripcion=?"); vals.append(descripcion.strip())
    if activo      is not None: campos.append("activo=?");      vals.append(activo)
    if not campos: raise ErrorOperacion("Sin cambios.")
    vals.append(cid)
    with closing(conectar(db_path)) as conn:
        conn.execute(f"UPDATE categorias SET {','.join(campos)} WHERE categoria_id=?", vals)
        conn.commit()
    return {"mensaje": "Categoría actualizada."}


# ===========================================================================
# PROVEEDORES
# ===========================================================================

def listar_proveedores(db_path: str | Path | None = None) -> list[dict]:
    crear_esquema(db_path)
    with closing(conectar(db_path)) as conn:
        rows = conn.execute("SELECT * FROM proveedores ORDER BY nombre").fetchall()
    return [dict(r) for r in rows]


def crear_proveedor(nombre: str, contacto: str = "", telefono: str = "",
                    email: str = "", ciudad: str = "", nit: str = "",
                    db_path: str | Path | None = None) -> dict:
    crear_esquema(db_path)
    with closing(conectar(db_path)) as conn:
        cur = conn.execute("""
            INSERT INTO proveedores (nombre,contacto,telefono,email,ciudad,nit)
            VALUES (?,?,?,?,?,?)""", (nombre, contacto, telefono, email, ciudad, nit))
        conn.commit()
    return {"proveedor_id": cur.lastrowid, "mensaje": "Proveedor creado."}


def editar_proveedor(pid: int, campos_vals: dict,
                     db_path: str | Path | None = None) -> dict:
    allowed = {"nombre","contacto","telefono","email","ciudad","nit","activo"}
    sets = {k: v for k, v in campos_vals.items() if k in allowed}
    if not sets: raise ErrorOperacion("Sin cambios.")
    sql = f"UPDATE proveedores SET {', '.join(k+'=?' for k in sets)} WHERE proveedor_id=?"
    with closing(conectar(db_path)) as conn:
        conn.execute(sql, list(sets.values()) + [pid])
        conn.commit()
    return {"mensaje": "Proveedor actualizado."}


# ===========================================================================
# PRODUCTOS
# ===========================================================================

def listar_productos(solo_activos: bool = True,
                     db_path: str | Path | None = None) -> list[dict]:
    crear_esquema(db_path)
    where = "WHERE p.activo=1" if solo_activos else ""
    with closing(conectar(db_path)) as conn:
        rows = conn.execute(f"""
            SELECT p.*, c.nombre AS categoria_nombre
              FROM productos p
              LEFT JOIN categorias c ON c.categoria_id=p.categoria_id
             {where} ORDER BY p.categoria, p.nombre""").fetchall()
    return [dict(r) for r in rows]


def crear_producto(nombre: str, categoria: str, precio: float, stock: int,
                   precio_compra: float = 0, stock_minimo: int = 5,
                   descripcion: str = "", sku: str = "", categoria_id: int = None,
                   db_path: str | Path | None = None) -> dict:
    crear_esquema(db_path)
    if precio <= 0: raise ErrorOperacion("Precio debe ser mayor que cero.")
    if stock  <  0: raise ErrorOperacion("Stock no puede ser negativo.")
    with closing(conectar(db_path)) as conn:
        cur = conn.execute("""
            INSERT INTO productos
              (nombre,categoria,categoria_id,sku,descripcion,precio_compra,precio,stock,stock_minimo)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (nombre, categoria, categoria_id, sku or None, descripcion,
             precio_compra, precio, stock, stock_minimo))
        conn.commit()
        pid = cur.lastrowid
    return {"producto_id": pid, "mensaje": "Producto creado."}


def editar_producto(producto_id: int, campos: dict,
                    db_path: str | Path | None = None) -> dict:
    allowed = {"nombre","categoria","categoria_id","sku","descripcion",
               "precio_compra","precio","stock","stock_minimo","activo"}
    sets = {k: v for k, v in campos.items() if k in allowed}
    if not sets: raise ErrorOperacion("Sin cambios.")
    sql = f"UPDATE productos SET {', '.join(k+'=?' for k in sets)} WHERE producto_id=?"
    with closing(conectar(db_path)) as conn:
        cur = conn.execute(sql, list(sets.values()) + [producto_id])
        conn.commit()
        if cur.rowcount != 1: raise ErrorOperacion("Producto no encontrado.")
    return {"mensaje": "Producto actualizado."}


# ===========================================================================
# CLIENTES
# ===========================================================================

def listar_clientes(db_path: str | Path | None = None) -> list[dict]:
    crear_esquema(db_path)
    with closing(conectar(db_path)) as conn:
        rows = conn.execute(
            "SELECT * FROM clientes WHERE activo=1 ORDER BY nombre").fetchall()
    return [dict(r) for r in rows]


def crear_cliente(nombre: str, email: str, ciudad: str,
                  telefono: str = "", nit_cc: str = "", tipo: str = "natural",
                  db_path: str | Path | None = None) -> dict:
    crear_esquema(db_path)
    with closing(conectar(db_path)) as conn:
        try:
            cur = conn.execute("""
                INSERT INTO clientes (nombre,email,ciudad,telefono,nit_cc,tipo)
                VALUES (?,?,?,?,?,?)""",
                (nombre, email.lower(), ciudad, telefono, nit_cc, tipo))
            conn.commit()
        except sqlite3.IntegrityError:
            raise ErrorOperacion("Ya existe un cliente con ese correo.")
    return {"cliente_id": cur.lastrowid, "mensaje": "Cliente creado."}


def editar_cliente(cid: int, campos: dict, db_path: str | Path | None = None) -> dict:
    allowed = {"nombre","email","ciudad","telefono","nit_cc","tipo","limite_credito","activo"}
    sets = {k: v for k, v in campos.items() if k in allowed}
    if not sets: raise ErrorOperacion("Sin cambios.")
    sql = f"UPDATE clientes SET {', '.join(k+'=?' for k in sets)} WHERE cliente_id=?"
    with closing(conectar(db_path)) as conn:
        conn.execute(sql, list(sets.values()) + [cid])
        conn.commit()
    return {"mensaje": "Cliente actualizado."}


# ===========================================================================
# INVENTARIO
# ===========================================================================

def listar_movimientos_inv(prod_id: int | None = None, limit: int = 100,
                            db_path: str | Path | None = None) -> list[dict]:
    crear_esquema(db_path)
    where = "WHERE mi.producto_id=?" if prod_id else ""
    params = (prod_id, limit) if prod_id else (limit,)
    with closing(conectar(db_path)) as conn:
        rows = conn.execute(f"""
            SELECT mi.*, p.nombre AS producto, u.nombre AS usuario
              FROM movimientos_inventario mi
              JOIN productos p ON p.producto_id=mi.producto_id
              JOIN usuarios  u ON u.usuario_id=mi.usuario_id
             {where} ORDER BY mi.movimiento_id DESC LIMIT ?""", params).fetchall()
    return [dict(r) for r in rows]


def ajustar_inventario(producto_id: int, tipo: str, cantidad: int,
                       motivo: str, usuario_id: int,
                       referencia: str = "",
                       db_path: str | Path | None = None) -> dict:
    tipos_validos = {"entrada","salida","ajuste","dano"}
    if tipo not in tipos_validos:
        raise ErrorOperacion(f"Tipo inválido. Válidos: {tipos_validos}")
    if cantidad <= 0:
        raise ErrorOperacion("La cantidad debe ser mayor que cero.")
    conn = conectar(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        prod = conn.execute("SELECT stock FROM productos WHERE producto_id=?",
                            (producto_id,)).fetchone()
        if not prod: raise ErrorOperacion("Producto no encontrado.")
        stock_antes = prod["stock"]
        delta = cantidad if tipo in ("entrada",) else -cantidad
        stock_nuevo = stock_antes + delta
        if stock_nuevo < 0:
            raise ErrorOperacion(f"Stock insuficiente. Actual: {stock_antes}")
        conn.execute("UPDATE productos SET stock=? WHERE producto_id=?",
                     (stock_nuevo, producto_id))
        conn.execute("""
            INSERT INTO movimientos_inventario
              (producto_id,tipo,cantidad,stock_antes,stock_despues,motivo,referencia,usuario_id,fecha)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (producto_id, tipo, cantidad, stock_antes, stock_nuevo,
             motivo, referencia, usuario_id, _now()))
        conn.commit()
        return {"stock_antes": stock_antes, "stock_despues": stock_nuevo,
                "mensaje": f"Inventario ajustado. Nuevo stock: {stock_nuevo}"}
    except ErrorOperacion:
        conn.rollback(); raise
    except sqlite3.IntegrityError as e:
        conn.rollback(); raise ErrorOperacion(_msg_int(e))
    finally:
        conn.close()


# ===========================================================================
# CAJA
# ===========================================================================

def sesion_caja_activa(db_path: str | Path | None = None) -> dict | None:
    crear_esquema(db_path)
    with closing(conectar(db_path)) as conn:
        row = conn.execute("""
            SELECT sc.*, u.nombre AS cajero
              FROM sesiones_caja sc JOIN usuarios u ON u.usuario_id=sc.usuario_id
             WHERE sc.estado='abierta' ORDER BY sc.sesion_id DESC LIMIT 1""").fetchone()
    return dict(row) if row else None


def abrir_caja(usuario_id: int, monto_inicial: float, notas: str = "",
               db_path: str | Path | None = None) -> dict:
    crear_esquema(db_path)
    activa = sesion_caja_activa(db_path)
    if activa: raise ErrorOperacion("Ya hay una caja abierta.")
    with closing(conectar(db_path)) as conn:
        cur = conn.execute("""
            INSERT INTO sesiones_caja (usuario_id,monto_inicial,notas_apertura,fecha_apertura)
            VALUES (?,?,?,?)""", (usuario_id, monto_inicial, notas, _now()))
        conn.commit()
    return {"sesion_id": cur.lastrowid, "mensaje": "Caja abierta exitosamente."}


def cerrar_caja(sesion_id: int, monto_contado: float, notas: str = "",
                db_path: str | Path | None = None) -> dict:
    crear_esquema(db_path)
    with closing(conectar(db_path)) as conn:
        ses = conn.execute("SELECT * FROM sesiones_caja WHERE sesion_id=? AND estado='abierta'",
                           (sesion_id,)).fetchone()
        if not ses: raise ErrorOperacion("Sesión de caja no encontrada o ya cerrada.")
        # Calcular esperado
        ingresos = conn.execute(
            "SELECT COALESCE(SUM(monto),0) FROM movimientos_caja WHERE sesion_id=? AND tipo='ingreso'",
            (sesion_id,)).fetchone()[0]
        egresos = conn.execute(
            "SELECT COALESCE(SUM(monto),0) FROM movimientos_caja WHERE sesion_id=? AND tipo='egreso'",
            (sesion_id,)).fetchone()[0]
        esperado   = round(ses["monto_inicial"] + ingresos - egresos, 2)
        diferencia = round(monto_contado - esperado, 2)
        conn.execute("""
            UPDATE sesiones_caja SET estado='cerrada', fecha_cierre=?,
              monto_esperado=?, monto_contado=?, diferencia=?, notas_cierre=?
             WHERE sesion_id=?""",
            (_now(), esperado, monto_contado, diferencia, notas, sesion_id))
        conn.commit()
    return {"esperado": esperado, "contado": monto_contado,
            "diferencia": diferencia, "mensaje": "Caja cerrada."}


def mov_caja(sesion_id: int, tipo: str, concepto: str, monto: float,
             usuario_id: int, referencia: str = "",
             db_path: str | Path | None = None) -> dict:
    crear_esquema(db_path)
    if tipo not in ("ingreso","egreso"): raise ErrorOperacion("Tipo inválido.")
    if monto <= 0: raise ErrorOperacion("Monto debe ser mayor que cero.")
    with closing(conectar(db_path)) as conn:
        ses = conn.execute("SELECT 1 FROM sesiones_caja WHERE sesion_id=? AND estado='abierta'",
                           (sesion_id,)).fetchone()
        if not ses: raise ErrorOperacion("Caja no abierta.")
        cur = conn.execute("""
            INSERT INTO movimientos_caja
              (sesion_id,tipo,concepto,monto,referencia,usuario_id,fecha)
            VALUES (?,?,?,?,?,?,?)""",
            (sesion_id, tipo, concepto, monto, referencia, usuario_id, _now()))
        conn.commit()
    return {"mov_id": cur.lastrowid, "mensaje": f"{tipo.capitalize()} registrado."}


def listar_sesiones_caja(limit: int = 20, db_path: str | Path | None = None) -> list[dict]:
    crear_esquema(db_path)
    with closing(conectar(db_path)) as conn:
        rows = conn.execute("""
            SELECT sc.*, u.nombre AS cajero
              FROM sesiones_caja sc JOIN usuarios u ON u.usuario_id=sc.usuario_id
             ORDER BY sc.sesion_id DESC LIMIT ?""", (limit,)).fetchall()
    return [dict(r) for r in rows]


def movimientos_de_sesion(sesion_id: int, db_path: str | Path | None = None) -> list[dict]:
    crear_esquema(db_path)
    with closing(conectar(db_path)) as conn:
        rows = conn.execute("""
            SELECT mc.*, u.nombre AS usuario
              FROM movimientos_caja mc JOIN usuarios u ON u.usuario_id=mc.usuario_id
             WHERE mc.sesion_id=? ORDER BY mc.mov_id""", (sesion_id,)).fetchall()
    return [dict(r) for r in rows]


# ===========================================================================
# FACTURACIÓN POS
# ===========================================================================

def _numero_factura(conn: sqlite3.Connection) -> str:
    ultimo = conn.execute(
        "SELECT numero FROM facturas ORDER BY factura_id DESC LIMIT 1").fetchone()
    if not ultimo: return "FAC-00001"
    try:
        n = int(ultimo["numero"].split("-")[1]) + 1
    except Exception:
        n = 1
    return f"FAC-{n:05d}"


def registrar_factura(items: list[dict], vendedor_id: int,
                      metodo_pago: str = "efectivo",
                      cliente_id: int | None = None,
                      descuento: float = 0.0, notas: str = "",
                      db_path: str | Path | None = None) -> dict:
    crear_esquema(db_path)
    metodo_pago = metodo_pago.strip().lower()
    pagos_ok = {"tarjeta","transferencia","efectivo","nequi","daviplata"}
    if metodo_pago not in pagos_ok:
        raise ErrorOperacion(f"Método de pago inválido: {metodo_pago}")
    if not items:
        raise ErrorOperacion("La factura requiere al menos un producto.")

    conn = conectar(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        if cliente_id:
            if not conn.execute("SELECT 1 FROM clientes WHERE cliente_id=?",
                                (cliente_id,)).fetchone():
                raise ErrorOperacion("Cliente no encontrado.")
        subtotal = 0.0
        lineas   = []
        for item in items:
            pid = int(item["producto_id"]); cant = int(item["cantidad"])
            if cant <= 0: raise ErrorOperacion("Cantidad debe ser > 0.")
            prod = conn.execute(
                "SELECT nombre,precio,stock FROM productos WHERE producto_id=? AND activo=1",
                (pid,)).fetchone()
            if not prod: raise ErrorOperacion(f"Producto ID {pid} no encontrado o inactivo.")
            if prod["stock"] < cant:
                raise ErrorOperacion(
                    f"Stock insuficiente para '{prod['nombre']}': "
                    f"disponible {prod['stock']}, solicitado {cant}.")
            conn.execute("UPDATE productos SET stock=stock-? WHERE producto_id=?",
                         (cant, pid))
            # Registrar movimiento de inventario
            stock_nuevo = prod["stock"] - cant
            conn.execute("""
                INSERT INTO movimientos_inventario
                  (producto_id,tipo,cantidad,stock_antes,stock_despues,motivo,usuario_id,fecha)
                VALUES (?,?,?,?,?,'venta',?,?)""",
                (pid, "venta", cant, prod["stock"], stock_nuevo, vendedor_id, _now()))
            sub_lin = round(float(prod["precio"]) * cant, 2)
            subtotal += sub_lin
            lineas.append({"producto_id": pid, "nombre": prod["nombre"],
                           "cantidad": cant, "precio_unit": prod["precio"], "subtotal": sub_lin})

        subtotal  = round(subtotal, 2)
        desc_val  = round(subtotal * (descuento / 100), 2) if descuento > 0 else 0.0
        base_imp  = round(subtotal - desc_val, 2)
        impuesto  = round(base_imp * 0.19, 2)
        total     = round(base_imp + impuesto, 2)
        num_fac   = _numero_factura(conn)

        cur = conn.execute("""
            INSERT INTO facturas
              (numero,cliente_id,vendedor_id,fecha,subtotal,descuento,impuesto,total,metodo_pago,notas)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (num_fac, cliente_id, vendedor_id, _now(),
             subtotal, desc_val, impuesto, total, metodo_pago, notas.strip()))
        fid = cur.lastrowid

        for lin in lineas:
            conn.execute("""
                INSERT INTO detalle_factura
                  (factura_id,producto_id,cantidad,precio_unit,subtotal)
                VALUES (?,?,?,?,?)""",
                (fid, lin["producto_id"], lin["cantidad"],
                 lin["precio_unit"], lin["subtotal"]))

        conn.commit()
        return {"factura_id": fid, "numero": num_fac, "subtotal": subtotal,
                "descuento": desc_val, "impuesto": impuesto, "total": total,
                "metodo_pago": metodo_pago, "lineas": lineas,
                "mensaje": f"Factura {num_fac} generada exitosamente."}
    except ErrorOperacion:
        conn.rollback(); raise
    except sqlite3.IntegrityError as e:
        conn.rollback(); raise ErrorOperacion(_msg_int(e))
    finally:
        conn.close()


def listar_facturas(vendedor_id: int | None = None, limit: int = 60,
                    db_path: str | Path | None = None) -> list[dict]:
    crear_esquema(db_path)
    where = "WHERE f.vendedor_id=?" if vendedor_id else ""
    params = (vendedor_id, limit) if vendedor_id else (limit,)
    with closing(conectar(db_path)) as conn:
        rows = conn.execute(f"""
            SELECT f.factura_id, f.numero, f.fecha, f.total, f.metodo_pago, f.estado,
                   c.nombre AS cliente, u.nombre AS vendedor
              FROM facturas f
              LEFT JOIN clientes c ON c.cliente_id=f.cliente_id
              JOIN  usuarios  u ON u.usuario_id=f.vendedor_id
             {where} ORDER BY f.factura_id DESC LIMIT ?""", params).fetchall()
    return [dict(r) for r in rows]


def detalle_factura_por_id(fid: int, db_path: str | Path | None = None) -> dict:
    crear_esquema(db_path)
    with closing(conectar(db_path)) as conn:
        cab = conn.execute("""
            SELECT f.*, c.nombre AS cliente_nombre, u.nombre AS vendedor_nombre
              FROM facturas f
              LEFT JOIN clientes c ON c.cliente_id=f.cliente_id
              JOIN  usuarios  u ON u.usuario_id=f.vendedor_id
             WHERE f.factura_id=?""", (fid,)).fetchone()
        if not cab: raise ErrorOperacion("Factura no encontrada.")
        lins = conn.execute("""
            SELECT d.*, p.nombre AS producto
              FROM detalle_factura d JOIN productos p ON p.producto_id=d.producto_id
             WHERE d.factura_id=?""", (fid,)).fetchall()
    return {**dict(cab), "lineas": [dict(l) for l in lins]}


def anular_factura(fid: int, motivo: str, usuario_id: int,
                   db_path: str | Path | None = None) -> dict:
    crear_esquema(db_path)
    with closing(conectar(db_path)) as conn:
        fac = conn.execute("SELECT estado FROM facturas WHERE factura_id=?", (fid,)).fetchone()
        if not fac: raise ErrorOperacion("Factura no encontrada.")
        if fac["estado"] == "anulada": raise ErrorOperacion("Factura ya está anulada.")
        # Devolver stock
        lins = conn.execute(
            "SELECT producto_id, cantidad FROM detalle_factura WHERE factura_id=?",
            (fid,)).fetchall()
        for lin in lins:
            prod = conn.execute("SELECT stock FROM productos WHERE producto_id=?",
                                (lin["producto_id"],)).fetchone()
            stock_antes = prod["stock"] if prod else 0
            conn.execute("UPDATE productos SET stock=stock+? WHERE producto_id=?",
                         (lin["cantidad"], lin["producto_id"]))
            conn.execute("""
                INSERT INTO movimientos_inventario
                  (producto_id,tipo,cantidad,stock_antes,stock_despues,motivo,usuario_id,fecha)
                VALUES (?,?,?,?,?,'devolucion_anulacion',?,?)""",
                (lin["producto_id"], "devolucion", lin["cantidad"],
                 stock_antes, stock_antes + lin["cantidad"], usuario_id, _now()))
        conn.execute("UPDATE facturas SET estado='anulada', notas=? WHERE factura_id=?",
                     (f"Anulada: {motivo}", fid))
        conn.commit()
    audit(usuario_id, "anular", "ventas", f"Factura #{fid} anulada. Motivo: {motivo}", db_path)
    return {"mensaje": "Factura anulada y stock devuelto."}


# ===========================================================================
# USUARIOS (ADMIN)
# ===========================================================================

def listar_usuarios(db_path: str | Path | None = None) -> list[dict]:
    crear_esquema(db_path)
    with closing(conectar(db_path)) as conn:
        rows = conn.execute("""
            SELECT usuario_id, username, nombre, email, rol, activo, creado_en
              FROM usuarios ORDER BY rol, nombre""").fetchall()
    return [dict(r) for r in rows]


def crear_usuario(username: str, password: str, nombre: str, email: str,
                  rol: str, db_path: str | Path | None = None) -> dict:
    crear_esquema(db_path)
    if rol not in ROLES_VALIDOS:
        raise ErrorOperacion(f"Rol inválido. Opciones: {', '.join(sorted(ROLES_VALIDOS))}")
    with closing(conectar(db_path)) as conn:
        try:
            cur = conn.execute("""
                INSERT INTO usuarios (username,password_hash,nombre,email,rol)
                VALUES (?,?,?,?,?)""",
                (username.strip(), hash_password(password), nombre.strip(),
                 email.strip().lower(), rol))
            conn.commit()
        except sqlite3.IntegrityError:
            raise ErrorOperacion("Ya existe un usuario con ese nombre o correo.")
    return {"usuario_id": cur.lastrowid, "mensaje": "Usuario creado."}


def editar_usuario(uid: int, campos: dict,
                   db_path: str | Path | None = None) -> dict:
    allowed = {"nombre","email","rol","activo"}
    sets = {k: v for k, v in campos.items() if k in allowed}
    if "password" in campos:
        sets["password_hash"] = hash_password(campos["password"])
    if not sets: raise ErrorOperacion("Sin cambios.")
    if "rol" in sets and sets["rol"] not in ROLES_VALIDOS:
        raise ErrorOperacion("Rol inválido.")
    sql = f"UPDATE usuarios SET {', '.join(k+'=?' for k in sets)} WHERE usuario_id=?"
    with closing(conectar(db_path)) as conn:
        conn.execute(sql, list(sets.values()) + [uid])
        conn.commit()
    return {"mensaje": "Usuario actualizado."}


# ===========================================================================
# CONFIGURACIÓN
# ===========================================================================

def obtener_config(db_path: str | Path | None = None) -> dict:
    crear_esquema(db_path)
    with closing(conectar(db_path)) as conn:
        rows = conn.execute("SELECT clave, valor FROM configuracion").fetchall()
    return {r["clave"]: r["valor"] for r in rows}


def guardar_config(cambios: dict, db_path: str | Path | None = None) -> dict:
    with closing(conectar(db_path)) as conn:
        for k, v in cambios.items():
            conn.execute("""
                INSERT INTO configuracion (clave,valor,actualizado_en)
                VALUES (?,?,?)
                ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor, actualizado_en=excluded.actualizado_en""",
                (k, str(v), _now()))
        conn.commit()
    return {"mensaje": "Configuración guardada."}


# ===========================================================================
# PEDIDOS (LEGADO)
# ===========================================================================

def consultar_pedidos_cliente(cliente_id: int,
                              db_path: str | Path | None = None) -> list[dict]:
    crear_esquema(db_path)
    with closing(conectar(db_path)) as conn:
        rows = conn.execute("""
            SELECT ped.pedido_id, c.nombre AS cliente, p.nombre AS producto,
                   ped.fecha_pedido, ped.cantidad, ped.valor_total,
                   ped.estado, ped.tiempo_entrega_dias
              FROM pedidos ped
              JOIN clientes  c ON c.cliente_id=ped.cliente_id
              JOIN productos p ON p.producto_id=ped.producto_id
             WHERE ped.cliente_id=?
             ORDER BY ped.fecha_pedido DESC, ped.pedido_id DESC""",
            (cliente_id,)).fetchall()
    return [dict(r) for r in rows]


def marcar_entregado(pedido_id: str, dias: int,
                     db_path: str | Path | None = None) -> dict:
    crear_esquema(db_path)
    if dias < 0: raise ErrorOperacion("Días no puede ser negativo.")
    with closing(conectar(db_path)) as conn, conn:
        cur = conn.execute(
            "UPDATE pedidos SET estado='entregado', tiempo_entrega_dias=? WHERE pedido_id=?",
            (dias, pedido_id))
        if cur.rowcount != 1: raise ErrorOperacion("Pedido no encontrado.")
    return {"mensaje": "Pedido marcado como entregado."}


def probar_rechazo_stock_negativo(prod_id: int,
                                  db_path: str | Path | None = None) -> dict:
    crear_esquema(db_path)
    conn = conectar(db_path, autocommit=True)
    try:
        row = conn.execute("SELECT stock FROM productos WHERE producto_id=?",
                           (prod_id,)).fetchone()
        if not row: raise ErrorOperacion("Producto no encontrado.")
        stock_antes = row["stock"]
        try:
            conn.execute("UPDATE productos SET stock=-1 WHERE producto_id=?", (prod_id,))
        except sqlite3.IntegrityError as e:
            return {"rechazado": True, "regla": "ck_prod_stock",
                    "stock_antes": stock_antes, "stock_despues": stock_antes,
                    "mensaje": _msg_int(e)}
        raise AssertionError("CHECK no actuó.")
    finally:
        conn.close()
