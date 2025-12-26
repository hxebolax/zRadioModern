========================================
zRadioModern - Carpeta de Bibliotecas
========================================

Esta carpeta contiene todas las dependencias de terceros necesarias
para el funcionamiento del complemento zRadioModern para NVDA.

Las bibliotecas están empaquetadas junto al addon para evitar 
conflictos con otras versiones instaladas en el sistema.

BIBLIOTECAS INCLUIDAS:
======================

Clientes HTTP:
- httpx: Cliente HTTP moderno y asíncrono
- httpcore: Núcleo de transporte HTTP  
- h11: Implementación HTTP/1.1
- requests: Cliente HTTP clásico
- requests_cache: Sistema de caché para requests
- urllib3: Cliente HTTP de bajo nivel

Async y utilidades:
- anyio: Capa de abstracción para async
- certifi: Certificados SSL de Mozilla
- idna: Codificación de nombres de dominio internacionales
- charset_normalizer: Detección de codificación de caracteres

Radio Browser API:
- pyradios: Cliente oficial para RadioBrowser API
- url_normalize: Normalización de URLs

Clases de datos:
- attrs: Clases de datos mejoradas
- cattrs: Serialización de clases attrs

Sistema:
- platformdirs: Directorios de plataforma independientes

Audio:
- mpv.py: Bindings Python para libmpv
- libmpv-2.dll: Biblioteca nativa mpv para reproducción de audio

Tipado:
- typing_extensions.py: Extensiones de tipado para Python

NOTAS:
======
- La DLL de mpv (libmpv-2.dll) DEBE estar en esta carpeta
- El complemento agrega automáticamente esta carpeta al sys.path
- No modificar ni eliminar archivos de esta carpeta

Actualizado: Diciembre 2024
