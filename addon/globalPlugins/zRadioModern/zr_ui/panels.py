# -*- coding: utf-8 -*-
# Copyright (C) 2025 Héctor J. Benítez Corredera <xebolax@gmail.com>
# This file is covered by the GNU General Public License.

"""
Paneles de la interfaz de usuario de zRadioModern.

Contiene los paneles para cada pestaña de la ventana principal.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional, List, Dict
import threading

import wx
import wx.adv
import addonHandler
import ui

from logHandler import log

if TYPE_CHECKING:
    from ..zr_core.database import DatabaseManager
    from ..zr_core.player import AudioPlayer
    from ..zr_core.api_client import RadioBrowserAPI
    from ..zr_core.events import EventBus

from ..zr_core.models import Station, Favorite
from ..zr_core.events import EventType
from ..zr_core.config import get_config
from .dialogs import show_error, show_info, StationEditDialog, StationInfoDialog

# Para traducción
addonHandler.initTranslation()


class BasePanel(wx.Panel):
    """
    Panel base con funcionalidades comunes.
    """
    
    def __init__(
        self,
        parent: wx.Window,
        player: "AudioPlayer",
        event_bus: "EventBus"
    ):
        super().__init__(parent)
        self._player = player
        self._event_bus = event_bus
        self._stations: List[Station] = []
    
    def focus_list(self) -> None:
        """Enfoca la lista principal del panel."""
        pass
    
    def refresh(self) -> None:
        """Refresca el contenido del panel."""
        pass
    
    def _play_station(self, station: Station) -> None:
        """Reproduce una emisora."""
        from ..zr_core.internet import InternetChecker
        
        checker = InternetChecker()
        if not checker.check_url(station.url):
            show_error(
                # Translators: Error al cargar emisora
                _("No se pudo conectar con la emisora.\n\n"
                  "Verifique su conexión o intente más tarde."),
                _("Error")
            )
            return
        
        # Reproducir
        self._player.play(station.url)
        self._player.current_station = station
        self._event_bus.emit(EventType.PLAYBACK_STARTED, station)

    def _announce_list_position(self, list_ctrl: wx.ListBox) -> None:
        """Anuncia la posición actual y el total de elementos de la lista."""
        idx = list_ctrl.GetSelection()
        total = list_ctrl.GetCount()
        
        if idx == wx.NOT_FOUND or total == 0:
            # Translators: Mensaje cuando la lista está vacía
            ui.message(_("Lista vacía"))
            return
            
        # El índice es 0-based, sumamos 1 para que sea natural para el usuario
        # Translators: Mensaje de posición en la lista (ej: 1 de 10)
        ui.message(_("{} de {}").format(idx + 1, total))


class GeneralPanel(BasePanel):
    """
    Panel de la pestaña General.
    
    Muestra la lista de emisoras del país/idioma/etiqueta
    configurados por defecto.
    """
    
    def __init__(
        self,
        parent: wx.Window,
        api: "RadioBrowserAPI",
        player: "AudioPlayer",
        db: "DatabaseManager",
        event_bus: "EventBus"
    ):
        super().__init__(parent, player, event_bus)
        self._api = api
        self._db = db
        self._config = get_config()
        self._stations: List[Station] = []
        self._filtered_stations: List[Station] = []
        self._country_codes: Dict[str, str] = {}
        
        self._init_ui()
        self._load_data()
    
    def _init_ui(self) -> None:
        """Inicializa la interfaz."""
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Selector de país
        country_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Translators: Etiqueta del selector de país
        lbl_country = wx.StaticText(self, label=_("País:"))
        country_sizer.Add(lbl_country, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        
        self.cmb_country = wx.ComboBox(self, style=wx.CB_READONLY)
        self.cmb_country.SetName(_("Seleccionar país"))
        country_sizer.Add(self.cmb_country, 1, wx.EXPAND | wx.ALL, 5)
        
        # Translators: Botón cargar emisoras
        self.btn_load = wx.Button(self, label=_("&Cargar emisoras"))
        country_sizer.Add(self.btn_load, 0, wx.ALL, 5)
        
        main_sizer.Add(country_sizer, 0, wx.EXPAND)
        
        # Campo de búsqueda
        search_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Translators: Etiqueta del campo de búsqueda
        lbl_search = wx.StaticText(self, label=_("Filtrar:"))
        search_sizer.Add(lbl_search, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        
        self.txt_search = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        search_sizer.Add(self.txt_search, 1, wx.EXPAND | wx.ALL, 5)
        
        # Translators: Botón buscar
        self.btn_search = wx.Button(self, label=_("&Buscar"))
        search_sizer.Add(self.btn_search, 0, wx.ALL, 5)
        
        main_sizer.Add(search_sizer, 0, wx.EXPAND)
        
        # Lista de emisoras
        # Translators: Etiqueta de la lista
        lbl_list = wx.StaticText(self, label=_("Listado de emisoras:"))
        main_sizer.Add(lbl_list, 0, wx.ALL, 5)
        
        self.lst_stations = wx.ListBox(self, style=wx.LB_SINGLE)
        main_sizer.Add(self.lst_stations, 1, wx.EXPAND | wx.ALL, 5)
        
        self.SetSizer(main_sizer)
        
        # Cargar países
        self._load_countries()
        
        # Eventos
        self.btn_load.Bind(wx.EVT_BUTTON, self._on_load_country)
        self.txt_search.Bind(wx.EVT_TEXT_ENTER, self._on_search)
        self.btn_search.Bind(wx.EVT_BUTTON, self._on_search)
        self.lst_stations.Bind(wx.EVT_KEY_UP, self._on_list_key)
        self.lst_stations.Bind(wx.EVT_CONTEXT_MENU, self._on_context_menu)
        self.lst_stations.Bind(wx.EVT_LISTBOX_DCLICK, self._on_double_click)
    
    def _load_countries(self) -> None:
        """Carga la lista de países en el combo."""
        # Lista de países comunes con sus códigos
        countries = [
            (_("Todas las populares"), "TOP"),
            (_("España"), "ES"),
            (_("México"), "MX"),
            (_("Argentina"), "AR"),
            (_("Colombia"), "CO"),
            (_("Chile"), "CL"),
            (_("Perú"), "PE"),
            (_("Venezuela"), "VE"),
            (_("Ecuador"), "EC"),
            (_("Estados Unidos"), "US"),
            (_("Reino Unido"), "GB"),
            (_("Francia"), "FR"),
            (_("Alemania"), "DE"),
            (_("Italia"), "IT"),
            (_("Brasil"), "BR"),
            (_("Portugal"), "PT"),
        ]
        
        self._country_codes = {}
        for name, code in countries:
            self.cmb_country.Append(name)
            self._country_codes[name] = code
        
        # Seleccionar país por defecto de la configuración o España
        default_country = self._config.default_country or "ES"
        for i, (name, code) in enumerate(countries):
            if code == default_country:
                self.cmb_country.SetSelection(i)
                break
        else:
            self.cmb_country.SetSelection(1)  # España por defecto
    
    def _on_load_country(self, event) -> None:
        """Carga emisoras del país seleccionado."""
        self._load_data()
    
    def _load_data(self) -> None:
        """Carga los datos iniciales."""
        # Cargar en hilo separado
        thread = threading.Thread(target=self._fetch_stations, daemon=True)
        thread.start()
    
    def _fetch_stations(self) -> None:
        """Obtiene las emisoras de la API según el país seleccionado."""
        try:
            # Obtener código del país seleccionado
            selected = self.cmb_country.GetStringSelection()
            country_code = self._country_codes.get(selected, "ES")
            
            # Guardar en configuración
            self._config.default_country = country_code
            self._config.save()
            
            # Límite alto para obtener todas las emisoras
            limit = 10000
            
            if country_code == "TOP":
                # Emisoras más populares a nivel mundial
                stations = self._api.get_top_stations(limit=2000)
            else:
                # Emisoras por país
                stations = self._api.get_stations_by_country(country_code, limit=limit)
            
            if stations:
                wx.CallAfter(self._update_list, stations)
            else:
                wx.CallAfter(
                    self._show_empty_message,
                    # Translators: Mensaje cuando no hay emisoras
                    _("Sin emisoras para este país.")
                )
        except Exception as e:
            log.error(f"Error cargando emisoras: {e}")
            wx.CallAfter(
                self._show_empty_message,
                # Translators: Mensaje de error
                _("Error al cargar emisoras.")
            )
    
    def _update_list(self, stations: List[Station]) -> None:
        """Actualiza la lista de emisoras."""
        self._stations = stations
        self._filtered_stations = stations
        
        self.lst_stations.Clear()
        for station in stations:
            self.lst_stations.Append(station.name)
        
        if self.lst_stations.GetCount() > 0:
            self.lst_stations.SetSelection(0)
    
    def _show_empty_message(self, message: str) -> None:
        """Muestra un mensaje cuando no hay datos."""
        self.lst_stations.Clear()
        self.lst_stations.Append(message)
        self.lst_stations.SetSelection(0)
    
    def _on_search(self, event) -> None:
        """Maneja la búsqueda."""
        query = self.txt_search.GetValue().strip().lower()
        
        if self.btn_search.GetLabel() == _("&Buscar"):
            if not query:
                show_error(
                    # Translators: Error de búsqueda vacía
                    _("Escriba algo para buscar."),
                    _("Error")
                )
                self.txt_search.SetFocus()
                return
            
            # Filtrar la lista
            self._filtered_stations = [
                s for s in self._stations
                if query in s.name.lower()
            ]
            
            if not self._filtered_stations:
                show_error(
                    # Translators: Sin resultados
                    _("No se encontraron resultados."),
                    _("Búsqueda")
                )
                return
            
            self.lst_stations.Clear()
            for station in self._filtered_stations:
                self.lst_stations.Append(station.name)
            self.lst_stations.SetSelection(0)
            self.lst_stations.SetFocus()
            
            # Translators: Botón limpiar
            self.btn_search.SetLabel(_("&Limpiar"))
        else:
            # Limpiar búsqueda
            self.txt_search.Clear()
            self._filtered_stations = self._stations
            self._update_list(self._stations)
            self.txt_search.SetFocus()
            # Translators: Botón buscar
            self.btn_search.SetLabel(_("&Buscar"))
    
    def _on_list_key(self, event: wx.KeyEvent) -> None:
        """Maneja las teclas en la lista."""
        key_code = event.GetKeyCode()
        if key_code in (wx.WXK_SPACE, wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._play_selected()
            return  # No procesar más esta tecla
        elif key_code == wx.WXK_F1:
            self._announce_list_position(self.lst_stations)
            return
        event.Skip()
    
    def _on_double_click(self, event) -> None:
        """Maneja el doble clic."""
        self._play_selected()
    
    def _play_selected(self) -> None:
        """Reproduce la emisora seleccionada."""
        idx = self.lst_stations.GetSelection()
        if idx == wx.NOT_FOUND or not self._filtered_stations:
            return
        
        if idx >= len(self._filtered_stations):
            return
        
        station = self._filtered_stations[idx]
        self._play_station(station)
    
    def _on_context_menu(self, event) -> None:
        """Muestra el menú contextual."""
        idx = self.lst_stations.GetSelection()
        if idx == wx.NOT_FOUND or not self._filtered_stations:
            return
        
        if idx >= len(self._filtered_stations):
            return
        
        station = self._filtered_stations[idx]
        menu = wx.Menu()
        
        # Translators: Elemento de menú
        item_play = menu.Append(wx.ID_ANY, _("&Reproducir"))
        self.Bind(wx.EVT_MENU, lambda e: self._play_selected(), item_play)
        
        # Verificar si ya está en favoritos para mostrar la opción adecuada
        if self._db.favorite_exists(station.url):
            # Translators: Elemento de menú para quitar de favoritos
            item_fav = menu.Append(wx.ID_ANY, _("&Quitar de favoritos"))
            self.Bind(wx.EVT_MENU, lambda e: self._remove_from_favorites(), item_fav)
        else:
            # Translators: Elemento de menú para agregar a favoritos
            item_fav = menu.Append(wx.ID_ANY, _("&Agregar a favoritos"))
            self.Bind(wx.EVT_MENU, lambda e: self._add_to_favorites(), item_fav)
        
        menu.AppendSeparator()
        
        # Translators: Elemento de menú para ver información
        item_info = menu.Append(wx.ID_ANY, _("&Información de la emisora"))
        self.Bind(wx.EVT_MENU, lambda e: self._show_station_info(), item_info)
        
        # Translators: Elemento de menú
        item_copy = menu.Append(wx.ID_ANY, _("&Copiar URL"))
        self.Bind(wx.EVT_MENU, lambda e: self._copy_url(), item_copy)
        
        self.PopupMenu(menu)
        menu.Destroy()
    
    def _add_to_favorites(self) -> None:
        """Añade la emisora a favoritos."""
        idx = self.lst_stations.GetSelection()
        if idx == wx.NOT_FOUND or idx >= len(self._filtered_stations):
            return
        
        station = self._filtered_stations[idx]
        
        if self._db.favorite_exists(station.url):
            show_info(
                # Translators: La emisora ya existe
                _("Esta emisora ya está en favoritos."),
                _("Información")
            )
            return
        
        favorite = Favorite.from_station(station)
        self._db.add_favorite(favorite)
        
        self._event_bus.emit(EventType.FAVORITE_ADDED, favorite)
        
        # Notificación
        wx.adv.NotificationMessage(
            # Translators: Título de notificación
            title=_("Favorito añadido"),
            # Translators: Mensaje de notificación
            message=_("Se añadió {} a favoritos.").format(station.name)
        ).Show(timeout=5)
    
    def _remove_from_favorites(self) -> None:
        """Quita la emisora de favoritos."""
        idx = self.lst_stations.GetSelection()
        if idx == wx.NOT_FOUND or idx >= len(self._filtered_stations):
            return
        
        station = self._filtered_stations[idx]
        
        # Buscar el favorito por URL
        favorites = self._db.get_favorites()
        favorite = next((f for f in favorites if f.url == station.url), None)
        
        if favorite:
            self._db.delete_favorite(favorite.id)
            self._event_bus.emit(EventType.FAVORITE_REMOVED, favorite)
            
            # Notificación
            wx.adv.NotificationMessage(
                # Translators: Título de notificación
                title=_("Favorito eliminado"),
                # Translators: Mensaje de notificación
                message=_("Se eliminó {} de favoritos.").format(station.name)
            ).Show(timeout=5)
    
    def _show_station_info(self) -> None:
        """Muestra información de la emisora seleccionada."""
        idx = self.lst_stations.GetSelection()
        if idx == wx.NOT_FOUND or idx >= len(self._filtered_stations):
            return
        
        station = self._filtered_stations[idx]
        dlg = StationInfoDialog(self, station=station, api=self._api)
        dlg.ShowModal()
        dlg.Destroy()
    
    def _copy_url(self) -> None:
        """Copia la URL al portapapeles."""
        idx = self.lst_stations.GetSelection()
        if idx == wx.NOT_FOUND or idx >= len(self._filtered_stations):
            return
        
        station = self._filtered_stations[idx]
        
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(station.url))
            wx.TheClipboard.Close()
            
            wx.adv.NotificationMessage(
                title=_("URL copiada"),
                message=_("URL de {} copiada al portapapeles.").format(
                    station.name
                )
            ).Show(timeout=5)
    
    def focus_list(self) -> None:
        """Enfoca la lista."""
        self.lst_stations.SetFocus()
    
    def refresh(self) -> None:
        """Refresca los datos."""
        self._load_data()


class FavoritesPanel(BasePanel):
    """
    Panel de la pestaña Favoritos.
    
    Gestiona las emisoras marcadas como favoritas.
    """
    
    def __init__(
        self,
        parent: wx.Window,
        api: "RadioBrowserAPI",
        db: "DatabaseManager",
        player: "AudioPlayer",
        event_bus: "EventBus"
    ):
        super().__init__(parent, player, event_bus)
        self._api = api
        self._db = db
        self._favorites: List[Favorite] = []
        self._filtered_favorites: List[Favorite] = []
        
        self._init_ui()
        self._setup_event_subscriptions()
        self._load_data()
    
    def _setup_event_subscriptions(self) -> None:
        """Configura las suscripciones a eventos para actualización en tiempo real."""
        # Suscribirse a eventos de favoritos para actualización en tiempo real
        self._event_bus.subscribe(
            EventType.FAVORITE_ADDED,
            lambda data: wx.CallAfter(self._on_favorites_changed),
            weak=False
        )
        self._event_bus.subscribe(
            EventType.FAVORITE_REMOVED,
            lambda data: wx.CallAfter(self._on_favorites_changed),
            weak=False
        )
        self._event_bus.subscribe(
            EventType.FAVORITE_UPDATED,
            lambda data: wx.CallAfter(self._on_favorites_changed),
            weak=False
        )
    
    def _on_favorites_changed(self) -> None:
        """Maneja cambios en favoritos para actualización en tiempo real."""
        # Guardar selección actual
        current_selection = self.lst_favorites.GetSelection()
        current_name = ""
        if current_selection != wx.NOT_FOUND and current_selection < len(self._filtered_favorites):
            current_name = self._filtered_favorites[current_selection].name
        
        # Recargar datos
        self._load_data()
        
        # Intentar restaurar selección
        if current_name:
            for i, fav in enumerate(self._filtered_favorites):
                if fav.name == current_name:
                    self.lst_favorites.SetSelection(i)
                    break
    
    def _init_ui(self) -> None:
        """Inicializa la interfaz."""
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Campo de búsqueda
        search_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Translators: Etiqueta del campo de búsqueda
        lbl_search = wx.StaticText(self, label=_("Buscar favorito:"))
        search_sizer.Add(lbl_search, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        
        self.txt_search = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        search_sizer.Add(self.txt_search, 1, wx.EXPAND | wx.ALL, 5)
        
        # Translators: Botón buscar
        self.btn_search = wx.Button(self, label=_("&Buscar"))
        search_sizer.Add(self.btn_search, 0, wx.ALL, 5)
        
        main_sizer.Add(search_sizer, 0, wx.EXPAND)
        
        # Lista de favoritos
        # Translators: Etiqueta de la lista
        lbl_list = wx.StaticText(self, label=_("Emisoras favoritas:"))
        main_sizer.Add(lbl_list, 0, wx.ALL, 5)
        
        self.lst_favorites = wx.ListBox(self, style=wx.LB_SINGLE)
        main_sizer.Add(self.lst_favorites, 1, wx.EXPAND | wx.ALL, 5)
        
        # Botones de gestión
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Translators: Botón nueva emisora
        self.btn_new = wx.Button(self, label=_("&Nueva"))
        btn_sizer.Add(self.btn_new, 1, wx.ALL, 5)
        
        # Translators: Botón editar emisora
        self.btn_edit = wx.Button(self, label=_("&Editar"))
        btn_sizer.Add(self.btn_edit, 1, wx.ALL, 5)
        
        # Translators: Botón eliminar emisora
        self.btn_delete = wx.Button(self, label=_("E&liminar"))
        btn_sizer.Add(self.btn_delete, 1, wx.ALL, 5)
        
        main_sizer.Add(btn_sizer, 0, wx.EXPAND)
        
        self.SetSizer(main_sizer)
        
        # Eventos
        self.txt_search.Bind(wx.EVT_TEXT_ENTER, self._on_search)
        self.btn_search.Bind(wx.EVT_BUTTON, self._on_search)
        self.lst_favorites.Bind(wx.EVT_KEY_UP, self._on_list_key)
        self.lst_favorites.Bind(wx.EVT_CONTEXT_MENU, self._on_context_menu)
        self.lst_favorites.Bind(wx.EVT_LISTBOX_DCLICK, self._on_double_click)
        self.btn_new.Bind(wx.EVT_BUTTON, self._on_new)
        self.btn_edit.Bind(wx.EVT_BUTTON, self._on_edit)
        self.btn_delete.Bind(wx.EVT_BUTTON, self._on_delete)
    
    def _load_data(self) -> None:
        """Carga los favoritos."""
        self._favorites = self._db.get_favorites()
        self._filtered_favorites = self._favorites
        self._update_list()
    
    def _update_list(self) -> None:
        """Actualiza la lista de favoritos."""
        self.lst_favorites.Clear()
        
        if not self._filtered_favorites:
            # Translators: Mensaje sin favoritos
            self.lst_favorites.Append(_("No hay favoritos."))
        else:
            for fav in self._filtered_favorites:
                self.lst_favorites.Append(fav.name)
        
        self.lst_favorites.SetSelection(0)
    
    def _on_search(self, event) -> None:
        """Maneja la búsqueda."""
        query = self.txt_search.GetValue().strip().lower()
        
        if self.btn_search.GetLabel() == _("&Buscar"):
            if not query:
                show_error(
                    _("Escriba algo para buscar."),
                    _("Error")
                )
                return
            
            self._filtered_favorites = [
                f for f in self._favorites
                if query in f.name.lower()
            ]
            
            if not self._filtered_favorites:
                show_error(
                    _("No se encontraron resultados."),
                    _("Búsqueda")
                )
                return
            
            self._update_list()
            self.lst_favorites.SetFocus()
            self.btn_search.SetLabel(_("&Limpiar"))
        else:
            self.txt_search.Clear()
            self._filtered_favorites = self._favorites
            self._update_list()
            self.txt_search.SetFocus()
            self.btn_search.SetLabel(_("&Buscar"))
    
    def _on_list_key(self, event: wx.KeyEvent) -> None:
        """Maneja las teclas en la lista."""
        key_code = event.GetKeyCode()
        
        if key_code in (wx.WXK_SPACE, wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._play_selected()
            return
        elif key_code == wx.WXK_F1:
            self._announce_list_position(self.lst_favorites)
            return
        elif event.AltDown():
            if key_code == wx.WXK_UP:
                self._move_favorite(-1)
                return
            elif key_code == wx.WXK_DOWN:
                self._move_favorite(1)
                return
        
        event.Skip()
    
    def _on_double_click(self, event) -> None:
        """Maneja el doble clic."""
        self._play_selected()
    
    def _play_selected(self) -> None:
        """Reproduce el favorito seleccionado."""
        idx = self.lst_favorites.GetSelection()
        if idx == wx.NOT_FOUND or not self._filtered_favorites:
            return
        
        # Verificar que no sea el mensaje de vacío
        if self.lst_favorites.GetString(idx) == _("No hay favoritos."):
            return
        
        if idx >= len(self._filtered_favorites):
            return
        
        favorite = self._filtered_favorites[idx]
        station = favorite.to_station()
        
        # Incrementar contador
        if favorite.id:
            self._db.increment_play_count(favorite.id)
        
        self._play_station(station)
    
    def _on_context_menu(self, event) -> None:
        """Muestra el menú contextual."""
        idx = self.lst_favorites.GetSelection()
        if idx == wx.NOT_FOUND:
            return
        
        if self.lst_favorites.GetString(idx) == _("No hay favoritos."):
            return
        
        if idx >= len(self._filtered_favorites):
            return
        
        menu = wx.Menu()
        
        # Translators: Elemento de menú
        item_play = menu.Append(wx.ID_ANY, _("&Reproducir"))
        self.Bind(wx.EVT_MENU, lambda e: self._play_selected(), item_play)
        
        menu.AppendSeparator()
        
        # Translators: Elemento de menú
        item_edit = menu.Append(wx.ID_ANY, _("&Editar"))
        self.Bind(wx.EVT_MENU, lambda e: self._on_edit(None), item_edit)
        
        # Translators: Elemento de menú
        item_delete = menu.Append(wx.ID_ANY, _("E&liminar"))
        self.Bind(wx.EVT_MENU, lambda e: self._on_delete(None), item_delete)
        
        menu.AppendSeparator()
        
        # Translators: Elemento de menú para ver información
        item_info = menu.Append(wx.ID_ANY, _("&Información de la emisora"))
        self.Bind(wx.EVT_MENU, lambda e: self._show_station_info(), item_info)
        
        # Translators: Elemento de menú
        item_copy = menu.Append(wx.ID_ANY, _("&Copiar URL"))
        self.Bind(wx.EVT_MENU, lambda e: self._copy_url(), item_copy)
        
        self.PopupMenu(menu)
        menu.Destroy()
    
    def _on_new(self, event) -> None:
        """Crea un nuevo favorito."""
        dlg = StationEditDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            result = dlg.get_result()
            if result:
                favorite = Favorite(
                    name=result["name"],
                    url=result["url"],
                    notes=result["notes"]
                )
                self._db.add_favorite(favorite)
                self._load_data()
                self._event_bus.emit(EventType.FAVORITE_ADDED, favorite)
        dlg.Destroy()
    
    def _on_edit(self, event) -> None:
        """Edita el favorito seleccionado."""
        idx = self.lst_favorites.GetSelection()
        if idx == wx.NOT_FOUND or idx >= len(self._filtered_favorites):
            return
        
        favorite = self._filtered_favorites[idx]
        dlg = StationEditDialog(self, favorite)
        
        if dlg.ShowModal() == wx.ID_OK:
            result = dlg.get_result()
            if result:
                favorite.name = result["name"]
                favorite.url = result["url"]
                favorite.notes = result["notes"]
                self._db.update_favorite(favorite)
                self._load_data()
                self._event_bus.emit(EventType.FAVORITE_UPDATED, favorite)
        
        dlg.Destroy()
    
    def _on_delete(self, event) -> None:
        """Elimina el favorito seleccionado."""
        idx = self.lst_favorites.GetSelection()
        if idx == wx.NOT_FOUND or idx >= len(self._filtered_favorites):
            return
        
        favorite = self._filtered_favorites[idx]
        
        from .dialogs import show_confirm
        if show_confirm(
            # Translators: Confirmación de eliminación
            _("¿Eliminar '{}' de favoritos?").format(favorite.name)
        ):
            self._db.delete_favorite(favorite.id)
            self._load_data()
            self._event_bus.emit(EventType.FAVORITE_REMOVED, favorite)
    
    def _move_favorite(self, direction: int) -> None:
        """Mueve un favorito arriba o abajo."""
        idx = self.lst_favorites.GetSelection()
        if idx == wx.NOT_FOUND or idx >= len(self._filtered_favorites):
            return
        
        favorite = self._filtered_favorites[idx]
        if self._db.move_favorite(favorite.id, direction):
            new_idx = idx + direction
            self._load_data()
            if 0 <= new_idx < len(self._favorites):
                self.lst_favorites.SetSelection(new_idx)
    
    def _copy_url(self) -> None:
        """Copia la URL al portapapeles."""
        idx = self.lst_favorites.GetSelection()
        if idx == wx.NOT_FOUND or idx >= len(self._filtered_favorites):
            return
        
        favorite = self._filtered_favorites[idx]
        
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(favorite.url))
            wx.TheClipboard.Close()
            
            wx.adv.NotificationMessage(
                title=_("URL copiada"),
                message=_("URL copiada al portapapeles.")
            ).Show(timeout=5)
    
    def _show_station_info(self) -> None:
        """Muestra información de la emisora favorita seleccionada."""
        idx = self.lst_favorites.GetSelection()
        if idx == wx.NOT_FOUND or idx >= len(self._filtered_favorites):
            return
        
        favorite = self._filtered_favorites[idx]
        station = favorite.to_station()
        dlg = StationInfoDialog(self, station=station, favorite=favorite, api=self._api)
        dlg.ShowModal()
        dlg.Destroy()
    
    def focus_list(self) -> None:
        """Enfoca la lista."""
        self.lst_favorites.SetFocus()
    
    def refresh(self) -> None:
        """Refresca los datos."""
        self._load_data()


class SearchPanel(BasePanel):
    """
    Panel de la pestaña Buscador.
    
    Permite búsqueda avanzada por país, idioma y etiqueta.
    """
    
    def __init__(
        self,
        parent: wx.Window,
        api: "RadioBrowserAPI",
        player: "AudioPlayer",
        db: "DatabaseManager",
        event_bus: "EventBus"
    ):
        super().__init__(parent, player, event_bus)
        self._api = api
        self._db = db
        self._results: List[Station] = []
        
        self._init_ui()
    
    def _init_ui(self) -> None:
        """Inicializa la interfaz."""
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Selector de categoría
        cat_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Translators: Etiqueta del selector
        lbl_category = wx.StaticText(self, label=_("Categoría:"))
        cat_sizer.Add(lbl_category, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        
        self.choice_category = wx.Choice(self, choices=[
            # Translators: Opciones de búsqueda
            _("Búsqueda general"),
            _("Por país"),
            _("Por idioma"),
            _("Por etiqueta")
        ])
        self.choice_category.SetSelection(0)
        cat_sizer.Add(self.choice_category, 1, wx.EXPAND | wx.ALL, 5)
        
        main_sizer.Add(cat_sizer, 0, wx.EXPAND)
        
        # Campo de búsqueda
        search_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Translators: Etiqueta de búsqueda
        self.lbl_search = wx.StaticText(self, label=_("Buscar:"))
        search_sizer.Add(self.lbl_search, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        
        self.txt_search = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        search_sizer.Add(self.txt_search, 1, wx.EXPAND | wx.ALL, 5)
        
        # Translators: Botón buscar
        self.btn_search = wx.Button(self, label=_("&Buscar"))
        search_sizer.Add(self.btn_search, 0, wx.ALL, 5)
        
        main_sizer.Add(search_sizer, 0, wx.EXPAND)
        
        # Lista de resultados
        # Translators: Etiqueta de resultados
        lbl_results = wx.StaticText(self, label=_("Resultados:"))
        main_sizer.Add(lbl_results, 0, wx.ALL, 5)
        
        self.lst_results = wx.ListBox(self, style=wx.LB_SINGLE)
        # Translators: Mensaje esperando búsqueda
        self.lst_results.Append(_("Esperando una búsqueda."))
        self.lst_results.SetSelection(0)
        main_sizer.Add(self.lst_results, 1, wx.EXPAND | wx.ALL, 5)
        
        self.SetSizer(main_sizer)
        
        # Eventos
        self.choice_category.Bind(wx.EVT_CHOICE, self._on_category_change)
        self.txt_search.Bind(wx.EVT_TEXT_ENTER, self._on_search)
        self.btn_search.Bind(wx.EVT_BUTTON, self._on_search)
        self.lst_results.Bind(wx.EVT_KEY_UP, self._on_list_key)
        self.lst_results.Bind(wx.EVT_CONTEXT_MENU, self._on_context_menu)
        self.lst_results.Bind(wx.EVT_LISTBOX_DCLICK, self._on_double_click)
    
    def _on_category_change(self, event) -> None:
        """Maneja el cambio de categoría."""
        idx = self.choice_category.GetSelection()
        
        labels = [
            # Translators: Etiquetas de búsqueda
            _("Buscar nombre:"),
            _("Buscar país:"),
            _("Buscar idioma:"),
            _("Buscar etiqueta:")
        ]
        
        self.lbl_search.SetLabel(labels[idx])
        self.txt_search.Clear()
        self.lst_results.Clear()
        self.lst_results.Append(_("Esperando una búsqueda."))
        self.lst_results.SetSelection(0)
        self._results = []
        self.btn_search.SetLabel(_("&Buscar"))
    
    def _on_search(self, event) -> None:
        """Realiza la búsqueda."""
        if self.btn_search.GetLabel() == _("&Limpiar"):
            self._on_category_change(None)
            return
        
        query = self.txt_search.GetValue().strip()
        if not query:
            show_error(_("Escriba algo para buscar."), _("Error"))
            return
        
        category = self.choice_category.GetSelection()
        
        # Buscar en hilo separado
        thread = threading.Thread(
            target=self._perform_search,
            args=(category, query),
            daemon=True
        )
        thread.start()
    
    def _perform_search(self, category: int, query: str) -> None:
        """Realiza la búsqueda en segundo plano."""
        try:
            limit = 10000  # Aumentar límite para obtener "todas" las emisoras posibles
            if category == 0:  # General
                results = self._api.search_by_name(query, limit=limit)
            elif category == 1:  # País
                results = self._api.get_stations_by_country(query.upper(), limit=limit)
            elif category == 2:  # Idioma
                results = self._api.get_stations_by_language(query, limit=limit)
            elif category == 3:  # Etiqueta
                results = self._api.get_stations_by_tag(query, limit=limit)
            else:
                results = []
            
            wx.CallAfter(self._show_results, results)
            
        except Exception as e:
            log.error(f"Error en búsqueda: {e}")
            wx.CallAfter(self._show_error)
    
    def _show_results(self, results: List[Station]) -> None:
        """Muestra los resultados."""
        self._results = results
        self.lst_results.Clear()
        
        if not results:
            self.lst_results.Append(_("No se encontraron resultados."))
        else:
            for station in results:
                self.lst_results.Append(station.name)
        
        self.lst_results.SetSelection(0)
        self.lst_results.SetFocus()
        self.btn_search.SetLabel(_("&Limpiar"))
    
    def _show_error(self) -> None:
        """Muestra error de búsqueda."""
        self.lst_results.Clear()
        self.lst_results.Append(_("Error al buscar."))
        self.lst_results.SetSelection(0)
    
    def _on_list_key(self, event: wx.KeyEvent) -> None:
        """Maneja las teclas en la lista."""
        key_code = event.GetKeyCode()
        if key_code in (wx.WXK_SPACE, wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._play_selected()
            return
        elif key_code == wx.WXK_F1:
            self._announce_list_position(self.lst_results)
            return
        event.Skip()
    
    def _on_double_click(self, event) -> None:
        """Maneja el doble clic."""
        self._play_selected()
    
    def _play_selected(self) -> None:
        """Reproduce la emisora seleccionada."""
        idx = self.lst_results.GetSelection()
        if idx == wx.NOT_FOUND or not self._results:
            return
        
        if idx >= len(self._results):
            return
        
        station = self._results[idx]
        self._play_station(station)
    
    def _on_context_menu(self, event) -> None:
        """Muestra el menú contextual."""
        idx = self.lst_results.GetSelection()
        if idx == wx.NOT_FOUND or not self._results:
            return
        
        if idx >= len(self._results):
            return
        
        station = self._results[idx]
        menu = wx.Menu()
        
        item_play = menu.Append(wx.ID_ANY, _("&Reproducir"))
        self.Bind(wx.EVT_MENU, lambda e: self._play_selected(), item_play)
        
        # Verificar si ya está en favoritos para mostrar la opción adecuada
        if self._db.favorite_exists(station.url):
            # Translators: Elemento de menú para quitar de favoritos
            item_fav = menu.Append(wx.ID_ANY, _("&Quitar de favoritos"))
            self.Bind(wx.EVT_MENU, lambda e: self._remove_from_favorites(), item_fav)
        else:
            # Translators: Elemento de menú para agregar a favoritos
            item_fav = menu.Append(wx.ID_ANY, _("&Agregar a favoritos"))
            self.Bind(wx.EVT_MENU, lambda e: self._add_to_favorites(), item_fav)
        
        menu.AppendSeparator()
        
        # Translators: Elemento de menú para ver información
        item_info = menu.Append(wx.ID_ANY, _("&Información de la emisora"))
        self.Bind(wx.EVT_MENU, lambda e: self._show_station_info(), item_info)
        
        item_copy = menu.Append(wx.ID_ANY, _("&Copiar URL"))
        self.Bind(wx.EVT_MENU, lambda e: self._copy_url(), item_copy)
        
        self.PopupMenu(menu)
        menu.Destroy()
    
    def _add_to_favorites(self) -> None:
        """Añade a favoritos."""
        idx = self.lst_results.GetSelection()
        if idx >= len(self._results):
            return
        
        station = self._results[idx]
        
        if self._db.favorite_exists(station.url):
            show_info(_("Esta emisora ya está en favoritos."))
            return
        
        favorite = Favorite.from_station(station)
        self._db.add_favorite(favorite)
        self._event_bus.emit(EventType.FAVORITE_ADDED, favorite)
        
        wx.adv.NotificationMessage(
            title=_("Favorito añadido"),
            message=_("Se añadió {} a favoritos.").format(station.name)
        ).Show(timeout=5)
    
    def _remove_from_favorites(self) -> None:
        """Quita la emisora de favoritos."""
        idx = self.lst_results.GetSelection()
        if idx >= len(self._results):
            return
        
        station = self._results[idx]
        
        # Buscar el favorito por URL
        favorites = self._db.get_favorites()
        favorite = next((f for f in favorites if f.url == station.url), None)
        
        if favorite:
            self._db.delete_favorite(favorite.id)
            self._event_bus.emit(EventType.FAVORITE_REMOVED, favorite)
            
            # Notificación
            wx.adv.NotificationMessage(
                # Translators: Título de notificación
                title=_("Favorito eliminado"),
                # Translators: Mensaje de notificación
                message=_("Se eliminó {} de favoritos.").format(station.name)
            ).Show(timeout=5)
    
    def _show_station_info(self) -> None:
        """Muestra información de la emisora seleccionada."""
        idx = self.lst_results.GetSelection()
        if idx >= len(self._results):
            return
        
        station = self._results[idx]
        dlg = StationInfoDialog(self, station=station, api=self._api)
        dlg.ShowModal()
        dlg.Destroy()
    
    def _copy_url(self) -> None:
        """Copia la URL al portapapeles."""
        idx = self.lst_results.GetSelection()
        if idx >= len(self._results):
            return
        
        station = self._results[idx]
        
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(station.url))
            wx.TheClipboard.Close()
    
    def focus_list(self) -> None:
        """Enfoca la lista."""
        self.lst_results.SetFocus()


class HistoryPanel(BasePanel):
    """
    Panel de la pestaña Historial.
    
    Muestra el historial de reproducción.
    """
    
    def __init__(
        self,
        parent: wx.Window,
        api: "RadioBrowserAPI",
        db: "DatabaseManager",
        player: "AudioPlayer",
        event_bus: "EventBus"
    ):
        super().__init__(parent, player, event_bus)
        self._api = api
        self._db = db
        self._history = []
        
        self._init_ui()
        self._setup_event_subscriptions()
        self._load_data()
    
    def _setup_event_subscriptions(self) -> None:
        """Configura las suscripciones a eventos para actualización en tiempo real."""
        # Suscribirse al evento de reproducción para actualizar el historial
        self._event_bus.subscribe(
            EventType.PLAYBACK_STARTED,
            lambda data: wx.CallAfter(self._on_playback_started, data),
            weak=False
        )
        # También actualizar cuando se agregue/quite de favoritos para reflejar cambios
        self._event_bus.subscribe(
            EventType.FAVORITE_ADDED,
            lambda data: wx.CallAfter(self._on_favorites_changed),
            weak=False
        )
        self._event_bus.subscribe(
            EventType.FAVORITE_REMOVED,
            lambda data: wx.CallAfter(self._on_favorites_changed),
            weak=False
        )
    
    def _on_playback_started(self, station) -> None:
        """Maneja el evento de inicio de reproducción para actualizar historial."""
        # Agregar al historial si se emitió una Station
        if station:
            self._db.add_to_history(station)
            # Recargar la lista para mostrar la nueva entrada
            self._load_data()
    
    def _on_favorites_changed(self) -> None:
        """Maneja cambios en favoritos (no necesita recargar, pero mantiene consistencia)."""
        # El historial no cambia cuando cambian los favoritos, pero el menú contextual sí
        pass
    
    def _init_ui(self) -> None:
        """Inicializa la interfaz."""
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Etiqueta
        # Translators: Etiqueta del historial
        lbl = wx.StaticText(self, label=_("Historial de reproducción:"))
        main_sizer.Add(lbl, 0, wx.ALL, 5)
        
        # Lista
        self.lst_history = wx.ListBox(self, style=wx.LB_SINGLE)
        main_sizer.Add(self.lst_history, 1, wx.EXPAND | wx.ALL, 5)
        
        self.SetSizer(main_sizer)
        
        # Eventos
        self.lst_history.Bind(wx.EVT_KEY_UP, self._on_list_key)
        self.lst_history.Bind(wx.EVT_LISTBOX_DCLICK, self._on_double_click)
        self.lst_history.Bind(wx.EVT_CONTEXT_MENU, self._on_context_menu)
    
    def _load_data(self) -> None:
        """Carga el historial."""
        self._history = self._db.get_history(limit=100)
        self._update_list()
    
    def _update_list(self) -> None:
        """Actualiza la lista."""
        # Guardar selección actual
        current_selection = self.lst_history.GetSelection()
        
        self.lst_history.Clear()
        
        if not self._history:
            # Translators: Sin historial
            self.lst_history.Append(_("Sin historial."))
        else:
            for item in self._history:
                date_str = item.played_at.strftime("%d/%m/%Y %H:%M") if item.played_at else ""
                self.lst_history.Append(f"{item.station_name} - {date_str}")
        
        # Restaurar selección o seleccionar primer elemento
        if self.lst_history.GetCount() > 0:
            if current_selection != wx.NOT_FOUND and current_selection < self.lst_history.GetCount():
                self.lst_history.SetSelection(current_selection)
            else:
                self.lst_history.SetSelection(0)
    
    def _on_list_key(self, event: wx.KeyEvent) -> None:
        """Maneja las teclas."""
        key_code = event.GetKeyCode()
        if key_code in (wx.WXK_SPACE, wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._play_selected()
            return
        elif key_code == wx.WXK_F1:
            self._announce_list_position(self.lst_history)
            return
        event.Skip()
    
    def _on_double_click(self, event) -> None:
        """Maneja el doble clic."""
        self._play_selected()
    
    def _play_selected(self) -> None:
        """Reproduce desde el historial."""
        idx = self.lst_history.GetSelection()
        if idx == wx.NOT_FOUND or not self._history:
            return
        
        if self.lst_history.GetString(idx) == _("Sin historial."):
            return
        
        if idx >= len(self._history):
            return
        
        item = self._history[idx]
        station = Station(
            name=item.station_name,
            url=item.station_url,
            stationuuid=item.station_uuid
        )
        self._play_station(station)
    
    def _on_context_menu(self, event) -> None:
        """Muestra el menú contextual."""
        idx = self.lst_history.GetSelection()
        if idx == wx.NOT_FOUND or not self._history:
            return
        
        if self.lst_history.GetString(idx) == _("Sin historial."):
            return
        
        if idx >= len(self._history):
            return
        
        item = self._history[idx]
        menu = wx.Menu()
        
        item_play = menu.Append(wx.ID_ANY, _("&Reproducir"))
        self.Bind(wx.EVT_MENU, lambda e: self._play_selected(), item_play)
        
        # Verificar si ya está en favoritos para mostrar la opción adecuada
        if self._db.favorite_exists(item.station_url):
            # Translators: Elemento de menú para quitar de favoritos
            item_fav = menu.Append(wx.ID_ANY, _("&Quitar de favoritos"))
            self.Bind(wx.EVT_MENU, lambda e: self._remove_from_favorites(), item_fav)
        else:
            # Translators: Elemento de menú para agregar a favoritos
            item_fav = menu.Append(wx.ID_ANY, _("&Agregar a favoritos"))
            self.Bind(wx.EVT_MENU, lambda e: self._add_to_favorites(), item_fav)
        
        menu.AppendSeparator()
        
        # Translators: Elemento de menú para ver información
        item_info = menu.Append(wx.ID_ANY, _("&Información de la emisora"))
        self.Bind(wx.EVT_MENU, lambda e: self._show_station_info(), item_info)
        
        self.PopupMenu(menu)
        menu.Destroy()
    
    def _add_to_favorites(self) -> None:
        """Añade a favoritos desde el historial."""
        idx = self.lst_history.GetSelection()
        if idx >= len(self._history):
            return
        
        item = self._history[idx]
        
        if self._db.favorite_exists(item.station_url):
            show_info(_("Esta emisora ya está en favoritos."))
            return
        
        favorite = Favorite(
            name=item.station_name,
            url=item.station_url,
            station_uuid=item.station_uuid
        )
        self._db.add_favorite(favorite)
        self._event_bus.emit(EventType.FAVORITE_ADDED, favorite)
        
        wx.adv.NotificationMessage(
            title=_("Favorito añadido"),
            message=_("Se añadió {} a favoritos.").format(item.station_name)
        ).Show(timeout=5)
    
    def _remove_from_favorites(self) -> None:
        """Quita la emisora del historial de favoritos."""
        idx = self.lst_history.GetSelection()
        if idx >= len(self._history):
            return
        
        item = self._history[idx]
        
        # Buscar el favorito por URL
        favorites = self._db.get_favorites()
        favorite = next((f for f in favorites if f.url == item.station_url), None)
        
        if favorite:
            self._db.delete_favorite(favorite.id)
            self._event_bus.emit(EventType.FAVORITE_REMOVED, favorite)
            
            # Notificación
            wx.adv.NotificationMessage(
                # Translators: Título de notificación
                title=_("Favorito eliminado"),
                # Translators: Mensaje de notificación
                message=_("Se eliminó {} de favoritos.").format(item.station_name)
            ).Show(timeout=5)
    
    def _show_station_info(self) -> None:
        """Muestra información de la emisora del historial."""
        idx = self.lst_history.GetSelection()
        if idx >= len(self._history):
            return
        
        item = self._history[idx]
        station = Station(
            name=item.station_name,
            url=item.station_url,
            stationuuid=item.station_uuid
        )
        dlg = StationInfoDialog(self, station=station, api=self._api)
        dlg.ShowModal()
        dlg.Destroy()
    
    def focus_list(self) -> None:
        """Enfoca la lista."""
        self.lst_history.SetFocus()
    
    def refresh(self) -> None:
        """Refresca los datos."""
        self._load_data()


class SettingsPanel(wx.Panel):
    """
    Panel de configuración (para usar en plugin settings).
    """
    pass
