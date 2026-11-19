"""Carga idempotente del CSV original a la base relacional."""

from __future__ import annotations

import csv
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from database import APP_DIR, conectar, crear_esquema


DEFAULT_DATASET = APP_DIR.parent / "01_dataset" / "datos_originales.csv"
FECHA_CORTE = date(2026, 8, 31)
ESTADOS = {"entregado", "pendiente", "cancelado"}
PAGOS = {"tarjeta", "transferencia", "efectivo"}
CANALES = {"web", "movil", "whatsapp"}

# El CSV no incluye existencias. Se conserva el inventario inicial usado en E1.
STOCK_INICIAL = {
    101: 25,
    102: 15,
    103: 30,
    104: 40,
    105: 12,
    106: 22,
    107: 50,
    108: 10,
    109: 18,
    110: 14,
}


@dataclass(frozen=True)
class ResultadoCarga:
    registros_entrada: int
    registros_validos: int
    registros_rechazados: int
    pedidos_insertados: int
    pedidos_en_bd: int
    clientes_en_bd: int
    productos_en_bd: int

    def como_diccionario(self) -> dict[str, int]:
        return asdict(self)


def _texto(row: dict[str, str], key: str) -> str:
    return (row.get(key) or "").strip()


def _entero(valor: str, campo: str) -> int:
    try:
        numero = float(valor)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{campo} no es numérico") from error
    if not numero.is_integer():
        raise ValueError(f"{campo} debe ser entero")
    return int(numero)


def _decimal(valor: str, campo: str) -> float:
    try:
        return float(valor)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{campo} no es numérico") from error


def _normalizar(
    row: dict[str, str], fila: int, pedidos_vistos: set[str]
) -> tuple[dict[str, Any] | None, str | None]:
    pedido_id = _texto(row, "pedido_id")
    if not pedido_id:
        return None, "pedido_id vacío"
    if pedido_id in pedidos_vistos:
        return None, "pedido_id repetido con datos distintos; no se sobrescribió"
    pedidos_vistos.add(pedido_id)

    try:
        cliente_id = _entero(_texto(row, "cliente_id"), "cliente_id")
        producto_id = _entero(_texto(row, "producto_id"), "producto_id")
        precio = _decimal(_texto(row, "precio_unitario"), "precio_unitario")
        cantidad = _entero(_texto(row, "cantidad"), "cantidad")
        valor_total = _decimal(_texto(row, "valor_total"), "valor_total")
        fecha_pedido = datetime.strptime(
            _texto(row, "fecha_pedido"), "%Y-%m-%d"
        ).date()
        tiempo_texto = _texto(row, "tiempo_entrega_dias")
        tiempo = _entero(tiempo_texto, "tiempo_entrega_dias") if tiempo_texto else None
    except ValueError as error:
        return None, str(error)

    estado = _texto(row, "estado_pedido").lower()
    pago = _texto(row, "metodo_pago").lower()
    canal = _texto(row, "canal_venta").lower()

    razones: list[str] = []
    if cliente_id not in range(1, 21):
        razones.append("cliente_id fuera de 1..20")
    if producto_id not in range(101, 111):
        razones.append("producto_id fuera de 101..110")
    if estado not in ESTADOS:
        razones.append("estado no permitido")
    if pago not in PAGOS:
        razones.append("método de pago no permitido")
    if canal not in CANALES:
        razones.append("canal no permitido")
    if precio <= 0:
        razones.append("precio no positivo")
    if cantidad <= 0:
        razones.append("cantidad no positiva")
    if valor_total <= 0:
        razones.append("valor total no positivo")
    if fecha_pedido > FECHA_CORTE:
        razones.append("fecha posterior al corte")
    if tiempo is not None and tiempo < 0:
        razones.append("tiempo de entrega negativo")
    if estado == "entregado" and tiempo is None:
        razones.append("pedido entregado sin tiempo de entrega")
    if abs(valor_total - precio * cantidad) > 0.01:
        razones.append("valor total distinto de precio por cantidad")

    if razones:
        return None, "; ".join(razones)

    return {
        "fila": fila,
        "pedido_id": pedido_id,
        "cliente_id": cliente_id,
        "cliente_nombre": _texto(row, "cliente_nombre"),
        "cliente_email": _texto(row, "cliente_email").lower(),
        "cliente_ciudad": _texto(row, "cliente_ciudad"),
        "producto_id": producto_id,
        "producto_nombre": _texto(row, "producto_nombre"),
        "categoria": _texto(row, "categoria"),
        "precio": precio,
        "cantidad": cantidad,
        "valor_total": valor_total,
        "fecha_pedido": fecha_pedido.isoformat(),
        "estado": estado,
        "metodo_pago": pago,
        "tiempo_entrega_dias": tiempo,
        "canal_venta": canal,
    }, None


