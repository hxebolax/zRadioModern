# -*- coding: utf-8 -*-
# Copyright (C) 2025 Héctor J. Benítez Corredera <xebolax@gmail.com>
# This file is covered by the GNU General Public License.

"""
Tareas de instalación para el complemento zRadioModern.
Ejecutadas automáticamente por NVDA durante la instalación/actualización.
"""

import os
import globalVars

def onInstall():
    """Se ejecuta durante la instalación del complemento."""
    # Crear directorio de datos si no existe
    data_dir = os.path.join(globalVars.appArgs.configPath, "zRadioModern")
    if not os.path.isdir(data_dir):
        try:
            os.makedirs(data_dir)
        except OSError:
            pass

