# -*- coding: utf-8 -*-
# Copyright (C) 2025 Héctor J. Benítez Corredera <xebolax@gmail.com>
# This file is covered by the GNU General Public License.

"""
Módulo UI de zRadioModern.

Contiene todos los componentes de la interfaz gráfica de usuario.
"""

from .main_window import MainWindow
from .dialogs import (
    show_error,
    show_info,
    show_confirm,
    StationEditDialog,
    CategoryEditDialog,
    ExportImportDialog
)
from .panels import (
    GeneralPanel,
    FavoritesPanel,
    SearchPanel,
    HistoryPanel,
    SettingsPanel
)

__all__ = [
    "MainWindow",
    "show_error",
    "show_info",
    "show_confirm",
    "StationEditDialog",
    "CategoryEditDialog",
    "ExportImportDialog",
    "GeneralPanel",
    "FavoritesPanel",
    "SearchPanel",
    "HistoryPanel",
    "SettingsPanel",
]
