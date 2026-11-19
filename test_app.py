from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = APP_DIR.parent
sys.path.insert(0, str(APP_DIR))

from database import conectar  # noqa: E402
from etl import cargar_dataset  # noqa: E402
from service import (  # noqa: E402
    ErrorOperacion,
    consultar_pedidos_cliente,
    marcar_entregado,
    probar_rechazo_stock_negativo,
    registrar_pedido,
)


class TechStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "test.db"
        self.dataset = PROJECT_DIR / "01_dataset" / "datos_originales.csv"
        self.first_load = cargar_dataset(self.db, self.dataset)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_carga_es_idempotente_y_auditada(self) -> None:
        second = cargar_dataset(self.db, self.dataset)
        self.assertEqual(self.first_load.registros_entrada, 156)
        self.assertEqual(self.first_load.registros_validos, 151)
        self.assertEqual(self.first_load.registros_rechazados, 5)
        self.assertEqual(self.first_load.pedidos_insertados, 151)
        self.assertEqual(second.pedidos_insertados, 0)
        self.assertEqual(second.pedidos_en_bd, 151)
        with closing(conectar(self.db)) as connection:
            collision = connection.execute(
                "SELECT COUNT(*) FROM rechazos_carga WHERE pedido_id = ?",
                ("PED-1025",),
            ).fetchone()[0]
        self.assertEqual(collision, 1)

    def test_registrar_descuenta_stock_en_una_transaccion(self) -> None:
        with closing(conectar(self.db)) as connection:
            before = connection.execute(
                "SELECT stock FROM productos WHERE producto_id = ?", (101,)
            ).fetchone()[0]
        result = registrar_pedido(
            "PED-TEST-OK", 1, 101, 2, "tarjeta", "web", self.db, "2026-10-22"
        )
        self.assertEqual(result["stock_final"], before - 2)
        with closing(conectar(self.db)) as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM pedidos WHERE pedido_id = ?", ("PED-TEST-OK",)
            ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_error_de_pedido_revierte_el_descuento(self) -> None:
        registrar_pedido(
            "PED-TEST-DUP", 1, 101, 1, "tarjeta", "web", self.db, "2026-10-22"
        )
        with closing(conectar(self.db)) as connection:
            before = connection.execute(
                "SELECT stock FROM productos WHERE producto_id = ?", (101,)
            ).fetchone()[0]
        with self.assertRaises(ErrorOperacion):
            registrar_pedido(
                "PED-TEST-DUP",
                1,
                101,
                1,
                "tarjeta",
                "web",
                self.db,
                "2026-10-22",
            )
        with closing(conectar(self.db)) as connection:
            after = connection.execute(
                "SELECT stock FROM productos WHERE producto_id = ?", (101,)
            ).fetchone()[0]
        self.assertEqual(after, before)

    def test_consultar_pedidos_de_cliente(self) -> None:
        registrar_pedido(
            "PED-TEST-CONSULTA",
            1,
            101,
            1,
            "efectivo",
            "web",
            self.db,
            "2026-10-22",
        )
        ids = {item["pedido_id"] for item in consultar_pedidos_cliente(1, self.db)}
        self.assertIn("PED-TEST-CONSULTA", ids)

    def test_marcar_entregado(self) -> None:
        registrar_pedido(
            "PED-TEST-ENTREGA",
            1,
            101,
            1,
            "tarjeta",
            "web",
            self.db,
            "2026-10-22",
        )
        marcar_entregado("PED-TEST-ENTREGA", 2, self.db)
        with closing(conectar(self.db)) as connection:
            row = connection.execute(
                "SELECT estado, tiempo_entrega_dias FROM pedidos WHERE pedido_id = ?",
                ("PED-TEST-ENTREGA",),
            ).fetchone()
        self.assertEqual((row["estado"], row["tiempo_entrega_dias"]), ("entregado", 2))

    def test_base_rechaza_stock_negativo_fuera_de_begin(self) -> None:
        result = probar_rechazo_stock_negativo(101, self.db)
        self.assertTrue(result["rechazado"])
        self.assertEqual(result["stock_antes"], result["stock_despues"])
        self.assertIn("ck_prod_stock", result["regla"])

    def test_checks_de_tiempo_estan_separados(self) -> None:
        connection = conectar(self.db, autocommit=True)
        try:
            with self.assertRaisesRegex(
                sqlite3.IntegrityError, "ck_pedido_entregado_con_tiempo"
            ):
                connection.execute(
                    """
                    INSERT INTO pedidos
                        (pedido_id, cliente_id, producto_id, fecha_pedido,
                         cantidad, valor_total, estado, metodo_pago,
                         tiempo_entrega_dias, canal_venta)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "PED-TEST-SIN-TIEMPO",
                        1,
                        101,
                        "2026-10-22",
                        1,
                        3200000,
                        "entregado",
                        "tarjeta",
                        None,
                        "web",
                    ),
                )
            with self.assertRaisesRegex(
                sqlite3.IntegrityError, "ck_pedido_tiempo_no_negativo"
            ):
                connection.execute(
                    """
                    INSERT INTO pedidos
                        (pedido_id, cliente_id, producto_id, fecha_pedido,
                         cantidad, valor_total, estado, metodo_pago,
                         tiempo_entrega_dias, canal_venta)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "PED-TEST-TIEMPO-NEG",
                        1,
                        101,
                        "2026-10-22",
                        1,
                        3200000,
                        "pendiente",
                        "tarjeta",
                        -1,
                        "web",
                    ),
                )
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
