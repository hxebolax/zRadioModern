# -*- coding: utf-8 -*-
# Copyright (C) 2025 Héctor J. Benítez Corredera <xebolax@gmail.com>
# This file is covered by the GNU General Public License.

"""
Reproductor de audio para zRadioModern.

Utiliza la biblioteca VLC para reproducir streams de radio.
Proporciona control de volumen, silencio, gestión del estado
y grabación de streams a MP3.

Todas las operaciones de reproducción son asíncronas para no bloquear la GUI.
"""

from __future__ import annotations
from typing import Optional, Callable, Any
from enum import Enum, auto
from pathlib import Path
from datetime import datetime, timedelta
import os
import sys
import threading
import time

from logHandler import log

# Configurar ruta para las librerías
_addon_path = Path(__file__).parent.parent
_lib_path = _addon_path / "lib"
if str(_lib_path) not in sys.path:
    sys.path.insert(0, str(_lib_path))

try:
    from . import vlc_wrapper as vlc
    VLC_AVAILABLE = True
except ImportError as e:
    VLC_AVAILABLE = False
    log.warning(f"VLC wrapper no disponible: {e}")


class PlayerState(Enum):
    """Estados posibles del reproductor."""
    STOPPED = auto()
    PLAYING = auto()
    BUFFERING = auto()
    PAUSED = auto()
    ERROR = auto()


class RecordingState(Enum):
    """Estados posibles de la grabación."""
    IDLE = auto()
    RECORDING = auto()
    SCHEDULED = auto()


class ScheduledRecording:
    """Representa una grabación programada."""
    
    def __init__(
        self,
        station_url: str,
        station_name: str,
        start_time: datetime,
        end_time: datetime,
        output_path: str
    ):
        self.station_url = station_url
        self.station_name = station_name
        self.start_time = start_time
        self.end_time = end_time
        self.output_path = output_path
        self.active = True


