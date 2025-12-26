# -*- coding: utf-8 -*-
# Copyright (C) 2025 Héctor J. Benítez Corredera <xebolax@gmail.com>
# This file is covered by the GNU General Public License.

"""
Verificador de conexión a Internet para zRadioModern.

Proporciona métodos para verificar la conectividad a Internet
y la disponibilidad de URLs específicas.
"""

from __future__ import annotations
from typing import Optional
import socket
import threading
from urllib.parse import urlparse

from logHandler import log


class InternetChecker:
    """
    Verificador de conexión a Internet.
    
    Proporciona métodos para comprobar si hay conexión a Internet
    y verificar la disponibilidad de URLs específicas.
    """
    
    # Hosts de prueba para verificar conectividad
    TEST_HOSTS = [
        ("8.8.8.8", 53),           # Google DNS
        ("1.1.1.1", 53),           # Cloudflare DNS
        ("208.67.222.222", 53),    # OpenDNS
    ]
    
    # Timeout para conexiones (segundos)
    TIMEOUT = 3
    
    def __init__(self):
        """Inicializa el verificador."""
        self._cached_status: Optional[bool] = None
        self._lock = threading.Lock()
    
    def is_connected(self, force_check: bool = False) -> bool:
        """
        Verifica si hay conexión a Internet.
        
        Args:
            force_check: Si forzar la verificación ignorando caché.
            
        Returns:
            True si hay conexión a Internet.
        """
        if not force_check and self._cached_status is not None:
            return self._cached_status
        
        with self._lock:
            for host, port in self.TEST_HOSTS:
                try:
                    socket.setdefaulttimeout(self.TIMEOUT)
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.connect((host, port))
                    s.close()
                    self._cached_status = True
                    return True
                except (socket.error, socket.timeout):
                    continue
            
            self._cached_status = False
            log.warning("No hay conexión a Internet")
            return False
    
    def check_url(self, url: str, timeout: Optional[int] = None) -> bool:
        """
        Verifica si una URL es accesible.
        
        Args:
            url: URL a verificar.
            timeout: Tiempo de espera en segundos.
            
        Returns:
            True si la URL es accesible.
        """
        if not url:
            return False
        
        if timeout is None:
            timeout = self.TIMEOUT
        
        try:
            parsed = urlparse(url)
            host = parsed.hostname
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            
            if not host:
                return False
            
            socket.setdefaulttimeout(timeout)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((host, port))
            s.close()
            return True
            
        except Exception as e:
            log.debug(f"URL no accesible {url}: {e}")
            return False
    
    def test_internet(self, url: Optional[str] = None) -> bool:
        """
        Prueba la conexión a Internet o una URL específica.
        
        Método de compatibilidad con el complemento original.
        
        Args:
            url: URL opcional a verificar.
            
        Returns:
            True si está conectado/URL accesible.
        """
        if url:
            return self.check_url(url)
        return self.is_connected()
    
    def resolve_host(self, hostname: str) -> Optional[str]:
        """
        Resuelve un hostname a dirección IP.
        
        Args:
            hostname: Nombre de host a resolver.
            
        Returns:
            Dirección IP o None si falla.
        """
        try:
            ip = socket.gethostbyname(hostname)
            return ip
        except socket.gaierror:
            return None
    
    def clear_cache(self) -> None:
        """Limpia el caché de estado de conexión."""
        with self._lock:
            self._cached_status = None
    
    def check_radio_browser_api(self) -> bool:
        """
        Verifica la disponibilidad de la API de RadioBrowser.
        
        Returns:
            True si la API está accesible.
        """
        return self.check_url("https://de1.api.radio-browser.info")
