# -*- coding: utf-8 -*-
# Copyright (C) 2025 Héctor J. Benítez Corredera <xebolax@gmail.com>
# This file is covered by the GNU General Public License.

"""
zRadioModern - Reproductor de Radios Online moderno para NVDA.

Este complemento proporciona:
- Búsqueda avanzada de emisoras por nombre, país, idioma y etiquetas
- Sistema de favoritos con categorías y ordenación
- Historial de reproducción
- Sistema de plugins extensible
- Reproducción de audio mediante VLC
- Grabación de emisoras a archivos MP3
- Programación de grabaciones con temporizador
- Interfaz accesible para lectores de pantalla
"""

from __future__ import annotations

# ============================================================================
# IMPORTANTE: Configurar sys.path ANTES de cualquier import externo
# Esto asegura que el complemento use las bibliotecas empaquetadas en 'lib'
# ============================================================================
import sys
import os

# Obtener la ruta del directorio actual del complemento
_addon_path = os.path.dirname(os.path.abspath(__file__))
_lib_path = os.path.join(_addon_path, "lib")

# Insertar la carpeta lib al inicio del path para priorizar nuestras bibliotecas
if _lib_path not in sys.path:
    sys.path.insert(0, _lib_path)

# Configurar las variables de entorno para VLC
os.environ['PYTHON_VLC_MODULE_PATH'] = _lib_path
os.environ['PYTHON_VLC_LIB_PATH'] = os.path.join(_lib_path, "libvlc.dll")
os.environ["PATH"] = _lib_path + os.pathsep + os.environ.get("PATH", "")

from typing import TYPE_CHECKING, Optional, Any

import globalPluginHandler
import addonHandler
import gui
import globalVars
import ui
import wx
import wx.adv
from scriptHandler import script
from tones import beep
from threading import Thread
from logHandler import log

# Importaciones internas del complemento
from .zr_core.config import ConfigManager, get_config
from .zr_core.database import DatabaseManager
from .zr_core.player import AudioPlayer, PlayerState
from .zr_core.api_client import RadioBrowserAPI
from .zr_core.models import Station, Favorite, PlaybackHistory
from .zr_core.plugin_manager import PluginManager
from .zr_core.events import EventBus, EventType
from .zr_core.internet import InternetChecker
from .zr_ui.main_window import MainWindow
from .zr_ui.dialogs import show_error, show_info

