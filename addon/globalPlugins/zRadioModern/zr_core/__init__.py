# -*- coding: utf-8 -*-
# Copyright (C) 2025 Héctor J. Benítez Corredera <xebolax@gmail.com>
# This file is covered by the GNU General Public License.

"""
Módulo core de zRadioModern.

Contiene los componentes principales del complemento:
- Gestión de configuración
- Base de datos
- Reproductor de audio con VLC
- Grabación de streams a MP3
- Cliente de API
- Sistema de plugins
- Sistema de eventos
"""

from .config import ConfigManager, get_config
from .database import DatabaseManager
from .player import AudioPlayer, PlayerState, RecordingState, ScheduledRecording
from .api_client import RadioBrowserAPI
from .models import Station, Favorite, PlaybackHistory, Category
from .plugin_manager import PluginManager, PluginBase
from .events import EventBus, EventType
from .internet import InternetChecker

__all__ = [
    "ConfigManager",
    "get_config",
    "DatabaseManager",
    "AudioPlayer",
    "PlayerState",
    "RecordingState",
    "ScheduledRecording",
    "RadioBrowserAPI",
    "Station",
    "Favorite",
    "PlaybackHistory",
    "Category",
    "PluginManager",
    "PluginBase",
    "EventBus",
    "EventType",
    "InternetChecker",
]

