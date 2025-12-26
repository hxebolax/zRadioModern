# -*- coding: utf-8 -*-
# Copyright (C) 2025 Héctor J. Benítez Corredera <xebolax@gmail.com>
# This file is covered by the GNU General Public License.

"""
Diálogos de zRadioModern.

Contiene funciones de ayuda y clases de diálogo para
la interfaz de usuario.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Tuple

import wx
import addonHandler

from datetime import datetime, timedelta

if TYPE_CHECKING:
    from ..zr_core.config import ConfigManager
    from ..zr_core.models import Station, Favorite, Category
    from ..zr_core.api_client import RadioBrowserAPI

# Para traducción
addonHandler.initTranslation()


def show_error(message: str, title: str = None) -> None:
    """
    Muestra un diálogo de error.
    
    Args:
        message: Mensaje de error.
        title: Título del diálogo.
    """
    if title is None:
        # Translators: Título por defecto para diálogos de error
        title = _("Error")
    
    dlg = wx.MessageDialog(
        None,
        message,
        title,
        wx.OK | wx.ICON_ERROR
    )
    # Translators: Texto del botón Aceptar
    dlg.SetOKLabel(_("&Aceptar"))
    dlg.ShowModal()
    dlg.Destroy()


def show_info(message: str, title: str = None) -> None:
    """
    Muestra un diálogo informativo.
    
    Args:
        message: Mensaje informativo.
        title: Título del diálogo.
    """
    if title is None:
        # Translators: Título por defecto para diálogos informativos
        title = _("Información")
    
    dlg = wx.MessageDialog(
        None,
        message,
        title,
        wx.OK | wx.ICON_INFORMATION
    )
    # Translators: Texto del botón Aceptar
    dlg.SetOKLabel(_("&Aceptar"))
    dlg.ShowModal()
    dlg.Destroy()


def show_confirm(message: str, title: str = None) -> bool:
    """
    Muestra un diálogo de confirmación.
    
    Args:
        message: Mensaje de confirmación.
        title: Título del diálogo.
        
    Returns:
        True si el usuario confirmó.
    """
    if title is None:
        # Translators: Título por defecto para diálogos de confirmación
        title = _("Confirmar")
    
    dlg = wx.MessageDialog(
        None,
        message,
        title,
        wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION
    )
    # Translators: Texto del botón Sí
    dlg.SetYesNoLabels(_("&Sí"), _("&No"))
    result = dlg.ShowModal() == wx.ID_YES
    dlg.Destroy()
    return result


class StationEditDialog(wx.Dialog):
    """
    Diálogo para editar o crear una emisora.
    """
    
    def __init__(
        self,
        parent: wx.Window,
        station: Optional["Favorite"] = None,
        title: str = None
    ):
        """
        Inicializa el diálogo.
        
        Args:
            parent: Ventana padre.
            station: Emisora a editar (None para nueva).
            title: Título del diálogo.
        """
        if title is None:
            if station is None:
                # Translators: Título del diálogo de nueva emisora
                title = _("Nueva emisora")
            else:
                # Translators: Título del diálogo de editar emisora
                title = _("Editar emisora")
        
        super().__init__(
            parent,
            id=wx.ID_ANY,
            title=title,
            size=(500, 250),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        
        self._station = station
        self._result = None
        
        self._init_ui()
        self._load_data()
    
    def _init_ui(self) -> None:
        """Inicializa la interfaz."""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Campo de nombre
        # Translators: Etiqueta del campo de nombre
        lbl_name = wx.StaticText(panel, label=_("Nombre de la emisora:"))
        main_sizer.Add(lbl_name, 0, wx.ALL | wx.EXPAND, 5)
        
        self.txt_name = wx.TextCtrl(panel)
        main_sizer.Add(self.txt_name, 0, wx.ALL | wx.EXPAND, 5)
        
        # Campo de URL
        # Translators: Etiqueta del campo de URL
        lbl_url = wx.StaticText(panel, label=_("URL de la emisora:"))
        main_sizer.Add(lbl_url, 0, wx.ALL | wx.EXPAND, 5)
        
        self.txt_url = wx.TextCtrl(panel)
        main_sizer.Add(self.txt_url, 0, wx.ALL | wx.EXPAND, 5)
        
        # Campo de notas
        # Translators: Etiqueta del campo de notas
        lbl_notes = wx.StaticText(panel, label=_("Notas (opcional):"))
        main_sizer.Add(lbl_notes, 0, wx.ALL | wx.EXPAND, 5)
        
        self.txt_notes = wx.TextCtrl(panel, style=wx.TE_MULTILINE)
        main_sizer.Add(self.txt_notes, 1, wx.ALL | wx.EXPAND, 5)
        
        # Botones
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Translators: Botón Aceptar
        self.btn_ok = wx.Button(panel, wx.ID_OK, _("&Aceptar"))
        btn_sizer.Add(self.btn_ok, 1, wx.ALL, 5)
        
        # Translators: Botón Cancelar
        self.btn_cancel = wx.Button(panel, wx.ID_CANCEL, _("&Cancelar"))
        btn_sizer.Add(self.btn_cancel, 1, wx.ALL, 5)
        
        main_sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER)
        
        panel.SetSizer(main_sizer)
        
        # Eventos
        self.btn_ok.Bind(wx.EVT_BUTTON, self._on_ok)
        self.btn_cancel.Bind(wx.EVT_BUTTON, self._on_cancel)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)
    
    def _load_data(self) -> None:
        """Carga los datos de la emisora."""
        if self._station is not None:
            self.txt_name.SetValue(self._station.name)
            self.txt_url.SetValue(self._station.url)
            self.txt_notes.SetValue(self._station.notes or "")
    
    def _on_ok(self, event: wx.CommandEvent) -> None:
        """Maneja el botón Aceptar."""
        name = self.txt_name.GetValue().strip()
        url = self.txt_url.GetValue().strip()
        notes = self.txt_notes.GetValue().strip()
        
        if not name:
            show_error(
                # Translators: Mensaje de error
                _("El nombre de la emisora no puede estar vacío."),
                _("Error")
            )
            self.txt_name.SetFocus()
            return
        
        if not url:
            show_error(
                # Translators: Mensaje de error
                _("La URL de la emisora no puede estar vacía."),
                _("Error")
            )
            self.txt_url.SetFocus()
            return
        
        self._result = {
            "name": name,
            "url": url,
            "notes": notes
        }
        
        self.EndModal(wx.ID_OK)
    
    def _on_cancel(self, event: wx.CommandEvent) -> None:
        """Maneja el botón Cancelar."""
        self.EndModal(wx.ID_CANCEL)
    
    def _on_key(self, event: wx.KeyEvent) -> None:
        """Maneja las teclas."""
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self._on_cancel(None)
        else:
            event.Skip()
    
    def get_result(self) -> Optional[dict]:
        """Obtiene el resultado del diálogo."""
        return self._result


class StationInfoDialog(wx.Dialog):
    """
    Diálogo para mostrar información detallada de una emisora.
    """
    
    def __init__(
        self,
        parent: wx.Window,
        station: "Station" = None,
        favorite: "Favorite" = None,
        api: "RadioBrowserAPI" = None,
        title: str = None
    ):
        """
        Inicializa el diálogo.
        
        Args:
            parent: Ventana padre.
            station: Emisora a mostrar información.
            favorite: Favorito para mostrar información adicional.
            api: Cliente de la API para obtener detalles faltantes.
            title: Título del diálogo.
        """
        if title is None:
            # Translators: Título del diálogo de información de emisora
            title = _("Información de la emisora")
        
        super().__init__(
            parent,
            id=wx.ID_ANY,
            title=title,
            size=(550, 450),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        
        self._station = station
        self._favorite = favorite
        self._api = api
        
        self._init_ui()
    
    def _init_ui(self) -> None:
        """Inicializa la interfaz."""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # TextCtrl de solo lectura con toda la información
        # Translators: Etiqueta del campo de información
        lbl_info = wx.StaticText(panel, label=_("Información de la emisora:"))
        main_sizer.Add(lbl_info, 0, wx.ALL | wx.EXPAND, 5)
        
        self.txt_info = wx.TextCtrl(
            panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_DONTWRAP
        )
        self.txt_info.SetName(_("Información de la emisora"))
        main_sizer.Add(self.txt_info, 1, wx.ALL | wx.EXPAND, 5)
        
        # Cargar información
        self._load_info()
        
        # Botón cerrar
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Translators: Botón Cerrar
        btn_close = wx.Button(panel, wx.ID_CANCEL, _("&Cerrar"))
        btn_sizer.Add(btn_close, 1, wx.ALL, 5)
        
        main_sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER)
        
        panel.SetSizer(main_sizer)
        
        # Eventos
        btn_close.Bind(wx.EVT_BUTTON, self._on_close)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)
        
        # Enfocar el TextCtrl
        self.txt_info.SetFocus()
    
    def _load_info(self) -> None:
        """Carga la información de la emisora."""
        # Si tenemos el API y falta información (ej: viene de favoritos local), intentar obtenerla
        if self._api and self._station and self._station.stationuuid:
            # Si faltan campos típicos de la API, buscamos
            if not hasattr(self._station, 'country') or not self._station.country:
                try:
                    results = self._api.get_stations_by_uuid(self._station.stationuuid)
                    if results:
                        self._station = results[0]
                except Exception:
                    pass

        lines = []
        
        if self._station:
            station = self._station
            
            # === Información básica ===
            # Translators: Sección de información básica
            lines.append(_("=== Información básica ==="))
            
            # Nombre
            # Translators: Etiqueta de información
            lines.append(_("Nombre: {}").format(station.name or _("No disponible")))
            
            # URL
            # Translators: Etiqueta de información
            lines.append(_("URL: {}").format(station.url or _("No disponible")))
            
            # UUID de la estación
            if hasattr(station, 'stationuuid') and station.stationuuid:
                # Translators: Etiqueta de información
                lines.append(_("UUID: {}").format(station.stationuuid))
            
            # === Ubicación ===
            lines.append("")
            # Translators: Sección de ubicación
            lines.append(_("=== Ubicación ==="))
            
            # País
            if hasattr(station, 'country') and station.country:
                # Translators: Etiqueta de información
                lines.append(_("País: {}").format(station.country))
            
            # Código de país
            if hasattr(station, 'countrycode') and station.countrycode:
                # Translators: Etiqueta de información
                lines.append(_("Código de país: {}").format(station.countrycode))
            
            # Estado/provincia
            if hasattr(station, 'state') and station.state:
                # Translators: Etiqueta de información
                lines.append(_("Estado/Provincia: {}").format(station.state))
            
            # Coordenadas geográficas
            if hasattr(station, 'geo_lat') and hasattr(station, 'geo_long'):
                if station.geo_lat != 0.0 or station.geo_long != 0.0:
                    # Translators: Etiqueta de información
                    lines.append(_("Coordenadas: {}, {}").format(station.geo_lat, station.geo_long))
            
            # === Idioma y contenido ===
            lines.append("")
            # Translators: Sección de idioma y contenido
            lines.append(_("=== Idioma y contenido ==="))
            
            # Idioma
            if hasattr(station, 'language') and station.language:
                # Translators: Etiqueta de información
                lines.append(_("Idioma: {}").format(station.language))
            
            # Códigos de idioma
            if hasattr(station, 'languagecodes') and station.languagecodes:
                # Translators: Etiqueta de información
                lines.append(_("Códigos de idioma: {}").format(station.languagecodes))
            
            # Etiquetas/géneros
            if hasattr(station, 'tags') and station.tags:
                # Translators: Etiqueta de información
                lines.append(_("Etiquetas: {}").format(station.tags))
            
            # === Información técnica ===
            lines.append("")
            # Translators: Sección de información técnica
            lines.append(_("=== Información técnica ==="))
            
            # Codec
            if hasattr(station, 'codec') and station.codec:
                # Translators: Etiqueta de información
                lines.append(_("Codec: {}").format(station.codec))
            
            # Bitrate
            if hasattr(station, 'bitrate') and station.bitrate and station.bitrate > 0:
                # Translators: Etiqueta de información
                lines.append(_("Bitrate: {} kbps").format(station.bitrate))
            
            # HLS
            if hasattr(station, 'hls') and station.hls:
                # Translators: Etiqueta de información
                lines.append(_("HLS (HTTP Live Streaming): {}").format(_("Sí") if station.hls else _("No")))
            
            # Error SSL
            if hasattr(station, 'ssl_error') and station.ssl_error:
                # Translators: Etiqueta de información
                lines.append(_("Error SSL: {}").format(_("Sí") if station.ssl_error else _("No")))
            
            # Estado de verificación
            if hasattr(station, 'lastcheckok'):
                status = _("Funcionando") if station.lastcheckok else _("No disponible")
                # Translators: Etiqueta de información
                lines.append(_("Estado: {}").format(status))
            
            # === Estadísticas ===
            lines.append("")
            # Translators: Sección de estadísticas
            lines.append(_("=== Estadísticas ==="))
            
            # Votos
            if hasattr(station, 'votes') and station.votes:
                # Translators: Etiqueta de información
                lines.append(_("Votos: {}").format(station.votes))
            
            # Clics totales
            if hasattr(station, 'clickcount') and station.clickcount:
                # Translators: Etiqueta de información
                lines.append(_("Reproducciones totales: {}").format(station.clickcount))
            
            # Tendencia de clics
            if hasattr(station, 'clicktrend') and station.clicktrend:
                trend = _("Subiendo") if station.clicktrend > 0 else (_("Bajando") if station.clicktrend < 0 else _("Estable"))
                # Translators: Etiqueta de información
                lines.append(_("Tendencia: {} ({})").format(trend, station.clicktrend))
            
            # === Fechas y verificación ===
            lines.append("")
            # Translators: Sección de fechas
            lines.append(_("=== Fechas ==="))
            
            # Última modificación
            if hasattr(station, 'lastchangetime') and station.lastchangetime:
                # Translators: Etiqueta de información
                lines.append(_("Última modificación: {}").format(station.lastchangetime))
            
            # Última verificación
            if hasattr(station, 'lastchecktime') and station.lastchecktime:
                # Translators: Etiqueta de información
                lines.append(_("Última verificación: {}").format(station.lastchecktime))
            
            # Última verificación exitosa
            if hasattr(station, 'lastcheckoktime') and station.lastcheckoktime:
                # Translators: Etiqueta de información
                lines.append(_("Última verificación OK: {}").format(station.lastcheckoktime))
            
            # === Enlaces ===
            lines.append("")
            # Translators: Sección de enlaces
            lines.append(_("=== Enlaces ==="))
            
            # Favicon
            if hasattr(station, 'favicon') and station.favicon:
                # Translators: Etiqueta de información
                lines.append(_("Icono: {}").format(station.favicon))
            
            # Página web
            if hasattr(station, 'homepage') and station.homepage:
                # Translators: Etiqueta de información
                lines.append(_("Página web: {}").format(station.homepage))
        
        # Información adicional de favorito
        if self._favorite:
            fav = self._favorite
            lines.append("")
            # Translators: Separador de información de favorito
            lines.append(_("--- Información de favorito ---"))
            
            # Categoría
            if fav.category_id:
                # Translators: Etiqueta de información
                lines.append(_("Categoría ID: {}").format(fav.category_id))
            
            # Contador de reproducciones
            if fav.play_count > 0:
                # Translators: Etiqueta de información
                lines.append(_("Veces reproducida: {}").format(fav.play_count))
            
            # Última reproducción
            if fav.last_played:
                # Translators: Etiqueta de información
                lines.append(_("Última reproducción: {}").format(
                    fav.last_played.strftime("%d/%m/%Y %H:%M")
                ))
            
            # Fecha de añadido
            if fav.created_at:
                # Translators: Etiqueta de información
                lines.append(_("Añadida a favoritos: {}").format(
                    fav.created_at.strftime("%d/%m/%Y %H:%M")
                ))
            
            # Notas
            if fav.notes:
                # Translators: Etiqueta de información
                lines.append(_("Notas: {}").format(fav.notes))
        
        # Si no hay información
        if not lines:
            # Translators: Mensaje cuando no hay información
            lines.append(_("No hay información disponible para esta emisora."))
        
        self.txt_info.SetValue("\n".join(lines))
    
    def _on_close(self, event: wx.CommandEvent) -> None:
        """Maneja el botón Cerrar."""
        self.EndModal(wx.ID_CANCEL)
    
    def _on_key(self, event: wx.KeyEvent) -> None:
        """Maneja las teclas."""
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self._on_close(None)
        else:
            event.Skip()


class CategoryEditDialog(wx.Dialog):
    """
    Diálogo para editar o crear una categoría.
    """
    
    def __init__(
        self,
        parent: wx.Window,
        category: Optional["Category"] = None
    ):
        """
        Inicializa el diálogo.
        
        Args:
            parent: Ventana padre.
            category: Categoría a editar (None para nueva).
        """
        if category is None:
            # Translators: Título del diálogo de nueva categoría
            title = _("Nueva categoría")
        else:
            # Translators: Título del diálogo de editar categoría
            title = _("Editar categoría")
        
        super().__init__(
            parent,
            id=wx.ID_ANY,
            title=title,
            size=(400, 200),
            style=wx.DEFAULT_DIALOG_STYLE
        )
        
        self._category = category
        self._result = None
        
        self._init_ui()
        self._load_data()
    
    def _init_ui(self) -> None:
        """Inicializa la interfaz."""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Campo de nombre
        # Translators: Etiqueta del campo de nombre
        lbl_name = wx.StaticText(panel, label=_("Nombre de la categoría:"))
        main_sizer.Add(lbl_name, 0, wx.ALL | wx.EXPAND, 5)
        
        self.txt_name = wx.TextCtrl(panel)
        main_sizer.Add(self.txt_name, 0, wx.ALL | wx.EXPAND, 5)
        
        # Campo de descripción
        # Translators: Etiqueta del campo de descripción
        lbl_desc = wx.StaticText(panel, label=_("Descripción (opcional):"))
        main_sizer.Add(lbl_desc, 0, wx.ALL | wx.EXPAND, 5)
        
        self.txt_description = wx.TextCtrl(panel)
        main_sizer.Add(self.txt_description, 0, wx.ALL | wx.EXPAND, 5)
        
        # Botones
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Translators: Botón Aceptar
        btn_ok = wx.Button(panel, wx.ID_OK, _("&Aceptar"))
        btn_sizer.Add(btn_ok, 1, wx.ALL, 5)
        
        # Translators: Botón Cancelar
        btn_cancel = wx.Button(panel, wx.ID_CANCEL, _("&Cancelar"))
        btn_sizer.Add(btn_cancel, 1, wx.ALL, 5)
        
        main_sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER)
        
        panel.SetSizer(main_sizer)
        
        # Eventos
        btn_ok.Bind(wx.EVT_BUTTON, self._on_ok)
        btn_cancel.Bind(wx.EVT_BUTTON, self._on_cancel)
    
    def _load_data(self) -> None:
        """Carga los datos de la categoría."""
        if self._category is not None:
            self.txt_name.SetValue(self._category.name)
            self.txt_description.SetValue(self._category.description or "")
    
    def _on_ok(self, event: wx.CommandEvent) -> None:
        """Maneja el botón Aceptar."""
        name = self.txt_name.GetValue().strip()
        description = self.txt_description.GetValue().strip()
        
        if not name:
            show_error(
                # Translators: Mensaje de error
                _("El nombre de la categoría no puede estar vacío."),
                _("Error")
            )
            self.txt_name.SetFocus()
            return
        
        self._result = {
            "name": name,
            "description": description
        }
        
        self.EndModal(wx.ID_OK)
    
    def _on_cancel(self, event: wx.CommandEvent) -> None:
        """Maneja el botón Cancelar."""
        self.EndModal(wx.ID_CANCEL)
    
    def get_result(self) -> Optional[dict]:
        """Obtiene el resultado del diálogo."""
        return self._result


class ExportImportDialog(wx.Dialog):
    """
    Diálogo para opciones de exportación/importación.
    """
    pass  # Implementar según necesidades


class SettingsDialog(wx.Dialog):
    """
    Diálogo de configuración de la aplicación.
    """
    
    def __init__(self, parent: wx.Window, config: "ConfigManager"):
        """
        Inicializa el diálogo de configuración.
        
        Args:
            parent: Ventana padre.
            config: Gestor de configuración.
        """
        # Translators: Título del diálogo de configuración
        super().__init__(
            parent,
            id=wx.ID_ANY,
            title=_("Configuración"),
            size=(500, 400),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        
        self._config = config
        self._init_ui()
        self._load_settings()
    
    def _init_ui(self) -> None:
        """Inicializa la interfaz."""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Notebook para categorías de configuración
        notebook = wx.Notebook(panel)
        
        # === Pestaña General ===
        page_general = wx.Panel(notebook)
        sizer_general = wx.BoxSizer(wx.VERTICAL)
        
        # Verificar Internet al inicio
        self.chk_check_internet = wx.CheckBox(
            page_general,
            # Translators: Opción de configuración
            label=_("Verificar conexión a Internet al iniciar")
        )
        sizer_general.Add(self.chk_check_internet, 0, wx.ALL, 5)
        
        # Recordar última emisora
        self.chk_remember_station = wx.CheckBox(
            page_general,
            # Translators: Opción de configuración
            label=_("Recordar última emisora reproducida")
        )
        sizer_general.Add(self.chk_remember_station, 0, wx.ALL, 5)
        
        # Verificar actualizaciones
        self.chk_check_updates = wx.CheckBox(
            page_general,
            # Translators: Opción de configuración
            label=_("Buscar actualizaciones automáticamente")
        )
        sizer_general.Add(self.chk_check_updates, 0, wx.ALL, 5)
        
        page_general.SetSizer(sizer_general)
        # Translators: Nombre de pestaña de configuración
        notebook.AddPage(page_general, _("General"))
        
        # === Pestaña Caché ===
        page_cache = wx.Panel(notebook)
        sizer_cache = wx.BoxSizer(wx.VERTICAL)
        
        # Habilitar caché
        self.chk_cache_enabled = wx.CheckBox(
            page_cache,
            # Translators: Opción de configuración
            label=_("Habilitar caché de resultados")
        )
        sizer_cache.Add(self.chk_cache_enabled, 0, wx.ALL, 5)
        
        # Duración del caché
        cache_duration_sizer = wx.BoxSizer(wx.HORIZONTAL)
        # Translators: Etiqueta de configuración
        cache_duration_sizer.Add(
            wx.StaticText(page_cache, label=_("Duración del caché (días):")),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.ALL,
            5
        )
        self.spin_cache_days = wx.SpinCtrl(
            page_cache,
            min=1,
            max=30,
            initial=3
        )
        cache_duration_sizer.Add(self.spin_cache_days, 0, wx.ALL, 5)
        sizer_cache.Add(cache_duration_sizer, 0, wx.EXPAND)
        
        page_cache.SetSizer(sizer_cache)
        # Translators: Nombre de pestaña de configuración
        notebook.AddPage(page_cache, _("Caché"))
        
        # === Pestaña Grabaciones ===
        page_recording = wx.Panel(notebook)
        sizer_recording = wx.BoxSizer(wx.VERTICAL)
        
        # Directorio de grabaciones
        # Translators: Etiqueta de configuración
        lbl_recording_dir = wx.StaticText(
            page_recording,
            label=_("Directorio para guardar grabaciones:")
        )
        sizer_recording.Add(lbl_recording_dir, 0, wx.ALL, 5)
        
        recording_dir_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.txt_recording_dir = wx.TextCtrl(page_recording, style=wx.TE_READONLY)
        recording_dir_sizer.Add(self.txt_recording_dir, 1, wx.ALL | wx.EXPAND, 5)
        
        # Translators: Botón para examinar directorio
        self.btn_browse_recording = wx.Button(page_recording, label=_("E&xaminar..."))
        recording_dir_sizer.Add(self.btn_browse_recording, 0, wx.ALL, 5)
        
        sizer_recording.Add(recording_dir_sizer, 0, wx.EXPAND)
        
        # Nota sobre el directorio por defecto
        # Translators: Nota informativa
        lbl_recording_note = wx.StaticText(
            page_recording,
            label=_("Si no se especifica, se usará la carpeta Música del usuario.")
        )
        sizer_recording.Add(lbl_recording_note, 0, wx.ALL, 5)
        
        # Botón para limpiar directorio
        # Translators: Botón para usar directorio por defecto
        self.btn_default_recording = wx.Button(
            page_recording,
            label=_("&Usar directorio por defecto")
        )
        sizer_recording.Add(self.btn_default_recording, 0, wx.ALL, 5)
        
        page_recording.SetSizer(sizer_recording)
        # Translators: Nombre de pestaña de configuración
        notebook.AddPage(page_recording, _("Grabaciones"))
        
        # Eventos de grabación
        self.btn_browse_recording.Bind(wx.EVT_BUTTON, self._on_browse_recording)
        self.btn_default_recording.Bind(wx.EVT_BUTTON, self._on_default_recording)
        
        main_sizer.Add(notebook, 1, wx.EXPAND | wx.ALL, 5)
        
        # Botones
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Translators: Botón Guardar
        btn_save = wx.Button(panel, wx.ID_OK, _("&Guardar"))
        btn_sizer.Add(btn_save, 1, wx.ALL, 5)
        
        # Translators: Botón Cancelar
        btn_cancel = wx.Button(panel, wx.ID_CANCEL, _("&Cancelar"))
        btn_sizer.Add(btn_cancel, 1, wx.ALL, 5)
        
        # Translators: Botón Restablecer
        btn_reset = wx.Button(panel, wx.ID_ANY, _("&Restablecer"))
        btn_sizer.Add(btn_reset, 1, wx.ALL, 5)
        
        main_sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER)
        
        panel.SetSizer(main_sizer)
        
        # Eventos
        btn_save.Bind(wx.EVT_BUTTON, self._on_save)
        btn_cancel.Bind(wx.EVT_BUTTON, self._on_cancel)
        btn_reset.Bind(wx.EVT_BUTTON, self._on_reset)
    
    def _load_settings(self) -> None:
        """Carga la configuración actual."""
        self.chk_check_internet.SetValue(self._config.check_internet_on_start)
        self.chk_remember_station.SetValue(self._config.remember_last_station)
        self.chk_check_updates.SetValue(self._config.check_updates)
        self.chk_cache_enabled.SetValue(self._config.cache_enabled)
        self.spin_cache_days.SetValue(self._config.cache_duration_days)
        
        # Directorio de grabaciones
        if self._config.recording_directory:
            self.txt_recording_dir.SetValue(self._config.recording_directory)
        else:
            # Translators: Texto que indica directorio por defecto
            self.txt_recording_dir.SetValue(_("(Carpeta Música por defecto)"))
    
    def _on_save(self, event: wx.CommandEvent) -> None:
        """Guarda la configuración."""
        self._config.check_internet_on_start = self.chk_check_internet.GetValue()
        self._config.remember_last_station = self.chk_remember_station.GetValue()
        self._config.check_updates = self.chk_check_updates.GetValue()
        self._config.cache_enabled = self.chk_cache_enabled.GetValue()
        self._config.cache_duration_days = self.spin_cache_days.GetValue()
        
        # Guardar directorio de grabaciones (limpiar si es el valor por defecto)
        recording_dir = self.txt_recording_dir.GetValue()
        if recording_dir.startswith("("):
            self._config.recording_directory = ""
        else:
            self._config.recording_directory = recording_dir
        
        self._config.save()
        
        self.EndModal(wx.ID_OK)
    
    def _on_cancel(self, event: wx.CommandEvent) -> None:
        """Cancela los cambios."""
        self.EndModal(wx.ID_CANCEL)
    
    def _on_reset(self, event: wx.CommandEvent) -> None:
        """Restablece la configuración."""
        if show_confirm(
            # Translators: Mensaje de confirmación
            _("¿Está seguro de que desea restablecer toda la configuración?")
        ):
            self._config.reset()
            self._load_settings()
    
    def _on_browse_recording(self, event: wx.CommandEvent) -> None:
        """Maneja el botón de examinar directorio de grabaciones."""
        dlg = wx.DirDialog(
            self,
            # Translators: Título del diálogo de selección de directorio
            _("Seleccione el directorio para las grabaciones"),
            style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST
        )
        
        if dlg.ShowModal() == wx.ID_OK:
            self.txt_recording_dir.SetValue(dlg.GetPath())
        
        dlg.Destroy()
    
    def _on_default_recording(self, event: wx.CommandEvent) -> None:
        """Restablece el directorio de grabaciones al valor por defecto."""
        # Translators: Texto que indica directorio por defecto
        self.txt_recording_dir.SetValue(_("(Carpeta Música por defecto)"))


class ScheduleRecordingDialog(wx.Dialog):
    """
    Diálogo para programar una grabación.
    """
    
    def __init__(
        self,
        parent: wx.Window,
        station_name: str = "",
        station_url: str = "",
        config: "ConfigManager" = None
    ):
        """
        Inicializa el diálogo.
        
        Args:
            parent: Ventana padre.
            station_name: Nombre de la emisora a grabar.
            station_url: URL de la emisora.
            config: Gestor de configuración.
        """
        # Translators: Título del diálogo de programar grabación
        super().__init__(
            parent,
            id=wx.ID_ANY,
            title=_("Programar grabación"),
            size=(500, 450),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        
        self._station_name = station_name
        self._station_url = station_url
        self._config = config
        self._result = None
        
        self._init_ui()
    
    def _init_ui(self) -> None:
        """Inicializa la interfaz."""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        now = datetime.now()
        
        # Emisora
        # Translators: Etiqueta de emisora
        lbl_station = wx.StaticText(panel, label=_("Emisora a grabar:"))
        main_sizer.Add(lbl_station, 0, wx.ALL, 5)
        
        self.txt_station = wx.TextCtrl(panel)
        self.txt_station.SetValue(self._station_name)
        main_sizer.Add(self.txt_station, 0, wx.ALL | wx.EXPAND, 5)
        
        # URL de la emisora
        # Translators: Etiqueta de URL
        lbl_url = wx.StaticText(panel, label=_("URL de la emisora:"))
        main_sizer.Add(lbl_url, 0, wx.ALL, 5)
        
        self.txt_url = wx.TextCtrl(panel)
        self.txt_url.SetValue(self._station_url)
        main_sizer.Add(self.txt_url, 0, wx.ALL | wx.EXPAND, 5)
        
        # Fecha y hora de inicio
        # Translators: Etiqueta de fecha de inicio con formato
        lbl_start = wx.StaticText(panel, label=_("Inicio (formato DD/MM/AAAA HH:MM):"))
        main_sizer.Add(lbl_start, 0, wx.ALL, 5)
        
        self.txt_start = wx.TextCtrl(panel)
        self.txt_start.SetValue(now.strftime("%d/%m/%Y %H:%M"))
        main_sizer.Add(self.txt_start, 0, wx.ALL | wx.EXPAND, 5)
        
        # Fecha y hora de fin
        # Translators: Etiqueta de fecha de fin con formato
        lbl_end = wx.StaticText(panel, label=_("Fin (formato DD/MM/AAAA HH:MM):"))
        main_sizer.Add(lbl_end, 0, wx.ALL, 5)
        
        self.txt_end = wx.TextCtrl(panel)
        # Por defecto 1 hora después
        later = now + timedelta(hours=1)
        self.txt_end.SetValue(later.strftime("%d/%m/%Y %H:%M"))
        main_sizer.Add(self.txt_end, 0, wx.ALL | wx.EXPAND, 5)
        
        # Nombre del archivo
        # Translators: Etiqueta de nombre de archivo
        lbl_filename = wx.StaticText(panel, label=_("Nombre del archivo (sin extensión):"))
        main_sizer.Add(lbl_filename, 0, wx.ALL, 5)
        
        self.txt_filename = wx.TextCtrl(panel)
        # Generar nombre por defecto basado en la emisora y fecha
        import re
        default_name = f"{self._station_name}_{now.strftime('%Y%m%d_%H%M%S')}"
        default_name = re.sub(r'[<>:"/\\|?*]', '_', default_name)
        self.txt_filename.SetValue(default_name)
        main_sizer.Add(self.txt_filename, 0, wx.ALL | wx.EXPAND, 5)
        
        # Botones
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Translators: Botón Programar
        self.btn_ok = wx.Button(panel, wx.ID_OK, _("&Programar"))
        btn_sizer.Add(self.btn_ok, 1, wx.ALL, 5)
        
        # Translators: Botón Cancelar
        self.btn_cancel = wx.Button(panel, wx.ID_CANCEL, _("&Cancelar"))
        btn_sizer.Add(self.btn_cancel, 1, wx.ALL, 5)
        
        main_sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER)
        
        panel.SetSizer(main_sizer)
        
        # Eventos
        self.btn_ok.Bind(wx.EVT_BUTTON, self._on_ok)
        self.btn_cancel.Bind(wx.EVT_BUTTON, self._on_cancel)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)
    
    def _on_ok(self, event: wx.CommandEvent) -> None:
        """Maneja el botón Programar."""
        station_name = self.txt_station.GetValue().strip()
        station_url = self.txt_url.GetValue().strip()
        start_str = self.txt_start.GetValue().strip()
        end_str = self.txt_end.GetValue().strip()
        filename = self.txt_filename.GetValue().strip()
        
        if not station_name or not station_url:
            show_error(_("Debe especificar la emisora y su URL."), _("Error"))
            return
            
        try:
            start_time = datetime.strptime(start_str, "%d/%m/%Y %H:%M")
        except ValueError:
            show_error(
                _("Formato de fecha de inicio incorrecto.\nUse DD/MM/AAAA HH:MM (ej: 25/12/2024 18:30)"),
                _("Error")
            )
            self.txt_start.SetFocus()
            return
            
        try:
            end_time = datetime.strptime(end_str, "%d/%m/%Y %H:%M")
        except ValueError:
            show_error(
                _("Formato de fecha de fin incorrecto.\nUse DD/MM/AAAA HH:MM (ej: 25/12/2024 19:30)"),
                _("Error")
            )
            self.txt_end.SetFocus()
            return
            
        now = datetime.now()
        if start_time <= now:
            show_error(_("La fecha de inicio debe ser futura."), _("Error"))
            self.txt_start.SetFocus()
            return
            
        if start_time >= end_time:
            show_error(_("La hora de inicio debe ser anterior a la de fin."), _("Error"))
            self.txt_end.SetFocus()
            return
            
        if not filename:
            show_error(_("Especifique un nombre para el archivo."), _("Error"))
            self.txt_filename.SetFocus()
            return
            
        # Construir ruta del archivo
        import re
        safe_filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        
        if self._config:
            output_dir = self._config.recordings_dir
        else:
            from pathlib import Path
            output_dir = Path.home() / "Music"
        
        output_path = str(output_dir / f"{safe_filename}.mp3")
        
        self._result = {
            "station_name": station_name,
            "station_url": station_url,
            "start_time": start_time,
            "end_time": end_time,
            "output_path": output_path
        }
        
        self.EndModal(wx.ID_OK)
    
    def _on_cancel(self, event: wx.CommandEvent) -> None:
        """Maneja el botón Cancelar."""
        self.EndModal(wx.ID_CANCEL)
    
    def _on_key(self, event: wx.KeyEvent) -> None:
        """Maneja las teclas."""
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self._on_cancel(None)
        else:
            event.Skip()
    
    def get_result(self) -> Optional[dict]:
        """Obtiene el resultado del diálogo."""
        return self._result
