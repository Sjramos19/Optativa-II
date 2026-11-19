"""TechStore ERP — Servidor web local completo.
Una sola aplicación: login premium + SPA con sidebar minimalista.
Uso: py -3 web_app.py
"""
from __future__ import annotations
import http.cookies, json, sqlite3, threading, urllib.parse, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from database import DEFAULT_DB_PATH, inicializar_db
from etl      import DEFAULT_DATASET, cargar_dataset
from service  import (
    ErrorOperacion, PERMS_SIDEBAR,
    audit, autenticar_usuario, cerrar_sesion, crear_sesion, verificar_sesion,
    tiene_permiso, req_perm,
    resumen, listar_categorias, crear_categoria, editar_categoria,
    listar_proveedores, crear_proveedor, editar_proveedor,
    listar_productos, crear_producto, editar_producto,
    listar_clientes, crear_cliente, editar_cliente,
    listar_movimientos_inv, ajustar_inventario,
    sesion_caja_activa, abrir_caja, cerrar_caja, mov_caja,
    listar_sesiones_caja, movimientos_de_sesion,
    registrar_factura, listar_facturas, detalle_factura_por_id, anular_factura,
    listar_usuarios, crear_usuario, editar_usuario,
    obtener_config, guardar_config,
    consultar_pedidos_cliente, marcar_entregado,
    probar_rechazo_stock_negativo, listar_auditoria,
)
from database import conectar

PORT = 8000

# ═══════════════════════════════════════════════════════════════════════════
# LOGIN PAGE
# ═══════════════════════════════════════════════════════════════════════════
HTML_LOGIN = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TechStore ERP — Iniciar Sesión</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@500;600&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --font:'Plus Jakarta Sans',-apple-system,BlinkMacSystemFont,sans-serif;
  --font-mono:'JetBrains Mono',monospace;
  --blue:#2563EB;--blue-light:#3B82F6;--blue-dark:#1D4ED8;--blue-soft:#EFF6FF;--blue-border:#BFDBFE;
  --bg-deep:#080E1E;--text-main:#0F172A;--text-muted:#64748B;--text-dim:#94A3B8;
  --border:#E2E8F0;
}

