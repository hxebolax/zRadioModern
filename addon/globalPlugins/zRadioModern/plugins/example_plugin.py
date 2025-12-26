# -*- coding: utf-8 -*-
# Copyright (C) 2025 Héctor J. Benítez Corredera <xebolax@gmail.com>
# This file is covered by the GNU General Public License.

"""
Plugin de ejemplo para zRadioModern.

Este plugin sirve como referencia para desarrollar plugins personalizados.
Muestra cómo:
- Implementar la clase base PluginBase
- Suscribirse a eventos
- Añadir elementos al menú
- Crear configuración personalizada
"""

from __future__ import annotations
from typing import List, Dict, Any

import addonHandler

# Importaciones absolutas (necesarias para carga dinámica de plugins)
from globalPlugins.zRadioModern.zr_core.plugin_manager import PluginBase
from globalPlugins.zRadioModern.zr_core.events import EventType

# Para traducción
addonHandler.initTranslation()


class ExamplePlugin(PluginBase):
    """
    Plugin de ejemplo que muestra las capacidades del sistema.
    
    Este plugin demuestra:
    - Cómo definir metadatos del plugin
    - Cómo responder a eventos del sistema
    - Cómo añadir elementos al menú
    """
    
    # Metadatos del plugin
    PLUGIN_ID = "example_plugin"
    PLUGIN_NAME = "Plugin de Ejemplo"
    PLUGIN_VERSION = "1.0.0"
    PLUGIN_AUTHOR = "Héctor J. Benítez Corredera"
    PLUGIN_DESCRIPTION = "Plugin de demostración para desarrolladores"
    
    def on_load(self) -> bool:
        """
        Se llama cuando el plugin se carga.
        
        Aquí se debe:
        - Inicializar recursos
        - Suscribirse a eventos
        - Cargar configuración
        
        Returns:
            True si se cargó correctamente.
        """
        from logHandler import log
        
        log.info(f"Cargando plugin: {self.PLUGIN_NAME}")
        
        # Suscribirse a eventos
        self._unsubscribe_playback = self._event_bus.subscribe(
            EventType.PLAYBACK_STARTED,
            self._on_playback_started
        )
        
        self._unsubscribe_stopped = self._event_bus.subscribe(
            EventType.PLAYBACK_STOPPED,
            self._on_playback_stopped
        )
        
        return True
    
    def on_unload(self) -> bool:
        """
        Se llama cuando el plugin se descarga.
        
        Aquí se debe:
        - Liberar recursos
        - Cancelar suscripciones a eventos
        - Guardar configuración
        
        Returns:
            True si se descargó correctamente.
        """
        from logHandler import log
        
        log.info(f"Descargando plugin: {self.PLUGIN_NAME}")
        
        # Cancelar suscripciones
        if hasattr(self, "_unsubscribe_playback"):
            self._unsubscribe_playback()
        
        if hasattr(self, "_unsubscribe_stopped"):
            self._unsubscribe_stopped()
        
        return True
    
    def _on_playback_started(self, station) -> None:
        """
        Manejador del evento de inicio de reproducción.
        
        Args:
            station: Estación que comenzó a reproducirse.
        """
        from logHandler import log
        log.debug(f"[ExamplePlugin] Reproduciendo: {station.name}")
    
    def _on_playback_stopped(self, data=None) -> None:
        """
        Manejador del evento de detención.
        """
        from logHandler import log
        log.debug("[ExamplePlugin] Reproducción detenida")
    
    def get_menu_items(self) -> List[Dict[str, Any]]:
        """
        Devuelve los elementos de menú del plugin.
        
        Returns:
            Lista de elementos de menú.
        """
        return [
            {
                # Translators: Elemento de menú del plugin de ejemplo
                "label": _("Acerca del plugin de ejemplo..."),
                "callback": self._show_about
            }
        ]
    
    def get_context_menu_items(self, context: str) -> List[Dict[str, Any]]:
        """
        Devuelve elementos de menú contextual.
        
        Args:
            context: Contexto actual ('station', 'favorite', etc.)
            
        Returns:
            Lista de elementos de menú.
        """
        if context == "station":
            return [
                {
                    # Translators: Elemento de menú contextual
                    "label": _("[Ejemplo] Información adicional"),
                    "callback": self._show_station_info
                }
            ]
        return []
    
    def _show_about(self, event=None) -> None:
        """Muestra información sobre el plugin."""
        import wx
        
        wx.MessageBox(
            _("Este es un plugin de demostración.\n\n"
              "Versión: {}\n"
              "Autor: {}").format(self.PLUGIN_VERSION, self.PLUGIN_AUTHOR),
            _("Acerca del Plugin de Ejemplo"),
            wx.OK | wx.ICON_INFORMATION
        )
    
    def _show_station_info(self, event=None) -> None:
        """Muestra información adicional de la emisora."""
        import wx
        
        wx.MessageBox(
            _("Esta función podría mostrar información adicional\n"
              "sobre la emisora seleccionada."),
            _("Información"),
            wx.OK | wx.ICON_INFORMATION
        )
