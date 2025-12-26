# -*- coding: utf-8 -*-
# Copyright (C) 2025 Héctor J. Benítez Corredera <xebolax@gmail.com>
# This file is covered by the GNU General Public License.

"""
Diccionarios de localización para zRadioModern.

Contiene mapeos de países, idiomas y otros términos
para diferentes idiomas de interfaz.
"""

from __future__ import annotations
from typing import Dict

# Mapeo de códigos de país a nombres en español
COUNTRIES_ES: Dict[str, str] = {
    "AF": "Afganistán",
    "AL": "Albania",
    "DE": "Alemania",
    "AD": "Andorra",
    "AO": "Angola",
    "AR": "Argentina",
    "AM": "Armenia",
    "AU": "Australia",
    "AT": "Austria",
    "AZ": "Azerbaiyán",
    "BE": "Bélgica",
    "BO": "Bolivia",
    "BA": "Bosnia y Herzegovina",
    "BR": "Brasil",
    "BG": "Bulgaria",
    "CA": "Canadá",
    "CL": "Chile",
    "CN": "China",
    "CO": "Colombia",
    "KR": "Corea del Sur",
    "CR": "Costa Rica",
    "HR": "Croacia",
    "CU": "Cuba",
    "DK": "Dinamarca",
    "EC": "Ecuador",
    "EG": "Egipto",
    "SV": "El Salvador",
    "AE": "Emiratos Árabes Unidos",
    "SK": "Eslovaquia",
    "SI": "Eslovenia",
    "ES": "España",
    "US": "Estados Unidos",
    "EE": "Estonia",
    "FI": "Finlandia",
    "FR": "Francia",
    "GR": "Grecia",
    "GT": "Guatemala",
    "HN": "Honduras",
    "HU": "Hungría",
    "IN": "India",
    "ID": "Indonesia",
    "IR": "Irán",
    "IQ": "Irak",
    "IE": "Irlanda",
    "IS": "Islandia",
    "IL": "Israel",
    "IT": "Italia",
    "JP": "Japón",
    "JO": "Jordania",
    "KZ": "Kazajistán",
    "KE": "Kenia",
    "LV": "Letonia",
    "LB": "Líbano",
    "LT": "Lituania",
    "LU": "Luxemburgo",
    "MK": "Macedonia del Norte",
    "MY": "Malasia",
    "MT": "Malta",
    "MA": "Marruecos",
    "MX": "México",
    "MD": "Moldavia",
    "MC": "Mónaco",
    "ME": "Montenegro",
    "NI": "Nicaragua",
    "NG": "Nigeria",
    "NO": "Noruega",
    "NZ": "Nueva Zelanda",
    "NL": "Países Bajos",
    "PA": "Panamá",
    "PY": "Paraguay",
    "PE": "Perú",
    "PL": "Polonia",
    "PT": "Portugal",
    "PR": "Puerto Rico",
    "GB": "Reino Unido",
    "CZ": "República Checa",
    "DO": "República Dominicana",
    "RO": "Rumania",
    "RU": "Rusia",
    "RS": "Serbia",
    "SG": "Singapur",
    "ZA": "Sudáfrica",
    "SE": "Suecia",
    "CH": "Suiza",
    "TH": "Tailandia",
    "TW": "Taiwán",
    "TR": "Turquía",
    "UA": "Ucrania",
    "UY": "Uruguay",
    "VE": "Venezuela",
    "VN": "Vietnam",
}

# Mapeo inverso: nombre español a código
COUNTRIES_ES_REVERSE: Dict[str, str] = {v: k for k, v in COUNTRIES_ES.items()}

# Mapeo de idiomas a nombres en español
LANGUAGES_ES: Dict[str, str] = {
    "spanish": "Español",
    "english": "Inglés",
    "french": "Francés",
    "german": "Alemán",
    "italian": "Italiano",
    "portuguese": "Portugués",
    "russian": "Ruso",
    "chinese": "Chino",
    "japanese": "Japonés",
    "korean": "Coreano",
    "arabic": "Árabe",
    "dutch": "Neerlandés",
    "polish": "Polaco",
    "turkish": "Turco",
    "greek": "Griego",
    "swedish": "Sueco",
    "norwegian": "Noruego",
    "danish": "Danés",
    "finnish": "Finlandés",
    "czech": "Checo",
    "hungarian": "Húngaro",
    "romanian": "Rumano",
    "ukrainian": "Ucraniano",
    "bulgarian": "Búlgaro",
    "indonesian": "Indonesio",
    "vietnamese": "Vietnamita",
    "thai": "Tailandés",
    "hindi": "Hindi",
    "catalan": "Catalán",
    "basque": "Euskera",
    "galician": "Gallego",
}

# Mapeo inverso: nombre español a idioma
LANGUAGES_ES_REVERSE: Dict[str, str] = {v: k for k, v in LANGUAGES_ES.items()}


def get_country_name(code: str, language: str = "es") -> str:
    """
    Obtiene el nombre localizado de un país.
    
    Args:
        code: Código ISO del país.
        language: Código del idioma de salida.
        
    Returns:
        Nombre del país localizado.
    """
    if language == "es":
        return COUNTRIES_ES.get(code.upper(), code)
    return code


def get_language_name(lang: str, ui_language: str = "es") -> str:
    """
    Obtiene el nombre localizado de un idioma.
    
    Args:
        lang: Nombre del idioma en inglés.
        ui_language: Idioma de la interfaz.
        
    Returns:
        Nombre del idioma localizado.
    """
    if ui_language == "es":
        return LANGUAGES_ES.get(lang.lower(), lang)
    return lang


def get_country_code(name: str, language: str = "es") -> str:
    """
    Obtiene el código ISO de un país desde su nombre.
    
    Args:
        name: Nombre del país.
        language: Idioma del nombre.
        
    Returns:
        Código ISO del país.
    """
    if language == "es":
        return COUNTRIES_ES_REVERSE.get(name, "")
    return ""
