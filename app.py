"""Aplicación de consola para demostrar las cuatro operaciones de Momento 2."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from database import DEFAULT_DB_PATH
from etl import DEFAULT_DATASET, cargar_dataset
from service import (
    ErrorOperacion,
    consultar_pedidos_cliente,
    marcar_entregado,
    probar_rechazo_stock_negativo,
    registrar_pedido,
    resumen,
)


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def ejecutar_demo(
    db_path: Path, dataset_path: Path, evidencia: Path | None = None
) -> list[str]:
    """Ejecuta ETL dos veces y luego las cuatro operaciones exigidas."""
    lines: list[str] = ["TECHSTORE - EVIDENCIA MOMENTO 2"]
    carga_1 = cargar_dataset(db_path, dataset_path)
    carga_2 = cargar_dataset(db_path, dataset_path)
    lines.append("\n1. Carga inicial")
    lines.append(_json(carga_1.como_diccionario()))
    lines.append("\n2. Segunda carga: no duplica pedidos")
    lines.append(_json(carga_2.como_diccionario()))

    pedido_id = "PED-M2-" + datetime.now().strftime("%Y%m%d%H%M%S%f")
    registro = registrar_pedido(
        pedido_id,
        cliente_id=1,
        producto_id=101,
        cantidad=1,
        metodo_pago="tarjeta",
        canal_venta="web",
        db_path=db_path,
        fecha_pedido="2026-10-22",
    )
    lines.append("\n3. Registrar pedido y descontar stock")
    lines.append(_json(registro))

    pedidos = consultar_pedidos_cliente(1, db_path)
    nuevo = next(item for item in pedidos if item["pedido_id"] == pedido_id)
    lines.append("\n4. Consultar pedidos del cliente")
    lines.append(_json({"total_encontrados": len(pedidos), "pedido_nuevo": nuevo}))

    entrega = marcar_entregado(pedido_id, 2, db_path)
    lines.append("\n5. Marcar pedido como entregado")
    lines.append(_json(entrega))

    rechazo = probar_rechazo_stock_negativo(101, db_path)
    lines.append("\n6. Rechazo de stock negativo fuera de transacción explícita")
    lines.append(_json(rechazo))
    lines.append("\n7. Estado final")
    lines.append(_json(resumen(db_path)))

    if evidencia:
        evidencia.parent.mkdir(parents=True, exist_ok=True)
        evidencia.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return lines


def crear_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="TechStore: prototipo conectado a SQLite."
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    sub = parser.add_subparsers(dest="comando", required=True)

    sub.add_parser("init", help="Crear la base y cargar el CSV sin duplicar.")
    sub.add_parser("resumen", help="Mostrar conteos de la base.")

    registrar = sub.add_parser("registrar", help="Registrar pedido y descontar stock.")
    registrar.add_argument("--pedido-id", required=True)
    registrar.add_argument("--cliente-id", required=True, type=int)
    registrar.add_argument("--producto-id", required=True, type=int)
    registrar.add_argument("--cantidad", required=True, type=int)
    registrar.add_argument("--metodo-pago", default="tarjeta")
    registrar.add_argument("--canal-venta", default="web")

    consultar = sub.add_parser("consultar", help="Consultar pedidos de un cliente.")
    consultar.add_argument("--cliente-id", required=True, type=int)

    entregar = sub.add_parser("entregar", help="Marcar pedido como entregado.")
    entregar.add_argument("--pedido-id", required=True)
    entregar.add_argument("--dias", required=True, type=int)

    rechazo = sub.add_parser(
        "rechazo-stock", help="Probar el CHECK de stock fuera de BEGIN explícito."
    )
    rechazo.add_argument("--producto-id", required=True, type=int)

    demo = sub.add_parser("demo", help="Ejecutar toda la demostración.")
    demo.add_argument("--evidencia", type=Path)
    return parser


def main() -> int:
    args = crear_parser().parse_args()
    try:
        if args.comando == "init":
            print(_json(cargar_dataset(args.db, args.dataset).como_diccionario()))
        elif args.comando == "resumen":
            print(_json(resumen(args.db)))
        elif args.comando == "registrar":
            print(
                _json(
                    registrar_pedido(
                        args.pedido_id,
                        args.cliente_id,
                        args.producto_id,
                        args.cantidad,
                        args.metodo_pago,
                        args.canal_venta,
                        args.db,
                    )
                )
            )
        elif args.comando == "consultar":
            print(_json(consultar_pedidos_cliente(args.cliente_id, args.db)))
        elif args.comando == "entregar":
            print(_json(marcar_entregado(args.pedido_id, args.dias, args.db)))
        elif args.comando == "rechazo-stock":
            print(_json(probar_rechazo_stock_negativo(args.producto_id, args.db)))
        elif args.comando == "demo":
            print(
                "\n".join(
                    ejecutar_demo(args.db, args.dataset, args.evidencia)
                )
            )
        return 0
    except (ErrorOperacion, FileNotFoundError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