# Para traducción
addonHandler.initTranslation()


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    """
    Plugin global de zRadioModern.
    
    Proporciona los comandos globales y gestiona el ciclo de vida
    del complemento dentro de NVDA.
    """
    
    def __init__(self) -> None:
        super().__init__()
        
        # Inicializar componentes del núcleo
        self._main_window: Optional[MainWindow] = None
        self._config = get_config()
        self._db = DatabaseManager()
        self._player = AudioPlayer()
        self._api = RadioBrowserAPI()
        self._event_bus = EventBus()
        self._internet_checker = InternetChecker()
        
        # IMPORTANTE: Pasar el event_bus al PluginManager para que los plugins
        # reciban los eventos correctamente
        self._plugin_manager = PluginManager(event_bus=self._event_bus)
        
        # Cargar plugins
        self._plugin_manager.discover_plugins()
        self._plugin_manager.load_all_plugins()
        
        # Registrar eventos
        self._setup_events()
        
        # Crear menú en la bandeja del sistema
        self._setup_menu()
        
        log.info("zRadioModern inicializado correctamente")

    def _setup_events(self) -> None:
        """Configura los manejadores de eventos internos."""
        self._event_bus.subscribe(EventType.PLAYBACK_STARTED, self._on_playback_started)
        self._event_bus.subscribe(EventType.PLAYBACK_STOPPED, self._on_playback_stopped)
        self._event_bus.subscribe(EventType.PLAYBACK_ERROR, self._on_playback_error)
        self._event_bus.subscribe(EventType.VOLUME_CHANGED, self._on_volume_changed)

    def _setup_menu(self) -> None:
        """Configura el menú en el menú Herramientas de NVDA."""
        self.tools_menu = gui.mainFrame.sysTrayIcon.toolsMenu
        # Translators: Nombre del elemento en el menú de herramientas
        self.menu_item = self.tools_menu.Append(
            wx.ID_ANY,
            _("&zRadio Moderno")
        )
        gui.mainFrame.sysTrayIcon.Bind(
            wx.EVT_MENU,
            self._on_menu_open,
            self.menu_item
        )

    def terminate(self) -> None:
        """Limpia los recursos al desactivar el complemento."""
        try:
            # Detener reproducción
            if self._player.state != PlayerState.STOPPED:
                self._player.stop()
            
            # Cerrar ventana si está abierta
            if self._main_window is not None:
                try:
                    self._main_window.Destroy()
                except RuntimeError:
                    pass
            
            # Descargar plugins
            self._plugin_manager.unload_all_plugins()
            
            # Guardar configuración
            self._config.save()
            
            # Cerrar base de datos
            self._db.close()
            
            # Eliminar menú
            try:
                self.tools_menu.Remove(self.menu_item)
            except Exception:
                pass
                
        except Exception as e:
            log.error(f"Error terminando zRadioModern: {e}")
        
        super().terminate()

    def _on_menu_open(self, event: wx.CommandEvent) -> None:
        """Maneja el evento de clic en el menú."""
        wx.CallAfter(self._show_main_window)

    def _show_main_window(self) -> None:
        """Muestra la ventana principal del complemento."""
        # Verificar conexión a Internet
        if not self._internet_checker.is_connected():
            show_error(
                # Translators: Mensaje de error cuando no hay conexión a Internet
                _("zRadio necesita conexión a Internet para funcionar.\n"
                  "Verifique su conexión e intente nuevamente."),
                # Translators: Título de la ventana de error
                _("Sin conexión")
            )
            return
        
        # Crear ventana si no existe
        if self._main_window is None:
            self._main_window = MainWindow(
                gui.mainFrame,
                config=self._config,
                db=self._db,
                player=self._player,
                api=self._api,
                plugin_manager=self._plugin_manager,
                event_bus=self._event_bus
            )
        
        # Mostrar ventana
        if not self._main_window.IsShown():
            gui.mainFrame.prePopup()
            self._main_window.Show()

    # === Eventos del reproductor ===
    
    def _on_playback_started(self, station: Station) -> None:
        """Manejador cuando inicia la reproducción."""
        # Registrar en historial
        self._db.add_to_history(station)

    def _on_playback_stopped(self) -> None:
        """Manejador cuando se detiene la reproducción."""
        pass

    def _on_playback_error(self, error: str) -> None:
        """Manejador cuando ocurre un error de reproducción."""
        ui.message(
            # Translators: Mensaje de error de reproducción
            _("Error de reproducción: {}").format(error)
        )

    def _on_volume_changed(self, volume: int) -> None:
        """Manejador cuando cambia el volumen."""
        pass

    # === Comandos globales (scripts) ===
    
    @script(
        gesture=None,
        # Translators: Descripción del comando para abrir la ventana principal
        description=_("Muestra la ventana principal de zRadio Moderno"),
        category="zRadio Moderno"
    )
    def script_show_main_window(self, gesture) -> None:
        """Muestra la ventana principal de zRadio."""
        wx.CallAfter(self._show_main_window)

    @script(
        gesture=None,
        # Translators: Descripción del comando para bajar volumen
        description=_("Bajar volumen de la radio"),
        category="zRadio Moderno"
    )
    def script_volume_down(self, gesture) -> None:
        """Reduce el volumen de la radio."""
        current_vol = self._player.volume
        if current_vol <= 0:
            # Translators: Mensaje cuando el volumen está al mínimo
            ui.message(_("Volumen al mínimo"))
        else:
            new_vol = max(0, current_vol - 5)
            self._player.volume = new_vol
            self._config.volume = new_vol
            ui.message(f"{new_vol}%")

    @script(
        gesture=None,
        # Translators: Descripción del comando para subir volumen
        description=_("Subir volumen de la radio"),
        category="zRadio Moderno"
    )
    def script_volume_up(self, gesture) -> None:
        """Aumenta el volumen de la radio."""
        current_vol = self._player.volume
        if current_vol >= 100:
            # Translators: Mensaje cuando el volumen está al máximo
            ui.message(_("Volumen al máximo"))
        else:
            new_vol = min(100, current_vol + 5)
            self._player.volume = new_vol
            self._config.volume = new_vol
            ui.message(f"{new_vol}%")

    @script(
        gesture=None,
        # Translators: Descripción del comando para detener
        description=_("Detener reproducción de la radio"),
        category="zRadio Moderno"
    )
    def script_stop(self, gesture) -> None:
        """Detiene la reproducción actual."""
        if self._player.state == PlayerState.STOPPED:
            # Translators: Mensaje cuando no hay reproducción activa
            ui.message(_("No hay nada reproduciéndose"))
        else:
            self._player.stop()
            self._event_bus.emit(EventType.PLAYBACK_STOPPED)
            # Translators: Mensaje cuando se detiene la reproducción
            ui.message(_("Reproducción detenida"))

    @script(
        gesture=None,
        # Translators: Descripción del comando para recargar
        description=_("Recargar la emisora actual"),
        category="zRadio Moderno"
    )
    def script_reload(self, gesture) -> None:
        """Recarga la emisora que se está reproduciendo."""
        if self._player.current_station is None:
            # Translators: Mensaje cuando no hay emisora cargada
            ui.message(_("No hay ninguna emisora para recargar"))
        else:
            self._player.reload()
            # Translators: Mensaje cuando se recarga la emisora
            ui.message(_("Recargando emisora..."))

    @script(
        gesture=None,
        # Translators: Descripción del comando para silenciar/restaurar
        description=_("Silenciar o restaurar el audio"),
        category="zRadio Moderno"
    )
    def script_toggle_mute(self, gesture) -> None:
        """Alterna el estado de silencio."""
        if self._player.state == PlayerState.STOPPED:
            # Translators: Mensaje cuando no hay reproducción para silenciar
            ui.message(_("No hay nada para silenciar"))
        else:
            self._player.toggle_mute()
            if self._player.muted:
                # Translators: Mensaje cuando se silencia
                ui.message(_("Silenciado"))
            else:
                # Translators: Mensaje cuando se quita el silencio
                ui.message(_("Silencio desactivado"))

    @script(
        gesture=None,
        # Translators: Descripción del comando para saber la emisora actual
        description=_("Anunciar la emisora en reproducción"),
        category="zRadio Moderno"
    )
    def script_current_station(self, gesture) -> None:
        """Anuncia el nombre de la emisora actual."""
        station = self._player.current_station
        if station is None:
            # Translators: Mensaje cuando no hay emisora reproduciéndose
            ui.message(_("No hay ninguna emisora reproduciéndose"))
        else:
            # Translators: Mensaje con el nombre de la emisora actual
            ui.message(_("Emisora: {}").format(station.name))

    @script(
        gesture=None,
        # Translators: Descripción del comando para información del estado
        description=_("Anunciar información del estado del reproductor"),
        category="zRadio Moderno"
    )
    def script_player_status(self, gesture) -> None:
        """Anuncia información completa del estado del reproductor."""
        status_message = self._player.get_status_message()
        ui.message(status_message)

    @script(
        gesture=None,
        # Translators: Descripción del comando para saber si está grabando
        description=_("Anunciar estado de grabación"),
        category="zRadio Moderno"
    )
    def script_recording_status(self, gesture) -> None:
        """Anuncia el estado de la grabación."""
        if self._player.is_recording:
            duration = self._player.recording_duration
            duration_str = ""
            if duration:
                minutes = int(duration.total_seconds() // 60)
                seconds = int(duration.total_seconds() % 60)
                duration_str = f" - {minutes}:{seconds:02d}"
            # Translators: Mensaje cuando está grabando
            ui.message(_("Grabando{}").format(duration_str))
        else:
            scheduled = self._player.scheduled_recordings
            if scheduled:
                # Translators: Mensaje con grabaciones programadas
                ui.message(_("No grabando. {} grabaciones programadas").format(len(scheduled)))
            else:
                # Translators: Mensaje cuando no está grabando
                ui.message(_("No hay grabación activa"))

    @script(
        gesture=None,
        # Translators: Descripción de comando para iniciar grabación inmediata
        description=_("Iniciar grabación de la emisora actual"),
        category="zRadio Moderno"
    )
    def script_start_recording(self, gesture) -> None:
        """Inicia la grabación de la emisora actual."""
        if not self._player.is_playing:
            # Translators: Error cuando se intenta grabar sin reproducir
            ui.message(_("No hay ninguna emisora reproduciéndose"))
            return
        
        if self._player.is_recording:
            # Translators: Error cuando ya se está grabando
            ui.message(_("Ya hay una grabación en curso"))
            return
            
        import re
        from datetime import datetime
        station = self._player.current_station
        station_name = station.name if station else "radio"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', station_name)
        filename = f"{safe_name}_{timestamp}.mp3"
        
        output_path = str(self._config.recordings_dir / filename)
        
        if self._player.start_recording(output_path):
            # Translators: Confirmación de inicio de grabación
            ui.message(_("Grabación iniciada"))
        else:
            # Translators: Error al iniciar grabación
            ui.message(_("Error al iniciar grabación"))

    @script(
        gesture=None,
        # Translators: Descripción de comando para detener grabación
        description=_("Detener grabación actual"),
        category="zRadio Moderno"
    )
    def script_stop_recording(self, gesture) -> None:
        """Detiene la grabación actual."""
        if not self._player.is_recording:
            # Translators: Error cuando no hay nada que detener
            ui.message(_("No hay ninguna grabación activa"))
            return
            
        result = self._player.stop_recording()
        if result:
            # Translators: Mensaje de éxito al detener y guardar
            ui.message(_("Grabación guardada"))
        else:
            # Translators: Mensaje cuando se detiene sin archivo
            ui.message(_("Grabación detenida"))

    @script(
        gesture=None,
        # Translators: Descripción de comando para programar grabación
        description=_("Abrir diálogo para programar grabación"),
        category="zRadio Moderno"
    )
    def script_schedule_recording(self, gesture) -> None:
        """Abre el diálogo de programación."""
        wx.CallAfter(self._on_schedule_recording_script)

    def _on_schedule_recording_script(self) -> None:
        """Manejador para programar grabación desde script."""
        from .zr_ui.dialogs import ScheduleRecordingDialog
        
        station_name = ""
        station_url = ""
        if self._player.current_station:
            station_name = self._player.current_station.name
            station_url = self._player.current_url
            
        dlg = ScheduleRecordingDialog(
            None,
            station_name=station_name,
            station_url=station_url,
            config=self._config
        )
        
        if dlg.ShowModal() == wx.ID_OK:
            result = dlg.get_result()
            if result:
                success = self._player.schedule_recording(
                    station_url=result["station_url"],
                    station_name=result["station_name"],
                    start_time=result["start_time"],
                    end_time=result["end_time"],
                    output_path=result["output_path"]
                )
                if success:
                    # Translators: Confirmación de programación
                    ui.message(_("Grabación programada"))
                else:
                    ui.message(_("Error al programar grabación"))
        dlg.Destroy()

    # === Atajos rápidos para favoritos (1-5) ===
    
    def _play_favorite(self, position: int) -> None:
        """Reproduce un favorito por su posición."""
        favorites = self._db.get_favorites(limit=5)
        if position > len(favorites):
            # Translators: Mensaje cuando no hay favorito en la posición
            ui.message(
                _("No hay emisora favorita en la posición {}").format(position)
            )
            return
        
        favorite = favorites[position - 1]
        station = Station(
            name=favorite.name,
            url=favorite.url,
            stationuuid=favorite.station_uuid or ""
        )
        
        # Verificar URL
        if not self._internet_checker.check_url(station.url):
            # Translators: Mensaje de error al cargar emisora
            ui.message(_("No se pudo conectar con la emisora"))
            return
        
        # Reproducir
        self._player.play(station.url)
        self._player.current_station = station
        self._event_bus.emit(EventType.PLAYBACK_STARTED, station)
        ui.message(station.name)

    @script(
        gesture=None,
        # Translators: Descripción del comando para favorito rápido 1
        description=_("Reproducir favorito 1"),
        category="zRadio Moderno"
    )
    def script_play_favorite_1(self, gesture) -> None:
        """Reproduce el favorito en posición 1."""
        self._play_favorite(1)

    @script(
        gesture=None,
        # Translators: Descripción del comando para favorito rápido 2
        description=_("Reproducir favorito 2"),
        category="zRadio Moderno"
    )
    def script_play_favorite_2(self, gesture) -> None:
        """Reproduce el favorito en posición 2."""
        self._play_favorite(2)

    @script(
        gesture=None,
        # Translators: Descripción del comando para favorito rápido 3
        description=_("Reproducir favorito 3"),
        category="zRadio Moderno"
    )
    def script_play_favorite_3(self, gesture) -> None:
        """Reproduce el favorito en posición 3."""
        self._play_favorite(3)

    @script(
        gesture=None,
        # Translators: Descripción del comando para favorito rápido 4
        description=_("Reproducir favorito 4"),
        category="zRadio Moderno"
    )
    def script_play_favorite_4(self, gesture) -> None:
        """Reproduce el favorito en posición 4."""
        self._play_favorite(4)

    @script(
        gesture=None,
        # Translators: Descripción del comando para favorito rápido 5
        description=_("Reproducir favorito 5"),
        category="zRadio Moderno"
    )
    def script_play_favorite_5(self, gesture) -> None:
        """Reproduce el favorito en posición 5."""
        self._play_favorite(5)
    
    # Índice actual para navegación de favoritos
    _current_favorite_index = 0
    
    def _play_favorite_by_index(self, index: int) -> None:
        """Reproduce un favorito por su índice (base 0), con navegación circular."""
        favorites = self._db.get_favorites()
        
        if not favorites:
            # Translators: Mensaje cuando no hay favoritos
            ui.message(_("No hay favoritos guardados"))
            return
        
        # Navegación circular
        total = len(favorites)
        self._current_favorite_index = index % total
        
        favorite = favorites[self._current_favorite_index]
        station = Station(
            name=favorite.name,
            url=favorite.url,
            stationuuid=favorite.station_uuid or ""
        )
        
        # Verificar URL
        if not self._internet_checker.check_url(station.url):
            # Translators: Mensaje de error al cargar emisora
            ui.message(_("No se pudo conectar con la emisora"))
            return
        
        # Reproducir
        self._player.play(station.url)
        self._player.current_station = station
        self._event_bus.emit(EventType.PLAYBACK_STARTED, station)
        
        # Anunciar posición y nombre
        # Translators: Mensaje al reproducir favorito con posición
        ui.message(_("{} de {}. {}").format(
            self._current_favorite_index + 1,
            total,
            station.name
        ))
    
    @script(
        gesture=None,
        # Translators: Descripción del comando para siguiente favorito
        description=_("Reproducir siguiente favorito"),
        category="zRadio Moderno"
    )
    def script_next_favorite(self, gesture) -> None:
        """Reproduce el siguiente favorito en la lista."""
        favorites = self._db.get_favorites()
        if not favorites:
            ui.message(_("No hay favoritos guardados"))
            return
        
        # Incrementar índice (circular)
        self._current_favorite_index = (self._current_favorite_index + 1) % len(favorites)
        self._play_favorite_by_index(self._current_favorite_index)
    
    @script(
        gesture=None,
        # Translators: Descripción del comando para favorito anterior
        description=_("Reproducir favorito anterior"),
        category="zRadio Moderno"
    )
    def script_previous_favorite(self, gesture) -> None:
        """Reproduce el favorito anterior en la lista."""
        favorites = self._db.get_favorites()
        if not favorites:
            ui.message(_("No hay favoritos guardados"))
            return
        
        # Decrementar índice (circular)
        self._current_favorite_index = (self._current_favorite_index - 1) % len(favorites)
        self._play_favorite_by_index(self._current_favorite_index)


# Desactivar el plugin en modo seguro
if globalVars.appArgs.secure:
    GlobalPlugin = globalPluginHandler.GlobalPlugin
