# -*- coding: utf-8 -*-
# Copyright (C) 2025 Héctor J. Benítez Corredera <xebolax@gmail.com>
# This file is covered by the GNU General Public License.

"""
Modelos de datos para zRadioModern.

Define las estructuras de datos principales usando dataclasses
para una mejor tipificación y manejo de datos.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum, auto


class StationCodec(Enum):
    """Codecs de audio soportados."""
    MP3 = "mp3"
    AAC = "aac"
    OGG = "ogg"
    FLAC = "flac"
    WMA = "wma"
    UNKNOWN = "unknown"


@dataclass
class Station:
    """
    Representa una estación de radio.
    
    Attributes:
        name: Nombre de la estación
        url: URL del stream de audio
        stationuuid: Identificador único de la estación
        country: País de origen
        countrycode: Código ISO del país
        state: Estado/provincia
        language: Idioma principal
        languagecodes: Códigos de idioma
        tags: Etiquetas/géneros
        codec: Codec de audio
        bitrate: Tasa de bits (kbps)
        hls: Si usa HLS (HTTP Live Streaming)
        votes: Número de votos
        clickcount: Número de clics/reproducciones
        clicktrend: Tendencia de clics
        ssl_error: Si hay error SSL
        geo_lat: Latitud geográfica
        geo_long: Longitud geográfica
        has_extended_info: Si tiene información extendida
        favicon: URL del ícono/logo
        homepage: Página web de la estación
        lastchangetime: Última modificación
        lastchecktime: Última verificación
        lastcheckoktime: Última verificación exitosa
        lastlocalchecktime: Última verificación local
        lastcheckok: Si la última verificación fue exitosa
    """
    name: str
    url: str
    stationuuid: str = ""
    country: str = ""
    countrycode: str = ""
    state: str = ""
    language: str = ""
    languagecodes: str = ""
    tags: str = ""
    codec: str = ""
    bitrate: int = 0
    hls: int = 0
    votes: int = 0
    clickcount: int = 0
    clicktrend: int = 0
    ssl_error: int = 0
    geo_lat: float = 0.0
    geo_long: float = 0.0
    has_extended_info: bool = False
    favicon: str = ""
    homepage: str = ""
    lastchangetime: str = ""
    lastchecktime: str = ""
    lastcheckoktime: str = ""
    lastlocalchecktime: str = ""
    lastcheckok: int = 1
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "Station":
        """Crea una instancia desde la respuesta de la API."""
        return cls(
            name=data.get("name", "").strip(),
            url=data.get("url", "").strip(),
            stationuuid=data.get("stationuuid", ""),
            country=data.get("country", ""),
            countrycode=data.get("countrycode", ""),
            state=data.get("state", ""),
            language=data.get("language", ""),
            languagecodes=data.get("languagecodes", ""),
            tags=data.get("tags", ""),
            codec=data.get("codec", ""),
            bitrate=int(data.get("bitrate", 0)),
            hls=int(data.get("hls", 0)),
            votes=int(data.get("votes", 0)),
            clickcount=int(data.get("clickcount", 0)),
            clicktrend=int(data.get("clicktrend", 0)),
            ssl_error=int(data.get("ssl_error", 0)),
            geo_lat=float(data.get("geo_lat", 0) or 0),
            geo_long=float(data.get("geo_long", 0) or 0),
            has_extended_info=bool(data.get("has_extended_info", False)),
            favicon=data.get("favicon", ""),
            homepage=data.get("homepage", ""),
            lastchangetime=data.get("lastchangetime", ""),
            lastchecktime=data.get("lastchecktime", ""),
            lastcheckoktime=data.get("lastcheckoktime", ""),
            lastlocalchecktime=data.get("lastlocalchecktime", ""),
            lastcheckok=int(data.get("lastcheckok", 1))
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario."""
        return asdict(self)
    
    def get_display_name(self) -> str:
        """Obtiene el nombre formateado para mostrar."""
        parts = [self.name]
        if self.country:
            parts.append(f"({self.country})")
        if self.bitrate > 0:
            parts.append(f"[{self.bitrate} kbps]")
        return " ".join(parts)


