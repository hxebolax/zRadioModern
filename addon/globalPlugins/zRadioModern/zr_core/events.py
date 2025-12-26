# -*- coding: utf-8 -*-
# Copyright (C) 2025 Héctor J. Benítez Corredera <xebolax@gmail.com>
# This file is covered by the GNU General Public License.

"""
Sistema de eventos para zRadioModern.

Proporciona un bus de eventos para comunicación desacoplada
entre componentes del complemento.
"""

from __future__ import annotations
from typing import Callable, Dict, List, Any, Optional
from enum import Enum, auto
from dataclasses import dataclass
import threading
import weakref

from logHandler import log


class EventType(Enum):
    """Tipos de eventos del sistema."""
    
    # Eventos de reproducción
    PLAYBACK_STARTED = auto()
    PLAYBACK_STOPPED = auto()
    PLAYBACK_PAUSED = auto()
    PLAYBACK_RESUMED = auto()
    PLAYBACK_ERROR = auto()
    BUFFERING_STARTED = auto()
    BUFFERING_ENDED = auto()
    
    # Eventos de volumen
    VOLUME_CHANGED = auto()
    MUTE_TOGGLED = auto()
    
    # Eventos de metadatos
    METADATA_UPDATED = auto()
    
    # Eventos de favoritos
    FAVORITE_ADDED = auto()
    FAVORITE_REMOVED = auto()
    FAVORITE_UPDATED = auto()
    FAVORITES_REORDERED = auto()
    
    # Eventos de categorías
    CATEGORY_ADDED = auto()
    CATEGORY_REMOVED = auto()
    CATEGORY_UPDATED = auto()
    
    # Eventos de búsqueda
    SEARCH_STARTED = auto()
    SEARCH_COMPLETED = auto()
    SEARCH_ERROR = auto()
    
    # Eventos de UI
    WINDOW_OPENED = auto()
    WINDOW_CLOSED = auto()
    TAB_CHANGED = auto()
    
    # Eventos de plugins
    PLUGIN_LOADED = auto()
    PLUGIN_UNLOADED = auto()
    PLUGIN_ERROR = auto()
    
    # Eventos de configuración
    CONFIG_CHANGED = auto()
    
    # Eventos de conexión
    INTERNET_CONNECTED = auto()
    INTERNET_DISCONNECTED = auto()


@dataclass
class Event:
    """
    Representa un evento del sistema.
    
    Attributes:
        type: Tipo de evento.
        data: Datos asociados al evento.
        source: Componente que emitió el evento.
        timestamp: Momento en que se emitió.
    """
    type: EventType
    data: Any = None
    source: Optional[str] = None
    timestamp: Optional[float] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            import time
            self.timestamp = time.time()


# Tipo para callbacks de eventos
EventCallback = Callable[[Any], None]


