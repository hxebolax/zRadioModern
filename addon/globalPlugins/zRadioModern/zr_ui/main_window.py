# -*- coding: utf-8 -*-
# Copyright (C) 2025 Héctor J. Benítez Corredera <xebolax@gmail.com>
# This file is covered by the GNU General Public License.

"""
Ventana principal de zRadioModern.

Contiene la interfaz gráfica principal del complemento con
pestañas para las diferentes funcionalidades.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional, List

import wx
import wx.adv
import addonHandler

from logHandler import log

if TYPE_CHECKING:
    from ..zr_core.config import ConfigManager
    from ..zr_core.database import DatabaseManager
    from ..zr_core.player import AudioPlayer
    from ..zr_core.api_client import RadioBrowserAPI
    from ..zr_core.plugin_manager import PluginManager
    from ..zr_core.events import EventBus

from ..zr_core.player import PlayerState
from ..zr_core.events import EventType
from ..zr_core.models import Station
from .panels import GeneralPanel, FavoritesPanel, SearchPanel, HistoryPanel
from .dialogs import show_error, show_info

# Para traducción
addonHandler.initTranslation()


def _calculate_position(width: int, height: int) -> tuple:
    """Calcula la posición para centrar la ventana."""
    screen_width = wx.SystemSettings.GetMetric(wx.SYS_SCREEN_X)
    screen_height = wx.SystemSettings.GetMetric(wx.SYS_SCREEN_Y)
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    return (x, y)


class MainWindow(wx.Dialog):
    """
    Ventana principal de zRadioModern.
    
    Proporciona la interfaz principal con pestañas para:
    - General: Lista de emisoras principal
    - Favoritos: Gestión de emisoras favoritas
    - Búsqueda: Búsqueda avanzada de emisoras
    - Historial: Historial de reproducción
    """
    
    def __init__(
        self,
        parent: wx.Window,
        config: "ConfigManager",
        db: "DatabaseManager",
        player: "AudioPlayer",
        api: "RadioBrowserAPI",
        plugin_manager: "PluginManager",
        event_bus: "EventBus"
    ):
        """
        Inicializa la ventana principal.
        
        Args:
            parent: Ventana padre.
            config: Gestor de configuración.
            db: Gestor de base de datos.
            player: Reproductor de audio.
            api: Cliente de API.
            plugin_manager: Gestor de plugins.
            event_bus: Bus de eventos.
        """
        self._config = config
        self._db = db
        self._player = player
        self._api = api
        self._plugin_manager = plugin_manager
        self._event_bus = event_bus
        
        # Dimensiones de la ventana
        width = config.window_width
        height = config.window_height
        pos = _calculate_position(width, height)
        
        super().__init__(
            parent,
            id=wx.ID_ANY,
            # Translators: Título de la ventana principal
            title=_("zRadio Moderno para NVDA"),
            pos=pos,
            size=(width, height),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        
        self._init_ui()
        self._setup_events()
        self._setup_player_callbacks()
        self._load_initial_data()
        
        # Restaurar estado del reproductor al abrir la ventana
        self._sync_player_state()
        
        log.debug("Ventana principal inicializada")
    
    def _init_ui(self) -> None:
        """Inicializa la interfaz de usuario."""
        main_panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # === Notebook con pestañas ===
        self.notebook = wx.Notebook(main_panel)
        
        # Pestaña General
        self.panel_general = GeneralPanel(
            self.notebook,
            api=self._api,
            player=self._player,
            db=self._db,
            event_bus=self._event_bus
        )
        # Translators: Nombre de pestaña
        self.notebook.AddPage(self.panel_general, _("General"))
        
        # Pestaña Favoritos
        self.panel_favorites = FavoritesPanel(
            self.notebook,
            api=self._api,
            db=self._db,
            player=self._player,
            event_bus=self._event_bus
        )
        # Translators: Nombre de pestaña
        self.notebook.AddPage(self.panel_favorites, _("Favoritos"))
        
        # Pestaña Búsqueda
        self.panel_search = SearchPanel(
            self.notebook,
            api=self._api,
            player=self._player,
            db=self._db,
            event_bus=self._event_bus
        )
        # Translators: Nombre de pestaña
        self.notebook.AddPage(self.panel_search, _("Buscador"))
        
        # Pestaña Historial
        self.panel_history = HistoryPanel(
            self.notebook,
            api=self._api,
            db=self._db,
            player=self._player,
            event_bus=self._event_bus
        )
        # Translators: Nombre de pestaña
        self.notebook.AddPage(self.panel_history, _("Historial"))
        
        main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 5)
        
        # === Controles de reproducción ===
        playback_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Translators: Botón detener
        self.btn_stop = wx.Button(main_panel, wx.ID_ANY, _("&Detener"))
        self.btn_stop.Disable()
        playback_sizer.Add(self.btn_stop, 1, wx.ALL, 5)
        
        # Translators: Botón recargar
        self.btn_reload = wx.Button(main_panel, wx.ID_ANY, _("&Recargar"))
        self.btn_reload.Disable()
        playback_sizer.Add(self.btn_reload, 1, wx.ALL, 5)
        
        # Translators: Botón silenciar
        self.btn_mute = wx.Button(main_panel, wx.ID_ANY, _("&Silenciar"))
        self.btn_mute.Disable()
        playback_sizer.Add(self.btn_mute, 1, wx.ALL, 5)
        
        # Control de volumen
        # Translators: Etiqueta del control de volumen
        playback_sizer.Add(
            wx.StaticText(main_panel, label=_("Volumen:")),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.LEFT,
            10
        )
        self.slider_volume = wx.Slider(
            main_panel,
            wx.ID_ANY,
            value=self._config.volume,
            minValue=0,
            maxValue=100,
            style=wx.SL_HORIZONTAL
        )
        self.slider_volume.SetName(_("Volumen"))
        playback_sizer.Add(self.slider_volume, 2, wx.ALL | wx.EXPAND, 5)
        
        main_sizer.Add(playback_sizer, 0, wx.EXPAND)
        
        # === Botones inferiores ===
        bottom_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Translators: Botón de herramientas
        self.btn_tools = wx.Button(main_panel, wx.ID_ANY, _("&Herramientas"))
        bottom_sizer.Add(self.btn_tools, 1, wx.ALL, 5)
        
        # Translators: Botón de ayuda
        self.btn_help = wx.Button(main_panel, wx.ID_HELP, _("A&yuda"))
        bottom_sizer.Add(self.btn_help, 1, wx.ALL, 5)
        
        # Translators: Botón cerrar
        self.btn_close = wx.Button(main_panel, wx.ID_CANCEL, _("&Cerrar"))
        bottom_sizer.Add(self.btn_close, 1, wx.ALL, 5)
        
        main_sizer.Add(bottom_sizer, 0, wx.EXPAND)
        
        main_panel.SetSizer(main_sizer)
        
        # === Menú de herramientas ===
        self._create_tools_menu()
        
        # Restaurar última pestaña
        if 0 <= self._config.last_tab < self.notebook.GetPageCount():
            self.notebook.SetSelection(self._config.last_tab)
    
    def _create_tools_menu(self) -> None:
        """Crea el menú de herramientas."""
        self.menu_tools = wx.Menu()
        
        # === Submenú de Grabación ===
        self.menu_recording = wx.Menu()
        
        # Translators: Elemento de menú
        self.item_start_recording = self.menu_recording.Append(
            wx.ID_ANY,
            _("&Grabar emisora actual")
        )
        self.Bind(wx.EVT_MENU, self._on_start_recording, self.item_start_recording)
        
        # Translators: Elemento de menú
        self.item_stop_recording = self.menu_recording.Append(
            wx.ID_ANY,
            _("&Detener grabación")
        )
        self.item_stop_recording.Enable(False)
        self.Bind(wx.EVT_MENU, self._on_stop_recording, self.item_stop_recording)
        
        self.menu_recording.AppendSeparator()
        
        # Translators: Elemento de menú
        item_schedule = self.menu_recording.Append(
            wx.ID_ANY,
            _("&Programar grabación...")
        )
        self.Bind(wx.EVT_MENU, self._on_schedule_recording, item_schedule)
        
        # Translators: Elemento de menú
        item_view_scheduled = self.menu_recording.Append(
            wx.ID_ANY,
            _("&Ver grabaciones programadas...")
        )
        self.Bind(wx.EVT_MENU, self._on_view_scheduled, item_view_scheduled)
        
        self.menu_recording.AppendSeparator()
        
        # Translators: Elemento de menú
        item_open_recordings = self.menu_recording.Append(
            wx.ID_ANY,
            _("&Abrir carpeta de grabaciones")
        )
        self.Bind(wx.EVT_MENU, self._on_open_recordings_folder, item_open_recordings)
        
        # Translators: Submenú de grabación
        self.menu_tools.AppendSubMenu(self.menu_recording, _("Gra&bación"))
        
        self.menu_tools.AppendSeparator()
        
        # Translators: Elemento de menú
        item_export = self.menu_tools.Append(
            wx.ID_ANY,
            _("&Exportar favoritos...")
        )
        self.Bind(wx.EVT_MENU, self._on_export, item_export)
        
        # Translators: Elemento de menú
        item_import = self.menu_tools.Append(
            wx.ID_ANY,
            _("&Importar favoritos...")
        )
        self.Bind(wx.EVT_MENU, self._on_import, item_import)
        
        self.menu_tools.AppendSeparator()
        
        # Translators: Elemento de menú
        item_clear_history = self.menu_tools.Append(
            wx.ID_ANY,
            _("&Limpiar historial...")
        )
        self.Bind(wx.EVT_MENU, self._on_clear_history, item_clear_history)
        
        self.menu_tools.AppendSeparator()
        
        # Translators: Elemento de menú
        item_settings = self.menu_tools.Append(
            wx.ID_PREFERENCES,
            _("&Configuración...")
        )
        self.Bind(wx.EVT_MENU, self._on_settings, item_settings)
        
        # Añadir elementos de menú de plugins en un submenú
        plugin_items = self._plugin_manager.get_menu_items_from_plugins()
        if plugin_items:
            self.menu_tools.AppendSeparator()
            
            # Crear submenú de plugins
            self.menu_plugins = wx.Menu()
            
            for item in plugin_items:
                menu_item = self.menu_plugins.Append(wx.ID_ANY, item["label"])
                self.Bind(wx.EVT_MENU, item["callback"], menu_item)
            
            # Translators: Submenú de plugins
            self.menu_tools.AppendSubMenu(self.menu_plugins, _("&Plugins"))
    
    def _setup_events(self) -> None:
        """Configura los manejadores de eventos."""
        # Eventos de la ventana
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)
        self.Bind(wx.EVT_SHOW, self._on_show)
        
        # Eventos de controles de reproducción
        self.btn_stop.Bind(wx.EVT_BUTTON, self._on_stop)
        self.btn_reload.Bind(wx.EVT_BUTTON, self._on_reload)
        self.btn_mute.Bind(wx.EVT_BUTTON, self._on_mute)
        self.slider_volume.Bind(wx.EVT_SLIDER, self._on_volume_change)
        
        # Eventos de botones inferiores
        self.btn_tools.Bind(wx.EVT_BUTTON, self._on_show_tools_menu)
        self.btn_help.Bind(wx.EVT_BUTTON, self._on_help)
        self.btn_close.Bind(wx.EVT_BUTTON, self._on_close)
        
        # Eventos del notebook
        self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self._on_tab_changed)
        
        # Suscribirse a eventos del sistema
        self._event_bus.subscribe(
            EventType.PLAYBACK_STARTED,
            self._handle_playback_started
        )
        self._event_bus.subscribe(
            EventType.PLAYBACK_STOPPED,
            self._handle_playback_stopped
        )
    
    def _load_initial_data(self) -> None:
        """Carga los datos iniciales."""
        # Los paneles cargan sus propios datos
        pass
    
    def _setup_player_callbacks(self) -> None:
        """Configura los callbacks del reproductor para actualizar la GUI."""
        # Cuando cambia el estado del reproductor
        self._player.set_on_state_change(self._on_player_state_change)
        
        # Cuando empieza a cargar (buffering)
        self._player.set_on_buffering(self._on_player_buffering)
        
        # Cuando empieza a reproducir
        self._player.set_on_playing(self._on_player_playing)
        
        # Cuando hay un error
        self._player.set_on_error(self._on_player_error)
        
        # Cuando inicia/detiene grabación
        self._player.set_on_recording_started(self._on_recording_state_change)
        self._player.set_on_recording_stopped(self._on_recording_state_change)
    
    def _on_player_state_change(self, state: PlayerState) -> None:
        """Callback cuando cambia el estado del reproductor."""
        wx.CallAfter(self._sync_player_state)
    
    def _on_player_buffering(self) -> None:
        """Callback cuando el reproductor está cargando."""
        wx.CallAfter(self._update_for_buffering)
    
    def _on_player_playing(self) -> None:
        """Callback cuando el reproductor empieza a reproducir."""
        wx.CallAfter(self._update_for_playing)
    
    def _on_player_error(self, error: str) -> None:
        """Callback cuando hay un error en el reproductor."""
        wx.CallAfter(self._update_for_error, error)
    
    def _on_recording_state_change(self, data=None) -> None:
        """Callback cuando cambia el estado de grabación."""
        wx.CallAfter(self._update_recording_controls)
    
    def _sync_player_state(self) -> None:
        """Sincroniza los controles con el estado actual del reproductor."""
        state = self._player.state
        is_playing = self._player.is_playing
        is_recording = self._player.is_recording
        
        # Actualizar controles de reproducción
        if state == PlayerState.BUFFERING:
            self._update_for_buffering()
        elif is_playing:
            self._update_for_playing()
        else:
            self._update_playback_controls(False)
        
        # Actualizar controles de grabación
        self._update_recording_controls()
        
        # Actualizar slider de volumen
        self.slider_volume.SetValue(self._player.volume)
    
    def _update_for_buffering(self) -> None:
        """Actualiza la GUI para el estado de buffering."""
        # Habilitar botones parcialmente
        self.btn_stop.Enable(True)
        self.btn_reload.Enable(False)  # No recargar mientras carga
        self.btn_mute.Enable(True)
        
        # Actualizar etiqueta de silencio
        if self._player.muted:
            self.btn_mute.SetLabel(_("Quitar &Silencio"))
        else:
            self.btn_mute.SetLabel(_("&Silenciar"))
        
        # Enfocar el botón detener ya que se ha iniciado la acción de reproducir
        self._set_focus_to_stop()
    
    def _update_for_playing(self) -> None:
        """Actualiza la GUI cuando el reproductor está reproduciendo."""
        self._update_playback_controls(True)
        # Enfocar el botón detener como solicita el usuario
        self._set_focus_to_stop()

    def _set_focus_to_stop(self) -> None:
        """Establece el foco en el botón detener si la ventana es visible."""
        if self.IsShown():
            if not self.btn_stop.IsEnabled():
                self.btn_stop.Enable(True)
            self.btn_stop.SetFocus()
    
    def _update_for_error(self, error: str) -> None:
        """Actualiza la GUI cuando hay un error."""
        self._update_playback_controls(False)
        # No mostrar diálogo aquí, solo actualizar controles
        log.error(f"Error de reproducción: {error}")
    
    def _update_recording_controls(self) -> None:
        """Actualiza los controles de grabación según el estado."""
        is_recording = self._player.is_recording
        
        # Actualizar elementos del menú de grabación
        if hasattr(self, 'item_start_recording'):
            self.item_start_recording.Enable(not is_recording and self._player.is_playing)
        if hasattr(self, 'item_stop_recording'):
            self.item_stop_recording.Enable(is_recording)
    
    # === Manejadores de eventos del reproductor ===
    
    def _handle_playback_started(self, station: Station) -> None:
        """Maneja el evento de inicio de reproducción."""
        wx.CallAfter(self._sync_player_state)
    
    def _handle_playback_stopped(self, data=None) -> None:
        """Maneja el evento de detención de reproducción."""
        wx.CallAfter(self._update_playback_controls, False)
        wx.CallAfter(self._update_recording_controls)
        wx.CallAfter(self._focus_current_list)
    
    def _update_playback_controls(self, playing: bool) -> None:
        """Actualiza los controles de reproducción."""
        self.btn_stop.Enable(playing)
        self.btn_reload.Enable(playing)
        self.btn_mute.Enable(playing)
        
        if playing and self._player.muted:
            # Translators: Texto del botón cuando está silenciado
            self.btn_mute.SetLabel(_("Quitar &Silencio"))
        else:
            # Translators: Texto del botón para silenciar
            self.btn_mute.SetLabel(_("&Silenciar"))
        
        # Actualizar también los controles de grabación
        self._update_recording_controls()
    
    # === Manejadores de controles de reproducción ===
    
    def _on_stop(self, event: wx.CommandEvent) -> None:
        """Maneja el botón de detener."""
        self._player.stop()
        self._event_bus.emit(EventType.PLAYBACK_STOPPED)
        self._update_playback_controls(False)
        self._focus_current_list()
    
    def _on_reload(self, event: wx.CommandEvent) -> None:
        """Maneja el botón de recargar."""
        self._player.reload()
        # El foco se moverá a Detener automáticamente por el evento de reproducción
        # No mostramos diálogo para no interrumpir el flujo y perder el foco
    
    def _on_mute(self, event: wx.CommandEvent) -> None:
        """Maneja el botón de silenciar."""
        self._player.toggle_mute()
        
        if self._player.muted:
            # Translators: Texto del botón cuando está silenciado
            self.btn_mute.SetLabel(_("Quitar &Silencio"))
        else:
            # Translators: Texto del botón para silenciar
            self.btn_mute.SetLabel(_("&Silenciar"))
    
    def _on_volume_change(self, event: wx.CommandEvent) -> None:
        """Maneja el cambio de volumen."""
        volume = self.slider_volume.GetValue()
        self._player.volume = volume
        self._config.volume = volume
        self._event_bus.emit(EventType.VOLUME_CHANGED, volume)
    
    # === Manejadores de herramientas ===
    
    def _on_show_tools_menu(self, event: wx.CommandEvent) -> None:
        """Muestra el menú de herramientas."""
        pos = self.btn_tools.GetPosition()
        self.PopupMenu(self.menu_tools, pos)
    
    def _on_export(self, event: wx.CommandEvent) -> None:
        """Exporta los favoritos."""
        with wx.FileDialog(
            self,
            # Translators: Título del diálogo de guardar
            _("Exportar favoritos"),
            wildcard="JSON files (*.json)|*.json",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        ) as dialog:
            if dialog.ShowModal() == wx.ID_CANCEL:
                return
            
            filepath = dialog.GetPath()
            
            try:
                json_data = self._db.export_favorites_json()
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(json_data)
                
                show_info(
                    # Translators: Mensaje de éxito al exportar
                    _("Favoritos exportados correctamente"),
                    _("Exportación completada")
                )
            except Exception as e:
                show_error(
                    # Translators: Mensaje de error al exportar
                    _("Error al exportar: {}").format(str(e)),
                    _("Error")
                )
    
    def _on_import(self, event: wx.CommandEvent) -> None:
        """Importa favoritos."""
        with wx.FileDialog(
            self,
            # Translators: Título del diálogo de abrir
            _("Importar favoritos"),
            wildcard="JSON files (*.json)|*.json",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        ) as dialog:
            if dialog.ShowModal() == wx.ID_CANCEL:
                return
            
            filepath = dialog.GetPath()
            
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    json_data = f.read()
                
                cats, favs = self._db.import_favorites_json(json_data)
                
                show_info(
                    # Translators: Mensaje de éxito al importar
                    _("Importados: {} categorías, {} favoritos").format(cats, favs),
                    _("Importación completada")
                )
                
                # Refrescar panel de favoritos
                self.panel_favorites.refresh()
                
            except Exception as e:
                show_error(
                    # Translators: Mensaje de error al importar
                    _("Error al importar: {}").format(str(e)),
                    _("Error")
                )
    
    def _on_clear_history(self, event: wx.CommandEvent) -> None:
        """Limpia el historial."""
        dlg = wx.MessageDialog(
            self,
            # Translators: Mensaje de confirmación
            _("¿Está seguro de que desea eliminar todo el historial?"),
            # Translators: Título del diálogo
            _("Confirmar"),
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION
        )
        
        if dlg.ShowModal() == wx.ID_YES:
            count = self._db.clear_history()
            show_info(
                # Translators: Mensaje informativo
                _("Se eliminaron {} registros del historial").format(count),
                _("Historial limpiado")
            )
            self.panel_history.refresh()
        
        dlg.Destroy()
    
    def _on_settings(self, event: wx.CommandEvent) -> None:
        """Muestra la configuración."""
        from .dialogs import SettingsDialog
        
        dlg = SettingsDialog(self, self._config)
        dlg.ShowModal()
        dlg.Destroy()
    
    def _on_help(self, event: wx.CommandEvent) -> None:
        """Muestra la ayuda."""
        # TODO: Implementar ayuda
        show_info(
            # Translators: Mensaje de ayuda
            _("zRadio Moderno para NVDA\n\n"
              "Use las pestañas para navegar entre secciones.\n"
              "Pulse Enter o Espacio para reproducir una emisora.\n"
              "Use el menú contextual para más opciones.\n\n"
              "Grabación:\n"
              "- Puede grabar la emisora actual desde el menú Herramientas > Grabación.\n"
              "- Las grabaciones se guardan en formato MP3.\n"
              "- Puede programar grabaciones para un horario específico."),
            _("Ayuda")
        )
    
    # === Funciones de grabación ===
    
    def _on_start_recording(self, event: wx.CommandEvent) -> None:
        """Inicia la grabación de la emisora actual."""
        from datetime import datetime
        import re
        
        if self._player.state != PlayerState.PLAYING:
            show_error(
                # Translators: Mensaje de error
                _("No hay ninguna emisora reproduciéndose para grabar."),
                _("Error")
            )
            return
        
        if self._player.is_recording:
            show_error(
                # Translators: Mensaje de error
                _("Ya hay una grabación en curso."),
                _("Error")
            )
            return
        
        # Generar nombre de archivo
        station = self._player.current_station
        station_name = station.name if station else "radio"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', station_name)
        filename = f"{safe_name}_{timestamp}.mp3"
        
        output_path = str(self._config.recordings_dir / filename)
        
        if self._player.start_recording(output_path):
            self.item_start_recording.Enable(False)
            self.item_stop_recording.Enable(True)
            show_info(
                # Translators: Mensaje de información
                _("Grabación iniciada.\n\nArchivo: {}").format(filename),
                _("Grabación")
            )
        else:
            show_error(
                # Translators: Mensaje de error
                _("No se pudo iniciar la grabación."),
                _("Error")
            )
    
    def _on_stop_recording(self, event: wx.CommandEvent) -> None:
        """Detiene la grabación actual."""
        if not self._player.is_recording:
            return
        
        result = self._player.stop_recording()
        self.item_start_recording.Enable(True)
        self.item_stop_recording.Enable(False)
        
        if result:
            # Calcular duración
            duration = self._player.recording_duration
            duration_str = ""
            if duration:
                minutes = int(duration.total_seconds() // 60)
                seconds = int(duration.total_seconds() % 60)
                duration_str = f"\nDuración: {minutes}:{seconds:02d}"
            
            show_info(
                # Translators: Mensaje de información
                _("Grabación guardada.\n\nArchivo: {}{}").format(result, duration_str),
                _("Grabación completada")
            )
        else:
            show_info(
                # Translators: Mensaje de información
                _("Grabación detenida."),
                _("Grabación")
            )
    
    def _on_schedule_recording(self, event: wx.CommandEvent) -> None:
        """Abre el diálogo para programar una grabación."""
        from .dialogs import ScheduleRecordingDialog
        
        # Prellenar con la emisora actual si está reproduciéndose
        station_name = ""
        station_url = ""
        if self._player.current_station:
            station_name = self._player.current_station.name
            station_url = self._player.current_url
        
        dlg = ScheduleRecordingDialog(
            self,
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
                    show_info(
                        # Translators: Mensaje de información
                        _("Grabación programada correctamente.\n\n"
                          "Emisora: {}\n"
                          "Inicio: {}\n"
                          "Fin: {}\n"
                          "Archivo: {}").format(
                            result["station_name"],
                            result["start_time"].strftime("%d/%m/%Y %H:%M"),
                            result["end_time"].strftime("%d/%m/%Y %H:%M"),
                            result["output_path"]
                        ),
                        _("Grabación programada")
                    )
                else:
                    show_error(
                        # Translators: Mensaje de error
                        _("No se pudo programar la grabación."),
                        _("Error")
                    )
        
        dlg.Destroy()
    
    def _on_view_scheduled(self, event: wx.CommandEvent) -> None:
        """Muestra las grabaciones programadas."""
        scheduled = self._player.scheduled_recordings
        
        if not scheduled:
            show_info(
                # Translators: Mensaje informativo
                _("No hay grabaciones programadas."),
                _("Grabaciones programadas")
            )
            return
        
        # Construir lista de grabaciones
        lines = []
        for i, rec in enumerate(scheduled, 1):
            lines.append(
                f"{i}. {rec.station_name}\n"
                f"   Inicio: {rec.start_time.strftime('%d/%m/%Y %H:%M')}\n"
                f"   Fin: {rec.end_time.strftime('%d/%m/%Y %H:%M')}"
            )
        
        # Diálogo para mostrar y gestionar grabaciones
        dlg = wx.SingleChoiceDialog(
            self,
            # Translators: Mensaje del diálogo
            _("Grabaciones programadas. Seleccione una para cancelarla:"),
            # Translators: Título del diálogo
            _("Grabaciones programadas"),
            [f"{i+1}. {r.station_name} - {r.start_time.strftime('%d/%m/%Y %H:%M')}" 
             for i, r in enumerate(scheduled)]
        )
        
        if dlg.ShowModal() == wx.ID_OK:
            index = dlg.GetSelection()
            
            # Confirmar cancelación
            confirm = wx.MessageDialog(
                self,
                # Translators: Mensaje de confirmación
                _("¿Desea cancelar esta grabación programada?\n\n{}").format(
                    scheduled[index].station_name
                ),
                _("Confirmar"),
                wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION
            )
            
            if confirm.ShowModal() == wx.ID_YES:
                if self._player.cancel_scheduled_recording(index):
                    show_info(
                        # Translators: Mensaje informativo
                        _("Grabación programada cancelada."),
                        _("Cancelada")
                    )
            
            confirm.Destroy()
        
        dlg.Destroy()
    
    def _on_open_recordings_folder(self, event: wx.CommandEvent) -> None:
        """Abre la carpeta de grabaciones en el explorador."""
        import os
        import subprocess
        
        recordings_dir = str(self._config.recordings_dir)
        
        if os.path.exists(recordings_dir):
            subprocess.Popen(f'explorer "{recordings_dir}"')
        else:
            show_error(
                # Translators: Mensaje de error
                _("La carpeta de grabaciones no existe:\n{}").format(recordings_dir),
                _("Error")
            )
    
    # === Navegación por teclado ===
    
    def _on_key(self, event: wx.KeyEvent) -> None:
        """Maneja las teclas globales."""
        key_code = event.GetKeyCode()
        
        # Ctrl+1-4: Cambiar de pestaña rápidamente
        if event.ControlDown():
            if key_code == ord("1"):
                if self.notebook.GetPageCount() > 0:
                    self.notebook.SetSelection(0)
                    self._focus_current_list()
                return
            elif key_code == ord("2"):
                if self.notebook.GetPageCount() > 1:
                    self.notebook.SetSelection(1)
                    self._focus_current_list()
                return
            elif key_code == ord("3"):
                if self.notebook.GetPageCount() > 2:
                    self.notebook.SetSelection(2)
                    self._focus_current_list()
                return
            elif key_code == ord("4"):
                if self.notebook.GetPageCount() > 3:
                    self.notebook.SetSelection(3)
                    self._focus_current_list()
                return
        
        # Alt+V: Ir al control de volumen
        if event.AltDown() and key_code == ord("V"):
            self.slider_volume.SetFocus()
            return
        
        # Escape: Cerrar ventana
        if key_code == wx.WXK_ESCAPE:
            self._on_close(None)
            return
        
        event.Skip()
    
    def _on_tab_changed(self, event: wx.NotebookEvent) -> None:
        """Maneja el cambio de pestaña."""
        self._config.last_tab = event.GetSelection()
        event.Skip()
    
    def _focus_current_list(self) -> None:
        """Enfoca la lista del panel actual."""
        current_page = self.notebook.GetCurrentPage()
        if hasattr(current_page, "focus_list"):
            current_page.focus_list()
    
    def _on_show(self, event: wx.ShowEvent) -> None:
        """Maneja cuando se muestra la ventana para sincronizar el foco."""
        if event.IsShown():
            wx.CallAfter(self._sync_player_state)
        event.Skip()

    # === Cierre de la ventana ===
    
    def _on_close(self, event) -> None:
        """Maneja el cierre de la ventana."""
        # Guardar configuración
        self._config.save()
        
        # Emitir evento
        self._event_bus.emit(EventType.WINDOW_CLOSED)
        
        # Ocultar ventana (no destruir para poder reabrirla)
        self.Hide()
        
        import gui
        gui.mainFrame.postPopup()
