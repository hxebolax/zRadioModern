# -*- coding: utf-8 -*-
# Copyright (C) 2025 Héctor J. Benítez Corredera <xebolax@gmail.com>
# This file is covered by the GNU General Public License.

"""
Cliente de la API de RadioBrowser para zRadioModern.

Proporciona acceso a la API de radio-browser.info para buscar
emisoras de radio por nombre, país, idioma, etiquetas, etc.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin
import random
import socket
import threading
from concurrent.futures import ThreadPoolExecutor

from logHandler import log

from .models import Station, Country, Language, Tag, SearchFilters
from .config import get_config

# Intentar importar httpx, sino usar requests
try:
    import httpx
    HTTP_CLIENT = "httpx"
except ImportError:
    try:
        import requests
        HTTP_CLIENT = "requests"
    except ImportError:
        HTTP_CLIENT = None
        log.warning("No hay cliente HTTP disponible")


class RadioBrowserAPI:
    """
    Cliente para la API de RadioBrowser.
    
    Proporciona métodos para buscar emisoras, países, idiomas
    y etiquetas desde el servicio radio-browser.info.
    
    La API selecciona automáticamente un servidor disponible
    mediante DNS round-robin.
    """
    
    # Lista de servidores conocidos como fallback
    FALLBACK_SERVERS = [
        "de1.api.radio-browser.info",
        "nl1.api.radio-browser.info",
        "at1.api.radio-browser.info"
    ]
    
    # Tiempo de espera para peticiones (segundos)
    TIMEOUT = 10
    
    def __init__(self, base_url: Optional[str] = None):
        """
        Inicializa el cliente de API.
        
        Args:
            base_url: URL base del servidor API (opcional).
        """
        self._config = get_config()
        self._available_servers: List[str] = []
        self._base_url = base_url
        self._session = None
        self._lock = threading.Lock()
        
        if self._base_url is None:
            self._available_servers = self._discover_servers()
            # Escoger un servidor inicial aleatorio
            if self._available_servers:
                self._base_url = random.choice(self._available_servers)
            else:
                # Fallback extremo
                self._base_url = f"https://{random.choice(self.FALLBACK_SERVERS)}"
        else:
            self._available_servers = [self._base_url]
        
        self._init_session()

    def _discover_servers(self) -> List[str]:
        """
        Descubre los servidores API disponibles mediante DNS.
        
        Returns:
            Lista de URLs de servidores.
        """
        hosts = []
        try:
            # Resolver DNS para obtener servidores disponibles
            ips = socket.getaddrinfo(
                "all.api.radio-browser.info",
                443,
                socket.AF_INET,
                socket.SOCK_STREAM
            )
            
            for ip in ips:
                try:
                    host = socket.gethostbyaddr(ip[4][0])[0]
                    if host not in hosts:
                        hosts.append(host)
                except (socket.herror, socket.gaierror):
                    pass
        except Exception as e:
            log.warning(f"Error descubriendo servidores por DNS: {e}")
        
        if not hosts:
            hosts = self.FALLBACK_SERVERS
            
        return [f"https://{h}" for h in hosts]

    def _rotate_server(self) -> str:
        """
        Cambia al siguiente servidor disponible en caso de error.
        
        Returns:
            URL del nuevo servidor.
        """
        with self._lock:
            if not self._available_servers or len(self._available_servers) <= 1:
                # Intentar re-descubrir si solo teníamos uno
                self._available_servers = self._discover_servers()
            
            if self._base_url in self._available_servers:
                idx = self._available_servers.index(self._base_url)
                next_idx = (idx + 1) % len(self._available_servers)
                self._base_url = self._available_servers[next_idx]
            else:
                self._base_url = random.choice(self._available_servers)
                
            log.info(f"Cambiando a servidor API de respaldo: {self._base_url}")
            return self._base_url
    
    def _init_session(self) -> None:
        """Inicializa la sesión HTTP."""
        if HTTP_CLIENT == "httpx":
            self._session = httpx.Client(
                timeout=self.TIMEOUT,
                headers={
                    "User-Agent": "zRadioModern/2.0 (NVDA Addon)"
                }
            )
        elif HTTP_CLIENT == "requests":
            import requests
            self._session = requests.Session()
            self._session.headers.update({
                "User-Agent": "zRadioModern/2.0 (NVDA Addon)"
            })
    
    def _get(self, endpoint: str, params: Optional[Dict] = None, retry_count: int = 0) -> Any:
        """
        Realiza una petición GET a la API con soporte para failover.
        
        Args:
            endpoint: Endpoint de la API.
            params: Parámetros de la petición.
            retry_count: Contador de reintentos internos.
            
        Returns:
            Respuesta JSON deserializada.
        """
        url = urljoin(self._base_url + "/json/", endpoint)
        
        try:
            with self._lock:
                if HTTP_CLIENT == "httpx":
                    response = self._session.get(url, params=params)
                    response.raise_for_status()
                    return response.json()
                elif HTTP_CLIENT == "requests":
                    response = self._session.get(
                        url, 
                        params=params,
                        timeout=self.TIMEOUT
                    )
                    response.raise_for_status()
                    return response.json()
                else:
                    raise RuntimeError("No hay cliente HTTP disponible")
                    
        except Exception as e:
            # Si es un error de servidor (5xx) o de conexión, intentar con otro servidor
            should_retry = False
            if retry_count < 3: # Máximo 3 intentos con diferentes servidores
                if hasattr(e, 'response') and e.response is not None:
                    # Errores 5xx (Server Error)
                    if 500 <= e.response.status_code < 600:
                        should_retry = True
                else:
                    # Errores de conexión, timeout, etc.
                    should_retry = True
            
            if should_retry:
                log.warning(f"Error en servidor {self._base_url} ({e}). Reintentando con otro servidor...")
                self._rotate_server()
                return self._get(endpoint, params, retry_count + 1)
                
            log.error(f"Error definitivo en petición API {endpoint}: {e}")
            raise
    
    # === Métodos de Búsqueda de Emisoras ===
    
    def get_stations_by_uuid(self, station_uuid: str) -> List[Station]:
        """
        Obtiene una emisora por su UUID.
        
        Args:
            station_uuid: UUID de la emisora.
            
        Returns:
            Lista con la emisora encontrada (o vacía).
        """
        if not station_uuid:
            return []
            
        endpoint = f"stations/byuuid/{station_uuid}"
        try:
            data = self._get(endpoint)
            return [Station(**item) for item in data]
        except Exception as e:
            log.error(f"Error obteniendo emisora por UUID {station_uuid}: {e}")
            return []

    def search_stations(
        self,
        filters: Optional[SearchFilters] = None,
        **kwargs
    ) -> List[Station]:
        """
        Busca emisoras con los filtros especificados.
        
        Args:
            filters: Objeto SearchFilters con los criterios.
            **kwargs: Criterios de búsqueda como argumentos.
            
        Returns:
            Lista de emisoras encontradas.
        """
        if filters:
            params = filters.to_api_params()
        else:
            params = {
                "limit": kwargs.get("limit", 100),
                "offset": kwargs.get("offset", 0),
                "order": kwargs.get("order", "name"),
                "reverse": str(kwargs.get("reverse", False)).lower()
            }
            
            if kwargs.get("name"):
                params["name"] = kwargs["name"]
                params["nameExact"] = str(kwargs.get("name_exact", False)).lower()
            if kwargs.get("country"):
                params["country"] = kwargs["country"]
            if kwargs.get("countrycode"):
                params["countrycode"] = kwargs["countrycode"]
            if kwargs.get("language"):
                params["language"] = kwargs["language"]
            if kwargs.get("tag"):
                params["tag"] = kwargs["tag"]
        
        try:
            data = self._get("stations/search", params)
            return [Station.from_api_response(item) for item in data]
        except Exception as e:
            log.error(f"Error buscando emisoras: {e}")
            return []
    
    def search_by_name(
        self,
        name: str,
        exact: bool = False,
        limit: int = 100
    ) -> List[Station]:
        """
        Busca emisoras por nombre.
        
        Args:
            name: Texto a buscar en el nombre.
            exact: Si debe ser coincidencia exacta.
            limit: Número máximo de resultados.
            
        Returns:
            Lista de emisoras.
        """
        return self.search_stations(name=name, name_exact=exact, limit=limit)
    
    def get_stations_by_country(
        self,
        countrycode: str,
        limit: int = 500
    ) -> List[Station]:
        """
        Obtiene emisoras de un país específico.
        
        Args:
            countrycode: Código ISO del país (ej: "ES", "MX").
            limit: Número máximo de resultados.
            
        Returns:
            Lista de emisoras.
        """
        try:
            data = self._get(
                f"stations/bycountrycodeexact/{countrycode}",
                {"limit": limit}
            )
            return [Station.from_api_response(item) for item in data]
        except Exception as e:
            log.error(f"Error obteniendo emisoras de {countrycode}: {e}")
            return []
    
    def get_stations_by_language(
        self,
        language: str,
        limit: int = 500
    ) -> List[Station]:
        """
        Obtiene emisoras por idioma.
        
        Args:
            language: Nombre del idioma.
            limit: Número máximo de resultados.
            
        Returns:
            Lista de emisoras.
        """
        try:
            data = self._get(
                f"stations/bylanguageexact/{language}",
                {"limit": limit}
            )
            return [Station.from_api_response(item) for item in data]
        except Exception as e:
            log.error(f"Error obteniendo emisoras en {language}: {e}")
            return []
    
    def get_stations_by_tag(
        self,
        tag: str,
        limit: int = 500
    ) -> List[Station]:
        """
        Obtiene emisoras por etiqueta/género.
        
        Args:
            tag: Nombre de la etiqueta.
            limit: Número máximo de resultados.
            
        Returns:
            Lista de emisoras.
        """
        try:
            data = self._get(
                f"stations/bytagexact/{tag}",
                {"limit": limit}
            )
            return [Station.from_api_response(item) for item in data]
        except Exception as e:
            log.error(f"Error obteniendo emisoras con tag {tag}: {e}")
            return []
    
    def get_top_stations(self, limit: int = 100) -> List[Station]:
        """
        Obtiene las emisoras más populares.
        
        Args:
            limit: Número de emisoras a obtener.
            
        Returns:
            Lista de emisoras ordenadas por votos.
        """
        try:
            data = self._get(
                "stations/topvote",
                {"limit": limit}
            )
            return [Station.from_api_response(item) for item in data]
        except Exception as e:
            log.error(f"Error obteniendo top emisoras: {e}")
            return []
    
    def get_recent_stations(self, limit: int = 100) -> List[Station]:
        """
        Obtiene las emisoras añadidas recientemente.
        
        Args:
            limit: Número de emisoras a obtener.
            
        Returns:
            Lista de emisoras recientes.
        """
        try:
            data = self._get(
                "stations/lastchange",
                {"limit": limit}
            )
            return [Station.from_api_response(item) for item in data]
        except Exception as e:
            log.error(f"Error obteniendo emisoras recientes: {e}")
            return []
    
    # === Métodos de Países ===
    
    def get_countries(self) -> List[Country]:
        """
        Obtiene la lista de países con emisoras.
        
        Returns:
            Lista de países con conteo de emisoras.
        """
        try:
            data = self._get("countries")
            return [
                Country(
                    name=item.get("name", ""),
                    code=item.get("iso_3166_1", ""),
                    station_count=item.get("stationcount", 0)
                )
                for item in data
                if item.get("name")  # Filtrar países sin nombre
            ]
        except Exception as e:
            log.error(f"Error obteniendo países: {e}")
            return []
    
    def get_countries_with_localization(
        self,
        localization_dict: Dict[str, str]
    ) -> List[Country]:
        """
        Obtiene países con nombres localizados.
        
        Args:
            localization_dict: Diccionario {nombre_local: código_país}
            
        Returns:
            Lista de países con nombres localizados.
        """
        countries = self.get_countries()
        
        # Crear diccionario inverso para búsqueda
        code_to_local = {v: k for k, v in localization_dict.items()}
        
        for country in countries:
            if country.code.upper() in code_to_local:
                country.name_localized = code_to_local[country.code.upper()]
        
        return countries
    
    # === Métodos de Idiomas ===
    
    def get_languages(self) -> List[Language]:
        """
        Obtiene la lista de idiomas disponibles.
        
        Returns:
            Lista de idiomas con conteo de emisoras.
        """
        try:
            data = self._get("languages")
            return [
                Language(
                    name=item.get("name", ""),
                    station_count=item.get("stationcount", 0)
                )
                for item in data
                if item.get("name")  # Filtrar idiomas sin nombre
            ]
        except Exception as e:
            log.error(f"Error obteniendo idiomas: {e}")
            return []
    
    def search_languages(self, query: str) -> List[Language]:
        """
        Busca idiomas por nombre.
        
        Args:
            query: Texto a buscar.
            
        Returns:
            Lista de idiomas que coinciden.
        """
        languages = self.get_languages()
        query_lower = query.lower()
        return [
            lang for lang in languages
            if query_lower in lang.name.lower()
        ]
    
    # === Métodos de Tags/Géneros ===
    
    def get_tags(self, limit: int = 500) -> List[Tag]:
        """
        Obtiene la lista de etiquetas/géneros.
        
        Args:
            limit: Número máximo de tags a obtener.
            
        Returns:
            Lista de tags ordenados por popularidad.
        """
        try:
            data = self._get(
                "tags",
                {"order": "stationcount", "reverse": "true", "limit": limit}
            )
            return [
                Tag(
                    name=item.get("name", ""),
                    station_count=item.get("stationcount", 0)
                )
                for item in data
                if item.get("name")  # Filtrar tags sin nombre
            ]
        except Exception as e:
            log.error(f"Error obteniendo tags: {e}")
            return []
    
    def search_tags(self, query: str) -> List[Tag]:
        """
        Busca etiquetas por nombre.
        
        Args:
            query: Texto a buscar.
            
        Returns:
            Lista de tags que coinciden.
        """
        tags = self.get_tags()
        query_lower = query.lower()
        return [
            tag for tag in tags
            if query_lower in tag.name.lower()
        ]
    
    # === Métodos de Estadísticas ===
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas del servidor.
        
        Returns:
            Diccionario con estadísticas.
        """
        try:
            data = self._get("stats")
            return data
        except Exception as e:
            log.error(f"Error obteniendo estadísticas: {e}")
            return {}
    
    def vote_for_station(self, station_uuid: str) -> bool:
        """
        Vota por una emisora.
        
        Args:
            station_uuid: UUID de la emisora.
            
        Returns:
            True si el voto fue exitoso.
        """
        try:
            data = self._get(f"vote/{station_uuid}")
            return data.get("ok", False)
        except Exception as e:
            log.error(f"Error votando por emisora: {e}")
            return False
    
    def click_station(self, station_uuid: str) -> bool:
        """
        Registra un click/reproducción en una emisora.
        
        Args:
            station_uuid: UUID de la emisora.
            
        Returns:
            True si se registró correctamente.
        """
        try:
            data = self._get(f"url/{station_uuid}")
            return data.get("ok", False)
        except Exception as e:
            log.error(f"Error registrando click: {e}")
            return False
    
    def close(self) -> None:
        """Cierra la sesión HTTP."""
        if self._session:
            try:
                if HTTP_CLIENT == "httpx":
                    self._session.close()
                # requests.Session no necesita cierre explícito
            except Exception:
                pass
            self._session = None
    
    def __del__(self):
        """Destructor."""
        self.close()
