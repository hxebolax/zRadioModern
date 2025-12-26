# -*- coding: utf-8 -*-
# Copyright (C) 2025 Héctor J. Benítez Corredera <xebolax@gmail.com>
# This file is covered by the GNU General Public License.

"""
Sistema de plugins para zRadioModern.

Proporciona una arquitectura extensible que permite a los usuarios
añadir funcionalidades al complemento mediante plugins.
"""

from __future__ import annotations
from typing import Dict, List, Type, Optional, Any, Callable
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum, auto
import importlib.util
import sys
import threading

from logHandler import log

from .config import get_config
from .events import EventBus, EventType


class PluginState(Enum):
    """Estados posibles de un plugin."""
    UNLOADED = auto()
    LOADED = auto()
    ACTIVE = auto()
    ERROR = auto()
    DISABLED = auto()


@dataclass
class PluginMetadata:
    """
    Metadatos de un plugin.
    
    Attributes:
        id: Identificador único del plugin.
        name: Nombre legible del plugin.
        version: Versión del plugin.
        author: Autor del plugin.
        description: Descripción del plugin.
        min_app_version: Versión mínima de zRadioModern requerida.
        dependencies: Lista de IDs de plugins requeridos.
        homepage: URL de la página web del plugin.
    """
    id: str
    name: str
    version: str = "1.0.0"
    author: str = ""
    description: str = ""
    min_app_version: str = "2024.2.0"
    dependencies: List[str] = field(default_factory=list)
    homepage: str = ""


class PluginBase(ABC):
    """
    Clase base para todos los plugins de zRadioModern.
    
    Los plugins deben heredar de esta clase e implementar
    los métodos abstractos.
    
    Attributes:
        metadata: Metadatos del plugin.
        state: Estado actual del plugin.
        event_bus: Bus de eventos para comunicación.
    """
    
    # Metadatos del plugin (deben ser definidos por subclases)
    PLUGIN_ID: str = ""
    PLUGIN_NAME: str = ""
    PLUGIN_VERSION: str = "1.0.0"
    PLUGIN_AUTHOR: str = ""
    PLUGIN_DESCRIPTION: str = ""
    
    def __init__(self, event_bus: EventBus):
        """
        Inicializa el plugin.
        
        Args:
            event_bus: Bus de eventos del sistema.
        """
        self._event_bus = event_bus
        self._state = PluginState.UNLOADED
        self._config = get_config()
        
        # Construir metadatos desde atributos de clase
        self._metadata = PluginMetadata(
            id=self.PLUGIN_ID or self.__class__.__name__,
            name=self.PLUGIN_NAME or self.__class__.__name__,
            version=self.PLUGIN_VERSION,
            author=self.PLUGIN_AUTHOR,
            description=self.PLUGIN_DESCRIPTION
        )
    
    @property
    def metadata(self) -> PluginMetadata:
        """Obtiene los metadatos del plugin."""
        return self._metadata
    
    @property
    def state(self) -> PluginState:
        """Obtiene el estado actual del plugin."""
        return self._state
    
    @property
    def event_bus(self) -> EventBus:
        """Obtiene el bus de eventos."""
        return self._event_bus
    
    @abstractmethod
    def on_load(self) -> bool:
        """
        Llamado cuando el plugin se carga.
        
        Realiza la inicialización del plugin.
        
        Returns:
            True si se cargó correctamente.
        """
        pass
    
    @abstractmethod
    def on_unload(self) -> bool:
        """
        Llamado cuando el plugin se descarga.
        
        Realiza la limpieza de recursos.
        
        Returns:
            True si se descargó correctamente.
        """
        pass
    
    def on_enable(self) -> None:
        """Llamado cuando el plugin se habilita."""
        pass
    
    def on_disable(self) -> None:
        """Llamado cuando el plugin se deshabilita."""
        pass
    
    def get_settings_panel(self) -> Optional[Any]:
        """
        Obtiene el panel de configuración del plugin.
        
        Returns:
            Widget wx con la configuración, o None.
        """
        return None
    
    def get_menu_items(self) -> List[Dict[str, Any]]:
        """
        Obtiene elementos de menú a añadir.
        
        Returns:
            Lista de diccionarios con 'label' y 'callback'.
        """
        return []
    
    def get_context_menu_items(self, context: str) -> List[Dict[str, Any]]:
        """
        Obtiene elementos de menú contextual.
        
        Args:
            context: Contexto del menú ('station', 'favorite', etc.)
            
        Returns:
            Lista de diccionarios con 'label' y 'callback'.
        """
        return []


