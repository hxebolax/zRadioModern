# -*- coding: utf-8 -*-
# Copyright (C) 2025 Héctor J. Benítez Corredera <xebolax@gmail.com>
# This file is covered by the GNU General Public License.

"""
Gestión de configuración para zRadioModern.

Proporciona una clase ConfigManager para manejar la configuración
del complemento de forma persistente usando JSON.
"""

from __future__ import annotations
from typing import Any, Dict, Optional
from dataclasses import dataclass, field, asdict
from pathlib import Path
import json
import os
import threading
import ctypes

import globalVars
from logHandler import log


# Singleton para la configuración global
_config_instance: Optional["ConfigManager"] = None
_config_lock = threading.Lock()


def get_config() -> "ConfigManager":
    """
    Obtiene la instancia global de configuración.
    
    Returns:
        ConfigManager: Instancia singleton de configuración.
    """
    global _config_instance
    if _config_instance is None:
        with _config_lock:
            if _config_instance is None:
                _config_instance = ConfigManager()
    return _config_instance


@dataclass
class ConfigManager:
    """
    Gestor de configuración del complemento.
    
    Almacena y recupera la configuración en formato JSON.
    Proporciona valores por defecto y validación.
    """
    
    # Configuración del reproductor
    volume: int = 50
    muted: bool = False
    
    # Configuración de búsqueda por defecto
    default_country: str = ""
    default_language: str = ""
    default_tag: str = ""
    search_limit: int = 100
    
    # Configuración de la interfaz
    window_width: int = 800
    window_height: int = 600
    last_tab: int = 0
    
    # Configuración de comportamiento
    check_internet_on_start: bool = True
    cache_enabled: bool = True
    cache_duration_days: int = 3
    remember_last_station: bool = True
    last_station_uuid: str = ""
    last_station_name: str = ""
    last_station_url: str = ""
    
    # Configuración de actualizaciones
    check_updates: bool = True
    last_update_check: str = ""
    
    # Plugins habilitados
    enabled_plugins: list = field(default_factory=list)
    
    # Configuración de grabación
    recording_directory: str = ""  # Vacío = Carpeta Música del usuario
    
    # Ruta del archivo de configuración
    _config_path: Path = field(default=None, repr=False, compare=False)
    _data_dir: Path = field(default=None, repr=False, compare=False)
    
    def __post_init__(self):
        """Inicializa rutas y carga la configuración existente."""
        self._data_dir = Path(globalVars.appArgs.configPath) / "zRadioModern"
        self._config_path = self._data_dir / "config.json"
        
        # Asegurar que el directorio existe
        self._data_dir.mkdir(parents=True, exist_ok=True)
        
        # Cargar configuración existente
        self.load()
    
    @property
    def data_dir(self) -> Path:
        """Obtiene el directorio de datos del complemento."""
        return self._data_dir
    
    @property
    def plugins_dir(self) -> Path:
        """Obtiene el directorio de plugins personalizados."""
        plugins_path = self._data_dir / "plugins"
        plugins_path.mkdir(parents=True, exist_ok=True)
        return plugins_path
    
    @property
    def cache_dir(self) -> Path:
        """Obtiene el directorio de caché."""
        cache_path = self._data_dir / "cache"
        cache_path.mkdir(parents=True, exist_ok=True)
        return cache_path
    
    @property
    def database_path(self) -> Path:
        """Obtiene la ruta de la base de datos."""
        return self._data_dir / "zradio.db"
    
    @property
    def recordings_dir(self) -> Path:
        """
        Obtiene el directorio de grabaciones.
        
        Si no está configurado, devuelve la carpeta Música del usuario.
        """
        if self.recording_directory and os.path.isdir(self.recording_directory):
            return Path(self.recording_directory)
        
        # Carpeta Música del usuario en Windows
        import ctypes.wintypes
        CSIDL_MYMUSIC = 13
        buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_MYMUSIC, None, 0, buf)
        music_path = Path(buf.value)
        
        if music_path.exists():
            return music_path
        
        # Fallback al directorio de datos del complemento
        recordings_path = self._data_dir / "recordings"
        recordings_path.mkdir(parents=True, exist_ok=True)
        return recordings_path
    
    def load(self) -> bool:
        """
        Carga la configuración desde el archivo JSON.
        
        Returns:
            bool: True si se cargó correctamente, False en caso contrario.
        """
        if not self._config_path.exists():
            log.debug("No existe archivo de configuración, usando valores por defecto")
            return False
        
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Actualizar atributos desde el archivo
            for key, value in data.items():
                if hasattr(self, key) and not key.startswith("_"):
                    setattr(self, key, value)
            
            log.debug("Configuración cargada correctamente")
            return True
            
        except json.JSONDecodeError as e:
            log.error(f"Error decodificando configuración JSON: {e}")
            return False
        except Exception as e:
            log.error(f"Error cargando configuración: {e}")
            return False
    
    def save(self) -> bool:
        """
        Guarda la configuración en el archivo JSON.
        
        Returns:
            bool: True si se guardó correctamente, False en caso contrario.
        """
        try:
            # Crear diccionario excluyendo atributos privados
            data = {
                key: value
                for key, value in asdict(self).items()
                if not key.startswith("_")
            }
            
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            log.debug("Configuración guardada correctamente")
            return True
            
        except Exception as e:
            log.error(f"Error guardando configuración: {e}")
            return False
    
    def reset(self) -> None:
        """Restablece la configuración a los valores por defecto."""
        defaults = ConfigManager()
        for key, value in asdict(defaults).items():
            if not key.startswith("_"):
                setattr(self, key, value)
        self.save()
        log.info("Configuración restablecida a valores por defecto")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Obtiene un valor de configuración.
        
        Args:
            key: Nombre de la configuración.
            default: Valor por defecto si no existe.
            
        Returns:
            El valor de la configuración o el default.
        """
        return getattr(self, key, default)
    
    def set(self, key: str, value: Any) -> None:
        """
        Establece un valor de configuración.
        
        Args:
            key: Nombre de la configuración.
            value: Valor a establecer.
        """
        if hasattr(self, key):
            setattr(self, key, value)
            self.save()
    
    def update(self, **kwargs) -> None:
        """
        Actualiza múltiples valores de configuración.
        
        Args:
            **kwargs: Pares clave-valor a actualizar.
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.save()
    
    def validate_volume(self, volume: int) -> int:
        """Valida y ajusta el volumen al rango válido."""
        return max(0, min(100, volume))