class AudioPlayer:
    """
    Reproductor de audio basado en VLC.
    
    Proporciona reproducción de streams de radio con control
    de volumen, silencio, eventos de estado y grabación.
    
    Todas las operaciones son asíncronas para no bloquear la GUI.
    
    Attributes:
        state: Estado actual del reproductor.
        volume: Volumen actual (0-100).
        muted: Si el audio está silenciado.
        current_station: Estación actualmente en reproducción.
    """
    
    def __init__(self):
        """Inicializa el reproductor."""
        self._player: Optional[Any] = None
        self._state = PlayerState.STOPPED
        self._volume = 50
        self._muted = False
        self._current_url: str = ""
        self._current_station: Optional[Any] = None
        self._lock = threading.Lock()
        
        # Estado de grabación
        self._recording_state = RecordingState.IDLE
        self._recording_start_time: Optional[datetime] = None
        self._scheduled_recordings: list[ScheduledRecording] = []
        self._scheduler_thread: Optional[threading.Thread] = None
        self._scheduler_running = False
        
        # Callbacks de eventos
        self._on_state_change: Optional[Callable[[PlayerState], None]] = None
        self._on_error: Optional[Callable[[str], None]] = None
        self._on_metadata: Optional[Callable[[dict], None]] = None
        self._on_recording_started: Optional[Callable[[str], None]] = None
        self._on_recording_stopped: Optional[Callable[[str], None]] = None
        self._on_buffering: Optional[Callable[[], None]] = None
        self._on_playing: Optional[Callable[[], None]] = None
        
        # Iniciar scheduler de grabaciones
        self._start_scheduler()
    
    @property
    def state(self) -> PlayerState:
        """Obtiene el estado actual del reproductor."""
        return self._state
    
    @property
    def volume(self) -> int:
        """Obtiene el volumen actual."""
        return self._volume
    
    @volume.setter
    def volume(self, value: int) -> None:
        """Establece el volumen (0-100)."""
        self._volume = max(0, min(100, value))
        if self._player is not None:
            try:
                self._player.volume = self._volume
            except Exception as e:
                log.error(f"Error estableciendo volumen: {e}")
    
    @property
    def muted(self) -> bool:
        """Obtiene el estado de silencio."""
        return self._muted
    
    @muted.setter
    def muted(self, value: bool) -> None:
        """Establece el estado de silencio."""
        self._muted = value
        if self._player is not None:
            try:
                self._player.mute = value
            except Exception as e:
                log.error(f"Error estableciendo mute: {e}")
    
    @property
    def current_station(self) -> Optional[Any]:
        """Obtiene la estación actual."""
        return self._current_station
    
    @current_station.setter
    def current_station(self, station: Any) -> None:
        """Establece la estación actual."""
        self._current_station = station
    
    @property
    def current_url(self) -> str:
        """Obtiene la URL actual siendo reproducida."""
        return self._current_url
    
    @property
    def is_playing(self) -> bool:
        """Verifica si está reproduciendo."""
        return self._state in (PlayerState.PLAYING, PlayerState.BUFFERING)
    
    @property
    def is_recording(self) -> bool:
        """Verifica si está grabando."""
        if self._player is not None:
            try:
                return self._player.is_recording
            except Exception:
                pass
        return self._recording_state == RecordingState.RECORDING
    
    @property
    def recording_state(self) -> RecordingState:
        """Obtiene el estado de grabación."""
        return self._recording_state
    
    @property
    def recording_file(self) -> str:
        """Obtiene el archivo de grabación actual."""
        if self._player is not None:
            try:
                return self._player.recording_file
            except Exception:
                pass
        return ""
    
    @property
    def recording_duration(self) -> Optional[timedelta]:
        """Obtiene la duración de la grabación actual."""
        if self._recording_start_time is not None and self.is_recording:
            return datetime.now() - self._recording_start_time
        return None
    
    @property
    def scheduled_recordings(self) -> list[ScheduledRecording]:
        """Obtiene la lista de grabaciones programadas."""
        return [r for r in self._scheduled_recordings if r.active]
    
    def _init_player(self) -> bool:
        """
        Inicializa el reproductor VLC si no está activo.
        
        Returns:
            True si se inicializó correctamente.
        """
        if not VLC_AVAILABLE:
            log.error("VLC no está disponible")
            return False
        
        if self._player is not None:
            return True
        
        try:
            with self._lock:
                log.debug("Intentando crear instancia de VLC")
                
                self._player = vlc.VLC(
                    video=False  # Solo audio, sin video
                )
                
                log.debug("Instancia VLC creada, configurando volumen")
                self._player.volume = self._volume
                self._player.mute = self._muted
                
                log.debug("Reproductor VLC inicializado")
                return True
                
        except Exception as e:
            log.error(f"Error inicializando VLC: {e}")
            self._player = None
            return False
    
    def play(self, url: str, async_play: bool = True) -> bool:
        """
        Reproduce un stream de radio de forma asíncrona.
        
        Args:
            url: URL del stream a reproducir.
            async_play: Si True, reproduce de forma asíncrona (no bloquea).
            
        Returns:
            True si inició la reproducción correctamente.
        """
        if not url:
            log.warning("URL vacía, no se puede reproducir")
            return False
        
        if async_play:
            # Iniciar reproducción en hilo separado
            self._state = PlayerState.BUFFERING
            self._current_url = url
            
            # Notificar que estamos cargando
            if self._on_state_change:
                self._on_state_change(self._state)
            if self._on_buffering:
                self._on_buffering()
            
            thread = threading.Thread(
                target=self._play_async,
                args=(url,),
                daemon=True
            )
            thread.start()
            return True
        else:
            return self._play_sync(url)
    
    def _play_async(self, url: str) -> None:
        """Reproduce una URL de forma asíncrona en un hilo separado."""
        try:
            if not self._init_player():
                self._state = PlayerState.ERROR
                if self._on_error:
                    self._on_error("No se pudo inicializar el reproductor")
                return
            
            with self._lock:
                self._player.play(url)
            
            # Esperar un momento para que VLC empiece a cargar
            time.sleep(0.5)
            
            # Verificar si realmente está reproduciendo
            self._state = PlayerState.PLAYING
            
            log.debug(f"Reproduciendo: {url}")
            
            if self._on_state_change:
                self._on_state_change(self._state)
            if self._on_playing:
                self._on_playing()
                
        except Exception as e:
            log.error(f"Error reproduciendo {url}: {e}")
            self._state = PlayerState.ERROR
            if self._on_error:
                self._on_error(str(e))
    
    def _play_sync(self, url: str) -> bool:
        """Reproduce una URL de forma síncrona (bloquea hasta que empiece)."""
        if not self._init_player():
            self._state = PlayerState.ERROR
            if self._on_error:
                self._on_error("No se pudo inicializar el reproductor")
            return False
        
        try:
            with self._lock:
                self._current_url = url
                self._state = PlayerState.BUFFERING
                self._player.play(url)
                self._state = PlayerState.PLAYING
                
                log.debug(f"Reproduciendo: {url}")
                
                if self._on_state_change:
                    self._on_state_change(self._state)
                
                return True
                
        except Exception as e:
            log.error(f"Error reproduciendo {url}: {e}")
            self._state = PlayerState.ERROR
            if self._on_error:
                self._on_error(str(e))
            return False
    
    def stop(self) -> None:
        """Detiene la reproducción actual."""
        if self._player is None:
            return
        
        # Ejecutar stop en hilo separado para no bloquear
        def _stop_async():
            try:
                with self._lock:
                    # Detener grabación si está activa
                    if self.is_recording:
                        self.stop_recording()
                    
                    self._player.command("stop")
                    self._state = PlayerState.STOPPED
                    self._current_url = ""
                    self._current_station = None
                    
                    log.debug("Reproducción detenida")
                    
                    if self._on_state_change:
                        self._on_state_change(self._state)
                        
            except Exception as e:
                log.error(f"Error deteniendo reproducción: {e}")
        
        thread = threading.Thread(target=_stop_async, daemon=True)
        thread.start()
    
    def pause(self) -> None:
        """Pausa la reproducción."""
        if self._player is None:
            return
        
        try:
            self._player.pause = True
            self._state = PlayerState.PAUSED
            if self._on_state_change:
                self._on_state_change(self._state)
        except Exception as e:
            log.error(f"Error pausando: {e}")
    
    def resume(self) -> None:
        """Reanuda la reproducción."""
        if self._player is None:
            return
        
        try:
            self._player.pause = False
            self._state = PlayerState.PLAYING
            if self._on_state_change:
                self._on_state_change(self._state)
        except Exception as e:
            log.error(f"Error reanudando: {e}")
    
    def toggle_pause(self) -> None:
        """Alterna entre pausa y reproducción."""
        if self._state == PlayerState.PAUSED:
            self.resume()
        elif self._state == PlayerState.PLAYING:
            self.pause()
    
    def toggle_mute(self) -> None:
        """Alterna el estado de silencio."""
        self.muted = not self._muted
    
    def reload(self) -> bool:
        """
        Recarga la emisora actual.
        
        Returns:
            True si se recargó correctamente.
        """
        if not self._current_url:
            return False
        
        url = self._current_url
        station = self._current_station
        self.stop()
        time.sleep(0.2)  # Pequeña espera antes de recargar
        self._current_station = station
        return self.play(url)
    
    def set_volume_percent(self, percent: int) -> None:
        """Establece el volumen como porcentaje (0-100)."""
        self.volume = percent
    
    def volume_up(self, step: int = 5) -> int:
        """
        Incrementa el volumen.
        
        Args:
            step: Cantidad a incrementar.
            
        Returns:
            Nuevo volumen.
        """
        self.volume = min(100, self._volume + step)
        return self._volume
    
    def volume_down(self, step: int = 5) -> int:
        """
        Reduce el volumen.
        
        Args:
            step: Cantidad a reducir.
            
        Returns:
            Nuevo volumen.
        """
        self.volume = max(0, self._volume - step)
        return self._volume
    
    def get_metadata(self) -> dict:
        """
        Obtiene los metadatos del stream actual.
        
        Returns:
            Diccionario con metadatos (título, artista, etc.)
        """
        if self._player is None:
            return {}
        
        try:
            return {
                "title": self._player.media_title or "",
                "duration": self._player.duration or 0,
            }
        except Exception:
            return {}
    
    def get_status_info(self) -> dict:
        """
        Obtiene información completa del estado del reproductor.
        
        Returns:
            Diccionario con toda la información del estado actual.
        """
        station_name = ""
        if self._current_station:
            station_name = getattr(self._current_station, 'name', str(self._current_station))
        
        recording_duration = None
        if self.recording_duration:
            recording_duration = self.recording_duration.total_seconds()
        
        return {
            "state": self._state.name,
            "is_playing": self.is_playing,
            "is_recording": self.is_recording,
            "station_name": station_name,
            "station_url": self._current_url,
            "volume": self._volume,
            "muted": self._muted,
            "recording_file": self.recording_file,
            "recording_duration_seconds": recording_duration,
            "scheduled_recordings_count": len(self.scheduled_recordings),
        }
    
    def get_status_message(self) -> str:
        """
        Obtiene un mensaje legible con el estado actual.
        
        Returns:
            Cadena con la información del estado.
        """
        info = self.get_status_info()
        lines = []
        
        # Estado de reproducción
        if info["is_playing"]:
            if info["state"] == "BUFFERING":
                lines.append(f"Cargando: {info['station_name'] or info['station_url']}")
            else:
                lines.append(f"Reproduciendo: {info['station_name'] or 'Emisora desconocida'}")
        else:
            lines.append("Sin reproducción activa")
        
        # Volumen
        if info["muted"]:
            lines.append(f"Volumen: {info['volume']}% (Silenciado)")
        else:
            lines.append(f"Volumen: {info['volume']}%")
        
        # Grabación
        if info["is_recording"]:
            duration_str = ""
            if info["recording_duration_seconds"]:
                minutes = int(info["recording_duration_seconds"] // 60)
                seconds = int(info["recording_duration_seconds"] % 60)
                duration_str = f" ({minutes}:{seconds:02d})"
            lines.append(f"Grabando{duration_str}")
        
        # Grabaciones programadas
        if info["scheduled_recordings_count"] > 0:
            lines.append(f"Grabaciones programadas: {info['scheduled_recordings_count']}")
        
        return "\n".join(lines)
    
    # === Métodos de grabación ===
    
    def start_recording(self, output_path: str, url: str = None, async_record: bool = True) -> bool:
        """
        Inicia la grabación del stream actual o especificado de forma asíncrona.
        
        Args:
            output_path: Ruta del archivo de salida MP3.
            url: URL a grabar (si no se especifica, usa la actual).
            async_record: Si True, graba de forma asíncrona.
            
        Returns:
            True si la grabación inició correctamente.
        """
        if not self._init_player():
            return False
        
        record_url = url or self._current_url
        if not record_url:
            log.warning("No hay URL para grabar")
            return False
        
        if async_record:
            self._recording_state = RecordingState.RECORDING
            self._recording_start_time = datetime.now()
            
            thread = threading.Thread(
                target=self._start_recording_async,
                args=(record_url, output_path),
                daemon=True
            )
            thread.start()
            return True
        else:
            return self._start_recording_sync(record_url, output_path)
    
    def _start_recording_async(self, url: str, output_path: str) -> None:
        """Inicia la grabación de forma asíncrona."""
        try:
            result = self._player.start_recording(url, output_path)
            if result:
                log.info(f"Grabación iniciada: {output_path}")
                if self._on_recording_started:
                    self._on_recording_started(output_path)
            else:
                self._recording_state = RecordingState.IDLE
                self._recording_start_time = None
                log.error("No se pudo iniciar la grabación")
        except Exception as e:
            log.error(f"Error iniciando grabación: {e}")
            self._recording_state = RecordingState.IDLE
            self._recording_start_time = None
    
    def _start_recording_sync(self, url: str, output_path: str) -> bool:
        """Inicia la grabación de forma síncrona."""
        try:
            result = self._player.start_recording(url, output_path)
            if result:
                self._recording_state = RecordingState.RECORDING
                self._recording_start_time = datetime.now()
                log.info(f"Grabación iniciada: {output_path}")
                
                if self._on_recording_started:
                    self._on_recording_started(output_path)
            return result
            
        except Exception as e:
            log.error(f"Error iniciando grabación: {e}")
            return False
    
    def stop_recording(self) -> Optional[str]:
        """
        Detiene la grabación actual.
        
        Returns:
            Ruta del archivo grabado o None.
        """
        if self._player is None:
            return None
        
        try:
            result = self._player.stop_recording()
            self._recording_state = RecordingState.IDLE
            self._recording_start_time = None
            
            if result and self._on_recording_stopped:
                self._on_recording_stopped(result)
            
            return result
            
        except Exception as e:
            log.error(f"Error deteniendo grabación: {e}")
            return None
    
    def schedule_recording(
        self,
        station_url: str,
        station_name: str,
        start_time: datetime,
        end_time: datetime,
        output_path: str
    ) -> bool:
        """
        Programa una grabación para un horario específico.
        
        Args:
            station_url: URL de la emisora a grabar.
            station_name: Nombre de la emisora.
            start_time: Hora de inicio.
            end_time: Hora de finalización.
            output_path: Ruta del archivo de salida.
            
        Returns:
            True si se programó correctamente.
        """
        if start_time >= end_time:
            log.error("La hora de inicio debe ser anterior a la de fin")
            return False
        
        if start_time <= datetime.now():
            log.error("La hora de inicio debe ser en el futuro")
            return False
        
        scheduled = ScheduledRecording(
            station_url=station_url,
            station_name=station_name,
            start_time=start_time,
            end_time=end_time,
            output_path=output_path
        )
        
        self._scheduled_recordings.append(scheduled)
        log.info(f"Grabación programada: {station_name} de {start_time} a {end_time}")
        return True
    
    def cancel_scheduled_recording(self, index: int) -> bool:
        """
        Cancela una grabación programada.
        
        Args:
            index: Índice de la grabación a cancelar.
            
        Returns:
            True si se canceló correctamente.
        """
        active_recordings = self.scheduled_recordings
        if 0 <= index < len(active_recordings):
            active_recordings[index].active = False
            log.info(f"Grabación programada cancelada: {active_recordings[index].station_name}")
            return True
        return False
    
    def _start_scheduler(self) -> None:
        """Inicia el hilo del scheduler de grabaciones."""
        if self._scheduler_running:
            return
        
        self._scheduler_running = True
        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            daemon=True
        )
        self._scheduler_thread.start()
    
    def _stop_scheduler(self) -> None:
        """Detiene el scheduler de grabaciones."""
        self._scheduler_running = False
        if self._scheduler_thread is not None:
            self._scheduler_thread.join(timeout=2)
    
    def _scheduler_loop(self) -> None:
        """Bucle principal del scheduler de grabaciones."""
        while self._scheduler_running:
            try:
                now = datetime.now()
                
                for recording in self._scheduled_recordings:
                    if not recording.active:
                        continue
                    
                    # Verificar si es hora de iniciar
                    if recording.start_time <= now < recording.end_time:
                        if not self.is_recording:
                            log.info(f"Iniciando grabación programada: {recording.station_name}")
                            self.start_recording(
                                output_path=recording.output_path,
                                url=recording.station_url
                            )
                    
                    # Verificar si es hora de detener
                    elif now >= recording.end_time:
                        if self.is_recording and self.recording_file == recording.output_path:
                            log.info(f"Deteniendo grabación programada: {recording.station_name}")
                            self.stop_recording()
                        recording.active = False
                
                # Limpiar grabaciones inactivas
                self._scheduled_recordings = [
                    r for r in self._scheduled_recordings if r.active
                ]
                
            except Exception as e:
                log.error(f"Error en scheduler: {e}")
            
            time.sleep(10)  # Verificar cada 10 segundos
    
    # === Callbacks ===
    
    def set_on_state_change(self, callback: Callable[[PlayerState], None]) -> None:
        """Establece el callback para cambios de estado."""
        self._on_state_change = callback
    
    def set_on_error(self, callback: Callable[[str], None]) -> None:
        """Establece el callback para errores."""
        self._on_error = callback
    
    def set_on_metadata(self, callback: Callable[[dict], None]) -> None:
        """Establece el callback para cambios de metadatos."""
        self._on_metadata = callback
    
    def set_on_recording_started(self, callback: Callable[[str], None]) -> None:
        """Establece el callback para inicio de grabación."""
        self._on_recording_started = callback
    
    def set_on_recording_stopped(self, callback: Callable[[str], None]) -> None:
        """Establece el callback para fin de grabación."""
        self._on_recording_stopped = callback
    
    def set_on_buffering(self, callback: Callable[[], None]) -> None:
        """Establece el callback para cuando empieza a cargar."""
        self._on_buffering = callback
    
    def set_on_playing(self, callback: Callable[[], None]) -> None:
        """Establece el callback para cuando empieza a reproducir."""
        self._on_playing = callback
    
    def dispose(self) -> None:
        """Libera los recursos del reproductor."""
        self._stop_scheduler()
        
        if self._player is not None:
            try:
                self.stop()
                self._player.terminate()
                self._player = None
                log.debug("Recursos del reproductor liberados")
            except Exception as e:
                log.error(f"Error liberando recursos: {e}")
    
    def __del__(self):
        """Destructor para liberar recursos."""
        self.dispose()