def cargar_dataset(
    db_path: str | Path | None = None,
    dataset_path: str | Path | None = None,
) -> ResultadoCarga:
    """Limpia, valida y carga el CSV sin duplicar datos al repetir el proceso."""
    database = crear_esquema(db_path)
    dataset = Path(dataset_path) if dataset_path else DEFAULT_DATASET
    pedidos_vistos: set[str] = set()
    entrada = validos = rechazados = insertados = 0

    with dataset.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        with closing(conectar(database)) as connection, connection:
            for fila, raw in enumerate(reader, start=2):
                entrada += 1
                data, motivo = _normalizar(raw, fila, pedidos_vistos)
                pedido_id = _texto(raw, "pedido_id") or None
                if motivo:
                    rechazados += 1
                    connection.execute(
                        """
                        INSERT OR IGNORE INTO rechazos_carga
                            (fila_origen, pedido_id, motivo)
                        VALUES (?, ?, ?)
                        """,
                        (fila, pedido_id, motivo),
                    )
                    continue

                assert data is not None
                validos += 1
                connection.execute(
                    """
                    INSERT OR IGNORE INTO clientes
                        (cliente_id, nombre, email, ciudad)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        data["cliente_id"],
                        data["cliente_nombre"],
                        data["cliente_email"],
                        data["cliente_ciudad"],
                    ),
                )
                connection.execute(
                    """
                    INSERT OR IGNORE INTO productos
                        (producto_id, nombre, categoria, precio, stock)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        data["producto_id"],
                        data["producto_nombre"],
                        data["categoria"],
                        data["precio"],
                        STOCK_INICIAL[data["producto_id"]],
                    ),
                )
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO pedidos
                        (pedido_id, cliente_id, producto_id, fecha_pedido,
                         cantidad, valor_total, estado, metodo_pago,
                         tiempo_entrega_dias, canal_venta)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        data["pedido_id"],
                        data["cliente_id"],
                        data["producto_id"],
                        data["fecha_pedido"],
                        data["cantidad"],
                        data["valor_total"],
                        data["estado"],
                        data["metodo_pago"],
                        data["tiempo_entrega_dias"],
                        data["canal_venta"],
                    ),
                )
                insertados += max(cursor.rowcount, 0)

            pedidos_en_bd = connection.execute(
                "SELECT COUNT(*) FROM pedidos"
            ).fetchone()[0]
            clientes_en_bd = connection.execute(
                "SELECT COUNT(*) FROM clientes"
            ).fetchone()[0]
            productos_en_bd = connection.execute(
                "SELECT COUNT(*) FROM productos"
            ).fetchone()[0]

    return ResultadoCarga(
        registros_entrada=entrada,
        registros_validos=validos,
        registros_rechazados=rechazados,
        pedidos_insertados=insertados,
        pedidos_en_bd=pedidos_en_bd,
        clientes_en_bd=clientes_en_bd,
        productos_en_bd=productos_en_bd,
    )