@dataclass
class Category:
    """
    Representa una categoría de favoritos.
    
    Attributes:
        id: Identificador único
        name: Nombre de la categoría
        description: Descripción opcional
        color: Color para identificación visual (hex)
        order: Orden de visualización
        created_at: Fecha de creación
    """
    id: Optional[int] = None
    name: str = ""
    description: str = ""
    color: str = "#0078D4"
    order: int = 0
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class Favorite:
    """
    Representa una emisora favorita.
    
    Attributes:
        id: Identificador único en la base de datos
        name: Nombre de la emisora
        url: URL del stream
        station_uuid: UUID de la estación en RadioBrowser
        category_id: ID de la categoría a la que pertenece
        order: Posición en la lista de favoritos
        play_count: Número de veces reproducida
        last_played: Última vez que se reprodujo
        notes: Notas del usuario
        created_at: Fecha de añadido a favoritos
    """
    id: Optional[int] = None
    name: str = ""
    url: str = ""
    station_uuid: Optional[str] = None
    category_id: Optional[int] = None
    order: int = 0
    play_count: int = 0
    last_played: Optional[datetime] = None
    notes: str = ""
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
    
    def to_station(self) -> Station:
        """Convierte a objeto Station para reproducción."""
        return Station(
            name=self.name,
            url=self.url,
            stationuuid=self.station_uuid or ""
        )
    
    @classmethod
    def from_station(cls, station: Station, category_id: Optional[int] = None) -> "Favorite":
        """Crea un favorito desde una estación."""
        return cls(
            name=station.name,
            url=station.url,
            station_uuid=station.stationuuid,
            category_id=category_id
        )


@dataclass
class PlaybackHistory:
    """
    Representa un registro del historial de reproducción.
    
    Attributes:
        id: Identificador único
        station_name: Nombre de la emisora
        station_url: URL del stream
        station_uuid: UUID de la estación
        played_at: Fecha y hora de reproducción
        duration_seconds: Duración de la escucha en segundos
    """
    id: Optional[int] = None
    station_name: str = ""
    station_url: str = ""
    station_uuid: str = ""
    played_at: Optional[datetime] = None
    duration_seconds: int = 0
    
    def __post_init__(self):
        if self.played_at is None:
            self.played_at = datetime.now()
    
    @classmethod
    def from_station(cls, station: Station) -> "PlaybackHistory":
        """Crea un registro de historial desde una estación."""
        return cls(
            station_name=station.name,
            station_url=station.url,
            station_uuid=station.stationuuid
        )


@dataclass
class Country:
    """
    Representa un país con emisoras.
    
    Attributes:
        name: Nombre del país (en inglés)
        name_localized: Nombre localizado
        code: Código ISO del país
        station_count: Número de emisoras
    """
    name: str
    code: str
    station_count: int = 0
    name_localized: str = ""
    
    def get_display_name(self) -> str:
        """Obtiene el nombre para mostrar con conteo."""
        display_name = self.name_localized or self.name
        return f"{display_name} ({self.station_count} emisoras)"


@dataclass
class Language:
    """
    Representa un idioma con emisoras.
    
    Attributes:
        name: Nombre del idioma
        station_count: Número de emisoras
    """
    name: str
    station_count: int = 0
    
    def get_display_name(self) -> str:
        """Obtiene el nombre para mostrar con conteo."""
        return f"{self.name} ({self.station_count} emisoras)"


@dataclass
class Tag:
    """
    Representa una etiqueta/género musical.
    
    Attributes:
        name: Nombre de la etiqueta
        station_count: Número de emisoras
    """
    name: str
    station_count: int = 0
    
    def get_display_name(self) -> str:
        """Obtiene el nombre para mostrar con conteo."""
        return f"{self.name} ({self.station_count} emisoras)"


@dataclass
class SearchFilters:
    """
    Filtros para búsqueda de emisoras.
    
    Attributes:
        name: Texto a buscar en el nombre
        country: Código de país
        language: Idioma
        tag: Etiqueta/género
        codec: Codec de audio
        min_bitrate: Bitrate mínimo
        order: Campo de ordenación
        reverse: Ordenar descendente
        limit: Límite de resultados
        offset: Desplazamiento para paginación
    """
    name: str = ""
    country: str = ""
    language: str = ""
    tag: str = ""
    codec: str = ""
    min_bitrate: int = 0
    order: str = "name"
    reverse: bool = False
    limit: int = 100
    offset: int = 0
    
    def to_api_params(self) -> Dict[str, Any]:
        """Convierte los filtros a parámetros de API."""
        params = {}
        if self.name:
            params["name"] = self.name
        if self.country:
            params["countrycode"] = self.country
        if self.language:
            params["language"] = self.language
        if self.tag:
            params["tag"] = self.tag
        if self.codec:
            params["codec"] = self.codec
        if self.min_bitrate > 0:
            params["bitrateMin"] = self.min_bitrate
        params["order"] = self.order
        params["reverse"] = str(self.reverse).lower()
        params["limit"] = self.limit
        params["offset"] = self.offset
        return params


@dataclass
class AppSettings:
    """
    Configuración general de la aplicación.
    
    Attributes:
        volume: Volumen actual (0-100)
        default_country: País por defecto para búsquedas
        default_language: Idioma por defecto
        check_updates: Verificar actualizaciones
        cache_duration_days: Días que dura el caché
        remember_last_station: Recordar última emisora
        last_station_uuid: UUID de la última emisora
        theme: Tema visual
    """
    volume: int = 50
    default_country: str = "ES"
    default_language: str = "spanish"
    check_updates: bool = True
    cache_duration_days: int = 3
    remember_last_station: bool = True
    last_station_uuid: str = ""
    theme: str = "system"