class EventBus:
    """
    Bus de eventos para comunicación entre componentes.
    
    Implementa el patrón publicador/suscriptor para permitir
    comunicación desacoplada entre los diferentes módulos
    del complemento.
    
    Thread-safe para uso en entornos multihilo.
    
    Example:
        >>> bus = EventBus()
        >>> bus.subscribe(EventType.PLAYBACK_STARTED, lambda s: print(s.name))
        >>> bus.emit(EventType.PLAYBACK_STARTED, station)
    """
    
    def __init__(self):
        """Inicializa el bus de eventos."""
        self._subscribers: Dict[EventType, List[weakref.ref]] = {}
        self._lock = threading.RLock()
        self._enabled = True
    
    def subscribe(
        self,
        event_type: EventType,
        callback: EventCallback,
        weak: bool = True
    ) -> Callable[[], None]:
        """
        Suscribe un callback a un tipo de evento.
        
        Args:
            event_type: Tipo de evento al que suscribirse.
            callback: Función a llamar cuando ocurra el evento.
            weak: Si usar referencia débil (permite garbage collection).
            
        Returns:
            Función para cancelar la suscripción.
        """
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            
            if weak:
                # Usar referencia débil para evitar memory leaks
                ref = weakref.ref(callback)
            else:
                # Crear un wrapper que actúa como referencia débil pero no lo es
                class StrongRef:
                    def __init__(self, obj):
                        self._obj = obj
                    def __call__(self):
                        return self._obj
                ref = StrongRef(callback)
            
            self._subscribers[event_type].append(ref)
            
            log.debug(f"Suscrito a evento {event_type.name}")
            
            # Devolver función de cancelación
            def unsubscribe():
                self._unsubscribe(event_type, ref)
            
            return unsubscribe
    
    def _unsubscribe(self, event_type: EventType, ref: weakref.ref) -> None:
        """Elimina una suscripción."""
        with self._lock:
            if event_type in self._subscribers:
                try:
                    self._subscribers[event_type].remove(ref)
                except ValueError:
                    pass
    
    def unsubscribe_all(self, event_type: Optional[EventType] = None) -> None:
        """
        Elimina todas las suscripciones.
        
        Args:
            event_type: Tipo de evento específico, o None para todos.
        """
        with self._lock:
            if event_type is None:
                self._subscribers.clear()
            elif event_type in self._subscribers:
                self._subscribers[event_type].clear()
    
    def emit(
        self,
        event_type: EventType,
        data: Any = None,
        source: Optional[str] = None
    ) -> int:
        """
        Emite un evento a todos los suscriptores.
        
        Args:
            event_type: Tipo de evento a emitir.
            data: Datos asociados al evento.
            source: Identificador del emisor.
            
        Returns:
            Número de callbacks notificados.
        """
        if not self._enabled:
            return 0
        
        event = Event(type=event_type, data=data, source=source)
        notified = 0
        
        with self._lock:
            if event_type not in self._subscribers:
                return 0
            
            # Limpiar referencias muertas y notificar
            alive_refs = []
            for ref in self._subscribers[event_type]:
                callback = ref()
                if callback is not None:
                    alive_refs.append(ref)
                    try:
                        callback(data)
                        notified += 1
                    except Exception as e:
                        log.error(
                            f"Error en callback de evento {event_type.name}: {e}"
                        )
            
            # Actualizar lista eliminando referencias muertas
            self._subscribers[event_type] = alive_refs
        
        log.debug(f"Evento {event_type.name} emitido a {notified} suscriptores")
        return notified
    
    def emit_async(
        self,
        event_type: EventType,
        data: Any = None,
        source: Optional[str] = None
    ) -> None:
        """
        Emite un evento de forma asíncrona.
        
        Los callbacks se ejecutan en un hilo separado.
        
        Args:
            event_type: Tipo de evento a emitir.
            data: Datos asociados al evento.
            source: Identificador del emisor.
        """
        thread = threading.Thread(
            target=self.emit,
            args=(event_type, data, source),
            daemon=True
        )
        thread.start()
    
    def enable(self) -> None:
        """Habilita la emisión de eventos."""
        self._enabled = True
    
    def disable(self) -> None:
        """Deshabilita temporalmente la emisión de eventos."""
        self._enabled = False
    
    @property
    def is_enabled(self) -> bool:
        """Indica si el bus está habilitado."""
        return self._enabled
    
    def get_subscriber_count(self, event_type: EventType) -> int:
        """
        Obtiene el número de suscriptores de un evento.
        
        Args:
            event_type: Tipo de evento.
            
        Returns:
            Número de suscriptores.
        """
        with self._lock:
            if event_type not in self._subscribers:
                return 0
            
            # Contar solo referencias vivas
            return sum(
                1 for ref in self._subscribers[event_type]
                if ref() is not None
            )


# Instancia global del bus de eventos
_global_event_bus: Optional[EventBus] = None
_bus_lock = threading.Lock()


def get_event_bus() -> EventBus:
    """
    Obtiene el bus de eventos global.
    
    Returns:
        EventBus: Instancia global del bus de eventos.
    """
    global _global_event_bus
    if _global_event_bus is None:
        with _bus_lock:
            if _global_event_bus is None:
                _global_event_bus = EventBus()
    return _global_event_bus
