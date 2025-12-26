# -*- coding: utf-8 -*-
# Copyright (C) 2025 Héctor J. Benítez Corredera <xebolax@gmail.com>
# This file is covered by the GNU General Public License.

"""
Wrapper para reproducción de audio usando VLC.

Este módulo proporciona una interfaz para reproducir streams de radio
usando la biblioteca python-vlc. También soporta grabación de streams
a archivos MP3.
"""

from __future__ import annotations
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Optional, Callable
from datetime import datetime

from logHandler import log

# Configurar rutas para VLC ANTES de importar vlc
_addon_path = Path(__file__).parent.parent
_lib_path = _addon_path / "lib"

# Configurar variables de entorno para VLC
os.environ['PYTHON_VLC_MODULE_PATH'] = str(_lib_path)
os.environ['PYTHON_VLC_LIB_PATH'] = str(_lib_path / "libvlc.dll")

# Añadir lib al PATH de Windows para que encuentre las DLLs
if str(_lib_path) not in os.environ.get("PATH", ""):
    os.environ["PATH"] = str(_lib_path) + os.pathsep + os.environ.get("PATH", "")

# Ahora importar VLC
try:
    if str(_lib_path) not in sys.path:
        sys.path.insert(0, str(_lib_path))
    import vlc
    VLC_AVAILABLE = True
    log.debug(f"VLC cargado correctamente desde {_lib_path}")
except Exception as e:
    VLC_AVAILABLE = False
    vlc = None
    log.error(f"Error cargando VLC: {e}")