html,body{height:100%;font-family:var(--font);background:var(--bg-deep);color:#F8FAFC;overflow-x:hidden}
body{display:flex;align-items:center;justify-content:center;min-height:100vh;padding:1.5rem 1rem;position:relative}

/* ─── AMBIENT GLOW ANIMATIONS ─── */
.ambient-scene{position:fixed;inset:0;overflow:hidden;pointer-events:none;z-index:0}
.glow-orb{position:absolute;border-radius:50%;filter:blur(110px);opacity:.45}
.orb-1{width:620px;height:620px;background:radial-gradient(circle,rgba(37,99,235,.55) 0%,transparent 70%);
  top:-160px;left:-100px;animation:floatOrb1 20s ease-in-out infinite alternate}
.orb-2{width:520px;height:520px;background:radial-gradient(circle,rgba(79,70,229,.4) 0%,transparent 70%);
  bottom:-120px;right:-80px;animation:floatOrb2 24s ease-in-out infinite alternate}
.orb-3{width:400px;height:400px;background:radial-gradient(circle,rgba(6,182,212,.28) 0%,transparent 70%);
  top:45%;left:45%;animation:floatOrb3 18s ease-in-out infinite alternate}

@keyframes floatOrb1{0%{transform:translate(0,0) scale(1)}50%{transform:translate(60px,-30px) scale(1.08)}100%{transform:translate(-30px,45px) scale(0.96)}}
@keyframes floatOrb2{0%{transform:translate(0,0) scale(1)}50%{transform:translate(-50px,40px) scale(1.1)}100%{transform:translate(40px,-20px) scale(0.94)}}
@keyframes floatOrb3{0%{transform:translate(0,0) scale(1)}50%{transform:translate(35px,35px) scale(1.12)}100%{transform:translate(-45px,-30px) scale(0.95)}}

/* Micro Grid */
.grid-mesh{position:fixed;inset:0;background-image:radial-gradient(rgba(255,255,255,0.08) 1px,transparent 1px);
  background-size:26px 26px;pointer-events:none;z-index:1;opacity:.65}

/* ─── CONTAINER PRINCIPAL SHELL (COMPACTO, ELEGANTE & CUADRADO) ─── */
.login-shell{position:relative;z-index:10;width:100%;max-width:890px;
  background:transparent;border-radius:18px;overflow:hidden;
  border:1px solid rgba(59,130,246,0.32);
  box-shadow:0 30px 80px -15px rgba(0,0,0,0.85),0 0 50px -10px rgba(37,99,235,0.28);
  display:grid;grid-template-columns:1fr 1fr;
  animation:shellIn .45s cubic-bezier(0.16,1,0.3,1)}

@keyframes shellIn{from{opacity:0;transform:translateY(14px) scale(.988)}to{opacity:1;transform:translateY(0) scale(1)}}

/* ─── FONDO CONTINUO INTEGRADO (SIN LÍNEA RECTA NI CORTES DE COLOR) ─── */
.shell-backdrop{position:absolute;inset:0;pointer-events:none;z-index:1;
  background:linear-gradient(90deg,#060B1A 0%,#060B1A 46.5%,#0B193C 48%,#1E3A8A 49.2%,#2563EB 50%,#60A5FA 50.8%,#BFDBFE 52%,#FFFFFF 53.5%,#FFFFFF 100%)}

/* ─── LA DIVISIÓN SON LOS PUNTITOS DESVANECIDOS (FINOS, COMPACTOS Y ELEGANTES: 52px) ─── */
.halftone-divider{position:absolute;top:0;bottom:0;left:50%;transform:translateX(-50%);
  width:52px;pointer-events:none;z-index:3;display:flex;align-items:center;justify-content:center;
  overflow:hidden;
  mask-image:linear-gradient(90deg,transparent 0%,rgba(0,0,0,0.95) 15%,rgba(0,0,0,0.95) 85%,transparent 100%);
  -webkit-mask-image:linear-gradient(90deg,transparent 0%,rgba(0,0,0,0.95) 15%,rgba(0,0,0,0.95) 85%,transparent 100%);
  animation:seamBreathe 6s ease-in-out infinite alternate}

.halftone-glow{position:absolute;inset:0;
  background:radial-gradient(ellipse at center,rgba(37,99,235,0.18) 0%,rgba(59,130,246,0.05) 60%,transparent 85%);
  filter:blur(8px)}

.halftone-svg{position:absolute;inset:0;width:100%;height:100%;
  filter:drop-shadow(0 0 2px rgba(59,130,246,0.3))}

@keyframes seamBreathe{0%{opacity:.85;transform:translateX(-50%) scaleX(.98)}50%{opacity:1;transform:translateX(-50%) scaleX(1.03)}100%{opacity:.9;transform:translateX(-50%) scaleX(1)}}

/* ─── LEFT: BRAND HERO (TRANSPARENTE SOBRE EL FONDO CONTINUO) ─── */
.hero-col{padding:2.2rem 2.4rem 2.2rem 2.2rem;
  background:transparent;
  display:flex;flex-direction:column;justify-content:space-between;
  position:relative;color:#F8FAFC;z-index:5}

/* Brand Badge */
.brand-badge{display:flex;align-items:center;gap:.85rem;margin-bottom:1.2rem}
.brand-logo{width:44px;height:44px;background:linear-gradient(135deg,var(--blue),#4F46E5);
  border-radius:12px;display:flex;align-items:center;justify-content:center;
  box-shadow:0 8px 20px rgba(37,99,235,.45);flex-shrink:0;position:relative}
.brand-logo::after{content:'';position:absolute;inset:-1.5px;border-radius:13px;
  background:linear-gradient(135deg,rgba(255,255,255,0.35),transparent);pointer-events:none}
.brand-logo svg{width:22px;height:22px;stroke:#fff;fill:none;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}

.brand-text h1{font-size:1.35rem;font-weight:800;letter-spacing:-0.03em;color:#fff;line-height:1.15}
.brand-text h1 span{background:linear-gradient(90deg,#60A5FA,#93C5FD);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.brand-tag{display:inline-block;font-size:.62rem;font-weight:700;letter-spacing:.08em;
  text-transform:uppercase;color:#38BDF8;background:rgba(56,189,248,.14);
  padding:.12rem .48rem;border-radius:4px;margin-top:.15rem;border:1px solid rgba(56,189,248,.25)}

.hero-main h2{font-size:1.35rem;font-weight:800;letter-spacing:-.03em;color:#F8FAFC;line-height:1.25;margin-bottom:.5rem}
.hero-main p{color:#94A3B8;font-size:.82rem;line-height:1.5;margin-bottom:1.1rem}

/* Live Status */
.status-pill{display:inline-flex;align-items:center;gap:.55rem;background:rgba(16,185,129,.12);
  border:1px solid rgba(16,185,129,.28);padding:.28rem .75rem;border-radius:20px;
  font-size:.72rem;font-weight:600;color:#34D399;margin-bottom:1.3rem}
.radar-beacon{width:7px;height:7px;background:#10B981;border-radius:50%;position:relative}
.radar-beacon::after{content:'';position:absolute;inset:-3px;border-radius:50%;
  background:rgba(16,185,129,.5);animation:radarPulse 1.8s infinite}
@keyframes radarPulse{0%{transform:scale(1);opacity:1}100%{transform:scale(2.6);opacity:0}}

/* Feature List (High-Tech Cards) */
.feature-stack{display:flex;flex-direction:column;gap:.55rem}
.feat-row{display:flex;align-items:center;justify-content:space-between;background:rgba(255,255,255,.035);
  border:1px solid rgba(255,255,255,.07);padding:.5rem .75rem;border-radius:10px;
  transition:all .18s ease}
.feat-row:hover{background:rgba(255,255,255,.065);border-color:rgba(59,130,246,.4);transform:translateX(3px)}
.feat-left{display:flex;align-items:center;gap:.75rem}
.feat-ico{width:30px;height:30px;background:rgba(37,99,235,.18);border:1px solid rgba(37,99,235,.32);
  border-radius:8px;display:flex;align-items:center;justify-content:center;flex-shrink:0;color:#60A5FA}
.feat-ico.green{background:rgba(16,185,129,.15);border-color:rgba(16,185,129,.3);color:#34D399}
.feat-ico.purple{background:rgba(139,92,246,.15);border-color:rgba(139,92,246,.3);color:#A78BFA}
.feat-ico.amber{background:rgba(245,158,11,.15);border-color:rgba(245,158,11,.3);color:#FBBF24}
.feat-ico svg{width:15px;height:15px;stroke:currentColor;fill:none;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.feat-text{font-size:.78rem;font-weight:600;color:#F1F5F9}
.feat-desc{font-size:.68rem;color:#94A3B8;font-weight:400}
.feat-chip{font-size:.58rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;
  padding:.12rem .4rem;border-radius:4px;background:rgba(255,255,255,.06);color:#94A3B8}

.hero-footer{margin-top:1.3rem;display:flex;align-items:center;justify-content:space-between;font-size:.68rem;color:#64748B}
.security-stamp{display:inline-flex;align-items:center;gap:.35rem;color:#38BDF8;font-weight:600}
.security-stamp svg{width:12px;height:12px;stroke:currentColor;fill:none;stroke-width:2}

/* ─── RIGHT: FORM & CUADRITO AZUL INTEGRADO ─── */
.form-col{padding:2.2rem 2.2rem 2.2rem 2.6rem;
  background:transparent;
  display:flex;flex-direction:column;justify-content:center;color:var(--text-main);
  position:relative;z-index:5}

.form-hdr{margin-bottom:1.15rem}
.form-hdr h3{font-size:1.45rem;font-weight:800;letter-spacing:-.03em;color:var(--text-main);margin-bottom:.25rem}
.form-hdr p{font-size:.82rem;color:var(--text-muted)}

.form-group{margin-bottom:.85rem;position:relative}
.form-label-row{display:flex;justify-content:space-between;align-items:center;margin-bottom:.3rem}
.form-label{display:block;font-size:.68rem;font-weight:700;letter-spacing:.08em;
  text-transform:uppercase;color:#475569}
.caps-warning{display:none;font-size:.65rem;font-weight:700;color:#D97706;background:#FEF3C7;
  padding:.1rem .45rem;border-radius:4px;border:1px solid #FDE68A}
.caps-warning.show{display:inline-block}

.input-wrap{position:relative;display:flex;align-items:center}
.input-icon{position:absolute;left:.85rem;color:#94A3B8;pointer-events:none;
  display:flex;align-items:center;transition:color .15s}
.input-icon svg{width:16px;height:16px;stroke:currentColor;fill:none;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}

.form-input{width:100%;height:42px;padding:0 2.5rem 0 2.6rem;
  background:#FFFFFF;border:1.5px solid #CBD5E1;border-radius:9px;
  font-family:var(--font);font-size:.88rem;color:var(--text-main);outline:none;
  transition:all .18s cubic-bezier(0.16,1,0.3,1);box-shadow:0 1px 2px rgba(15,23,42,0.03)}
.form-input::placeholder{color:#94A3B8}
.form-input:focus{background:#FFFFFF;border-color:var(--blue);
  box-shadow:0 0 0 3.5px rgba(37,99,235,0.14)}
.form-input:focus + .input-icon{color:var(--blue)}

/* Botón ojo mostrar/ocultar contraseña */
.pwd-toggle-btn{position:absolute;right:.75rem;top:50%;transform:translateY(-50%);
  background:transparent;border:none;color:#94A3B8;cursor:pointer;padding:.25rem;
  display:flex;align-items:center;justify-content:center;border-radius:5px;transition:color .15s}
.pwd-toggle-btn:hover{color:var(--blue)}
.pwd-toggle-btn svg{width:17px;height:17px;stroke:currentColor;fill:none;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}

/* Sub row: Remember me & Forgot Password */
.form-sub-row{display:flex;align-items:center;justify-content:space-between;
  margin-top:-.15rem;margin-bottom:.85rem;font-size:.78rem}
.remember-label{display:inline-flex;align-items:center;gap:.45rem;color:#475569;
  font-weight:500;cursor:pointer;user-select:none}
.remember-label input[type="checkbox"]{width:15px;height:15px;accent-color:var(--blue);cursor:pointer}
.forgot-link{color:var(--blue);font-weight:600;text-decoration:none;transition:color .15s}
.forgot-link:hover{color:var(--blue-dark);text-decoration:underline}

/* Submit Button */
.btn-submit{width:100%;height:42px;margin-top:.2rem;
  background:linear-gradient(135deg,var(--blue) 0%,var(--blue-dark) 100%);
  border:none;border-radius:9px;color:#fff;font-family:var(--font);font-size:.9rem;font-weight:700;
  cursor:pointer;display:flex;align-items:center;justify-content:center;gap:.55rem;
  box-shadow:0 4px 14px rgba(37,99,235,0.35);position:relative;overflow:hidden;
  transition:all .18s cubic-bezier(0.16,1,0.3,1)}
.btn-submit:hover{transform:translateY(-1.5px);box-shadow:0 7px 20px rgba(37,99,235,0.45)}
.btn-submit:active{transform:translateY(0)}
.btn-submit svg{width:16px;height:16px;stroke:currentColor;fill:none;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}

/* Error Alert */
.alert-box{background:#FEF2F2;border:1.5px solid #FECACA;
  color:#DC2626;border-radius:9px;padding:.55rem .85rem;font-size:.82rem;
  display:none;align-items:center;gap:.55rem;margin-bottom:.85rem;
  animation:alertSlide .2s ease}
.alert-box.show{display:flex}
@keyframes alertSlide{from{opacity:0;transform:translateY(-5px)}to{opacity:1;transform:translateY(0)}}
.alert-box svg{width:15px;height:15px;stroke:currentColor;fill:none;stroke-width:2;flex-shrink:0}

/* ─── CUADRITO AZULITO BIEN INTEGRADO (ROLES DEMO) ─── */
.demo-card-box{background:#F0F7FF;border:1.5px solid var(--blue-border);border-radius:12px;
  padding:.75rem .85rem;margin-top:1rem;box-shadow:0 2px 8px rgba(37,99,235,0.04)}

.demo-box-hdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:.55rem}
.demo-badge{font-size:.62rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
  background:#DBEAFE;color:#1D4ED8;padding:.15rem .5rem;border-radius:4px;
  border:1px solid #93C5FD}
.demo-tip{font-size:.7rem;color:#64748B;font-weight:500}

.demo-grid{display:grid;grid-template-columns:1fr 1fr;gap:.4rem}
.role-card{background:#FFFFFF;border:1px solid #DBEAFE;border-radius:8px;
  padding:.38rem .55rem;cursor:pointer;display:flex;align-items:center;justify-content:space-between;
  transition:all .15s ease;user-select:none;box-shadow:0 1px 2px rgba(15,23,42,0.03);position:relative}
.role-card:hover{background:#EFF6FF;border-color:var(--blue);transform:translateY(-1px);
  box-shadow:0 3px 8px rgba(37,99,235,0.12)}
.role-card.selected{background:#EFF6FF;border-color:var(--blue);box-shadow:0 0 0 2px var(--blue)}

.role-info{display:flex;align-items:center;gap:.45rem;min-width:0}
.role-avatar{width:20px;height:20px;border-radius:5px;display:flex;align-items:center;justify-content:center;
  font-size:.62rem;font-weight:800;color:#fff;background:var(--blue);flex-shrink:0}
.role-meta{display:flex;flex-direction:column;gap:.05rem;min-width:0}
.role-name{font-size:.75rem;font-weight:700;color:var(--text-main);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.role-badge{font-size:.55rem;font-weight:700;letter-spacing:.05em;text-transform:uppercase;
  display:inline-block;padding:.04rem .28rem;border-radius:3px;width:fit-content}

.rb-superadmin{background:#FEE2E2;color:#B91C1C;border:1px solid #FECACA}
.rb-admin     {background:#DBEAFE;color:#1D4ED8;border:1px solid #BFDBFE}
.rb-supervisor{background:#D1FAE5;color:#047857;border:1px solid #A7F3D0}
.rb-vendedor  {background:#F3E8FF;color:#7E22CE;border:1px solid #E9D5FF}
.rb-cajero    {background:#FEF3C7;color:#B45309;border:1px solid #FDE68A}
.rb-bodeguero {background:#E0F2FE;color:#0369A1;border:1px solid #BAE6FD}
.rb-contador  {background:#FCE7F3;color:#BE185D;border:1px solid #FBCFE8}
.rb-consultor {background:#F1F5F9;color:#475569;border:1px solid #E2E8F0}

.role-pass{font-family:var(--font-mono);font-size:.68rem;color:var(--blue);font-weight:600}

/* ─── MODAL RECUPERAR CONTRASEÑA ─── */
.modal-backdrop{position:fixed;inset:0;background:rgba(8,14,30,0.72);
  backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);
  z-index:999;display:none;align-items:center;justify-content:center;
  padding:1rem;animation:modalFadeIn .2s ease}
.modal-backdrop.show{display:flex}
@keyframes modalFadeIn{from{opacity:0}to{opacity:1}}

.modal-card{background:#FFFFFF;border-radius:14px;width:100%;max-width:440px;
  box-shadow:0 25px 60px -12px rgba(0,0,0,0.35),0 0 0 1px rgba(15,23,42,0.08);
  overflow:hidden;animation:cardPop .25s cubic-bezier(0.16,1,0.3,1);
  color:var(--text-main)}
@keyframes cardPop{from{opacity:0;transform:scale(0.94) translateY(10px)}to{opacity:1;transform:scale(1) translateY(0)}}

.modal-hdr{padding:1.1rem 1.3rem;background:#F8FAFC;border-bottom:1px solid #E2E8F0;
  display:flex;align-items:center;gap:.8rem;position:relative}
.modal-ico{width:36px;height:36px;border-radius:9px;background:#EFF6FF;
  border:1px solid #BFDBFE;display:flex;align-items:center;justify-content:center;
  color:var(--blue);flex-shrink:0}
.modal-ico svg{width:18px;height:18px;stroke:currentColor;fill:none;stroke-width:2}
.modal-hdr h4{font-size:1.02rem;font-weight:800;color:#0F172A;line-height:1.2}
.modal-hdr p{font-size:.72rem;color:#64748B}
.modal-close{position:absolute;right:1rem;top:.9rem;background:transparent;border:none;
  font-size:1.4rem;line-height:1;color:#94A3B8;cursor:pointer;padding:.2rem;
  border-radius:6px;transition:color .15s}
.modal-close:hover{color:#0F172A}

.modal-body{padding:1.2rem 1.3rem;font-size:.82rem;line-height:1.5;color:#334155}
.modal-info-box{background:#EFF6FF;border:1px solid #BFDBFE;border-radius:8px;
  padding:.7rem .8rem;margin-bottom:.9rem;font-size:.78rem;color:#1E40AF}
.modal-field{margin-bottom:.85rem}
.modal-field label{display:block;font-size:.7rem;font-weight:700;color:#475569;margin-bottom:.3rem}
.modal-input{width:100%;height:38px;padding:0 .85rem;background:#FFFFFF;border:1.5px solid #CBD5E1;
  border-radius:8px;font-family:var(--font);font-size:.85rem;color:var(--text-main);outline:none;
  transition:border .15s}
.modal-input:focus{border-color:var(--blue);box-shadow:0 0 0 3px rgba(37,99,235,0.15)}

.modal-tip{display:flex;gap:.5rem;align-items:flex-start;
  background:#F8FAFC;border:1px solid #E2E8F0;border-radius:8px;
  padding:.6rem .75rem;font-size:.73rem;color:#64748B;margin-bottom:.4rem}
.modal-tip svg{width:15px;height:15px;stroke:var(--blue);fill:none;stroke-width:2;flex-shrink:0;margin-top:1px}

.modal-msg{display:none;padding:.6rem .8rem;border-radius:8px;font-size:.78rem;
  font-weight:600;margin-top:.6rem;animation:alertSlide .2s ease}
.modal-msg.success{display:block;background:#ECFDF5;border:1px solid #A7F3D0;color:#065F46}
.modal-msg.error{display:block;background:#FEF2F2;border:1px solid #FECACA;color:#DC2626}

.modal-ftr{padding:.85rem 1.3rem;background:#F8FAFC;border-top:1px solid #E2E8F0;
  display:flex;justify-content:space-between;align-items:center;gap:.55rem}
.btn-modal-demo{padding:.4rem .75rem;border-radius:7px;border:1px solid #93C5FD;
  background:#EFF6FF;font-family:var(--font);font-size:.76rem;font-weight:700;
  color:var(--blue);cursor:pointer;transition:all .15s}
.btn-modal-demo:hover{background:#DBEAFE}
.modal-ftr-actions{display:flex;gap:.5rem}
.btn-modal-sec{padding:.4rem .85rem;border-radius:7px;border:1px solid #CBD5E1;
  background:#FFFFFF;font-family:var(--font);font-size:.8rem;font-weight:600;
  color:#475569;cursor:pointer;transition:all .15s}
.btn-modal-sec:hover{background:#F1F5F9;color:#0F172A}
.btn-modal-pri{padding:.4rem 1rem;border-radius:7px;border:none;
  background:var(--blue);font-family:var(--font);font-size:.8rem;font-weight:700;
  color:#FFFFFF;cursor:pointer;transition:all .15s;box-shadow:0 2px 7px rgba(37,99,235,0.25)}
.btn-modal-pri:hover{background:var(--blue-dark);transform:translateY(-1px)}

@media(max-width:880px){
  .login-shell{grid-template-columns:1fr;max-width:440px}
  .hero-col{display:none}
  .halftone-divider{display:none}
  .shell-backdrop{background:#FFFFFF}
  .form-col{padding:2rem 1.5rem}
}
</style>
</head>
<body>

<div class="ambient-scene">
  <div class="glow-orb orb-1"></div>
  <div class="glow-orb orb-2"></div>
  <div class="glow-orb orb-3"></div>
</div>
<div class="grid-mesh"></div>

<main class="login-shell">
  <!-- FONDO CONTINUO INTEGRADO (SIN LÍNEA RECTA NI CORTES) -->
  <div class="shell-backdrop" aria-hidden="true"></div>

  <!-- LA DIVISIÓN SON LOS PUNTITOS DESVANECIDOS (FINOS, DELICADOS Y PRECISOS: 52px) -->
  <div class="halftone-divider" aria-hidden="true">
    <div class="halftone-glow"></div>
    <svg class="halftone-svg" width="52" height="100%" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <pattern id="halftone-pat-ext" width="52" height="18" patternUnits="userSpaceOnUse">
          <!-- Fila 1 (y=4.5): micro-puntos delicados graduados con apex sutil en el centro -->
          <circle cx="5"  cy="4.5" r="0.65" fill="#38BDF8" opacity="0.30"/>
          <circle cx="13" cy="4.5" r="1.05" fill="#60A5FA" opacity="0.55"/>
          <circle cx="21" cy="4.5" r="1.55" fill="#3B82F6" opacity="0.80"/>
          <circle cx="29" cy="4.5" r="1.95" fill="#2563EB" opacity="0.95"/>
          <circle cx="37" cy="4.5" r="1.40" fill="#60A5FA" opacity="0.70"/>
          <circle cx="45" cy="4.5" r="0.85" fill="#93C5FD" opacity="0.40"/>
          <!-- Fila 2 (y=13.5): intercalada hexagonal fina -->
          <circle cx="9"  cy="13.5" r="0.80" fill="#38BDF8" opacity="0.40"/>
          <circle cx="17" cy="13.5" r="1.30" fill="#60A5FA" opacity="0.70"/>
          <circle cx="25" cy="13.5" r="1.85" fill="#2563EB" opacity="0.92"/>
          <circle cx="33" cy="13.5" r="1.75" fill="#2563EB" opacity="0.88"/>
          <circle cx="41" cy="13.5" r="1.10" fill="#60A5FA" opacity="0.55"/>
          <circle cx="48" cy="13.5" r="0.65" fill="#93C5FD" opacity="0.30"/>
        </pattern>
      </defs>
      <rect width="52" height="100%" fill="url(#halftone-pat-ext)"/>
    </svg>
  </div>

  <!-- COLUMNA IZQUIERDA: HERO ENTERPRISE AZUL -->
  <section class="hero-col">
    <div>
      <div class="brand-badge">
        <div class="brand-logo">
          <svg viewBox="0 0 24 24"><path d="M20 7H4a2 2 0 00-2 2v6a2 2 0 002 2h16a2 2 0 002-2V9a2 2 0 00-2-2z"/><path d="M16 21V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v16"/></svg>
        </div>
        <div class="brand-text">
          <h1>TechStore <span>ERP</span></h1>
          <span class="brand-tag">Enterprise v2.4</span>
        </div>
      </div>

      <div class="hero-main">
        <h2>Gestión Comercial, POS & Control de Inventario</h2>
        <p>Ecosistema corporativo integrado para administración de ventas, kardex en tiempo real, arqueo de caja y auditoría financiera.</p>
        <div class="status-pill">
          <span class="radar-beacon"></span>
          Sistema en Línea &bull; Entorno Local Seguro
        </div>
      </div>

      <div class="feature-stack">
        <div class="feat-row">
          <div class="feat-left">
            <div class="feat-ico green"><svg viewBox="0 0 24 24"><circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.68 13.39a2 2 0 001.98 1.61h9.72a2 2 0 001.98-1.61L23 6H6"/></svg></div>
            <div><div class="feat-text">Punto de Venta POS & Facturación</div><div class="feat-desc">Descuento automático de stock e impresión rápida</div></div>
          </div>
          <span class="feat-chip">POS</span>
        </div>
        <div class="feat-row">
          <div class="feat-left">
            <div class="feat-ico"><svg viewBox="0 0 24 24"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg></div>
            <div><div class="feat-text">Kardex & Control de Existencias</div><div class="feat-desc">Trazabilidad de movimientos y alertas de stock bajo</div></div>
          </div>
          <span class="feat-chip">KARDEX</span>
        </div>
        <div class="feat-row">
          <div class="feat-left">
            <div class="feat-ico amber"><svg viewBox="0 0 24 24"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg></div>
            <div><div class="feat-text">Caja, Arqueo & Movimientos</div><div class="feat-desc">Control de turnos, ingresos, egresos y cuadre exacto</div></div>
          </div>
          <span class="feat-chip">CAJA</span>
        </div>
        <div class="feat-row">
          <div class="feat-left">
            <div class="feat-ico purple"><svg viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg></div>
            <div><div class="feat-text">Seguridad RBAC & Auditoría</div><div class="feat-desc">8 roles empresariales con permisos centralizados</div></div>
          </div>
          <span class="feat-chip">RBAC</span>
        </div>
      </div>
    </div>

    <div class="hero-footer">
      <span>TechStore Colombia &copy; 2026</span>
      <span class="security-stamp">
        <svg viewBox="0 0 24 24"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg>
        Cifrado Local Seguro
      </span>
    </div>
  </section>

  <!-- COLUMNA DERECHA: FORMULARIO Y CUADRITO AZULITO -->
  <section class="form-col">
    <div class="form-hdr">
      <h3>Iniciar Sesión</h3>
      <p>Ingresa tus credenciales autorizadas para acceder</p>
    </div>

    <div class="alert-box" id="err-box">
      <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
      <span id="err-txt"></span>
    </div>

    <form onsubmit="doLogin(event)">
      <div class="form-group">
        <div class="form-label-row">
          <label class="form-label">Usuario</label>
        </div>
        <div class="input-wrap">
          <span class="input-icon"><svg viewBox="0 0 24 24"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg></span>
          <input type="text" id="u" class="form-input" placeholder="Ingresa tu usuario" required autocomplete="username">
        </div>
      </div>

      <div class="form-group">
        <div class="form-label-row">
          <label class="form-label">Contraseña</label>
          <span id="caps-warning" class="caps-warning">⇪ Bloq Mayús activo</span>
        </div>
        <div class="input-wrap">
          <span class="input-icon"><svg viewBox="0 0 24 24"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg></span>
          <input type="password" id="p" class="form-input" placeholder="••••••••" required autocomplete="current-password" onkeyup="checkCaps(event)" onkeydown="checkCaps(event)">
          <button type="button" class="pwd-toggle-btn" id="btn-toggle-pwd" onclick="togglePasswordVisibility()" title="Mostrar u ocultar contraseña">
            <svg id="pwd-eye-icon" viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
          </button>
        </div>
      </div>

      <div class="form-sub-row">
        <label class="remember-label" title="Recordar usuario en este navegador">
          <input type="checkbox" id="remember-me" checked>
          <span>Recordarme</span>
        </label>
        <a href="javascript:void(0)" class="forgot-link" onclick="openForgotModal()">¿Olvidaste tu contraseña?</a>
      </div>

      <button type="submit" class="btn-submit" id="btn-in">
        <span>Ingresar al Sistema</span>
        <svg viewBox="0 0 24 24"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
      </button>
    </form>

    <!-- CUADRITO AZULITO BIEN ORGANIZADO -->
    <div class="demo-card-box">
      <div class="demo-box-hdr">
        <span class="demo-badge">ACCESO DEMO RÁPIDO</span>
        <span class="demo-tip">Selecciona un rol para probar</span>
      </div>
      <div class="demo-grid" id="demo-roles-box">
        <div class="role-card" onclick="pick('superadmin','super123',this)">
          <div class="role-info">
            <div class="role-avatar" style="background:#DC2626">S</div>
            <div class="role-meta">
              <span class="role-name">superadmin</span>
              <span class="role-badge rb-superadmin">Super</span>
            </div>
          </div>
          <span class="role-pass">super123</span>
        </div>
        <div class="role-card" onclick="pick('admin','admin123',this)">
          <div class="role-info">
            <div class="role-avatar" style="background:#2563EB">A</div>
            <div class="role-meta">
              <span class="role-name">admin</span>
              <span class="role-badge rb-admin">Admin</span>
            </div>
          </div>
          <span class="role-pass">admin123</span>
        </div>
        <div class="role-card" onclick="pick('supervisor1','super123',this)">
          <div class="role-info">
            <div class="role-avatar" style="background:#059669">SP</div>
            <div class="role-meta">
              <span class="role-name">supervisor1</span>
              <span class="role-badge rb-supervisor">Supervisor</span>
            </div>
          </div>
          <span class="role-pass">super123</span>
        </div>
        <div class="role-card" onclick="pick('vendedor1','vend123',this)">
          <div class="role-info">
            <div class="role-avatar" style="background:#7C3AED">V</div>
            <div class="role-meta">
              <span class="role-name">vendedor1</span>
              <span class="role-badge rb-vendedor">Vendedor</span>
            </div>
          </div>
          <span class="role-pass">vend123</span>
        </div>
        <div class="role-card" onclick="pick('cajero1','caj123',this)">
          <div class="role-info">
            <div class="role-avatar" style="background:#D97706">C</div>
            <div class="role-meta">
              <span class="role-name">cajero1</span>
              <span class="role-badge rb-cajero">Cajero</span>
            </div>
          </div>
          <span class="role-pass">caj123</span>
        </div>
        <div class="role-card" onclick="pick('bodeguero1','bod123',this)">
          <div class="role-info">
            <div class="role-avatar" style="background:#0284C7">B</div>
            <div class="role-meta">
              <span class="role-name">bodeguero1</span>
              <span class="role-badge rb-bodeguero">Bodeguero</span>
            </div>
          </div>
          <span class="role-pass">bod123</span>
        </div>
        <div class="role-card" onclick="pick('contador1','cont123',this)">
          <div class="role-info">
            <div class="role-avatar" style="background:#DB2777">CT</div>
            <div class="role-meta">
              <span class="role-name">contador1</span>
              <span class="role-badge rb-contador">Contador</span>
            </div>
          </div>
          <span class="role-pass">cont123</span>
        </div>
        <div class="role-card" onclick="pick('consultor1','cons123',this)">
          <div class="role-info">
            <div class="role-avatar" style="background:#475569">CS</div>
            <div class="role-meta">
              <span class="role-name">consultor1</span>
              <span class="role-badge rb-consultor">Consultor</span>
            </div>
          </div>
          <span class="role-pass">cons123</span>
        </div>
      </div>
    </div>
  </section>
</main>

<!-- MODAL ¿OLVIDASTE TU CONTRASEÑA? -->
<div class="modal-backdrop" id="forgot-modal" onclick="if(event.target===this)closeForgotModal()">
  <div class="modal-card">
    <div class="modal-hdr">
      <div class="modal-ico">
        <svg viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
      </div>
      <div>
        <h4>Recuperación de Contraseña</h4>
        <p>Políticas de Acceso y Seguridad RBAC</p>
      </div>
      <button type="button" class="modal-close" onclick="closeForgotModal()" aria-label="Cerrar">&times;</button>
    </div>
    <div class="modal-body">
      <div class="modal-info-box">
        <strong>Seguridad Corporativa RBAC:</strong> Por políticas de auditoría, el restablecimiento de credenciales es administrado de forma centralizada por el <strong>Superadministrador</strong>.
      </div>
      <div class="modal-field">
        <label>Usuario o Correo Registrado</label>
        <input type="text" id="forgot-usr" class="modal-input" placeholder="Ej: admin o tu nombre de usuario">
      </div>
      <div class="modal-tip">
        <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
        <span><strong>Acceso Inmediato Demo:</strong> Para pruebas locales, puedes usar de inmediato cualquiera de los <strong>8 roles</strong> precargados.</span>
      </div>
      <div class="modal-msg" id="forgot-msg"></div>
    </div>
    <div class="modal-ftr">
      <button type="button" class="btn-modal-demo" onclick="useAdminQuick()">⚡ Usar Admin Demo</button>
      <div class="modal-ftr-actions">
        <button type="button" class="btn-modal-sec" onclick="closeForgotModal()">Cerrar</button>
        <button type="button" class="btn-modal-pri" onclick="submitForgot()">Notificar al Admin</button>
      </div>
    </div>
  </div>
</div>

<script>
window.addEventListener('DOMContentLoaded', () => {
  try {
    const saved = localStorage.getItem('techstore_rem_usr');
    if(saved){
      document.getElementById('u').value = saved;
      document.getElementById('remember-me').checked = true;
    }
  }catch(e){}
});

function pick(usr, pwd, el){
  document.getElementById('u').value = usr;
  document.getElementById('p').value = pwd;
  document.querySelectorAll('.role-card').forEach(c => c.classList.remove('selected'));
  if(el) el.classList.add('selected');
}

function checkCaps(e){
  const warning = document.getElementById('caps-warning');
  if(e.getModifierState && e.getModifierState('CapsLock')){
    warning.classList.add('show');
  } else {
    warning.classList.remove('show');
  }
}

function togglePasswordVisibility(){
  const pInput = document.getElementById('p');
  const icon = document.getElementById('pwd-eye-icon');
  if(pInput.type === 'password'){
    pInput.type = 'text';
    icon.innerHTML = '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>';
  } else {
    pInput.type = 'password';
    icon.innerHTML = '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>';
  }
}

function openForgotModal(){
  const cur = document.getElementById('u').value.trim();
  if(cur) document.getElementById('forgot-usr').value = cur;
  const msg = document.getElementById('forgot-msg');
  msg.className = 'modal-msg';
  msg.textContent = '';
  document.getElementById('forgot-modal').classList.add('show');
}

function closeForgotModal(){
  document.getElementById('forgot-modal').classList.remove('show');
}

function useAdminQuick(){
  closeForgotModal();
  document.getElementById('u').value = 'admin';
  document.getElementById('p').value = 'admin123';
  const adminCard = document.querySelectorAll('.role-card')[1];
  if(adminCard) adminCard.classList.add('selected');
}

function submitForgot(){
  const usr = document.getElementById('forgot-usr').value.trim();
  const msg = document.getElementById('forgot-msg');
  if(!usr){
    msg.className = 'modal-msg error';
    msg.textContent = 'Por favor ingresa un usuario o correo registrado.';
    return;
  }
  msg.className = 'modal-msg success';
  msg.innerHTML = '<strong>Solicitud Registrada:</strong> Se ha notificado al Superadministrador para restablecer la contraseña de <u>' + usr + '</u>. Mientras tanto, puedes usar las credenciales del panel demo.';
}

async function doLogin(e){
  e.preventDefault();
  const btn = document.getElementById('btn-in');
  const err = document.getElementById('err-box');
  const etx = document.getElementById('err-txt');
  const usr = document.getElementById('u').value.trim();
  const pwd = document.getElementById('p').value;
  btn.innerHTML = '<span>Verificando...</span>';
  btn.disabled = true;
  err.classList.remove('show');

  try{
    const r = await fetch('/api/login',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({ username: usr, password: pwd })
    });
    const d = await r.json();
    if(r.ok){
      try {
        const rem = document.getElementById('remember-me');
        if(rem && rem.checked){
          localStorage.setItem('techstore_rem_usr', usr);
        } else {
          localStorage.removeItem('techstore_rem_usr');
        }
      }catch(e){}

      btn.innerHTML = '<span>¡Acceso autorizado! Redirigiendo...</span>';
      setTimeout(() => location.href = '/app', 250);
    } else {
      etx.textContent = d.error || 'Credenciales no válidas.';
      err.classList.add('show');
      btn.innerHTML = '<span>Ingresar al Sistema</span><svg viewBox="0 0 24 24"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>';
      btn.disabled = false;
    }
  }catch(ex){
    etx.textContent = 'Error de conexión con el servidor.';
    err.classList.add('show');
    btn.innerHTML = '<span>Ingresar al Sistema</span><svg viewBox="0 0 24 24"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>';
    btn.disabled = false;
  }
}
</script>
</body>
</html>"""

# ═══════════════════════════════════════════════════════════════════════════
# APP PRINCIPAL SPA
# ═══════════════════════════════════════════════════════════════════════════
HTML_APP = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TechStore ERP</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@500;600&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --navy:#0F172A; --slate:#1E293B; --slate2:#334155;
  --blue:#2563EB; --blue-d:#1D4ED8; --blue-lt:#EFF6FF; --blue-b:rgba(37,99,235,.12);
  --green:#10B981; --amber:#F59E0B; --red:#EF4444; --purple:#8B5CF6;
  --bg:#F8FAFC; --card:#FFFFFF; --border:#E2E8F0; --border2:#CBD5E1;
  --text:#0F172A; --muted:#64748B; --light:#94A3B8;
  --shadow:0 1px 3px rgba(0,0,0,.06),0 1px 2px rgba(0,0,0,.04);
  --shadow-md:0 4px 6px -1px rgba(0,0,0,.06),0 2px 4px -1px rgba(0,0,0,.03);
  --shadow-lg:0 10px 15px -3px rgba(0,0,0,.07),0 4px 6px -2px rgba(0,0,0,.03);
  --sb-w:260px; --sb-w-mini:74px; --hdr:62px; --r:12px;
  --font:'Plus Jakarta Sans',-apple-system,BlinkMacSystemFont,sans-serif
}

html,body{height:100%;font-family:var(--font);background:var(--bg);color:var(--text);letter-spacing:-0.01em}
body{display:flex;min-height:100vh;overflow:hidden}

/* ─── SIDEBAR PREMIUM LIGHT INTEGRADO ─────────────────────────────────── */
.sidebar{width:var(--sb-w);background:#FFFFFF;border-right:1px solid var(--border);
  display:flex;flex-direction:column;flex-shrink:0;height:100vh;overflow:hidden;
  transition:width .28s cubic-bezier(0.16,1,0.3,1),box-shadow .2s;
  box-shadow:2px 0 16px rgba(15,23,42,0.03);z-index:20}
.sidebar.mini{width:var(--sb-w-mini)}

.sb-top{display:flex;align-items:center;gap:.75rem;padding:1.1rem 1rem .9rem;
  border-bottom:1px solid var(--border);flex-shrink:0;min-height:64px;overflow:hidden;
  background:#FFFFFF;position:relative}
.sb-logo-icon{width:36px;height:36px;background:linear-gradient(135deg,var(--blue),#1D4ED8);
  border-radius:10px;display:flex;align-items:center;justify-content:center;flex-shrink:0;
  box-shadow:0 4px 12px rgba(37,99,235,.25);cursor:pointer;transition:transform .15s}
.sb-logo-icon:hover{transform:scale(1.05)}
.sb-logo-icon svg{width:18px;height:18px;stroke:#fff;fill:none;stroke-width:2.2;
  stroke-linecap:round;stroke-linejoin:round}

.sb-logo-text{overflow:hidden;white-space:nowrap;transition:opacity .2s,width .28s;cursor:pointer}
.sb-logo-text strong{display:block;font-size:.96rem;font-weight:800;color:#0F172A;line-height:1.1;letter-spacing:-.02em}
.sb-logo-text small{font-size:.68rem;color:#64748B;font-weight:600;text-transform:uppercase;letter-spacing:.06em}

.sb-toggle{margin-left:auto;background:#F8FAFC;border:1px solid var(--border);cursor:pointer;
  color:#64748B;width:28px;height:28px;border-radius:7px;display:flex;align-items:center;
  justify-content:center;transition:all .15s;flex-shrink:0}
.sb-toggle:hover{background:#EFF6FF;border-color:#BFDBFE;color:var(--blue-d)}
.sb-toggle svg{width:16px;height:16px;stroke:currentColor;fill:none;stroke-width:2;
  stroke-linecap:round;stroke-linejoin:round}

/* Mini Mode Top Fix */
.sidebar.mini .sb-top{padding:1.1rem 0 .9rem;justify-content:center;cursor:pointer}
.sidebar.mini .sb-top:hover{background:#F8FAFC}
.sidebar.mini .sb-logo-text{display:none;opacity:0;width:0}
.sidebar.mini .sb-toggle{display:none}

.sb-nav{flex:1;overflow-y:auto;overflow-x:hidden;padding:.5rem 0 1rem}
.sb-nav::-webkit-scrollbar{width:3px}
.sb-nav::-webkit-scrollbar-thumb{background:#E2E8F0;border-radius:2px}

.sb-section{padding:.85rem .75rem .2rem}
.sb-label{font-size:.64rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;
  color:#94A3B8;padding:0 .5rem .35rem;white-space:nowrap;overflow:hidden;
  transition:opacity .2s;user-select:none}
.sidebar.mini .sb-label{display:none}

.sb-item{display:flex;align-items:center;gap:.75rem;padding:.58rem .8rem;
  margin:2px .5rem;border-radius:9px;cursor:pointer;color:#475569;
  font-size:.85rem;font-weight:500;transition:all .15s ease;
  border:none;background:none;width:calc(100% - 1rem);text-align:left;
  position:relative}
.sb-item:hover{background:#F1F5F9;color:#0F172A;transform:translateX(2px)}
.sb-item.active{background:#EFF6FF;color:#1D4ED8;font-weight:600;
  border-left:3px solid var(--blue);box-shadow:0 1px 3px rgba(37,99,235,.08)}
.sb-item .ico{width:17px;height:17px;stroke:#64748B;fill:none;stroke-width:1.8;
  stroke-linecap:round;stroke-linejoin:round;flex-shrink:0;transition:all .15s}
.sb-item:hover .ico{stroke:#0F172A}
.sb-item.active .ico{stroke:var(--blue)}
.sb-item .lbl{transition:opacity .2s,width .28s;overflow:hidden}

/* Mini Item Fix */
.sidebar.mini .sb-item{width:46px;height:46px;margin:4px auto;padding:0;
  justify-content:center;border-radius:10px}
.sidebar.mini .sb-item.active{background:#EFF6FF;color:#1D4ED8;border-left:none;
  box-shadow:0 0 0 2px var(--blue)}
.sidebar.mini .sb-item .lbl{display:none;opacity:0;width:0}

/* Footer & User Card */
.sb-foot{border-top:1px solid var(--border);padding:.85rem .75rem;flex-shrink:0;background:#F8FAFC}
.sb-user{display:flex;align-items:center;gap:.65rem;padding:.4rem .4rem;
  border-radius:8px;cursor:default;overflow:hidden}
.sb-avatar{width:34px;height:34px;background:linear-gradient(135deg,var(--blue),#4F46E5);
  border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-size:.8rem;font-weight:700;color:#fff;flex-shrink:0}
.sb-user-info{flex:1;min-width:0;overflow:hidden;transition:opacity .2s,width .28s}
.sb-user-info .nm{font-size:.82rem;font-weight:700;color:#0F172A;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sb-user-info .rl{font-size:.68rem;color:#64748B;font-weight:500}
.btn-out{background:none;border:none;cursor:pointer;color:#64748B;padding:6px;
  border-radius:6px;transition:all .15s;flex-shrink:0}
.btn-out:hover{background:#FEF2F2;color:var(--red)}
.btn-out svg{width:15px;height:15px;stroke:currentColor;fill:none;stroke-width:2;
  stroke-linecap:round;stroke-linejoin:round}

/* Mini Footer Fix */
.sidebar.mini .sb-foot{padding:.75rem 0;justify-content:center;display:flex}
.sidebar.mini .sb-user{padding:0;justify-content:center}
.sidebar.mini .sb-user-info{display:none}
.sidebar.mini .btn-out{display:none}

/* ─── MAIN ────────────────────────────────────────────────────────────── */
.main{flex:1;display:flex;flex-direction:column;min-width:0;overflow:hidden;background:var(--bg)}

.hdr{height:var(--hdr);background:#FFFFFF;border-bottom:1px solid var(--border);
  display:flex;align-items:center;padding:0 1.5rem;gap:1rem;flex-shrink:0;
  box-shadow:0 1px 4px rgba(15,23,42,0.03);position:relative;z-index:10}

/* Header persistent toggle button */
.hdr-sb-toggle{background:#F8FAFC;border:1px solid var(--border);border-radius:8px;
  width:36px;height:36px;display:inline-flex;align-items:center;justify-content:center;
  color:#475569;cursor:pointer;transition:all .15s;flex-shrink:0;margin-right:.4rem}
.hdr-sb-toggle:hover{background:#EFF6FF;border-color:#BFDBFE;color:var(--blue-d);transform:scale(1.02)}
.hdr-sb-toggle.active{background:#EFF6FF;border-color:#93C5FD;color:var(--blue)}
.hdr-sb-toggle svg{width:18px;height:18px;stroke:currentColor;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}

.hdr-title{font-size:1.05rem;font-weight:800;flex:1;color:var(--text);letter-spacing:-.02em}
.hdr-actions{display:flex;gap:.5rem;align-items:center}

.content{flex:1;overflow-y:auto;padding:1.5rem}
.content::-webkit-scrollbar{width:5px}
.content::-webkit-scrollbar-thumb{background:var(--border2);border-radius:3px}

.pane{display:none;animation:fadeUp .18s ease}
.pane.active{display:block}
@keyframes fadeUp{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}

/* ─── KPI GRID ────────────────────────────────────────────────────────── */
.kpi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));
  gap:1rem;margin-bottom:1.25rem}
.kpi{background:var(--card);border:1px solid var(--border);border-radius:var(--r);
  padding:1.1rem 1.25rem;box-shadow:var(--shadow);transition:box-shadow .15s;position:relative;overflow:hidden}
.kpi:hover{box-shadow:var(--shadow-md)}
.kpi::after{content:'';position:absolute;top:0;left:0;right:0;height:3px;border-radius:var(--r) var(--r) 0 0}
.kpi.blue::after{background:linear-gradient(90deg,var(--blue),#60A5FA)}
.kpi.green::after{background:linear-gradient(90deg,var(--green),#34D399)}
.kpi.amber::after{background:linear-gradient(90deg,var(--amber),#FCD34D)}
.kpi.red::after{background:linear-gradient(90deg,var(--red),#F87171)}
.kpi.purple::after{background:linear-gradient(90deg,var(--purple),#A78BFA)}
.kpi.slate::after{background:linear-gradient(90deg,var(--muted),var(--light))}
.kpi-lbl{font-size:.72rem;font-weight:600;color:var(--muted);text-transform:uppercase;
  letter-spacing:.05em;margin-bottom:.35rem}
.kpi-val{font-size:1.9rem;font-weight:800;color:var(--text);letter-spacing:-.03em;line-height:1}
.kpi-sub{font-size:.72rem;color:var(--light);margin-top:.3rem}

/* ─── CARDS ───────────────────────────────────────────────────────────── */
.card{background:var(--card);border:1px solid var(--border);border-radius:var(--r);
  padding:1.25rem;box-shadow:var(--shadow);margin-bottom:1.1rem}
.card-hdr{display:flex;justify-content:space-between;align-items:center;
  margin-bottom:1rem;padding-bottom:.85rem;border-bottom:1px solid var(--border)}
.card-hdr h2{font-size:.92rem;font-weight:700;color:var(--text)}
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:1rem}
.three-col{display:grid;grid-template-columns:1fr 1fr 1fr;gap:1rem}
@media(max-width:900px){.two-col,.three-col{grid-template-columns:1fr}}

/* ─── PRODUCTS GRID ───────────────────────────────────────────────────── */
.prod-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:.85rem}
.prod-card{background:var(--card);border:1px solid var(--border);border-radius:var(--r);
  padding:1rem;transition:all .15s;box-shadow:var(--shadow)}
.prod-card:hover{border-color:var(--blue);box-shadow:var(--shadow-md)}
.prod-tag{display:inline-block;font-size:.62rem;font-weight:700;text-transform:uppercase;
  letter-spacing:.05em;background:var(--blue-lt);color:var(--blue-d);
  border:1px solid rgba(37,99,235,.2);padding:.15rem .5rem;border-radius:5px;margin-bottom:.6rem}
.prod-nm{font-size:.88rem;font-weight:600;color:var(--text);margin-bottom:.35rem;line-height:1.3}
.prod-desc{font-size:.75rem;color:var(--muted);line-height:1.4}
.prod-foot{display:flex;justify-content:space-between;align-items:center;
  padding-top:.65rem;margin-top:.65rem;border-top:1px solid var(--border)}
.prod-price{font-size:1rem;font-weight:800;color:var(--blue)}
.stk-badge{font-size:.7rem;font-weight:600;padding:.2rem .5rem;border-radius:5px}
.stk-ok{background:#F0FDF4;color:#15803D;border:1px solid #BBF7D0}
.stk-low{background:#FFFBEB;color:#B45309;border:1px solid #FDE68A}
.stk-out{background:#FEF2F2;color:#DC2626;border:1px solid #FECACA}

/* ─── POS ─────────────────────────────────────────────────────────────── */
.pos-wrap{display:grid;grid-template-columns:1fr 320px;gap:1rem;height:calc(100vh - var(--hdr) - 3.5rem)}
.pos-prods{overflow-y:auto}
.pos-prods::-webkit-scrollbar{width:4px}
.pos-prods::-webkit-scrollbar-thumb{background:var(--border2);border-radius:2px}
.pos-search{width:100%;padding:.6rem .85rem;border:1px solid var(--border);border-radius:8px;
  font-family:var(--font);font-size:.85rem;color:var(--text);outline:none;
  transition:border-color .15s;background:var(--card);margin-bottom:.85rem}
.pos-search:focus{border-color:var(--blue);box-shadow:0 0 0 3px rgba(37,99,235,.1)}
.pos-row{display:flex;align-items:center;gap:.7rem;padding:.7rem .85rem;
  background:var(--card);border:1px solid var(--border);border-radius:9px;
  cursor:pointer;transition:all .15s;margin-bottom:.45rem}
.pos-row:hover{border-color:var(--blue);background:var(--blue-lt)}
.pos-row.oos{opacity:.4;cursor:not-allowed}
.pos-rinfo{flex:1;min-width:0}
.pos-rnm{font-size:.85rem;font-weight:600;color:var(--text);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pos-rcat{font-size:.72rem;color:var(--muted)}
.pos-rprice{font-size:.92rem;font-weight:700;color:var(--blue);flex-shrink:0}
.pos-radd{width:28px;height:28px;background:var(--blue-lt);border:1px solid rgba(37,99,235,.25);
  border-radius:6px;display:flex;align-items:center;justify-content:center;
  color:var(--blue);font-size:1.1rem;line-height:1;flex-shrink:0;transition:all .15s}
.pos-row:hover .pos-radd{background:var(--blue);color:#fff;border-color:var(--blue)}

/* Cart */
.cart-panel{background:var(--card);border:1px solid var(--border);border-radius:var(--r);
  display:flex;flex-direction:column;overflow:hidden;box-shadow:var(--shadow)}
.cart-hdr{padding:.9rem 1rem;border-bottom:1px solid var(--border)}
.cart-hdr h3{font-size:.88rem;font-weight:700;color:var(--text)}
.cart-items{flex:1;overflow-y:auto;padding:.6rem}
.cart-items::-webkit-scrollbar{width:3px}
.cart-items::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
.cart-empty{text-align:center;color:var(--muted);font-size:.82rem;
  padding:2rem 1rem;line-height:1.6}
.ci{display:flex;align-items:center;gap:.5rem;padding:.55rem .4rem;
  border-radius:7px;transition:background .12s}
.ci:hover{background:var(--bg)}
.ci-info{flex:1;min-width:0}
.ci-nm{font-size:.8rem;font-weight:600;color:var(--text);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ci-pr{font-size:.7rem;color:var(--muted)}
.ci-ctrl{display:flex;align-items:center;gap:.25rem;flex-shrink:0}
.ci-btn{width:20px;height:20px;background:var(--bg);border:1px solid var(--border);
  border-radius:5px;display:flex;align-items:center;justify-content:center;
  cursor:pointer;font-size:.8rem;line-height:1;transition:all .12s;color:var(--text)}
.ci-btn:hover{background:var(--blue);color:#fff;border-color:var(--blue)}
.ci-qty{font-size:.82rem;font-weight:700;min-width:18px;text-align:center}
.ci-del{background:none;border:none;color:var(--muted);cursor:pointer;
  font-size:.85rem;padding:2px;border-radius:4px;transition:color .12s}
.ci-del:hover{color:var(--red)}
.ci-sub{font-size:.8rem;font-weight:700;color:var(--blue);min-width:55px;text-align:right;flex-shrink:0}

.cart-foot{border-top:1px solid var(--border);padding:.85rem 1rem}
.cart-row{display:flex;justify-content:space-between;font-size:.8rem;
  color:var(--muted);margin-bottom:.3rem}
.cart-total{display:flex;justify-content:space-between;font-size:1rem;
  font-weight:800;color:var(--text);padding-top:.55rem;
  margin-top:.55rem;border-top:1px solid var(--border);margin-bottom:.85rem}
.sel{width:100%;padding:.55rem .75rem;border:1px solid var(--border);border-radius:8px;
  font-family:var(--font);font-size:.82rem;color:var(--text);background:var(--bg);
  outline:none;margin-bottom:.45rem;transition:border-color .15s}
.sel:focus{border-color:var(--blue)}

/* ─── BUTTONS ─────────────────────────────────────────────────────────── */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:.4rem;
  padding:.6rem 1.1rem;border:none;border-radius:8px;font-family:var(--font);
  font-size:.82rem;font-weight:600;cursor:pointer;transition:all .15s;white-space:nowrap}
.btn-primary{background:var(--blue);color:#fff}
.btn-primary:hover{background:var(--blue-d);box-shadow:0 4px 12px rgba(37,99,235,.3)}
.btn-success{background:var(--green);color:#fff}
.btn-success:hover{background:#059669;box-shadow:0 4px 12px rgba(16,185,129,.3)}
.btn-danger{background:var(--red);color:#fff}
.btn-danger:hover{background:#DC2626}
.btn-ghost{background:transparent;color:var(--muted);border:1px solid var(--border)}
.btn-ghost:hover{background:var(--bg);color:var(--text);border-color:var(--border2)}
.btn-sm{padding:.4rem .75rem;font-size:.76rem}
.btn-xs{padding:.25rem .55rem;font-size:.7rem}
.btn-block{width:100%}
.btn:disabled{opacity:.5;cursor:not-allowed;transform:none!important;box-shadow:none!important}

/* ─── FORMS ───────────────────────────────────────────────────────────── */
.form-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:.85rem}
.fg{display:flex;flex-direction:column;gap:.3rem}
.fg label{font-size:.72rem;font-weight:600;color:var(--muted);
  text-transform:uppercase;letter-spacing:.05em}
.fc{width:100%;padding:.6rem .8rem;border:1px solid var(--border);border-radius:8px;
  font-family:var(--font);font-size:.85rem;color:var(--text);background:var(--card);
  outline:none;transition:border-color .15s}
.fc:focus{border-color:var(--blue);box-shadow:0 0 0 3px rgba(37,99,235,.1)}
.fc::placeholder{color:#CBD5E1}
textarea.fc{resize:vertical;min-height:70px}

/* ─── TABLES ──────────────────────────────────────────────────────────── */
.tbl-wrap{overflow-x:auto;border:1px solid var(--border);border-radius:var(--r)}
table{width:100%;border-collapse:collapse;font-size:.82rem}
th{background:#F8FAFC;padding:.65rem .9rem;color:var(--muted);font-size:.7rem;
  font-weight:700;text-transform:uppercase;letter-spacing:.06em;
  border-bottom:1px solid var(--border);text-align:left;white-space:nowrap}
td{padding:.7rem .9rem;border-bottom:1px solid var(--border);color:var(--text);vertical-align:middle}
tr:last-child td{border-bottom:none}
tr:hover td{background:#FAFAFA}
code{font-family:monospace;font-size:.78rem;background:#F1F5F9;padding:.1rem .35rem;
  border-radius:4px;color:var(--slate2)}

/* ─── BADGES ──────────────────────────────────────────────────────────── */
.badge{display:inline-flex;align-items:center;padding:.2rem .55rem;
  border-radius:5px;font-size:.68rem;font-weight:700;white-space:nowrap}
.bg-green{background:#F0FDF4;color:#15803D;border:1px solid #BBF7D0}
.bg-amber{background:#FFFBEB;color:#B45309;border:1px solid #FDE68A}
.bg-red{background:#FEF2F2;color:#DC2626;border:1px solid #FECACA}
.bg-blue{background:var(--blue-lt);color:var(--blue-d);border:1px solid rgba(37,99,235,.2)}
.bg-purple{background:#F5F3FF;color:#6D28D9;border:1px solid #DDD6FE}
.bg-slate{background:#F1F5F9;color:var(--slate2);border:1px solid var(--border2)}

/* ─── MODALS ──────────────────────────────────────────────────────────── */
.overlay{position:fixed;inset:0;background:rgba(15,23,42,.45);
  backdrop-filter:blur(3px);z-index:900;display:flex;
  align-items:center;justify-content:center;animation:fo .18s}
.overlay.hidden{display:none}
@keyframes fo{from{opacity:0}to{opacity:1}}
.modal{background:var(--card);border:1px solid var(--border);border-radius:14px;
  padding:1.5rem;width:min(540px,94vw);max-height:90vh;overflow-y:auto;
  box-shadow:var(--shadow-lg);animation:su .2s ease}
@keyframes su{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}
.modal-hdr{display:flex;justify-content:space-between;align-items:center;margin-bottom:1.25rem}
.modal-hdr h3{font-size:1rem;font-weight:700}
.modal-close{background:none;border:none;cursor:pointer;color:var(--muted);
  font-size:1.1rem;padding:3px;border-radius:5px;transition:color .12s}
.modal-close:hover{color:var(--text)}
.modal-foot{display:flex;gap:.5rem;justify-content:flex-end;margin-top:1.25rem;
  padding-top:1rem;border-top:1px solid var(--border)}

/* ─── TOASTS ──────────────────────────────────────────────────────────── */
#toast-box{position:fixed;top:1rem;right:1rem;z-index:9999;
  display:flex;flex-direction:column;gap:.45rem;max-width:360px}
.toast{display:flex;align-items:flex-start;gap:.65rem;background:var(--card);
  border:1px solid var(--border);border-radius:10px;padding:.8rem .9rem;
  box-shadow:var(--shadow-lg);animation:tin .22s ease;font-size:.82rem;line-height:1.4}
@keyframes tin{from{opacity:0;transform:translateX(100%)}to{opacity:1;transform:translateX(0)}}
.toast.ok{border-color:#BBF7D0}
.toast.err{border-color:#FECACA}
.toast-ico{font-size:1rem;flex-shrink:0}
.toast-msg{flex:1}
.toast-x{background:none;border:none;color:var(--muted);cursor:pointer;font-size:.85rem}

/* ─── FACTURA PRINT ───────────────────────────────────────────────────── */
.fac-print{background:var(--bg);border:1px solid var(--border);border-radius:var(--r);padding:1.25rem}
.fac-ph{text-align:center;padding-bottom:.85rem;margin-bottom:.85rem;border-bottom:1px solid var(--border)}
.fac-ph h2{font-size:1.1rem;font-weight:800;letter-spacing:-.02em}
.fac-ph .num{font-size:.9rem;color:var(--blue);font-weight:700}
.fac-tot{margin-top:.85rem;padding-top:.6rem;border-top:1px solid var(--border)}
.fac-tot .row{display:flex;justify-content:space-between;font-size:.82rem;color:var(--muted);margin-bottom:.25rem}
.fac-tot .tot{font-size:1rem;font-weight:800;color:var(--text)}

/* ─── MISC ────────────────────────────────────────────────────────────── */
.section-hdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:1.1rem}
.section-hdr h1{font-size:1.1rem;font-weight:800;color:var(--text);letter-spacing:-.02em}
.search-row{display:flex;gap:.6rem;margin-bottom:.85rem}
.search-row .fc{flex:1}
.empty-state{text-align:center;padding:3rem 1rem;color:var(--muted);font-size:.88rem}
.empty-state svg{width:40px;height:40px;stroke:var(--border2);fill:none;
  stroke-width:1.5;margin:0 auto 1rem;display:block}
.chip{display:inline-flex;align-items:center;gap:.35rem;padding:.2rem .6rem;
  background:var(--bg);border:1px solid var(--border);border-radius:20px;
  font-size:.72rem;color:var(--muted)}
.divider{border:none;border-top:1px solid var(--border);margin:1rem 0}
.text-muted{color:var(--muted)}
.text-sm{font-size:.78rem}
.fw7{font-weight:700}
.mt1{margin-top:.85rem}
.mb1{margin-bottom:.85rem}
.flex{display:flex}
.gap1{gap:.5rem}
.al-c{align-items:center}
</style>
</head>
<body>

<!-- TOASTS -->
<div id="toast-box"></div>

<!-- MODAL -->
<div class="overlay hidden" id="ov" onclick="_oc(event)">
  <div class="modal" id="modal">
    <div class="modal-hdr">
      <h3 id="modal-ttl"></h3>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div id="modal-body"></div>
  </div>
</div>

<!-- APP LAYOUT -->
<nav class="sidebar" id="sb">
  <!-- TOP -->
  <div class="sb-top" onclick="handleSbTopClick(event)">
    <div class="sb-logo-icon" title="TechStore ERP • Clic para alternar"><svg viewBox="0 0 24 24"><path d="M20 7H4a2 2 0 00-2 2v6a2 2 0 002 2h16a2 2 0 002-2V9a2 2 0 00-2-2z"/><path d="M16 21V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v16"/></svg></div>
    <div class="sb-logo-text" onclick="toggleSidebar(event)"><strong>TechStore</strong><small>ERP Enterprise</small></div>
    <button class="sb-toggle" onclick="toggleSidebar(event)" title="Colapsar menú lateral">
      <svg id="sb-chev" viewBox="0 0 24 24"><polyline points="15 18 9 12 15 6"/></svg>
    </button>
  </div>
  <!-- NAV -->
  <div class="sb-nav" id="sb-nav"></div>
  <!-- FOOT -->
  <div class="sb-foot">
    <div class="sb-user">
      <div class="sb-avatar" id="av">?</div>
      <div class="sb-user-info">
        <div class="nm" id="un">—</div>
        <div class="rl" id="ur">—</div>
      </div>
      <button class="btn-out" onclick="doLogout()" title="Cerrar sesión">
        <svg viewBox="0 0 24 24"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
      </button>
    </div>
  </div>
</nav>

<div class="main">
  <div class="hdr">
    <button class="hdr-sb-toggle" id="btn-hdr-toggle" onclick="toggleSidebar(event)" title="Alternar menú lateral (Ctrl+B)">
      <svg viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="9" y1="3" x2="9" y2="21"/></svg>
    </button>
    <div class="hdr-title" id="hdr-ttl">Dashboard</div>
    <div class="hdr-actions" id="hdr-act"></div>
  </div>
  <div class="content" id="content">

    <!-- ===== DASHBOARD ===== -->
    <div class="pane active" id="pane-dashboard">
      <div class="kpi-grid" id="kpi-grid">
        <div class="kpi blue"><div class="kpi-lbl">Productos</div><div class="kpi-val" id="k-prod">—</div><div class="kpi-sub">Activos en catálogo</div></div>
        <div class="kpi green"><div class="kpi-lbl">Clientes</div><div class="kpi-val" id="k-cli">—</div><div class="kpi-sub">Registrados</div></div>
        <div class="kpi amber"><div class="kpi-lbl">Pedidos</div><div class="kpi-val" id="k-ped">—</div><div class="kpi-sub">Total en BD</div></div>
        <div class="kpi purple"><div class="kpi-lbl">Facturas</div><div class="kpi-val" id="k-fac">—</div><div class="kpi-sub">POS emitidas</div></div>
        <div class="kpi green"><div class="kpi-lbl">Ventas hoy</div><div class="kpi-val" id="k-hoy">—</div><div class="kpi-sub">Facturado</div></div>
        <div class="kpi red"><div class="kpi-lbl">Stock bajo</div><div class="kpi-val" id="k-stk">—</div><div class="kpi-sub">Bajo mínimo</div></div>
      </div>
      <div class="two-col">
        <div class="card">
          <div class="card-hdr"><h2>Últimas Facturas</h2><button class="btn btn-ghost btn-sm" onclick="loadFacs()">Actualizar</button></div>
          <div class="tbl-wrap"><table><thead><tr><th>Nro</th><th>Cliente</th><th>Total</th><th>Estado</th></tr></thead><tbody id="dash-fac-tb"></tbody></table></div>
        </div>
        <div class="card">
          <div class="card-hdr"><h2>Stock Bajo</h2></div>
          <div class="tbl-wrap"><table><thead><tr><th>Producto</th><th>Stock</th><th>Mínimo</th></tr></thead><tbody id="dash-stk-tb"></tbody></table></div>
        </div>
      </div>
    </div>

    <!-- ===== VENTAS (POS) ===== -->
    <div class="pane" id="pane-ventas">
      <div class="pos-wrap">
        <div class="pos-prods">
          <div class="card-hdr" style="margin-bottom:.85rem"><h2>Punto de Venta</h2></div>
          <input class="pos-search" id="pos-q" placeholder="Buscar producto..." oninput="filterPOS()">
          <div id="pos-list"></div>
        </div>
        <div class="cart-panel">
          <div class="cart-hdr"><h3>Carrito</h3></div>
          <div class="cart-items" id="cart-items"><div class="cart-empty">Agrega productos al carrito</div></div>
          <div class="cart-foot">
            <div class="cart-row"><span>Subtotal</span><span id="c-sub">$0</span></div>
            <div class="cart-row"><span>IVA 19%</span><span id="c-iva">$0</span></div>
            <div class="cart-total"><span>Total</span><strong id="c-tot">$0</strong></div>
            <select class="sel" id="c-pago"><option value="efectivo">💵 Efectivo</option><option value="tarjeta">💳 Tarjeta</option><option value="transferencia">🏦 Transferencia</option><option value="nequi">📱 Nequi</option><option value="daviplata">📱 Daviplata</option></select>
            <select class="sel" id="c-cli"><option value="">— Consumidor final —</option></select>
            <button class="btn btn-success btn-block mb1" id="btn-cobrar" onclick="cobrar()" disabled>Generar Factura</button>
            <button class="btn btn-ghost btn-block btn-sm" onclick="clearCart()">Vaciar carrito</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ===== HISTORIAL VENTAS ===== -->
    <div class="pane" id="pane-historial">
      <div class="card">
        <div class="card-hdr"><h2>Historial de Ventas / Facturas</h2><button class="btn btn-ghost btn-sm" onclick="loadFacs()">Actualizar</button></div>
        <div class="search-row"><input class="fc" id="fac-q" placeholder="Buscar..." oninput="filterFacs()"></div>
        <div class="tbl-wrap">
          <table><thead><tr><th>Número</th><th>Fecha</th><th>Cliente</th><th>Vendedor</th><th>Total</th><th>Pago</th><th>Estado</th><th></th></tr></thead>
          <tbody id="fac-tb"></tbody></table>
        </div>
      </div>
    </div>

    <!-- ===== PRODUCTOS ===== -->
    <div class="pane" id="pane-productos">
      <div class="section-hdr">
        <h1>Catálogo de Productos</h1>
        <div class="flex gap1">
          <input class="fc" id="cat-q" placeholder="Buscar..." oninput="filterCat()" style="width:200px">
          <button class="btn btn-primary btn-sm" id="btn-nuevo-prod" onclick="openNewProd()">+ Producto</button>
        </div>
      </div>
      <div class="prod-grid" id="prod-grid"></div>
    </div>

    <!-- ===== INVENTARIO ===== -->
    <div class="pane" id="pane-inventario">
      <div class="card">
        <div class="card-hdr"><h2>Movimientos de Inventario</h2><button class="btn btn-primary btn-sm" onclick="openAjusteInv()">+ Ajuste</button></div>
        <div class="tbl-wrap">
          <table><thead><tr><th>Fecha</th><th>Producto</th><th>Tipo</th><th>Cant.</th><th>Antes</th><th>Después</th><th>Motivo</th><th>Usuario</th></tr></thead>
          <tbody id="inv-tb"></tbody></table>
        </div>
      </div>
    </div>

    <!-- ===== CATEGORÍAS ===== -->
    <div class="pane" id="pane-categorias">
      <div class="card">
        <div class="card-hdr"><h2>Categorías de Productos</h2><button class="btn btn-primary btn-sm" onclick="openNewCat()">+ Categoría</button></div>
        <div class="tbl-wrap">
          <table><thead><tr><th>#</th><th>Nombre</th><th>Descripción</th><th>Estado</th><th></th></tr></thead>
          <tbody id="cat-tb"></tbody></table>
        </div>
      </div>
    </div>

    <!-- ===== CLIENTES ===== -->
    <div class="pane" id="pane-clientes">
      <div class="card">
        <div class="card-hdr"><h2>Clientes</h2><button class="btn btn-primary btn-sm" onclick="openNewCli()">+ Cliente</button></div>
        <div class="search-row"><input class="fc" id="cli-q" placeholder="Buscar cliente..." oninput="filterClis()"></div>
        <div class="tbl-wrap">
          <table><thead><tr><th>#</th><th>Nombre</th><th>Email</th><th>Ciudad</th><th>Teléfono</th><th>Tipo</th><th>Estado</th><th></th></tr></thead>
          <tbody id="cli-tb"></tbody></table>
        </div>
      </div>
    </div>

    <!-- ===== PROVEEDORES ===== -->
    <div class="pane" id="pane-proveedores">
      <div class="card">
        <div class="card-hdr"><h2>Proveedores</h2><button class="btn btn-primary btn-sm" onclick="openNewProv()">+ Proveedor</button></div>
        <div class="tbl-wrap">
          <table><thead><tr><th>#</th><th>Nombre</th><th>Contacto</th><th>Teléfono</th><th>Ciudad</th><th>NIT</th><th>Estado</th><th></th></tr></thead>
          <tbody id="prov-tb"></tbody></table>
        </div>
      </div>
    </div>

    <!-- ===== CAJA ===== -->
    <div class="pane" id="pane-caja">
      <div id="caja-abierta" style="display:none">
        <div class="card" id="caja-info-card"></div>
        <div class="two-col">
          <div class="card">
            <div class="card-hdr"><h2>Registrar Movimiento</h2></div>
            <div class="fg mb1"><label>Tipo</label><select class="fc" id="caj-tipo"><option value="ingreso">Ingreso</option><option value="egreso">Egreso</option></select></div>
            <div class="fg mb1"><label>Concepto</label><input class="fc" id="caj-concepto" placeholder="Descripción del movimiento"></div>
            <div class="fg mb1"><label>Monto</label><input class="fc" type="number" id="caj-monto" placeholder="0" min="1"></div>
            <button class="btn btn-primary btn-block" onclick="regMovCaja()">Registrar</button>
          </div>
          <div class="card">
            <div class="card-hdr"><h2>Movimientos de esta Sesión</h2></div>
            <div class="tbl-wrap"><table><thead><tr><th>Tipo</th><th>Concepto</th><th>Monto</th></tr></thead><tbody id="caj-movs-tb"></tbody></table></div>
            <div class="mt1" style="text-align:right">
              <button class="btn btn-danger btn-sm" onclick="openCerrarCaja()">Cerrar Caja</button>
            </div>
          </div>
        </div>
      </div>
      <div id="caja-cerrada">
        <div class="card" style="max-width:420px;margin:0 auto;text-align:center;padding:2rem">
          <div style="font-size:2.5rem;margin-bottom:1rem">🏦</div>
          <h2 style="margin-bottom:.5rem">Caja Cerrada</h2>
          <p class="text-muted text-sm mb1">No hay una sesión de caja abierta.</p>
          <button class="btn btn-primary" onclick="openAbrirCaja()">Abrir Caja</button>
        </div>
        <div class="card" style="margin-top:1rem">
          <div class="card-hdr"><h2>Historial de Sesiones</h2></div>
          <div class="tbl-wrap"><table><thead><tr><th>Apertura</th><th>Cierre</th><th>Inicial</th><th>Esperado</th><th>Contado</th><th>Dif.</th><th>Estado</th></tr></thead><tbody id="caj-hist-tb"></tbody></table></div>
        </div>
      </div>
    </div>

    <!-- ===== FINANZAS ===== -->
    <div class="pane" id="pane-finanzas">
      <div class="kpi-grid">
        <div class="kpi green"><div class="kpi-lbl">Ventas del mes</div><div class="kpi-val" id="f-mes">—</div><div class="kpi-sub">Facturado</div></div>
        <div class="kpi blue"><div class="kpi-lbl">Total facturas</div><div class="kpi-val" id="f-tot">—</div><div class="kpi-sub">Pagadas</div></div>
        <div class="kpi amber"><div class="kpi-lbl">Hoy</div><div class="kpi-val" id="f-hoy">—</div><div class="kpi-sub">Facturado</div></div>
      </div>
      <div class="card">
        <div class="card-hdr"><h2>Resumen Financiero</h2></div>
        <p class="text-muted text-sm">Módulo en desarrollo. Aquí se mostrará el P&L, flujo de caja y análisis de rentabilidad.</p>
      </div>
    </div>

    <!-- ===== USUARIOS ===== -->
    <div class="pane" id="pane-usuarios">
      <div class="card">
        <div class="card-hdr"><h2>Gestión de Usuarios</h2><button class="btn btn-primary btn-sm" onclick="openNewUser()">+ Usuario</button></div>
        <div class="tbl-wrap">
          <table><thead><tr><th>#</th><th>Usuario</th><th>Nombre</th><th>Email</th><th>Rol</th><th>Estado</th><th></th></tr></thead>
          <tbody id="usr-tb"></tbody></table>
        </div>
      </div>
    </div>

    <!-- ===== AUDITORÍA ===== -->
    <div class="pane" id="pane-auditoria">
      <div class="card">
        <div class="card-hdr"><h2>Registro de Auditoría</h2><button class="btn btn-ghost btn-sm" onclick="loadAudit()">Actualizar</button></div>
        <div class="tbl-wrap">
          <table><thead><tr><th>Fecha</th><th>Usuario</th><th>Módulo</th><th>Acción</th><th>Descripción</th></tr></thead>
          <tbody id="audit-tb"></tbody></table>
        </div>
      </div>
      <div class="card">
        <div class="card-hdr"><h2>Rechazos Carga ETL</h2>
          <button class="btn btn-ghost btn-sm" onclick="runETL()">Re-ejecutar ETL</button>
        </div>
        <div class="tbl-wrap"><table><thead><tr><th>#</th><th>Fila</th><th>Pedido ID</th><th>Motivo</th><th>Fecha</th></tr></thead><tbody id="rech-tb"></tbody></table></div>
      </div>
    </div>

    <!-- ===== REPORTES ===== -->
    <div class="pane" id="pane-reportes">
      <div class="card">
        <div class="card-hdr"><h2>Reportes del Sistema</h2></div>
        <div class="three-col">
          <div class="card" style="text-align:center;border:1px dashed var(--border)">
            <div style="font-size:2rem;margin-bottom:.5rem">📊</div>
            <div class="fw7 mb1">Ventas</div>
            <button class="btn btn-ghost btn-sm btn-block" onclick="toast('Reporte en desarrollo','info')">Ver Reporte</button>
          </div>
          <div class="card" style="text-align:center;border:1px dashed var(--border)">
            <div style="font-size:2rem;margin-bottom:.5rem">📦</div>
            <div class="fw7 mb1">Inventario</div>
            <button class="btn btn-ghost btn-sm btn-block" onclick="toast('Reporte en desarrollo','info')">Ver Reporte</button>
          </div>
          <div class="card" style="text-align:center;border:1px dashed var(--border)">
            <div style="font-size:2rem;margin-bottom:.5rem">👥</div>
            <div class="fw7 mb1">Clientes</div>
            <button class="btn btn-ghost btn-sm btn-block" onclick="toast('Reporte en desarrollo','info')">Ver Reporte</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ===== CONFIGURACIÓN ===== -->
    <div class="pane" id="pane-configuracion">
      <div class="two-col">
        <div class="card">
          <div class="card-hdr"><h2>Datos del Negocio</h2></div>
          <div class="form-grid" id="cfg-form"></div>
          <div class="mt1"><button class="btn btn-primary" onclick="saveConfig()">Guardar Configuración</button></div>
        </div>
        <div class="card">
          <div class="card-hdr"><h2>Parámetros del Sistema</h2></div>
          <div id="cfg-params"></div>
        </div>
      </div>
    </div>

  </div><!-- /content -->
</div><!-- /main -->

<script>
// ═══════════════════════════════════════════════
// ICONS
// ═══════════════════════════════════════════════
const IC = {
  dashboard: `<svg class="ico" viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>`,
  ventas:    `<svg class="ico" viewBox="0 0 24 24"><circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.68 13.39a2 2 0 001.98 1.61h9.72a2 2 0 001.98-1.61L23 6H6"/></svg>`,
  historial: `<svg class="ico" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>`,
  productos: `<svg class="ico" viewBox="0 0 24 24"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>`,
  inventario:`<svg class="ico" viewBox="0 0 24 24"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>`,
  categorias:`<svg class="ico" viewBox="0 0 24 24"><path d="M20.59 13.41l-7.17 7.17a2 2 0 01-2.83 0L2 12V2h10l8.59 8.59a2 2 0 010 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>`,
  clientes:  `<svg class="ico" viewBox="0 0 24 24"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>`,
  proveedores:`<svg class="ico" viewBox="0 0 24 24"><rect x="1" y="3" width="15" height="13" rx="2"/><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/></svg>`,
  caja:      `<svg class="ico" viewBox="0 0 24 24"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>`,
  finanzas:  `<svg class="ico" viewBox="0 0 24 24"><line x1="12" y1="20" x2="12" y2="10"/><line x1="18" y1="20" x2="18" y2="4"/><line x1="6" y1="20" x2="6" y2="16"/></svg>`,
  usuarios:  `<svg class="ico" viewBox="0 0 24 24"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`,
  auditoria: `<svg class="ico" viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`,
  reportes:  `<svg class="ico" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><line x1="10" y1="9" x2="8" y2="9"/></svg>`,
  configuracion:`<svg class="ico" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>`,
};

// ═══════════════════════════════════════════════
// SIDEBAR STRUCTURE
// ═══════════════════════════════════════════════
const NAV = [
  {sec:'GENERAL',   items:[{id:'dashboard',  lbl:'Dashboard',        ico:'dashboard'}]},
  {sec:'OPERACIONES',items:[
    {id:'ventas',    lbl:'Punto de Venta',    ico:'ventas'},
    {id:'historial', lbl:'Historial Ventas',  ico:'historial'},
  ]},
  {sec:'GESTIÓN COMERCIAL',items:[
    {id:'productos',   lbl:'Productos',       ico:'productos'},
    {id:'inventario',  lbl:'Inventario',      ico:'inventario'},
    {id:'categorias',  lbl:'Categorías',      ico:'categorias'},
    {id:'clientes',    lbl:'Clientes',        ico:'clientes'},
    {id:'proveedores', lbl:'Proveedores',     ico:'proveedores'},
  ]},
  {sec:'FINANZAS',items:[
    {id:'caja',     lbl:'Caja',              ico:'caja'},
    {id:'finanzas', lbl:'Rentabilidad',      ico:'finanzas'},
  ]},
  {sec:'ADMINISTRACIÓN',items:[
    {id:'usuarios',      lbl:'Usuarios',     ico:'usuarios'},
    {id:'auditoria',     lbl:'Auditoría',    ico:'auditoria'},
    {id:'reportes',      lbl:'Reportes',     ico:'reportes'},
  ]},
  {sec:'CONFIGURACIÓN',items:[
    {id:'configuracion', lbl:'Configuración',ico:'configuracion'},
  ]},
];

// ═══════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════
const S = {user:null, productos:[], clientes:[], categorias:[], facturas:[], cart:[]};
let sbMini = false;
let cajaActiva = null;
let configData = {};

// ═══════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════
const $ = id => document.getElementById(id);
const fmt = n => '$'+Number(n||0).toLocaleString('es-CO',{minimumFractionDigits:0,maximumFractionDigits:0});
const fmtD = s => s ? s.substring(0,10) : '—';
const fmtDT = s => s ? s.replace('T',' ').substring(0,16) : '—';

async function api(path, opts={}){
  const r = await fetch(path,{headers:{'Content-Type':'application/json'},...opts});
  const d = await r.json();
  if(!r.ok) throw new Error(d.error||'Error');
  return d;
}

function toast(msg, type='ok'){
  const box=$('toast-box');
  const t=document.createElement('div');
  t.className=`toast ${type}`;
  t.innerHTML=`<span class="toast-ico">${type==='ok'?'✓':'⚠'}</span><span class="toast-msg">${msg}</span><button class="toast-x" onclick="this.parentElement.remove()">✕</button>`;
  box.appendChild(t);
  setTimeout(()=>t.remove(),4500);
}

// Modal
function openModal(title, body){
  $('modal-ttl').textContent=title;
  $('modal-body').innerHTML=body;
  $('ov').classList.remove('hidden');
}
function closeModal(){$('ov').classList.add('hidden')}
function _oc(e){if(e.target===$('ov'))closeModal()}

// ═══════════════════════════════════════════════
// SIDEBAR RENDER + TOGGLE
// ═══════════════════════════════════════════════
function buildNav(){
  const perms = S.user ? (window.PERMS_SIDEBAR[S.user.rol]||[]) : [];
  const all = S.user && (S.user.rol==='superadmin'||S.user.rol==='admin');
  const nav = $('sb-nav');
  nav.innerHTML = NAV.map(sec=>{
    const its = sec.items.filter(i=>all||perms.includes(i.id));
    if(!its.length) return '';
    return `<div class="sb-section">
      <div class="sb-label">${sec.sec}</div>
      ${its.map(i=>`
        <button class="sb-item${i.id==='dashboard'?' active':''}"
          id="nav-${i.id}" onclick="showPane('${i.id}',this)">
          ${IC[i.ico]||''}
          <span class="lbl">${i.lbl}</span>
        </button>`).join('')}
    </div>`;
  }).join('');
}

function showPane(id, btn){
  document.querySelectorAll('.pane').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.sb-item').forEach(b=>b.classList.remove('active'));
  const pane=$('pane-'+id);
  if(pane) pane.classList.add('active');
  if(btn) btn.classList.add('active');
  const labels={dashboard:'Dashboard',ventas:'Punto de Venta',historial:'Historial Ventas',
    productos:'Catálogo de Productos',inventario:'Inventario',categorias:'Categorías',
    clientes:'Clientes',proveedores:'Proveedores',caja:'Caja',finanzas:'Rentabilidad',
    usuarios:'Gestión de Usuarios',auditoria:'Auditoría',reportes:'Reportes',configuracion:'Configuración'};
  $('hdr-ttl').textContent=labels[id]||id;
  $('hdr-act').innerHTML='';
  // Load data per pane
  if(id==='historial')  loadFacs();
  if(id==='productos')  loadProds();
  if(id==='inventario') loadInvMovs();
  if(id==='categorias') loadCats();
  if(id==='clientes')   loadClis();
  if(id==='proveedores')loadProvs();
  if(id==='caja')       loadCaja();
  if(id==='usuarios')   loadUsers();
  if(id==='auditoria')  loadAudit();
  if(id==='configuracion') loadConfig();
}

function toggleSidebar(e){
  if(e && e.stopPropagation) e.stopPropagation();
  sbMini = !sbMini;
  const sb = document.getElementById('sb');
  if(!sb) return;
  sb.classList.toggle('mini', sbMini);
  const chev = $('sb-chev');
  if(chev){
    chev.innerHTML = sbMini
      ? '<polyline points="9 18 15 12 9 6"/>'
      : '<polyline points="15 18 9 12 15 6"/>';
  }
  const btnHdr = $('btn-hdr-toggle');
  if(btnHdr) btnHdr.classList.toggle('active', sbMini);
  try{ localStorage.setItem('ts_sb_mini', sbMini ? '1' : '0'); }catch(_){}
}

function handleSbTopClick(e){
  // Si está en modo compacto, al dar clic en la barra superior se expande
  if(sbMini){
    toggleSidebar(e);
  }
}

// Atajo de teclado: Ctrl + B para alternar la barra lateral
document.addEventListener('keydown', e => {
  if((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'b'){
    e.preventDefault();
    toggleSidebar();
  }
});

// ═══════════════════════════════════════════════
// BOOT
// ═══════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', async()=>{
  try{
    const me = await api('/api/me');
    S.user = me;
    $('un').textContent = me.nombre;
    $('ur').textContent = me.rol.charAt(0).toUpperCase()+me.rol.slice(1);
    $('av').textContent = me.nombre.charAt(0).toUpperCase();
    buildNav();

    // Restaurar preferencia de menú compacto
    try{
      if(localStorage.getItem('ts_sb_mini') === '1'){
        sbMini = true;
        const sb = document.getElementById('sb');
        if(sb) sb.classList.add('mini');
        const chev = $('sb-chev');
        if(chev) chev.innerHTML = '<polyline points="9 18 15 12 9 6"/>';
        const btnHdr = $('btn-hdr-toggle');
        if(btnHdr) btnHdr.classList.add('active');
      }
    }catch(_){}

    await Promise.all([loadResumen(), loadProds(), loadClis(), loadFacs(), loadCats()]);
    loadDashFacs(); loadDashStk();
  }catch(e){location.href='/login';}
});

// ═══════════════════════════════════════════════
// RESUMEN / KPIs
// ═══════════════════════════════════════════════
async function loadResumen(){
  const d=await api('/api/resumen');
  $('k-prod').textContent=d.productos;
  $('k-cli').textContent=d.clientes;
  $('k-ped').textContent=d.pedidos;
  $('k-fac').textContent=d.facturas;
  $('k-hoy').textContent=fmt(d.ventas_hoy);
  $('k-stk').textContent=d.stock_bajo;
  $('f-mes').textContent=fmt(d.ventas_mes);
  $('f-tot').textContent=d.facturas;
  $('f-hoy').textContent=fmt(d.ventas_hoy);
}

function loadDashFacs(){
  const tb=$('dash-fac-tb');
  const rows=S.facturas.slice(0,6);
  tb.innerHTML=rows.map(f=>`<tr>
    <td><strong>${f.numero}</strong></td>
    <td>${f.cliente||'<span class="text-muted">Anónimo</span>'}</td>
    <td class="fw7">${fmt(f.total)}</td>
    <td>${facBadge(f.estado)}</td>
  </tr>`).join('')||'<tr><td colspan="4" class="empty-state" style="padding:1rem">Sin facturas</td></tr>';
}

async function loadDashStk(){
  const prods=await api('/api/productos');
  const low=prods.filter(p=>p.stock<=p.stock_minimo&&p.activo);
  const tb=$('dash-stk-tb');
  tb.innerHTML=low.slice(0,6).map(p=>`<tr>
    <td>${p.nombre}</td>
    <td><span class="badge ${p.stock===0?'bg-red':'bg-amber'}">${p.stock}</span></td>
    <td>${p.stock_minimo}</td>
  </tr>`).join('')||'<tr><td colspan="3" style="text-align:center;color:var(--muted);padding:.85rem">Sin alertas</td></tr>';
}

// ═══════════════════════════════════════════════
// PRODUCTOS
// ═══════════════════════════════════════════════
async function loadProds(){
  S.productos=await api('/api/productos');
  renderGrid(S.productos);
  renderPOS(S.productos);
  refreshCatSel();
}
function filterCat(){
  const q=$('cat-q').value.toLowerCase();
  renderGrid(S.productos.filter(p=>p.nombre.toLowerCase().includes(q)||p.categoria.toLowerCase().includes(q)));
}
function renderGrid(prods){
  const g=$('prod-grid');
  if(!prods.length){g.innerHTML='<div class="empty-state" style="grid-column:1/-1"><p>No se encontraron productos</p></div>';return;}
  g.innerHTML=prods.map(p=>`
    <div class="prod-card">
      <div class="prod-tag">${p.categoria||'Sin cat.'}</div>
      <div class="prod-nm">${p.nombre}</div>
      ${p.descripcion?`<div class="prod-desc">${p.descripcion}</div>`:''}
      <div class="prod-foot">
        <span class="prod-price">${fmt(p.precio)}</span>
        <span class="stk-badge ${p.stock===0?'stk-out':p.stock<=p.stock_minimo?'stk-low':'stk-ok'}">
          ${p.stock===0?'Sin stock':''+p.stock+' u.'}
        </span>
      </div>
      <div style="margin-top:.65rem;display:flex;gap:.35rem">
        <button class="btn btn-ghost btn-xs" onclick="openEditProd(${p.producto_id})">Editar</button>
      </div>
    </div>`).join('');
}

function openNewProd(){
  const catOpts=S.categorias.map(c=>`<option value="${c.categoria_id}">${c.nombre}</option>`).join('');
  openModal('Nuevo Producto',`
    <div class="form-grid">
      <div class="fg"><label>Nombre *</label><input class="fc" id="pn-nom" placeholder="Ej: Laptop Dell XPS"></div>
      <div class="fg"><label>Categoría</label><select class="fc" id="pn-cat"><option value="">Sin categoría</option>${catOpts}</select></div>
      <div class="fg"><label>SKU</label><input class="fc" id="pn-sku" placeholder="Referencia"></div>
      <div class="fg"><label>Precio Venta *</label><input class="fc" type="number" id="pn-prv" placeholder="0" min="1"></div>
      <div class="fg"><label>Precio Compra</label><input class="fc" type="number" id="pn-prc" placeholder="0" min="0"></div>
      <div class="fg"><label>Stock inicial</label><input class="fc" type="number" id="pn-stk" value="0" min="0"></div>
      <div class="fg"><label>Stock mínimo</label><input class="fc" type="number" id="pn-stkm" value="5" min="0"></div>
    </div>
    <div class="fg mb1"><label>Descripción</label><textarea class="fc" id="pn-desc" placeholder="Descripción breve..."></textarea></div>
    <div class="modal-foot">
      <button class="btn btn-ghost" onclick="closeModal()">Cancelar</button>
      <button class="btn btn-primary" onclick="saveProd()">Guardar</button>
    </div>`);
}

async function saveProd(){
  try{
    const catEl=$('pn-cat');
    const catId=catEl.value?parseInt(catEl.value):null;
    const catNom=catId?catEl.options[catEl.selectedIndex].text:'General';
    const d=await api('/api/producto/nuevo',{method:'POST',body:JSON.stringify({
      nombre:$('pn-nom').value, categoria:catNom, categoria_id:catId,
      sku:$('pn-sku').value, precio:parseFloat($('pn-prv').value||0),
      precio_compra:parseFloat($('pn-prc').value||0),
      stock:parseInt($('pn-stk').value||0),
      stock_minimo:parseInt($('pn-stkm').value||5),
      descripcion:$('pn-desc').value,
    })});
    toast(d.mensaje); closeModal(); loadProds(); loadResumen();
  }catch(e){toast(e.message,'err');}
}

function openEditProd(id){
  const p=S.productos.find(x=>x.producto_id===id); if(!p) return;
  const catOpts=S.categorias.map(c=>`<option value="${c.categoria_id}" ${p.categoria_id===c.categoria_id?'selected':''}>${c.nombre}</option>`).join('');
  openModal('Editar: '+p.nombre,`
    <div class="form-grid">
      <div class="fg"><label>Nombre</label><input class="fc" id="pe-nom" value="${p.nombre}"></div>
      <div class="fg"><label>Categoría</label><select class="fc" id="pe-cat"><option value="">Sin categoría</option>${catOpts}</select></div>
      <div class="fg"><label>SKU</label><input class="fc" id="pe-sku" value="${p.sku||''}"></div>
      <div class="fg"><label>Precio Venta</label><input class="fc" type="number" id="pe-prv" value="${p.precio}"></div>
      <div class="fg"><label>Precio Compra</label><input class="fc" type="number" id="pe-prc" value="${p.precio_compra||0}"></div>
      <div class="fg"><label>Stock</label><input class="fc" type="number" id="pe-stk" value="${p.stock}"></div>
      <div class="fg"><label>Stock mínimo</label><input class="fc" type="number" id="pe-stkm" value="${p.stock_minimo||5}"></div>
      <div class="fg"><label>Estado</label><select class="fc" id="pe-act"><option value="1" ${p.activo?'selected':''}>Activo</option><option value="0" ${!p.activo?'selected':''}>Inactivo</option></select></div>
    </div>
    <div class="fg mb1"><label>Descripción</label><textarea class="fc" id="pe-desc">${p.descripcion||''}</textarea></div>
    <div class="modal-foot">
      <button class="btn btn-ghost" onclick="closeModal()">Cancelar</button>
      <button class="btn btn-primary" onclick="saveProdEdit(${id})">Guardar</button>
    </div>`);
}

async function saveProdEdit(id){
  try{
    const catEl=$('pe-cat');
    const catId=catEl.value?parseInt(catEl.value):null;
    const catNom=catId?catEl.options[catEl.selectedIndex].text:'General';
    const d=await api('/api/producto/editar',{method:'POST',body:JSON.stringify({
      producto_id:id, nombre:$('pe-nom').value, categoria:catNom, categoria_id:catId,
      sku:$('pe-sku').value, precio:parseFloat($('pe-prv').value),
      precio_compra:parseFloat($('pe-prc').value),
      stock:parseInt($('pe-stk').value),
      stock_minimo:parseInt($('pe-stkm').value),
      activo:parseInt($('pe-act').value),
      descripcion:$('pe-desc').value,
    })});
    toast(d.mensaje); closeModal(); loadProds();
  }catch(e){toast(e.message,'err');}
}

// ═══════════════════════════════════════════════
// CATEGORÍAS
// ═══════════════════════════════════════════════
async function loadCats(){
  S.categorias=await api('/api/categorias');
  const tb=$('cat-tb');
  tb.innerHTML=S.categorias.map(c=>`<tr>
    <td>${c.categoria_id}</td><td class="fw7">${c.nombre}</td>
    <td class="text-muted text-sm">${c.descripcion||'—'}</td>
    <td>${c.activo?'<span class="badge bg-green">Activa</span>':'<span class="badge bg-slate">Inactiva</span>'}</td>
    <td><button class="btn btn-ghost btn-xs" onclick="openEditCat(${c.categoria_id})">Editar</button></td>
  </tr>`).join('')||'<tr><td colspan="5" class="empty-state" style="padding:1.5rem">Sin categorías</td></tr>';
}

function openNewCat(){
  openModal('Nueva Categoría',`
    <div class="fg mb1"><label>Nombre *</label><input class="fc" id="cn-nom" placeholder="Ej: Laptops"></div>
    <div class="fg mb1"><label>Descripción</label><input class="fc" id="cn-desc" placeholder="Descripción..."></div>
    <div class="modal-foot">
      <button class="btn btn-ghost" onclick="closeModal()">Cancelar</button>
      <button class="btn btn-primary" onclick="saveCat()">Guardar</button>
    </div>`);
}
async function saveCat(){
  try{
    const d=await api('/api/categoria/nueva',{method:'POST',body:JSON.stringify({
      nombre:$('cn-nom').value, descripcion:$('cn-desc').value})});
    toast(d.mensaje); closeModal(); loadCats();
  }catch(e){toast(e.message,'err');}
}

function openEditCat(id){
  const c=S.categorias.find(x=>x.categoria_id===id); if(!c) return;
  openModal('Editar Categoría',`
    <div class="fg mb1"><label>Nombre</label><input class="fc" id="ce-nom" value="${c.nombre}"></div>
    <div class="fg mb1"><label>Descripción</label><input class="fc" id="ce-desc" value="${c.descripcion||''}"></div>
    <div class="fg mb1"><label>Estado</label><select class="fc" id="ce-act"><option value="1" ${c.activo?'selected':''}>Activa</option><option value="0" ${!c.activo?'selected':''}>Inactiva</option></select></div>
    <div class="modal-foot">
      <button class="btn btn-ghost" onclick="closeModal()">Cancelar</button>
      <button class="btn btn-primary" onclick="saveCatEdit(${id})">Guardar</button>
    </div>`);
}
async function saveCatEdit(id){
  try{
    const d=await api('/api/categoria/editar',{method:'POST',body:JSON.stringify({
      categoria_id:id, nombre:$('ce-nom').value,
      descripcion:$('ce-desc').value, activo:parseInt($('ce-act').value)})});
    toast(d.mensaje); closeModal(); loadCats();
  }catch(e){toast(e.message,'err');}
}

function refreshCatSel(){
  const sel=document.querySelectorAll('[id^="pn-cat"],[id^="pe-cat"]');
  sel.forEach(s=>{
    const v=s.value;
    s.innerHTML='<option value="">Sin categoría</option>'+S.categorias.map(c=>`<option value="${c.categoria_id}">${c.nombre}</option>`).join('');
    s.value=v;
  });
}

// ═══════════════════════════════════════════════
// CLIENTES
// ═══════════════════════════════════════════════
async function loadClis(){
  S.clientes=await api('/api/clientes');
  renderClis(S.clientes);
  // Actualizar select en carrito y otros lugares
  const csel=$('c-cli');
  if(csel) csel.innerHTML='<option value="">— Consumidor final —</option>'+S.clientes.map(c=>`<option value="${c.cliente_id}">${c.nombre}</option>`).join('');
}
function filterClis(){
  const q=$('cli-q').value.toLowerCase();
  renderClis(S.clientes.filter(c=>c.nombre.toLowerCase().includes(q)||c.email.toLowerCase().includes(q)));
}
function renderClis(clis){
  const tb=$('cli-tb');
  tb.innerHTML=clis.map(c=>`<tr>
    <td>${c.cliente_id}</td><td class="fw7">${c.nombre}</td>
    <td>${c.email}</td><td>${c.ciudad}</td>
    <td>${c.telefono||'—'}</td>
    <td><span class="badge bg-slate">${c.tipo}</span></td>
    <td>${c.activo?'<span class="badge bg-green">Activo</span>':'<span class="badge bg-red">Inactivo</span>'}</td>
    <td><button class="btn btn-ghost btn-xs" onclick="openEditCli(${c.cliente_id})">Editar</button></td>
  </tr>`).join('')||'<tr><td colspan="8" class="empty-state" style="padding:1.5rem">Sin clientes</td></tr>';
}

function openNewCli(){
  openModal('Nuevo Cliente',`
    <div class="form-grid">
      <div class="fg"><label>Nombre *</label><input class="fc" id="cln-nom" placeholder="Nombre completo"></div>
      <div class="fg"><label>Email *</label><input class="fc" type="email" id="cln-em" placeholder="correo@ejemplo.com"></div>
      <div class="fg"><label>Ciudad *</label><input class="fc" id="cln-ciu" placeholder="Medellín"></div>
      <div class="fg"><label>Teléfono</label><input class="fc" id="cln-tel" placeholder="+57 300..."></div>
      <div class="fg"><label>NIT / CC</label><input class="fc" id="cln-nit" placeholder="Documento"></div>
      <div class="fg"><label>Tipo</label><select class="fc" id="cln-tipo"><option value="natural">Natural</option><option value="juridico">Jurídico</option></select></div>
    </div>
    <div class="modal-foot">
      <button class="btn btn-ghost" onclick="closeModal()">Cancelar</button>
      <button class="btn btn-primary" onclick="saveCli()">Guardar</button>
    </div>`);
}
async function saveCli(){
  try{
    const d=await api('/api/cliente/nuevo',{method:'POST',body:JSON.stringify({
      nombre:$('cln-nom').value, email:$('cln-em').value, ciudad:$('cln-ciu').value,
      telefono:$('cln-tel').value, nit_cc:$('cln-nit').value, tipo:$('cln-tipo').value})});
    toast(d.mensaje); closeModal(); loadClis(); loadResumen();
  }catch(e){toast(e.message,'err');}
}
function openEditCli(id){
  const c=S.clientes.find(x=>x.cliente_id===id); if(!c) return;
  openModal('Editar: '+c.nombre,`
    <div class="form-grid">
      <div class="fg"><label>Nombre</label><input class="fc" id="cle-nom" value="${c.nombre}"></div>
      <div class="fg"><label>Email</label><input class="fc" id="cle-em" value="${c.email}"></div>
      <div class="fg"><label>Ciudad</label><input class="fc" id="cle-ciu" value="${c.ciudad}"></div>
      <div class="fg"><label>Teléfono</label><input class="fc" id="cle-tel" value="${c.telefono||''}"></div>
      <div class="fg"><label>Estado</label><select class="fc" id="cle-act"><option value="1" ${c.activo?'selected':''}>Activo</option><option value="0" ${!c.activo?'selected':''}>Inactivo</option></select></div>
    </div>
    <div class="modal-foot">
      <button class="btn btn-ghost" onclick="closeModal()">Cancelar</button>
      <button class="btn btn-primary" onclick="saveCliEdit(${id})">Guardar</button>
    </div>`);
}
async function saveCliEdit(id){
  try{
    const d=await api('/api/cliente/editar',{method:'POST',body:JSON.stringify({
      cliente_id:id, nombre:$('cle-nom').value, email:$('cle-em').value,
      ciudad:$('cle-ciu').value, telefono:$('cle-tel').value,
      activo:parseInt($('cle-act').value)})});
    toast(d.mensaje); closeModal(); loadClis();
  }catch(e){toast(e.message,'err');}
}

// ═══════════════════════════════════════════════
// PROVEEDORES
// ═══════════════════════════════════════════════
async function loadProvs(){
  const rows=await api('/api/proveedores');
  const tb=$('prov-tb');
  tb.innerHTML=rows.map(p=>`<tr>
    <td>${p.proveedor_id}</td><td class="fw7">${p.nombre}</td>
    <td>${p.contacto||'—'}</td><td>${p.telefono||'—'}</td>
    <td>${p.ciudad||'—'}</td><td><code>${p.nit||'—'}</code></td>
    <td>${p.activo?'<span class="badge bg-green">Activo</span>':'<span class="badge bg-red">Inactivo</span>'}</td>
    <td><button class="btn btn-ghost btn-xs" onclick="openEditProv(${p.proveedor_id},'${p.nombre}')">Editar</button></td>
  </tr>`).join('')||'<tr><td colspan="8" class="empty-state" style="padding:1.5rem">Sin proveedores</td></tr>';
}
function openNewProv(){
  openModal('Nuevo Proveedor',`
    <div class="form-grid">
      <div class="fg"><label>Nombre *</label><input class="fc" id="pvn-nom" placeholder="Empresa"></div>
      <div class="fg"><label>Contacto</label><input class="fc" id="pvn-con" placeholder="Nombre contacto"></div>
      <div class="fg"><label>Teléfono</label><input class="fc" id="pvn-tel" placeholder="+57..."></div>
      <div class="fg"><label>Email</label><input class="fc" id="pvn-em" placeholder="email@empresa.com"></div>
      <div class="fg"><label>Ciudad</label><input class="fc" id="pvn-ciu" placeholder="Ciudad"></div>
      <div class="fg"><label>NIT</label><input class="fc" id="pvn-nit" placeholder="900.000.000-0"></div>
    </div>
    <div class="modal-foot">
      <button class="btn btn-ghost" onclick="closeModal()">Cancelar</button>
      <button class="btn btn-primary" onclick="saveProv()">Guardar</button>
    </div>`);
}
async function saveProv(){
  try{
    const d=await api('/api/proveedor/nuevo',{method:'POST',body:JSON.stringify({
      nombre:$('pvn-nom').value, contacto:$('pvn-con').value,
      telefono:$('pvn-tel').value, email:$('pvn-em').value,
      ciudad:$('pvn-ciu').value, nit:$('pvn-nit').value})});
    toast(d.mensaje); closeModal(); loadProvs();
  }catch(e){toast(e.message,'err');}
}
function openEditProv(id, nombre){
  toast('Función de edición disponible para administradores','info');
}

// ═══════════════════════════════════════════════
// INVENTARIO
// ═══════════════════════════════════════════════
async function loadInvMovs(){
  const rows=await api('/api/inventario/movimientos');
  const tipoBadge={entrada:'bg-green',salida:'bg-red',ajuste:'bg-blue',
    venta:'bg-amber',devolucion:'bg-purple',dano:'bg-red'};
  const tb=$('inv-tb');
  tb.innerHTML=rows.map(m=>`<tr>
    <td class="text-sm">${fmtDT(m.fecha)}</td>
    <td>${m.producto}</td>
    <td><span class="badge ${tipoBadge[m.tipo]||'bg-slate'}">${m.tipo}</span></td>
    <td class="fw7">${m.cantidad}</td>
    <td>${m.stock_antes}</td><td>${m.stock_despues}</td>
    <td class="text-muted text-sm">${m.motivo||'—'}</td>
    <td class="text-sm">${m.usuario||'—'}</td>
  </tr>`).join('')||'<tr><td colspan="8" class="empty-state" style="padding:1.5rem">Sin movimientos</td></tr>';
}

function openAjusteInv(){
  const prodOpts=S.productos.map(p=>`<option value="${p.producto_id}">${p.nombre} (Stock: ${p.stock})</option>`).join('');
  openModal('Ajuste de Inventario',`
    <div class="fg mb1"><label>Producto *</label><select class="fc" id="ai-prod">${prodOpts}</select></div>
    <div class="fg mb1"><label>Tipo *</label><select class="fc" id="ai-tipo">
      <option value="entrada">Entrada</option><option value="salida">Salida</option>
      <option value="ajuste">Ajuste</option><option value="dano">Daño/Pérdida</option>
    </select></div>
    <div class="fg mb1"><label>Cantidad *</label><input class="fc" type="number" id="ai-cant" min="1" value="1"></div>
    <div class="fg mb1"><label>Motivo *</label><input class="fc" id="ai-mot" placeholder="Motivo del ajuste"></div>
    <div class="fg mb1"><label>Referencia (opcional)</label><input class="fc" id="ai-ref" placeholder="Nro documento, factura..."></div>
    <div class="modal-foot">
      <button class="btn btn-ghost" onclick="closeModal()">Cancelar</button>
      <button class="btn btn-primary" onclick="saveAjuste()">Registrar</button>
    </div>`);
}
async function saveAjuste(){
  try{
    const d=await api('/api/inventario/ajuste',{method:'POST',body:JSON.stringify({
      producto_id:parseInt($('ai-prod').value), tipo:$('ai-tipo').value,
      cantidad:parseInt($('ai-cant').value), motivo:$('ai-mot').value,
      referencia:$('ai-ref').value})});
    toast(d.mensaje); closeModal(); loadInvMovs(); loadProds(); loadResumen();
  }catch(e){toast(e.message,'err');}
}

// ═══════════════════════════════════════════════
// CAJA
// ═══════════════════════════════════════════════
async function loadCaja(){
  cajaActiva=await api('/api/caja/sesion');
  const abierta=$('caja-abierta');
  const cerrada=$('caja-cerrada');
  if(cajaActiva){
    abierta.style.display='';
    cerrada.style.display='none';
    $('caja-info-card').innerHTML=`
      <div class="card-hdr"><h2>Sesión Activa</h2>
        <span class="badge bg-green">Abierta</span></div>
      <div class="form-grid">
        <div><div class="kpi-lbl">Cajero</div><div class="fw7">${cajaActiva.cajero}</div></div>
        <div><div class="kpi-lbl">Apertura</div><div class="fw7">${fmtDT(cajaActiva.fecha_apertura)}</div></div>
        <div><div class="kpi-lbl">Monto Inicial</div><div class="fw7">${fmt(cajaActiva.monto_inicial)}</div></div>
      </div>`;
    loadMovsCaja(cajaActiva.sesion_id);
  }else{
    abierta.style.display='none';
    cerrada.style.display='';
    loadHistCaja();
  }
}
async function loadMovsCaja(sid){
  const rows=await api('/api/caja/movimientos?sesion_id='+sid);
  const tb=$('caj-movs-tb');
  tb.innerHTML=rows.map(m=>`<tr>
    <td><span class="badge ${m.tipo==='ingreso'?'bg-green':'bg-red'}">${m.tipo}</span></td>
    <td>${m.concepto}</td><td class="fw7">${fmt(m.monto)}</td>
  </tr>`).join('')||'<tr><td colspan="3" style="text-align:center;color:var(--muted);padding:.85rem">Sin movimientos</td></tr>';
}
async function loadHistCaja(){
  const rows=await api('/api/caja/historial');
  const tb=$('caj-hist-tb');
  tb.innerHTML=rows.map(s=>`<tr>
    <td class="text-sm">${fmtDT(s.fecha_apertura)}</td>
    <td class="text-sm">${fmtDT(s.fecha_cierre)||'—'}</td>
    <td>${fmt(s.monto_inicial)}</td>
    <td>${s.monto_esperado!=null?fmt(s.monto_esperado):'—'}</td>
    <td>${s.monto_contado!=null?fmt(s.monto_contado):'—'}</td>
    <td class="${s.diferencia>0?'':s.diferencia<0?'':''}">
      ${s.diferencia!=null?fmt(s.diferencia):'—'}</td>
    <td><span class="badge ${s.estado==='abierta'?'bg-green':'bg-slate'}">${s.estado}</span></td>
  </tr>`).join('')||'<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:.85rem">Sin historial</td></tr>';
}
function openAbrirCaja(){
  openModal('Abrir Caja',`
    <div class="fg mb1"><label>Monto inicial en caja *</label><input class="fc" type="number" id="ac-monto" placeholder="0" min="0"></div>
    <div class="fg mb1"><label>Notas de apertura</label><input class="fc" id="ac-notas" placeholder="Notas..."></div>
    <div class="modal-foot">
      <button class="btn btn-ghost" onclick="closeModal()">Cancelar</button>
      <button class="btn btn-success" onclick="abrirCaja()">Abrir Caja</button>
    </div>`);
}
async function abrirCaja(){
  try{
    const d=await api('/api/caja/abrir',{method:'POST',body:JSON.stringify({
      monto_inicial:parseFloat($('ac-monto').value||0),
      notas:$('ac-notas').value})});
    toast(d.mensaje); closeModal(); loadCaja();
  }catch(e){toast(e.message,'err');}
}
function openCerrarCaja(){
  openModal('Cerrar Caja',`
    <p class="text-muted text-sm mb1">Registra el dinero físico contado en caja.</p>
    <div class="fg mb1"><label>Monto contado *</label><input class="fc" type="number" id="cc-monto" placeholder="0" min="0"></div>
    <div class="fg mb1"><label>Notas de cierre</label><input class="fc" id="cc-notas" placeholder="Notas..."></div>
    <div class="modal-foot">
      <button class="btn btn-ghost" onclick="closeModal()">Cancelar</button>
      <button class="btn btn-danger" onclick="cerrarCaja()">Cerrar Caja</button>
    </div>`);
}
async function cerrarCaja(){
  try{
    const d=await api('/api/caja/cerrar',{method:'POST',body:JSON.stringify({
      sesion_id:cajaActiva.sesion_id,
      monto_contado:parseFloat($('cc-monto').value||0),
      notas:$('cc-notas').value})});
    toast(`Caja cerrada. Diferencia: ${fmt(d.diferencia)}`); closeModal(); loadCaja();
  }catch(e){toast(e.message,'err');}
}
async function regMovCaja(){
  if(!cajaActiva){toast('No hay caja abierta','err');return;}
  try{
    const d=await api('/api/caja/movimiento',{method:'POST',body:JSON.stringify({
      sesion_id:cajaActiva.sesion_id, tipo:$('caj-tipo').value,
      concepto:$('caj-concepto').value, monto:parseFloat($('caj-monto').value||0)})});
    toast(d.mensaje); $('caj-concepto').value=''; $('caj-monto').value='';
    loadMovsCaja(cajaActiva.sesion_id);
  }catch(e){toast(e.message,'err');}
}

// ═══════════════════════════════════════════════
// POS / CARRITO
// ═══════════════════════════════════════════════
function renderPOS(prods){
  const c=$('pos-list');
  c.innerHTML=prods.map(p=>`
    <div class="pos-row ${p.stock===0?'oos':''}" ${p.stock>0?`onclick="addCart(${p.producto_id})"`:''}>
      <div class="pos-rinfo">
        <div class="pos-rnm">${p.nombre}</div>
        <div class="pos-rcat">${p.categoria} · Stock: ${p.stock}</div>
      </div>
      <div class="pos-rprice">${fmt(p.precio)}</div>
      ${p.stock>0?'<div class="pos-radd">+</div>':'<span class="text-muted" style="font-size:.7rem">Agotado</span>'}
    </div>`).join('');
}
function filterPOS(){
  const q=$('pos-q').value.toLowerCase();
  renderPOS(S.productos.filter(p=>p.nombre.toLowerCase().includes(q)||p.categoria.toLowerCase().includes(q)));
}
function addCart(pid){
  const p=S.productos.find(x=>x.producto_id===pid); if(!p||p.stock===0) return;
  const item=S.cart.find(i=>i.producto_id===pid);
  if(item){if(item.qty>=p.stock){toast('Stock máximo: '+p.stock,'err');return;} item.qty++;}
  else S.cart.push({producto_id:pid,nombre:p.nombre,precio:p.precio,qty:1});
  renderCart();
}
function chgQty(pid,d){
  const idx=S.cart.findIndex(i=>i.producto_id===pid);
  if(idx<0) return;
  S.cart[idx].qty+=d;
  if(S.cart[idx].qty<=0) S.cart.splice(idx,1);
  renderCart();
}
function remCart(pid){S.cart=S.cart.filter(i=>i.producto_id!==pid);renderCart();}
function clearCart(){S.cart=[];renderCart();}
function renderCart(){
  const box=$('cart-items');
  if(!S.cart.length){
    box.innerHTML='<div class="cart-empty">Agrega productos al carrito</div>';
    $('btn-cobrar').disabled=true;
  }else{
    box.innerHTML=S.cart.map(i=>`
      <div class="ci">
        <div class="ci-info"><div class="ci-nm">${i.nombre}</div><div class="ci-pr">${fmt(i.precio)} c/u</div></div>
        <div class="ci-ctrl">
          <div class="ci-btn" onclick="chgQty(${i.producto_id},-1)">−</div>
          <span class="ci-qty">${i.qty}</span>
          <div class="ci-btn" onclick="chgQty(${i.producto_id},1)">+</div>
        </div>
        <span class="ci-sub">${fmt(i.precio*i.qty)}</span>
        <button class="ci-del" onclick="remCart(${i.producto_id})">✕</button>
      </div>`).join('');
    $('btn-cobrar').disabled=false;
  }
  const sub=S.cart.reduce((a,i)=>a+i.precio*i.qty,0);
  const iva=sub*0.19;
  $('c-sub').textContent=fmt(sub);
  $('c-iva').textContent=fmt(iva);
  $('c-tot').textContent=fmt(sub+iva);
}
async function cobrar(){
  if(!S.cart.length) return;
  const btn=$('btn-cobrar'); btn.disabled=true; btn.textContent='Procesando...';
  try{
    const cli=$('c-cli').value;
    const d=await api('/api/facturar',{method:'POST',body:JSON.stringify({
      items:S.cart.map(i=>({producto_id:i.producto_id,cantidad:i.qty})),
      metodo_pago:$('c-pago').value,
      cliente_id:cli?parseInt(cli):null})});
    clearCart(); toast(d.mensaje+' · '+fmt(d.total));
    mostrarFacturaPrint(d);
    await Promise.all([loadResumen(),loadProds(),loadFacs()]);
  }catch(e){toast(e.message,'err');}
  finally{btn.disabled=false;btn.textContent='Generar Factura';}
}
function mostrarFacturaPrint(d){
  const lins=d.lineas.map(l=>`<tr><td>${l.nombre}</td><td style="text-align:center">${l.cantidad}</td><td style="text-align:right">${fmt(l.precio_unit)}</td><td style="text-align:right">${fmt(l.subtotal)}</td></tr>`).join('');
  openModal('Factura '+d.numero,`
    <div class="fac-print">
      <div class="fac-ph"><h2>TechStore ERP</h2><div class="num">${d.numero}</div><div class="text-sm text-muted">${new Date().toLocaleString('es-CO')}</div></div>
      <div class="tbl-wrap"><table><thead><tr><th>Producto</th><th style="text-align:center">Cant.</th><th style="text-align:right">Precio</th><th style="text-align:right">Sub</th></tr></thead><tbody>${lins}</tbody></table></div>
      <div class="fac-tot">
        <div class="row"><span>Subtotal</span><span>${fmt(d.subtotal)}</span></div>
        <div class="row"><span>IVA 19%</span><span>${fmt(d.impuesto)}</span></div>
        <div class="row tot"><strong>Total</strong><strong>${fmt(d.total)}</strong></div>
      </div>
      <div class="text-muted text-sm" style="text-align:center;margin-top:.85rem">Pago: ${d.metodo_pago} · Gracias por su compra</div>
    </div>
    <div class="modal-foot"><button class="btn btn-ghost" onclick="closeModal()">Cerrar</button></div>`);
}

// ═══════════════════════════════════════════════
// FACTURAS / HISTORIAL
// ═══════════════════════════════════════════════
async function loadFacs(){
  S.facturas=await api('/api/facturas');
  renderFacs(S.facturas); loadDashFacs();
}
function filterFacs(){
  const q=$('fac-q').value.toLowerCase();
  renderFacs(S.facturas.filter(f=>(f.numero+f.cliente+f.vendedor).toLowerCase().includes(q)));
}
function facBadge(est){
  const m={pagada:'bg-green',anulada:'bg-red',pendiente:'bg-amber'};
  return `<span class="badge ${m[est]||'bg-slate'}">${est}</span>`;
}
function renderFacs(rows){
  const tb=$('fac-tb');
  tb.innerHTML=rows.map(f=>`<tr>
    <td><strong>${f.numero}</strong></td>
    <td class="text-sm">${fmtDT(f.fecha)}</td>
    <td>${f.cliente||'<span class="text-muted">Anónimo</span>'}</td>
    <td class="text-sm">${f.vendedor}</td>
    <td class="fw7">${fmt(f.total)}</td>
    <td class="text-sm">${f.metodo_pago}</td>
    <td>${facBadge(f.estado)}</td>
    <td>
      <button class="btn btn-ghost btn-xs" onclick="verFac(${f.factura_id})">Ver</button>
      ${f.estado==='pagada'?`<button class="btn btn-ghost btn-xs" style="color:var(--red)" onclick="anularFac(${f.factura_id})">Anular</button>`:''}
    </td>
  </tr>`).join('')||'<tr><td colspan="8" class="empty-state" style="padding:1.5rem">Sin facturas</td></tr>';
}
async function verFac(id){
  const d=await api('/api/factura/'+id);
  const lins=d.lineas.map(l=>`<tr><td>${l.producto}</td><td style="text-align:center">${l.cantidad}</td><td style="text-align:right">${fmt(l.precio_unit)}</td><td style="text-align:right">${fmt(l.subtotal)}</td></tr>`).join('');
  openModal('Factura '+d.numero,`
    <div class="fac-print">
      <div class="fac-ph"><h2>TechStore ERP</h2><div class="num">${d.numero}</div><div class="text-sm text-muted">${fmtDT(d.fecha)}</div></div>
      <div class="form-grid" style="margin-bottom:.85rem">
        <div><div class="kpi-lbl">Cliente</div><div class="fw7">${d.cliente_nombre||'Anónimo'}</div></div>
        <div><div class="kpi-lbl">Vendedor</div><div class="fw7">${d.vendedor_nombre}</div></div>
        <div><div class="kpi-lbl">Pago</div><div class="fw7">${d.metodo_pago}</div></div>
        <div><div class="kpi-lbl">Estado</div>${facBadge(d.estado)}</div>
      </div>
      <div class="tbl-wrap"><table><thead><tr><th>Producto</th><th style="text-align:center">Cant.</th><th style="text-align:right">Precio</th><th style="text-align:right">Sub</th></tr></thead><tbody>${lins}</tbody></table></div>
      <div class="fac-tot">
        <div class="row"><span>Subtotal</span><span>${fmt(d.subtotal)}</span></div>
        ${d.descuento>0?`<div class="row"><span>Descuento</span><span>-${fmt(d.descuento)}</span></div>`:''}
        <div class="row"><span>IVA 19%</span><span>${fmt(d.impuesto)}</span></div>
        <div class="row tot"><strong>Total</strong><strong>${fmt(d.total)}</strong></div>
      </div>
    </div>
    <div class="modal-foot"><button class="btn btn-ghost" onclick="closeModal()">Cerrar</button></div>`);
}
async function anularFac(id){
  const mot=prompt('Motivo de anulación:'); if(!mot) return;
  try{
    const d=await api('/api/factura/anular',{method:'POST',body:JSON.stringify({factura_id:id,motivo:mot})});
    toast(d.mensaje); loadFacs(); loadResumen(); loadProds();
  }catch(e){toast(e.message,'err');}
}

// ═══════════════════════════════════════════════
// USUARIOS
// ═══════════════════════════════════════════════
async function loadUsers(){
  const rows=await api('/api/usuarios');
  const rolPills={superadmin:'bg-red',admin:'bg-blue',supervisor:'bg-green',
    vendedor:'bg-purple',cajero:'bg-amber',bodeguero:'bg-blue',
    contador:'bg-purple',consultor:'bg-slate'};
  const tb=$('usr-tb');
  tb.innerHTML=rows.map(u=>`<tr>
    <td>${u.usuario_id}</td><td><code>${u.username}</code></td>
    <td>${u.nombre}</td><td class="text-sm">${u.email}</td>
    <td><span class="badge ${rolPills[u.rol]||'bg-slate'}">${u.rol}</span></td>
    <td>${u.activo?'<span class="badge bg-green">Activo</span>':'<span class="badge bg-red">Inactivo</span>'}</td>
    <td><button class="btn btn-ghost btn-xs" onclick="openEditUser(${u.usuario_id})">Editar</button></td>
  </tr>`).join('')||'<tr><td colspan="7" class="empty-state" style="padding:1.5rem">Sin usuarios</td></tr>';
}
function openNewUser(){
  const roles=['superadmin','admin','supervisor','vendedor','cajero','bodeguero','contador','consultor'];
  openModal('Nuevo Usuario',`
    <div class="form-grid">
      <div class="fg"><label>Username *</label><input class="fc" id="un-usr" placeholder="nombre.usuario"></div>
      <div class="fg"><label>Nombre *</label><input class="fc" id="un-nom" placeholder="Nombre completo"></div>
      <div class="fg"><label>Email *</label><input class="fc" type="email" id="un-em" placeholder="email@empresa.com"></div>
      <div class="fg"><label>Contraseña *</label><input class="fc" type="password" id="un-pw" placeholder="Mínimo 6 caracteres"></div>
      <div class="fg"><label>Rol *</label><select class="fc" id="un-rol">${roles.map(r=>`<option value="${r}">${r}</option>`).join('')}</select></div>
    </div>
    <div class="modal-foot">
      <button class="btn btn-ghost" onclick="closeModal()">Cancelar</button>
      <button class="btn btn-primary" onclick="saveUser()">Crear Usuario</button>
    </div>`);
}
async function saveUser(){
  try{
    const d=await api('/api/usuario/nuevo',{method:'POST',body:JSON.stringify({
      username:$('un-usr').value, nombre:$('un-nom').value,
      email:$('un-em').value, password:$('un-pw').value, rol:$('un-rol').value})});
    toast(d.mensaje); closeModal(); loadUsers();
  }catch(e){toast(e.message,'err');}
}
function openEditUser(id){
  const roles=['superadmin','admin','supervisor','vendedor','cajero','bodeguero','contador','consultor'];
  openModal('Editar Usuario',`
    <div class="form-grid">
      <div class="fg"><label>Rol</label><select class="fc" id="ue-rol">${roles.map(r=>`<option value="${r}">${r}</option>`).join('')}</select></div>
      <div class="fg"><label>Estado</label><select class="fc" id="ue-act"><option value="1">Activo</option><option value="0">Inactivo</option></select></div>
      <div class="fg"><label>Nueva contraseña (opcional)</label><input class="fc" type="password" id="ue-pw" placeholder="Dejar vacío para no cambiar"></div>
    </div>
    <div class="modal-foot">
      <button class="btn btn-ghost" onclick="closeModal()">Cancelar</button>
      <button class="btn btn-primary" onclick="saveUserEdit(${id})">Guardar</button>
    </div>`);
}
async function saveUserEdit(id){
  try{
    const body={usuario_id:id, rol:$('ue-rol').value, activo:parseInt($('ue-act').value)};
    if($('ue-pw').value) body.password=$('ue-pw').value;
    const d=await api('/api/usuario/editar',{method:'POST',body:JSON.stringify(body)});
    toast(d.mensaje); closeModal(); loadUsers();
  }catch(e){toast(e.message,'err');}
}

// ═══════════════════════════════════════════════
// AUDITORÍA
// ═══════════════════════════════════════════════
async function loadAudit(){
  const rows=await api('/api/auditoria');
  const tb=$('audit-tb');
  tb.innerHTML=rows.map(a=>`<tr>
    <td class="text-sm">${fmtDT(a.fecha)}</td>
    <td class="text-sm">${a.username||'sistema'}</td>
    <td><span class="badge bg-blue">${a.modulo}</span></td>
    <td><strong>${a.accion}</strong></td>
    <td class="text-muted text-sm">${a.descripcion||'—'}</td>
  </tr>`).join('')||'<tr><td colspan="5" class="empty-state" style="padding:1.5rem">Sin registros</td></tr>';
  loadRechazos();
}
async function loadRechazos(){
  try{
    const rows=await api('/api/rechazos');
    const tb=$('rech-tb');
    tb.innerHTML=rows.map(r=>`<tr>
      <td>${r.rechazo_id}</td><td>Fila ${r.fila_origen}</td>
      <td><code>${r.pedido_id||'N/A'}</code></td>
      <td style="color:var(--red)">${r.motivo}</td>
      <td class="text-sm text-muted">${fmtDT(r.creado_en)}</td>
    </tr>`).join('')||'<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:1rem">Sin rechazos</td></tr>';
  }catch(e){}
}
async function runETL(){
  try{const d=await api('/api/etl');toast('ETL ejecutado. Registros: '+d.pedidos_en_bd);}
  catch(e){toast(e.message,'err');}
}

// ═══════════════════════════════════════════════
// CONFIGURACIÓN
// ═══════════════════════════════════════════════
async function loadConfig(){
  configData=await api('/api/configuracion');
  const campos=[
    {k:'empresa_nombre',  l:'Nombre del Negocio'},
    {k:'empresa_nit',     l:'NIT'},
    {k:'empresa_ciudad',  l:'Ciudad'},
    {k:'empresa_telefono',l:'Teléfono'},
    {k:'empresa_email',   l:'Email'},
    {k:'empresa_direccion',l:'Dirección'},
  ];
  $('cfg-form').innerHTML=campos.map(c=>`
    <div class="fg"><label>${c.l}</label>
      <input class="fc" id="cfg-${c.k}" value="${configData[c.k]||''}">
    </div>`).join('');
  const params=[
    {k:'moneda',l:'Moneda'},{k:'iva_porcentaje',l:'IVA %'},
    {k:'stock_minimo',l:'Alerta Stock Mínimo'},
  ];
  $('cfg-params').innerHTML=params.map(c=>`
    <div class="fg mb1"><label>${c.l}</label>
      <input class="fc" id="cfg-${c.k}" value="${configData[c.k]||''}">
    </div>`).join('');
}
async function saveConfig(){
  const campos=['empresa_nombre','empresa_nit','empresa_ciudad','empresa_telefono',
    'empresa_email','empresa_direccion','moneda','iva_porcentaje','stock_minimo'];
  const cambios={};
  campos.forEach(k=>{const el=$('cfg-'+k);if(el) cambios[k]=el.value;});
  try{
    const d=await api('/api/configuracion/guardar',{method:'POST',body:JSON.stringify(cambios)});
    toast(d.mensaje);
  }catch(e){toast(e.message,'err');}
}

// ═══════════════════════════════════════════════
// AUTH
// ═══════════════════════════════════════════════
async function doLogout(){
  await fetch('/logout');
  location.href='/login';
}

// RBAC visible en frontend (igual que Python)
window.PERMS_SIDEBAR={
  superadmin:['dashboard','ventas','historial','productos','inventario','categorias','clientes','proveedores','caja','finanzas','usuarios','auditoria','reportes','configuracion'],
  admin:     ['dashboard','ventas','historial','productos','inventario','categorias','clientes','proveedores','caja','finanzas','usuarios','auditoria','reportes','configuracion'],
  supervisor:['dashboard','ventas','historial','productos','inventario','clientes','caja','finanzas','auditoria','reportes'],
  vendedor:  ['dashboard','ventas','historial','productos','clientes'],
  cajero:    ['dashboard','ventas','caja','historial'],
  bodeguero: ['dashboard','productos','inventario'],
  contador:  ['dashboard','finanzas','ventas','historial','caja','reportes'],
  consultor: ['dashboard','ventas','historial','inventario','finanzas','auditoria','reportes'],
};
</script>
</body></html>"""

# ═══════════════════════════════════════════════════════════════════════════
# HTTP HANDLER
# ═══════════════════════════════════════════════════════════════════════════

def _tok(handler: "Handler") -> str | None:
    c = http.cookies.SimpleCookie(handler.headers.get("Cookie",""))
    m = c.get("ts_session")
    return m.value if m else None

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _j(self, data: Any, st: int = 200):
        raw = json.dumps(data, ensure_ascii=False, default=str).encode()
        self.send_response(st)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(raw)))
        self.send_header("Cache-Control","no-cache, no-store, must-revalidate")
        self.send_header("Pragma","no-cache")
        self.send_header("Expires","0")
        self.end_headers(); self.wfile.write(raw)

    def _h(self, html: str, st: int = 200):
        raw = html.encode()
        self.send_response(st)
        self.send_header("Content-Type","text/html; charset=utf-8")
        self.send_header("Content-Length",str(len(raw)))
        self.send_header("Cache-Control","no-cache, no-store, must-revalidate")
        self.send_header("Pragma","no-cache")
        self.send_header("Expires","0")
        self.end_headers(); self.wfile.write(raw)

    def _r(self, loc: str, cookie: str = None):
        self.send_response(302)
        self.send_header("Location", loc)
        if cookie: self.send_header("Set-Cookie", cookie)
        self.end_headers()

    def _me(self) -> dict | None:
        return verificar_sesion(_tok(self), DEFAULT_DB_PATH)

    def _auth(self) -> dict | None:
        u = self._me()
        if not u: self._j({"error":"No autenticado."},401)
        return u

    def _perm(self, modulo: str, escritura: bool = False) -> dict | None:
        u = self._auth()
        if not u: return None
        try: req_perm(u["rol"], modulo, escritura)
        except ErrorOperacion as e: self._j({"error":str(e)},403); return None
        return u

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length",0))
        raw = self.rfile.read(n).decode() if n else "{}"
        try: return json.loads(raw)
        except: return {}

    # ── GET ──────────────────────────────────────────────────────────────
    def do_GET(self):
        p = urllib.parse.urlparse(self.path)
        path = p.path
        qs   = urllib.parse.parse_qs(p.query)

        if path in ("/","/index.html"):
            self._r("/app" if self._me() else "/login"); return
        if path == "/login":  self._h(HTML_LOGIN); return
        if path == "/app":
            if not self._me(): self._r("/login"); return
            self._h(HTML_APP); return
        if path == "/logout":
            tok = _tok(self)
            if tok: cerrar_sesion(tok, DEFAULT_DB_PATH)
            self._r("/login","ts_session=; Max-Age=0; Path=/; HttpOnly"); return

        # ── API ──
        if path == "/api/me":
            u = self._auth()
            if u: self._j(u); return

        elif path == "/api/resumen":
            if not self._auth(): return
            self._j(resumen(DEFAULT_DB_PATH))

        elif path == "/api/productos":
            if not self._auth(): return
            show_all = qs.get("all",["0"])[0]=="1"
            self._j(listar_productos(solo_activos=not show_all, db_path=DEFAULT_DB_PATH))

        elif path == "/api/categorias":
            if not self._auth(): return
            self._j(listar_categorias(DEFAULT_DB_PATH))

        elif path == "/api/clientes":
            if not self._auth(): return
            self._j(listar_clientes(DEFAULT_DB_PATH))

        elif path == "/api/proveedores":
            if not self._auth(): return
            self._j(listar_proveedores(DEFAULT_DB_PATH))

        elif path == "/api/facturas":
            u = self._auth()
            if not u: return
            vid = None if u["rol"] in ("superadmin","admin","supervisor","contador","consultor") else u["usuario_id"]
            self._j(listar_facturas(vendedor_id=vid, db_path=DEFAULT_DB_PATH))

        elif path.startswith("/api/factura/"):
            if not self._auth(): return
            try: self._j(detalle_factura_por_id(int(path.split("/")[-1]), DEFAULT_DB_PATH))
            except ErrorOperacion as e: self._j({"error":str(e)},404)

        elif path == "/api/inventario/movimientos":
            if not self._auth(): return
            pid = qs.get("producto_id",[None])[0]
            self._j(listar_movimientos_inv(prod_id=int(pid) if pid else None, db_path=DEFAULT_DB_PATH))

        elif path == "/api/caja/sesion":
            if not self._auth(): return
            sc = sesion_caja_activa(DEFAULT_DB_PATH)
            self._j(sc or {})

        elif path == "/api/caja/historial":
            if not self._auth(): return
            self._j(listar_sesiones_caja(db_path=DEFAULT_DB_PATH))

        elif path == "/api/caja/movimientos":
            if not self._auth(): return
            sid = qs.get("sesion_id",[None])[0]
            if sid: self._j(movimientos_de_sesion(int(sid), DEFAULT_DB_PATH))
            else: self._j([])

        elif path == "/api/rechazos":
            if not self._auth(): return
            conn = conectar(DEFAULT_DB_PATH)
            rows = conn.execute("SELECT * FROM rechazos_carga ORDER BY rechazo_id DESC").fetchall()
            conn.close(); self._j([dict(r) for r in rows])

        elif path == "/api/auditoria":
            if not self._perm("auditoria"): return
            self._j(listar_auditoria(db_path=DEFAULT_DB_PATH))

        elif path == "/api/usuarios":
            if not self._perm("usuarios"): return
            self._j(listar_usuarios(DEFAULT_DB_PATH))

        elif path == "/api/configuracion":
            if not self._auth(): return
            self._j(obtener_config(DEFAULT_DB_PATH))

        elif path == "/api/etl":
            if not self._perm("auditoria"): return
            res = cargar_dataset(DEFAULT_DB_PATH, DEFAULT_DATASET)
            self._j(res.como_diccionario())

        else:
            self.send_error(404,"Not found")

    # ── POST ─────────────────────────────────────────────────────────────
    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        b    = self._body()

        # LOGIN — sin auth
        if path == "/api/login":
            try:
                u     = autenticar_usuario(b.get("username",""), b.get("password",""), DEFAULT_DB_PATH)
                token = crear_sesion(u["usuario_id"], DEFAULT_DB_PATH)
                audit(u["usuario_id"],"login","auth",f"Login: {u['username']}", DEFAULT_DB_PATH)
                raw = json.dumps({"ok":True,"rol":u["rol"]}).encode()
                self.send_response(200)
                self.send_header("Content-Type","application/json; charset=utf-8")
                self.send_header("Content-Length",str(len(raw)))
                self.send_header("Set-Cookie",f"ts_session={token}; Max-Age=28800; Path=/; HttpOnly")
                self.end_headers(); self.wfile.write(raw)
            except ErrorOperacion as e: self._j({"error":str(e)},401)
            return

        u = self._auth()
        if not u: return

        try:
            if path == "/api/facturar":
                req_perm(u["rol"],"ventas",True)
                res = registrar_factura(
                    items=b.get("items",[]), vendedor_id=u["usuario_id"],
                    metodo_pago=b.get("metodo_pago","efectivo"),
                    cliente_id=int(b["cliente_id"]) if b.get("cliente_id") else None,
                    descuento=float(b.get("descuento",0)),
                    notas=b.get("notas",""), db_path=DEFAULT_DB_PATH)
                audit(u["usuario_id"],"venta","ventas",f"Factura {res['numero']} · {res['total']}", DEFAULT_DB_PATH)
                self._j(res)

            elif path == "/api/factura/anular":
                req_perm(u["rol"],"ventas",True)
                self._j(anular_factura(int(b.get("factura_id",0)), b.get("motivo",""), u["usuario_id"], DEFAULT_DB_PATH))

            elif path == "/api/producto/nuevo":
                req_perm(u["rol"],"productos",True)
                self._j(crear_producto(db_path=DEFAULT_DB_PATH,**{k:b[k] for k in b if k in
                    {"nombre","categoria","categoria_id","sku","descripcion","precio_compra","precio","stock","stock_minimo"}}))

            elif path == "/api/producto/editar":
                req_perm(u["rol"],"productos",True)
                pid = int(b.pop("producto_id",0))
                self._j(editar_producto(pid, b, DEFAULT_DB_PATH))

            elif path == "/api/categoria/nueva":
                req_perm(u["rol"],"categorias",True)
                self._j(crear_categoria(b.get("nombre",""), b.get("descripcion",""), DEFAULT_DB_PATH))

            elif path == "/api/categoria/editar":
                req_perm(u["rol"],"categorias",True)
                self._j(editar_categoria(int(b.pop("categoria_id",0)),
                    b.get("nombre"), b.get("descripcion"),
                    int(b["activo"]) if "activo" in b else None, DEFAULT_DB_PATH))

            elif path == "/api/cliente/nuevo":
                req_perm(u["rol"],"clientes",True)
                self._j(crear_cliente(b.get("nombre",""), b.get("email",""),
                    b.get("ciudad",""), b.get("telefono",""),
                    b.get("nit_cc",""), b.get("tipo","natural"), DEFAULT_DB_PATH))

            elif path == "/api/cliente/editar":
                req_perm(u["rol"],"clientes",True)
                cid = int(b.pop("cliente_id",0))
                self._j(editar_cliente(cid, b, DEFAULT_DB_PATH))

            elif path == "/api/proveedor/nuevo":
                req_perm(u["rol"],"proveedores",True)
                self._j(crear_proveedor(db_path=DEFAULT_DB_PATH, **{k:b.get(k,"") for k in
                    ["nombre","contacto","telefono","email","ciudad","nit"]}))

            elif path == "/api/inventario/ajuste":
                req_perm(u["rol"],"inventario",True)
                self._j(ajustar_inventario(
                    int(b.get("producto_id",0)), b.get("tipo","ajuste"),
                    int(b.get("cantidad",0)), b.get("motivo",""),
                    u["usuario_id"], b.get("referencia",""), DEFAULT_DB_PATH))

            elif path == "/api/caja/abrir":
                req_perm(u["rol"],"caja",True)
                self._j(abrir_caja(u["usuario_id"], float(b.get("monto_inicial",0)),
                    b.get("notas",""), DEFAULT_DB_PATH))

            elif path == "/api/caja/cerrar":
                req_perm(u["rol"],"caja",True)
                self._j(cerrar_caja(int(b.get("sesion_id",0)),
                    float(b.get("monto_contado",0)), b.get("notas",""), DEFAULT_DB_PATH))

            elif path == "/api/caja/movimiento":
                req_perm(u["rol"],"caja",True)
                self._j(mov_caja(int(b.get("sesion_id",0)), b.get("tipo","ingreso"),
                    b.get("concepto",""), float(b.get("monto",0)),
                    u["usuario_id"], b.get("referencia",""), DEFAULT_DB_PATH))

            elif path == "/api/usuario/nuevo":
                req_perm(u["rol"],"usuarios",True)
                self._j(crear_usuario(b.get("username",""), b.get("password",""),
                    b.get("nombre",""), b.get("email",""), b.get("rol","vendedor"), DEFAULT_DB_PATH))

            elif path == "/api/usuario/editar":
                req_perm(u["rol"],"usuarios",True)
                uid = int(b.pop("usuario_id",0))
                self._j(editar_usuario(uid, b, DEFAULT_DB_PATH))

            elif path == "/api/configuracion/guardar":
                req_perm(u["rol"],"configuracion",True)
                self._j(guardar_config(b, DEFAULT_DB_PATH))

            elif path == "/api/entregar":
                req_perm(u["rol"],"ventas",True)
                self._j(marcar_entregado(b.get("pedido_id",""), int(b.get("dias",0)), DEFAULT_DB_PATH))

            else:
                self.send_error(404,"Not found")

        except ErrorOperacion as e:
            self._j({"error":str(e)},400)
        except Exception as e:
            self._j({"error":f"Error inesperado: {e}"},500)


# ═══════════════════════════════════════════════════════════════════════════
# INICIO
# ═══════════════════════════════════════════════════════════════════════════

def iniciar():
    import sys
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    inicializar_db(DEFAULT_DB_PATH)
    cargar_dataset(DEFAULT_DB_PATH, DEFAULT_DATASET)
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://127.0.0.1:{PORT}"
    sep = "-" * 58
    print(sep)
    print("   TECHSTORE ERP - Sistema de Gestion Comercial")
    print(sep)
    print(f"   URL:    {url}")
    print(f"   Login:  {url}/login")
    print()
    print("   superadmin/super123  admin/admin123")
    print("   vendedor1/vend123    cajero1/caj123")
    print()
    print("   Ctrl+C para detener")
    print(sep)
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:    srv.serve_forever()
    except KeyboardInterrupt: print("\n   Servidor detenido.")
    finally: srv.server_close()

if __name__ == "__main__":
    iniciar()
