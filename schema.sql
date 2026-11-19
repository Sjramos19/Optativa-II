PRAGMA foreign_keys = ON;

-- ============================================================
-- TABLA: categorias
-- ============================================================
CREATE TABLE IF NOT EXISTS categorias (
    categoria_id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre       TEXT    NOT NULL UNIQUE,
    descripcion  TEXT,
    activo       INTEGER NOT NULL DEFAULT 1,
    creado_en    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- TABLA: clientes
-- ============================================================
CREATE TABLE IF NOT EXISTS clientes (
    cliente_id     INTEGER PRIMARY KEY,
    nombre         TEXT    NOT NULL,
    email          TEXT    NOT NULL UNIQUE,
    ciudad         TEXT    NOT NULL,
    telefono       TEXT,
    nit_cc         TEXT,
    tipo           TEXT    NOT NULL DEFAULT 'natural',
    limite_credito REAL    NOT NULL DEFAULT 0,
    activo         INTEGER NOT NULL DEFAULT 1,
    creado_en      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_cli_tipo CHECK (tipo IN ('natural','juridico'))
);

-- ============================================================
-- TABLA: proveedores
-- ============================================================
CREATE TABLE IF NOT EXISTS proveedores (
    proveedor_id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre       TEXT    NOT NULL,
    contacto     TEXT,
    telefono     TEXT,
    email        TEXT,
    direccion    TEXT,
    ciudad       TEXT,
    nit          TEXT,
    activo       INTEGER NOT NULL DEFAULT 1,
    creado_en    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- TABLA: productos
-- ============================================================
CREATE TABLE IF NOT EXISTS productos (
    producto_id  INTEGER PRIMARY KEY,
    nombre       TEXT    NOT NULL,
    categoria_id INTEGER,
    categoria    TEXT    NOT NULL DEFAULT 'General',
    sku          TEXT,
    descripcion  TEXT,
    precio_compra REAL   NOT NULL DEFAULT 0,
    precio       REAL    NOT NULL,
    stock        INTEGER NOT NULL DEFAULT 0,
    stock_minimo INTEGER NOT NULL DEFAULT 5,
    activo       INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT fk_prod_cat  FOREIGN KEY (categoria_id) REFERENCES categorias(categoria_id),
    CONSTRAINT ck_prod_precio CHECK (precio > 0),
    CONSTRAINT ck_prod_stock  CHECK (stock  >= 0)
);

-- ============================================================
-- TABLA: usuarios  (sin CHECK en rol para soportar 8 roles)
-- ============================================================
CREATE TABLE IF NOT EXISTS usuarios (
    usuario_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    nombre        TEXT    NOT NULL,
    email         TEXT    NOT NULL UNIQUE,
    rol           TEXT    NOT NULL DEFAULT 'vendedor',
    activo        INTEGER NOT NULL DEFAULT 1,
    creado_en     TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- TABLA: sesiones
-- ============================================================
CREATE TABLE IF NOT EXISTS sesiones (
    token       TEXT    PRIMARY KEY,
    usuario_id  INTEGER NOT NULL,
    expira_en   TEXT    NOT NULL,
    creado_en   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ses_user FOREIGN KEY (usuario_id) REFERENCES usuarios(usuario_id)
);

-- ============================================================
-- TABLA: pedidos
-- ============================================================
CREATE TABLE IF NOT EXISTS pedidos (
    pedido_id           TEXT    PRIMARY KEY,
    cliente_id          INTEGER NOT NULL,
    producto_id         INTEGER NOT NULL,
    fecha_pedido        TEXT    NOT NULL,
    cantidad            INTEGER NOT NULL,
    valor_total         REAL    NOT NULL,
    estado              TEXT    NOT NULL,
    metodo_pago         TEXT    NOT NULL,
    tiempo_entrega_dias INTEGER,
    canal_venta         TEXT    NOT NULL,
    CONSTRAINT fk_ped_cli  FOREIGN KEY (cliente_id)  REFERENCES clientes(cliente_id),
    CONSTRAINT fk_ped_prod FOREIGN KEY (producto_id) REFERENCES productos(producto_id),
    CONSTRAINT ck_ped_cant  CHECK (cantidad    > 0),
    CONSTRAINT ck_ped_val   CHECK (valor_total > 0),
    CONSTRAINT ck_ped_est   CHECK (estado      IN ('entregado','pendiente','cancelado')),
    CONSTRAINT ck_ped_pago  CHECK (metodo_pago IN ('tarjeta','transferencia','efectivo','nequi','daviplata')),
    CONSTRAINT ck_ped_canal CHECK (canal_venta IN ('web','movil','whatsapp','pos')),
    CONSTRAINT ck_ped_tiempo CHECK (tiempo_entrega_dias IS NULL OR tiempo_entrega_dias >= 0),
    CONSTRAINT ck_ped_entregado CHECK (estado <> 'entregado' OR tiempo_entrega_dias IS NOT NULL)
);

-- ============================================================
-- TABLA: rechazos_carga
-- ============================================================
CREATE TABLE IF NOT EXISTS rechazos_carga (
    rechazo_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    fila_origen INTEGER NOT NULL,
    pedido_id   TEXT,
    motivo      TEXT NOT NULL,
    creado_en   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (fila_origen, pedido_id, motivo)
);

-- ============================================================
-- TABLA: facturas
-- ============================================================
CREATE TABLE IF NOT EXISTS facturas (
    factura_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    numero      TEXT    NOT NULL UNIQUE,
    cliente_id  INTEGER,
    vendedor_id INTEGER NOT NULL,
    fecha       TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    subtotal    REAL    NOT NULL DEFAULT 0,
    descuento   REAL    NOT NULL DEFAULT 0,
    impuesto    REAL    NOT NULL DEFAULT 0,
    total       REAL    NOT NULL DEFAULT 0,
    metodo_pago TEXT    NOT NULL DEFAULT 'efectivo',
    estado      TEXT    NOT NULL DEFAULT 'pagada',
    notas       TEXT,
    CONSTRAINT fk_fac_cli  FOREIGN KEY (cliente_id)  REFERENCES clientes(cliente_id),
    CONSTRAINT fk_fac_vend FOREIGN KEY (vendedor_id) REFERENCES usuarios(usuario_id),
    CONSTRAINT ck_fac_pago  CHECK (metodo_pago IN ('tarjeta','transferencia','efectivo','nequi','daviplata')),
    CONSTRAINT ck_fac_est   CHECK (estado      IN ('pagada','anulada','pendiente'))
);

-- ============================================================
-- TABLA: detalle_factura
-- ============================================================
CREATE TABLE IF NOT EXISTS detalle_factura (
    detalle_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    factura_id  INTEGER NOT NULL,
    producto_id INTEGER NOT NULL,
    cantidad    INTEGER NOT NULL,
    precio_unit REAL    NOT NULL,
    subtotal    REAL    NOT NULL,
    CONSTRAINT fk_det_fac  FOREIGN KEY (factura_id)  REFERENCES facturas(factura_id),
    CONSTRAINT fk_det_prod FOREIGN KEY (producto_id) REFERENCES productos(producto_id),
    CONSTRAINT ck_det_cant  CHECK (cantidad   > 0),
    CONSTRAINT ck_det_prec  CHECK (precio_unit > 0)
);

-- ============================================================
-- TABLA: movimientos_inventario
-- ============================================================
CREATE TABLE IF NOT EXISTS movimientos_inventario (
    movimiento_id INTEGER PRIMARY KEY AUTOINCREMENT,
    producto_id   INTEGER NOT NULL,
    tipo          TEXT    NOT NULL,
    cantidad      INTEGER NOT NULL,
    stock_antes   INTEGER NOT NULL,
    stock_despues INTEGER NOT NULL,
    motivo        TEXT,
    referencia    TEXT,
    usuario_id    INTEGER NOT NULL,
    fecha         TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_inv_prod FOREIGN KEY (producto_id) REFERENCES productos(producto_id),
    CONSTRAINT fk_inv_user FOREIGN KEY (usuario_id)  REFERENCES usuarios(usuario_id),
    CONSTRAINT ck_inv_tipo CHECK (tipo IN ('entrada','salida','ajuste','venta','devolucion','dano'))
);

-- ============================================================
-- TABLA: sesiones_caja
-- ============================================================
CREATE TABLE IF NOT EXISTS sesiones_caja (
    sesion_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id           INTEGER NOT NULL,
    fecha_apertura       TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_cierre         TEXT,
    monto_inicial        REAL    NOT NULL DEFAULT 0,
    monto_esperado       REAL,
    monto_contado        REAL,
    diferencia           REAL,
    estado               TEXT    NOT NULL DEFAULT 'abierta',
    notas_apertura       TEXT,
    notas_cierre         TEXT,
    CONSTRAINT fk_caja_user FOREIGN KEY (usuario_id) REFERENCES usuarios(usuario_id),
    CONSTRAINT ck_caja_est  CHECK (estado IN ('abierta','cerrada'))
);

-- ============================================================
-- TABLA: movimientos_caja
-- ============================================================
CREATE TABLE IF NOT EXISTS movimientos_caja (
    mov_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    sesion_id  INTEGER NOT NULL,
    tipo       TEXT    NOT NULL,
    concepto   TEXT    NOT NULL,
    monto      REAL    NOT NULL,
    referencia TEXT,
    usuario_id INTEGER NOT NULL,
    fecha      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_mcaja_ses  FOREIGN KEY (sesion_id)  REFERENCES sesiones_caja(sesion_id),
    CONSTRAINT fk_mcaja_user FOREIGN KEY (usuario_id) REFERENCES usuarios(usuario_id),
    CONSTRAINT ck_mcaja_tipo CHECK (tipo IN ('ingreso','egreso'))
);

-- ============================================================
-- TABLA: auditoria
-- ============================================================
CREATE TABLE IF NOT EXISTS auditoria (
    audit_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id  INTEGER,
    accion      TEXT    NOT NULL,
    modulo      TEXT    NOT NULL,
    descripcion TEXT,
    fecha       TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- TABLA: configuracion
-- ============================================================
CREATE TABLE IF NOT EXISTS configuracion (
    config_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    clave          TEXT    NOT NULL UNIQUE,
    valor          TEXT,
    descripcion    TEXT,
    actualizado_en TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- ÍNDICES
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_pedidos_cliente    ON pedidos(cliente_id);
CREATE INDEX IF NOT EXISTS idx_pedidos_producto   ON pedidos(producto_id);
CREATE INDEX IF NOT EXISTS idx_sesiones_usuario   ON sesiones(usuario_id);
CREATE INDEX IF NOT EXISTS idx_facturas_vendedor  ON facturas(vendedor_id);
CREATE INDEX IF NOT EXISTS idx_det_factura        ON detalle_factura(factura_id);
CREATE INDEX IF NOT EXISTS idx_inv_producto       ON movimientos_inventario(producto_id);
CREATE INDEX IF NOT EXISTS idx_inv_fecha          ON movimientos_inventario(fecha);
CREATE INDEX IF NOT EXISTS idx_caja_usuario       ON sesiones_caja(usuario_id);
CREATE INDEX IF NOT EXISTS idx_audit_modulo       ON auditoria(modulo);
CREATE INDEX IF NOT EXISTS idx_audit_fecha        ON auditoria(fecha);