class VLCPlayer:
    """
    Reproductor usando la biblioteca VLC.
    
    Proporciona reproducción de streams y grabación a MP3.
    """
    
    def __init__(
        self,
        video: bool = False,
        **kwargs
    ):
        """
        Inicializa el reproductor VLC.
        
        Args:
            video: Si debe habilitar video (False para solo audio).
            **kwargs: Argumentos adicionales ignorados para compatibilidad.
        """
        if not VLC_AVAILABLE:
            raise ImportError("VLC no está disponible")
        
        # Argumentos para la instancia VLC
        vlc_args = [
            '--no-video' if not video else '',
            '--quiet',
            '--no-xlib',
            '--network-caching=3000',
            '--aout=any'
        ]
        vlc_args = [arg for arg in vlc_args if arg]
        
        # Instancia principal para reproducción
        self._instance = vlc.Instance(vlc_args)
        self._player = self._instance.media_player_new()
        
        # Instancia secundaria permanente para grabaciones
        # Se inicializa aquí una sola vez para evitar tirones al empezar a grabar
        record_args = [
            '--no-video',
            '--quiet',
            '--no-xlib',
            '--aout=none',
            '--no-audio'
        ]
        try:
            self._record_instance = vlc.Instance(record_args)
        except Exception:
            self._record_instance = self._instance
            log.warning("No se pudo crear instancia de grabación independiente, usando la principal")
        
        self._volume = 100
        self._muted = False
        self._playing = False
        self._current_url = ""
        self._current_media = None
        self._lock = threading.Lock()
        
        # Estado de grabación
        self._recording = False
        self._record_player = None
        self._record_media = None
        self._record_file = ""
        
        log.debug("VLCPlayer inicializado con instancias duales")
    
    def play(self, url: str) -> None:
        """
        Reproduce una URL.
        
        Args:
            url: URL del stream a reproducir.
        """
        with self._lock:
            self.stop()
            
            try:
                self._current_media = self._instance.media_new(url)
                
                # Añadir opciones para mejorar la estabilidad y evitar conflictos con la grabación
                # User-Agent diferente al del grabador y mayor caché
                self._current_media.add_option(":http-user-agent=zRadio/1.0 (NVDA Addon)")
                self._current_media.add_option(":network-caching=5000")
                
                self._player.set_media(self._current_media)
                self._player.audio_set_volume(self._volume if not self._muted else 0)
                self._player.play()
                
                self._current_url = url
                self._playing = True
                log.debug(f"VLC reproduciendo: {url}")
                
            except Exception as e:
                log.error(f"Error VLC play: {e}")
                self._playing = False
                raise
    
    def stop(self) -> None:
        """Detiene la reproducción."""
        try:
            if self._player is not None:
                self._player.stop()
            self._playing = False
            self._current_url = ""
            if self._current_media is not None:
                self._current_media.release()
                self._current_media = None
        except Exception as e:
            log.debug(f"Error VLC stop: {e}")
    
    def command(self, name: str, *args) -> Any:
        """Ejecuta un comando."""
        if name == "stop":
            self.stop()
        return None
    
    @property
    def volume(self) -> int:
        """Obtiene el volumen actual."""
        return self._volume
    
    @volume.setter
    def volume(self, value: int) -> None:
        """Establece el volumen (0-100)."""
        self._volume = max(0, min(100, value))
        if self._player is not None and not self._muted:
            try:
                self._player.audio_set_volume(self._volume)
            except Exception:
                pass
    
    @property
    def mute(self) -> bool:
        """Obtiene el estado de silencio."""
        return self._muted
    
    @mute.setter
    def mute(self, value: bool) -> None:
        """Establece el estado de silencio."""
        self._muted = value
        if self._player is not None:
            try:
                self._player.audio_set_volume(0 if value else self._volume)
            except Exception:
                pass
    
    @property
    def pause(self) -> bool:
        """Obtiene el estado de pausa."""
        if self._player is not None:
            try:
                return not self._player.is_playing()
            except Exception:
                pass
        return False
    
    @pause.setter
    def pause(self, value: bool) -> None:
        """Establece el estado de pausa."""
        if self._player is not None:
            try:
                if value:
                    self._player.pause()
                else:
                    self._player.play()
            except Exception:
                pass
    
    @property
    def media_title(self) -> Optional[str]:
        """Obtiene el título del medio actual."""
        if self._current_media is not None:
            try:
                return self._current_media.get_meta(vlc.Meta.Title)
            except Exception:
                pass
        return None
    
    @property
    def duration(self) -> Optional[float]:
        """Obtiene la duración del medio."""
        if self._player is not None:
            try:
                length = self._player.get_length()
                return length / 1000.0 if length > 0 else None
            except Exception:
                pass
        return None
    
    @property
    def is_playing(self) -> bool:
        """Verifica si está reproduciendo."""
        if self._player is not None:
            try:
                return self._player.is_playing() == 1
            except Exception:
                pass
        return False
    
    @property
    def state(self) -> str:
        """Obtiene el estado del reproductor."""
        if self._player is not None:
            try:
                state = self._player.get_state()
                state_map = {
                    vlc.State.NothingSpecial: "nothing",
                    vlc.State.Opening: "opening",
                    vlc.State.Buffering: "buffering",
                    vlc.State.Playing: "playing",
                    vlc.State.Paused: "paused",
                    vlc.State.Stopped: "stopped",
                    vlc.State.Ended: "ended",
                    vlc.State.Error: "error",
                }
                return state_map.get(state, "unknown")
            except Exception:
                pass
        return "stopped"
    
    # === Funciones de grabación ===
    
    def start_recording(self, url: str, output_path: str) -> bool:
        """
        Inicia la grabación de un stream a un archivo MP3.
        
        Args:
            url: URL del stream a grabar.
            output_path: Ruta del archivo de salida (MP3).
            
        Returns:
            True si la grabación inició correctamente.
        """
        if self._recording:
            log.warning("Ya hay una grabación en curso")
            return False
        
        try:
            # Asegurar que el directorio de destino existe
            target_dir = os.path.dirname(output_path)
            if not os.path.exists(target_dir):
                os.makedirs(target_dir, exist_ok=True)
            
            # Normalizar ruta para VLC
            norm_path = os.path.normpath(output_path).replace("\\", "/")
            
            # Calcular ganancia basándose en el volumen actual del complemento (0.1 a 1.0)
            # Esto hace que la grabación tenga el mismo nivel de volumen que lo que el usuario escucha
            volume_factor = max(0.01, self._volume / 100.0)
            
            # Opciones de medio para la grabación
            # Quitamos 'gain' para evitar que el audio sea demasiado fuerte y grabamos al nivel nominal del stream
            sout_str = (
                f":sout=#transcode{{acodec=mp3,ab=192,channels=2,samplerate=44100}}"
                f":std{{access=file,mux=mp3,dst=\"{norm_path}\"}}"
            )
            
            options = [
                sout_str,
                ":http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
                ":network-caching=5000",
                ":no-audio",
                ":no-video"
            ]
            
            # Crear media con las opciones usando la instancia de grabación
            self._record_media = self._record_instance.media_new(url)
            for opt in options:
                self._record_media.add_option(opt)
            
            self._record_player = self._record_instance.media_player_new()
            self._record_player.set_media(self._record_media)
            
            # Comenzar la grabación
            self._record_player.play()
            
            # Verificación mínima
            time.sleep(0.2)
            if self._record_player.get_state() == vlc.State.Error:
                log.error("Error en el reproductor de grabación")
                self._recording = False
                return False

            self._recording = True
            self._record_file = output_path
            log.info(f"Grabación iniciada: {output_path}")
            return True
            
        except Exception as e:
            log.error(f"Error iniciando grabación: {e}")
            self._recording = False
            return False
    
    def stop_recording(self) -> Optional[str]:
        """
        Detiene la grabación actual.
        
        Returns:
            Ruta del archivo grabado o None si no había grabación.
        """
        if not self._recording:
            return None
        
        try:
            if self._record_player is not None:
                self._record_player.stop()
                self._record_player.release()
                self._record_player = None
            
            if self._record_media is not None:
                self._record_media.release()
                self._record_media = None
            
            saved_file = self._record_file
            self._recording = False
            self._record_file = ""
            
            log.info(f"Grabación detenida: {saved_file}")
            return saved_file
            
        except Exception as e:
            log.error(f"Error deteniendo grabación: {e}")
            self._recording = False
            return None
    
    @property
    def is_recording(self) -> bool:
        """Verifica si hay una grabación en curso."""
        return self._recording
    
    @property
    def recording_file(self) -> str:
        """Obtiene la ruta del archivo de grabación actual."""
        return self._record_file
    
    def property_observer(self, property_name: str) -> Callable:
        """Decorador para observadores de propiedades (compatibilidad)."""
        def decorator(func: Callable) -> Callable:
            return func
        return decorator
    
    def terminate(self) -> None:
        """Libera todos los recursos."""
        self.stop_recording()
        self.stop()
        
        if self._player is not None:
            try:
                self._player.release()
            except Exception:
                pass
            self._player = None
        
        if self._instance is not None:
            try:
                self._instance.release()
            except Exception:
                pass
            self._instance = None
    
    def __del__(self):
        """Destructor."""
        self.terminate()


