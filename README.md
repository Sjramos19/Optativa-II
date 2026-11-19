# TechStore - aplicación conectada

Prototipo de consola con SQLite persistente. Usa solo Python 3 y consultas parametrizadas; no contiene claves ni credenciales.

Esta carpeta es el entregable `04_app` solicitado en el Momento 2.

## Ejecución rápida

Desde la carpeta `04_app`:

```powershell
python app.py init
python app.py registrar --pedido-id PED-M2-001 --cliente-id 1 --producto-id 101 --cantidad 1 --metodo-pago tarjeta --canal-venta web
python app.py consultar --cliente-id 1
python app.py entregar --pedido-id PED-M2-001 --dias 2
python app.py rechazo-stock --producto-id 101
```

Demostración completa:

```powershell
python app.py demo
```

En Windows puede ejecutarse la misma demostración con doble clic en `EJECUTAR_DEMO.bat`.
Primero se debe extraer el ZIP por completo; Windows no carga los archivos vecinos si el `.bat` se abre directamente dentro del archivo comprimido.

Pruebas automáticas:

```powershell
python -m unittest discover -s tests -v
```

## Qué demuestra

- La carga recibe 156 filas, acepta 151 y rechaza 5 con causa.
- Una segunda carga no duplica pedidos.
- Registrar un pedido y descontar stock ocurre en una transacción.
- Se consultan los pedidos de un cliente con `JOIN`.
- Un pedido entregado guarda un tiempo no negativo.
- Un `UPDATE` directo a stock negativo es rechazado por `ck_prod_stock`.
- Los dos `CHECK` de tiempo están separados: uno impide valores negativos y otro exige tiempo cuando el estado es `entregado`.

La ruta de la base puede cambiarse con `--db` o con la variable `TECHSTORE_DB`.
