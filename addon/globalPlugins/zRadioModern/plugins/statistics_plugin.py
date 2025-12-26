# -*- coding: utf-8 -*-
# Copyright (C) 2025 Héctor J. Benítez Corredera <xebolax@gmail.com>
# This file is covered by the GNU General Public License.

"""
Plugin de estadísticas para zRadioModern.

Este plugin rastrea y muestra estadísticas de uso del reproductor.
"""

from __future__ import annotations
from typing import List, Dict, Any
from datetime import datetime

import addonHandler

# Importaciones absolutas (necesarias para carga dinámica de plugins)
from globalPlugins.zRadioModern.zr_core.plugin_manager import PluginBase
from globalPlugins.zRadioModern.zr_core.events import EventType
from globalPlugins.zRadioModern.zr_core.config import get_config

# Para traducción
addonHandler.initTranslation()


class StatisticsPlugin(PluginBase):
    """
    Plugin que rastrea estadísticas de uso.
    
    Funcionalidades:
    - Cuenta el tiempo total de escucha
    - Registra las emisoras más reproducidas
    - Muestra estadísticas al usuario
    """
    
    PLUGIN_ID = "statistics_plugin"
    PLUGIN_NAME = "Estadísticas de Uso"
    PLUGIN_VERSION = "1.0.0"
    PLUGIN_AUTHOR = "Héctor J. Benítez Corredera"
    PLUGIN_DESCRIPTION = "Rastrea y muestra estadísticas de uso del reproductor"
    
    def __init__(self, event_bus):
        super().__init__(event_bus)
        self._session_start = None
        self._current_station = None
        self._total_time_seconds = 0
        self._stations_played = 0
    
    def on_load(self) -> bool:
        """Carga el plugin."""
        from logHandler import log
        
        log.info(f"Cargando plugin: {self.PLUGIN_NAME}")
        
        # Suscribirse a eventos con weak=False para evitar que se pierdan los callbacks
        self._event_bus.subscribe(
            EventType.PLAYBACK_STARTED,
            self._on_playback_started,
            weak=False
        )
        
        self._event_bus.subscribe(
            EventType.PLAYBACK_STOPPED,
            self._on_playback_stopped,
            weak=False
        )
        
        # Cargar estadísticas previas
        self._load_statistics()
        
        return True
    
    def on_unload(self) -> bool:
        """Descarga el plugin."""
        from logHandler import log
        
        # Finalizar sesión actual si hay reproducción
        if self._session_start:
            self._end_session()
        
        # Guardar estadísticas
        self._save_statistics()
        
        log.info(f"Plugin descargado: {self.PLUGIN_NAME}")
        return True
    
    def _on_playback_started(self, station) -> None:
        """Maneja el inicio de reproducción."""
        from logHandler import log
        log.debug(f"StatisticsPlugin: Reproducción iniciada - {station.name if station else 'Unknown'}")
        
        # Finalizar sesión anterior si existe
        if self._session_start:
            self._end_session()
        
        # Iniciar nueva sesión
        self._session_start = datetime.now()
        self._current_station = station
        self._stations_played += 1
        
        # Guardar estadísticas después de cada reproducción
        self._save_statistics()
    
    def _on_playback_stopped(self, data=None) -> None:
        """Maneja la detención de reproducción."""
        self._end_session()
        # Guardar estadísticas al detener
        self._save_statistics()
    
    def _end_session(self) -> None:
        """Finaliza la sesión actual de escucha."""
        if self._session_start:
            duration = (datetime.now() - self._session_start).total_seconds()
            self._total_time_seconds += int(duration)
            self._session_start = None
            self._current_station = None
    
    def _load_statistics(self) -> None:
        """Carga estadísticas guardadas."""
        import json
        from pathlib import Path
        
        config = get_config()
        stats_file = config.data_dir / "statistics.json"
        
        if stats_file.exists():
            try:
                with open(stats_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._total_time_seconds = data.get("total_time_seconds", 0)
                    self._stations_played = data.get("stations_played", 0)
            except Exception:
                pass
    
    def _save_statistics(self) -> None:
        """Guarda las estadísticas."""
        import json
        
        config = get_config()
        stats_file = config.data_dir / "statistics.json"
        
        try:
            data = {
                "total_time_seconds": self._total_time_seconds,
                "stations_played": self._stations_played,
                "last_updated": datetime.now().isoformat()
            }
            with open(stats_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass
    
    def get_menu_items(self) -> List[Dict[str, Any]]:
        """Devuelve los elementos de menú."""
        return [
            {
                # Translators: Elemento de menú
                "label": _("Ver estadísticas de uso..."),
                "callback": self._show_statistics
            }
        ]
    
    def _show_statistics(self, event=None) -> None:
        """Muestra las estadísticas de uso."""
        import wx
        
        # Calcular tiempo formateado
        hours = self._total_time_seconds // 3600
        minutes = (self._total_time_seconds % 3600) // 60
        
        message = _(
            "Estadísticas de uso de zRadio:\n\n"
            "Tiempo total de escucha: {} horas, {} minutos\n"
            "Emisoras reproducidas: {}"
        ).format(hours, minutes, self._stations_played)
        
        wx.MessageBox(
            message,
            _("Estadísticas de Uso"),
            wx.OK | wx.ICON_INFORMATION
        )