class VLC:
    """
    Clase wrapper principal para reproducción de audio con VLC.
    
    Proporciona una interfaz compatible con el wrapper anterior de mpv.
    """
    
    def __init__(
        self,
        ytdl: bool = False,
        video: bool = False,
        **kwargs
    ):
        """
        Inicializa el reproductor VLC.
        
        Args:
            ytdl: Ignorado (se mantiene para compatibilidad).
            video: Si debe habilitar video.
            **kwargs: Argumentos adicionales.
        """
        self._backend = None
        self._backend_name = "none"
        
        if VLC_AVAILABLE:
            try:
                self._backend = VLCPlayer(video=video, **kwargs)
                self._backend_name = "vlc"
                log.info("Usando backend: VLC")
                return
            except Exception as e:
                log.error(f"No se pudo iniciar VLC: {e}")
        
        raise ImportError("No hay backend de audio VLC disponible")
    
    def play(self, url: str) -> None:
        """Reproduce una URL."""
        if self._backend:
            self._backend.play(url)
    
    def stop(self) -> None:
        """Detiene la reproducción."""
        if self._backend:
            self._backend.stop()
    
    def command(self, name: str, *args) -> Any:
        """Ejecuta un comando."""
        if self._backend:
            return self._backend.command(name, *args)
        return None
    
    @property
    def volume(self) -> int:
        """Obtiene el volumen."""
        return self._backend.volume if self._backend else 100
    
    @volume.setter
    def volume(self, value: int) -> None:
        """Establece el volumen."""
        if self._backend:
            self._backend.volume = value
    
    @property
    def mute(self) -> bool:
        """Obtiene el estado de silencio."""
        return self._backend.mute if self._backend else False
    
    @mute.setter
    def mute(self, value: bool) -> None:
        """Establece el estado de silencio."""
        if self._backend:
            self._backend.mute = value
    
    @property
    def pause(self) -> bool:
        """Obtiene el estado de pausa."""
        return self._backend.pause if self._backend else False
    
    @pause.setter
    def pause(self, value: bool) -> None:
        """Establece el estado de pausa."""
        if self._backend:
            self._backend.pause = value
    
    @property
    def media_title(self) -> Optional[str]:
        """Obtiene el título del medio."""
        return self._backend.media_title if self._backend else None
    
    @property
    def duration(self) -> Optional[float]:
        """Obtiene la duración."""
        return self._backend.duration if self._backend else None
    
    @property
    def is_playing(self) -> bool:
        """Verifica si está reproduciendo."""
        return self._backend.is_playing if self._backend else False
    
    @property
    def state(self) -> str:
        """Obtiene el estado."""
        return self._backend.state if self._backend else "stopped"
    
    # === Métodos de grabación ===
    
    def start_recording(self, url: str, output_path: str) -> bool:
        """Inicia la grabación."""
        if self._backend:
            return self._backend.start_recording(url, output_path)
        return False
    
    def stop_recording(self) -> Optional[str]:
        """Detiene la grabación."""
        if self._backend:
            return self._backend.stop_recording()
        return None
    
    @property
    def is_recording(self) -> bool:
        """Verifica si está grabando."""
        return self._backend.is_recording if self._backend else False
    
    @property
    def recording_file(self) -> str:
        """Obtiene el archivo de grabación."""
        return self._backend.recording_file if self._backend else ""
    
    def property_observer(self, property_name: str) -> Callable:
        """Decorador para observadores de propiedades."""
        def decorator(func: Callable) -> Callable:
            return func
        return decorator
    
    def terminate(self) -> None:
        """Libera recursos."""
        if self._backend:
            self._backend.terminate()
    
    def __del__(self):
        """Destructor."""
        self.terminate()


# Para compatibilidad con código existente
VLC_LIB_AVAILABLE = VLC_AVAILABLE
vlc_module = vlc if VLC_AVAILABLE else None
VLC_LOAD_ERROR = None if VLC_AVAILABLE else "VLC no disponible"