class PluginManager:
    """
    Gestor de plugins de zRadioModern.
    
    Se encarga de descubrir, cargar, descargar y gestionar
    el ciclo de vida de los plugins.
    """
    
    def __init__(self, event_bus: Optional[EventBus] = None):
        """
        Inicializa el gestor de plugins.
        
        Args:
            event_bus: Bus de eventos del sistema.
        """
        from .events import get_event_bus
        
        self._config = get_config()
        self._event_bus = event_bus or get_event_bus()
        self._plugins: Dict[str, PluginBase] = {}
        self._plugin_classes: Dict[str, Type[PluginBase]] = {}
        self._discovered_paths: List[Path] = []
        self._lock = threading.RLock()
        
        # Inicializar directorios de plugins
        self._init_plugin_dirs()
    
    def _init_plugin_dirs(self) -> None:
        """Inicializa los directorios de plugins."""
        # Plugins incluidos con el addon
        addon_plugins_dir = Path(__file__).parent.parent / "plugins"
        
        # Plugins del usuario
        user_plugins_dir = self._config.plugins_dir
        
        for plugins_dir in [addon_plugins_dir, user_plugins_dir]:
            if not plugins_dir.exists():
                try:
                    plugins_dir.mkdir(parents=True, exist_ok=True)
                except OSError:
                    pass
    
    def discover_plugins(self) -> List[str]:
        """
        Descubre todos los plugins disponibles.
        
        Busca en los directorios de plugins archivos Python
        que definan clases de plugin.
        
        Returns:
            Lista de IDs de plugins descubiertos.
        """
        discovered = []
        
        # Directorios a buscar
        search_dirs = [
            Path(__file__).parent.parent / "plugins",
            self._config.plugins_dir
        ]
        
        with self._lock:
            for plugins_dir in search_dirs:
                if not plugins_dir.exists():
                    continue
                
                for plugin_path in plugins_dir.glob("*.py"):
                    if plugin_path.name.startswith("_"):
                        continue
                    
                    try:
                        plugin_class = self._load_plugin_class(plugin_path)
                        if plugin_class:
                            plugin_id = (
                                plugin_class.PLUGIN_ID or 
                                plugin_path.stem
                            )
                            self._plugin_classes[plugin_id] = plugin_class
                            self._discovered_paths.append(plugin_path)
                            discovered.append(plugin_id)
                            log.debug(f"Plugin descubierto: {plugin_id}")
                            
                    except Exception as e:
                        log.error(f"Error descubriendo plugin {plugin_path}: {e}")
        
        return discovered
    
    def _load_plugin_class(self, path: Path) -> Optional[Type[PluginBase]]:
        """
        Carga la clase de plugin desde un archivo Python.
        
        Args:
            path: Ruta al archivo Python del plugin.
            
        Returns:
            Clase del plugin o None.
        """
        try:
            spec = importlib.util.spec_from_file_location(
                f"zradio_plugin_{path.stem}",
                str(path)
            )
            
            if spec is None or spec.loader is None:
                return None
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            
            # Buscar la clase de plugin
            for name in dir(module):
                obj = getattr(module, name)
                if (
                    isinstance(obj, type) and
                    issubclass(obj, PluginBase) and
                    obj is not PluginBase
                ):
                    return obj
            
            return None
            
        except Exception as e:
            log.error(f"Error cargando clase de plugin {path}: {e}")
            return None
    
    def load_plugin(self, plugin_id: str) -> bool:
        """
        Carga un plugin específico.
        
        Args:
            plugin_id: ID del plugin a cargar.
            
        Returns:
            True si se cargó correctamente.
        """
        with self._lock:
            if plugin_id in self._plugins:
                log.warning(f"Plugin {plugin_id} ya está cargado")
                return True
            
            if plugin_id not in self._plugin_classes:
                log.error(f"Plugin {plugin_id} no encontrado")
                return False
            
            try:
                plugin_class = self._plugin_classes[plugin_id]
                plugin = plugin_class(self._event_bus)
                
                if plugin.on_load():
                    plugin._state = PluginState.LOADED
                    self._plugins[plugin_id] = plugin
                    
                    # Emitir evento
                    self._event_bus.emit(
                        EventType.PLUGIN_LOADED,
                        plugin.metadata
                    )
                    
                    log.info(f"Plugin cargado: {plugin_id}")
                    return True
                else:
                    plugin._state = PluginState.ERROR
                    log.error(f"Plugin {plugin_id} falló al cargar")
                    return False
                    
            except Exception as e:
                log.error(f"Error cargando plugin {plugin_id}: {e}")
                self._event_bus.emit(
                    EventType.PLUGIN_ERROR,
                    {"plugin_id": plugin_id, "error": str(e)}
                )
                return False
    
    def unload_plugin(self, plugin_id: str) -> bool:
        """
        Descarga un plugin.
        
        Args:
            plugin_id: ID del plugin a descargar.
            
        Returns:
            True si se descargó correctamente.
        """
        with self._lock:
            if plugin_id not in self._plugins:
                log.warning(f"Plugin {plugin_id} no está cargado")
                return True
            
            try:
                plugin = self._plugins[plugin_id]
                
                if plugin.on_unload():
                    plugin._state = PluginState.UNLOADED
                    del self._plugins[plugin_id]
                    
                    # Emitir evento
                    self._event_bus.emit(
                        EventType.PLUGIN_UNLOADED,
                        plugin.metadata
                    )
                    
                    log.info(f"Plugin descargado: {plugin_id}")
                    return True
                else:
                    log.error(f"Plugin {plugin_id} falló al descargar")
                    return False
                    
            except Exception as e:
                log.error(f"Error descargando plugin {plugin_id}: {e}")
                return False
    
    def load_all_plugins(self) -> Dict[str, bool]:
        """
        Carga todos los plugins habilitados.
        
        Returns:
            Diccionario {plugin_id: éxito}.
        """
        results = {}
        enabled = self._config.enabled_plugins
        
        for plugin_id in self._plugin_classes:
            # Cargar solo si está habilitado o no hay lista
            if not enabled or plugin_id in enabled:
                results[plugin_id] = self.load_plugin(plugin_id)
        
        return results
    
    def unload_all_plugins(self) -> Dict[str, bool]:
        """
        Descarga todos los plugins cargados.
        
        Returns:
            Diccionario {plugin_id: éxito}.
        """
        results = {}
        
        for plugin_id in list(self._plugins.keys()):
            results[plugin_id] = self.unload_plugin(plugin_id)
        
        return results
    
    def reload_plugin(self, plugin_id: str) -> bool:
        """
        Recarga un plugin.
        
        Args:
            plugin_id: ID del plugin a recargar.
            
        Returns:
            True si se recargó correctamente.
        """
        if plugin_id in self._plugins:
            if not self.unload_plugin(plugin_id):
                return False
        return self.load_plugin(plugin_id)
    
    def get_plugin(self, plugin_id: str) -> Optional[PluginBase]:
        """
        Obtiene una instancia de plugin.
        
        Args:
            plugin_id: ID del plugin.
            
        Returns:
            Instancia del plugin o None.
        """
        return self._plugins.get(plugin_id)
    
    def get_loaded_plugins(self) -> List[PluginBase]:
        """
        Obtiene todos los plugins cargados.
        
        Returns:
            Lista de plugins cargados.
        """
        return list(self._plugins.values())
    
    def get_all_plugin_ids(self) -> List[str]:
        """
        Obtiene los IDs de todos los plugins descubiertos.
        
        Returns:
            Lista de IDs.
        """
        return list(self._plugin_classes.keys())
    
    def get_plugin_metadata(self, plugin_id: str) -> Optional[PluginMetadata]:
        """
        Obtiene los metadatos de un plugin.
        
        Args:
            plugin_id: ID del plugin.
            
        Returns:
            Metadatos o None.
        """
        if plugin_id in self._plugins:
            return self._plugins[plugin_id].metadata
        
        if plugin_id in self._plugin_classes:
            # Crear instancia temporal para obtener metadatos
            try:
                temp = self._plugin_classes[plugin_id](self._event_bus)
                return temp.metadata
            except Exception:
                pass
        
        return None
    
    def enable_plugin(self, plugin_id: str) -> bool:
        """
        Habilita un plugin (lo añade a la lista de habilitados).
        
        Args:
            plugin_id: ID del plugin.
            
        Returns:
            True si se habilitó.
        """
        enabled = list(self._config.enabled_plugins)
        if plugin_id not in enabled:
            enabled.append(plugin_id)
            self._config.enabled_plugins = enabled
            self._config.save()
        
        # Cargar si no está cargado
        if plugin_id not in self._plugins:
            return self.load_plugin(plugin_id)
        
        return True
    
    def disable_plugin(self, plugin_id: str) -> bool:
        """
        Deshabilita un plugin.
        
        Args:
            plugin_id: ID del plugin.
            
        Returns:
            True si se deshabilitó.
        """
        enabled = list(self._config.enabled_plugins)
        if plugin_id in enabled:
            enabled.remove(plugin_id)
            self._config.enabled_plugins = enabled
            self._config.save()
        
        # Descargar si está cargado
        if plugin_id in self._plugins:
            return self.unload_plugin(plugin_id)
        
        return True
    
    def is_plugin_enabled(self, plugin_id: str) -> bool:
        """
        Verifica si un plugin está habilitado.
        
        Args:
            plugin_id: ID del plugin.
            
        Returns:
            True si está habilitado.
        """
        enabled = self._config.enabled_plugins
        return not enabled or plugin_id in enabled
    
    def is_plugin_loaded(self, plugin_id: str) -> bool:
        """
        Verifica si un plugin está cargado.
        
        Args:
            plugin_id: ID del plugin.
            
        Returns:
            True si está cargado.
        """
        return plugin_id in self._plugins
    
    def get_menu_items_from_plugins(self) -> List[Dict[str, Any]]:
        """
        Obtiene elementos de menú de todos los plugins.
        
        Returns:
            Lista de elementos de menú.
        """
        items = []
        for plugin in self._plugins.values():
            try:
                items.extend(plugin.get_menu_items())
            except Exception as e:
                log.error(f"Error obteniendo menú de {plugin.metadata.id}: {e}")
        return items
    
    def get_context_menu_items_from_plugins(
        self,
        context: str
    ) -> List[Dict[str, Any]]:
        """
        Obtiene elementos de menú contextual de todos los plugins.
        
        Args:
            context: Contexto del menú.
            
        Returns:
            Lista de elementos de menú.
        """
        items = []
        for plugin in self._plugins.values():
            try:
                items.extend(plugin.get_context_menu_items(context))
            except Exception as e:
                log.error(
                    f"Error obteniendo menú contextual de "
                    f"{plugin.metadata.id}: {e}"
                )
        return items
