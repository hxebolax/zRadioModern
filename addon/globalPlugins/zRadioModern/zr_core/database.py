# -*- coding: utf-8 -*-
# Copyright (C) 2025 Héctor J. Benítez Corredera <xebolax@gmail.com>
# This file is covered by the GNU General Public License.

"""
Gestor de base de datos SQLite para zRadioModern.

Proporciona almacenamiento persistente para:
- Favoritos con categorías
- Historial de reproducción
- Caché de búsquedas
- Estadísticas de uso
"""

from __future__ import annotations
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import sys
import os
import threading

# Configurar path para usar las bibliotecas de lib
_module_path = Path(__file__).parent.parent
_lib_path = _module_path / "lib"

if str(_lib_path) not in sys.path:
    sys.path.insert(0, str(_lib_path))

# Intentar importar sqlite3 desde lib primero, luego fallback al sistema
try:
    # Verificar si hay sqlite3 en lib
    _sqlite3_path = _lib_path / "sqlite3"
    if _sqlite3_path.exists():
        # Importar desde lib
        import sqlite3
    else:
        # Usar sqlite3 del sistema (Python/NVDA)
        import sqlite3
except ImportError:
    import sqlite3

from logHandler import log

from .config import get_config
from .models import Favorite, Category, PlaybackHistory, Station


class DatabaseManager:
    """
    Gestor de base de datos SQLite.
    
    Proporciona operaciones CRUD para favoritos, categorías,
    historial y estadísticas.
    
    Thread-safe mediante el uso de conexiones por hilo.
    """
    
    def __init__(self):
        """Inicializa el gestor de base de datos."""
        self._config = get_config()
        self._db_path = self._config.database_path
        self._local = threading.local()
        
        # Crear tablas si no existen
        self._init_database()
    
    def _get_connection(self) -> sqlite3.Connection:
        """
        Obtiene una conexión SQLite para el hilo actual.
        
        Returns:
            sqlite3.Connection: Conexión a la base de datos.
        """
        if not hasattr(self._local, "connection"):
            self._local.connection = sqlite3.connect(
                str(self._db_path),
                check_same_thread=False
            )
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection
    
    @property
    def conn(self) -> sqlite3.Connection:
        """Acceso a la conexión del hilo actual."""
        return self._get_connection()
    
    def _init_database(self) -> None:
        """Crea las tablas de la base de datos si no existen."""
        try:
            cursor = self.conn.cursor()
            
            # Tabla de categorías
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT DEFAULT '',
                    color TEXT DEFAULT '#0078D4',
                    "order" INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tabla de favoritos
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS favorites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    station_uuid TEXT,
                    category_id INTEGER,
                    "order" INTEGER DEFAULT 0,
                    play_count INTEGER DEFAULT 0,
                    last_played TIMESTAMP,
                    notes TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (category_id) REFERENCES categories(id)
                        ON DELETE SET NULL
                )
            """)
            
            # Tabla de historial
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    station_name TEXT NOT NULL,
                    station_url TEXT NOT NULL,
                    station_uuid TEXT DEFAULT '',
                    played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    duration_seconds INTEGER DEFAULT 0
                )
            """)
            
            # Tabla de caché de países
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache_countries (
                    code TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    name_localized TEXT,
                    station_count INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tabla de caché de idiomas
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache_languages (
                    name TEXT PRIMARY KEY,
                    station_count INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tabla de caché de etiquetas
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache_tags (
                    name TEXT PRIMARY KEY,
                    station_count INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tabla de estadísticas
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS statistics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    total_play_time_seconds INTEGER DEFAULT 0,
                    total_stations_played INTEGER DEFAULT 0,
                    favorite_station_uuid TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Índices para optimización
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_favorites_category 
                ON favorites(category_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_favorites_order 
                ON favorites("order")
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_history_played_at 
                ON history(played_at)
            """)
            
            # Insertar categoría por defecto si no existe
            cursor.execute(
                "SELECT COUNT(*) FROM categories WHERE name = 'General'"
            )
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    """INSERT INTO categories (name, description, "order") 
                       VALUES ('General', 'Categoría por defecto', 0)"""
                )
            
            self.conn.commit()
            log.debug("Base de datos inicializada correctamente")
            
        except Exception as e:
            log.error(f"Error inicializando base de datos: {e}")
            raise
    
    def close(self) -> None:
        """Cierra la conexión de la base de datos del hilo actual."""
        if hasattr(self._local, "connection"):
            self._local.connection.close()
            del self._local.connection
    
    # === Operaciones de Categorías ===
    
    def get_categories(self) -> List[Category]:
        """
        Obtiene todas las categorías ordenadas.
        
        Returns:
            Lista de categorías.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT * FROM categories ORDER BY "order", name'
        )
        rows = cursor.fetchall()
        
        return [
            Category(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                color=row["color"],
                order=row["order"],
                created_at=datetime.fromisoformat(row["created_at"])
                    if row["created_at"] else None
            )
            for row in rows
        ]
    
    def add_category(self, category: Category) -> int:
        """
        Añade una nueva categoría.
        
        Args:
            category: Categoría a añadir.
            
        Returns:
            ID de la categoría insertada.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO categories (name, description, color, "order")
               VALUES (?, ?, ?, ?)""",
            (category.name, category.description, category.color, category.order)
        )
        self.conn.commit()
        return cursor.lastrowid
    
    def update_category(self, category: Category) -> bool:
        """Actualiza una categoría existente."""
        cursor = self.conn.cursor()
        cursor.execute(
            """UPDATE categories 
               SET name = ?, description = ?, color = ?, "order" = ?
               WHERE id = ?""",
            (category.name, category.description, category.color,
             category.order, category.id)
        )
        self.conn.commit()
        return cursor.rowcount > 0
    
    def delete_category(self, category_id: int) -> bool:
        """Elimina una categoría (los favoritos quedan sin categoría)."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    # === Operaciones de Favoritos ===
    
    def get_favorites(
        self,
        category_id: Optional[int] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Favorite]:
        """
        Obtiene los favoritos, opcionalmente filtrados por categoría.
        
        Args:
            category_id: ID de categoría para filtrar (None = todos).
            limit: Límite de resultados (None = sin límite).
            offset: Desplazamiento para paginación.
            
        Returns:
            Lista de favoritos.
        """
        cursor = self.conn.cursor()
        
        query = 'SELECT * FROM favorites'
        params = []
        
        if category_id is not None:
            query += ' WHERE category_id = ?'
            params.append(category_id)
        
        query += ' ORDER BY "order", name'
        
        if limit is not None:
            query += ' LIMIT ? OFFSET ?'
            params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        return [
            Favorite(
                id=row["id"],
                name=row["name"],
                url=row["url"],
                station_uuid=row["station_uuid"],
                category_id=row["category_id"],
                order=row["order"],
                play_count=row["play_count"],
                last_played=datetime.fromisoformat(row["last_played"])
                    if row["last_played"] else None,
                notes=row["notes"],
                created_at=datetime.fromisoformat(row["created_at"])
                    if row["created_at"] else None
            )
            for row in rows
        ]
    
    def get_favorite_by_id(self, favorite_id: int) -> Optional[Favorite]:
        """Obtiene un favorito por su ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM favorites WHERE id = ?", (favorite_id,))
        row = cursor.fetchone()
        
        if row is None:
            return None
        
        return Favorite(
            id=row["id"],
            name=row["name"],
            url=row["url"],
            station_uuid=row["station_uuid"],
            category_id=row["category_id"],
            order=row["order"],
            play_count=row["play_count"],
            last_played=datetime.fromisoformat(row["last_played"])
                if row["last_played"] else None,
            notes=row["notes"],
            created_at=datetime.fromisoformat(row["created_at"])
                if row["created_at"] else None
        )
    
    def add_favorite(self, favorite: Favorite) -> int:
        """
        Añade una nueva emisora a favoritos.
        
        Args:
            favorite: Favorito a añadir.
            
        Returns:
            ID del favorito insertado.
        """
        cursor = self.conn.cursor()
        
        # Obtener el siguiente orden disponible
        cursor.execute('SELECT MAX("order") FROM favorites')
        max_order = cursor.fetchone()[0]
        next_order = (max_order or 0) + 1
        
        cursor.execute(
            """INSERT INTO favorites 
               (name, url, station_uuid, category_id, "order", notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (favorite.name, favorite.url, favorite.station_uuid,
             favorite.category_id, next_order, favorite.notes)
        )
        self.conn.commit()
        return cursor.lastrowid
    
    def update_favorite(self, favorite: Favorite) -> bool:
        """Actualiza un favorito existente."""
        cursor = self.conn.cursor()
        cursor.execute(
            """UPDATE favorites 
               SET name = ?, url = ?, station_uuid = ?, category_id = ?,
                   "order" = ?, notes = ?
               WHERE id = ?""",
            (favorite.name, favorite.url, favorite.station_uuid,
             favorite.category_id, favorite.order, favorite.notes,
             favorite.id)
        )
        self.conn.commit()
        return cursor.rowcount > 0
    
    def delete_favorite(self, favorite_id: int) -> bool:
        """Elimina un favorito."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM favorites WHERE id = ?", (favorite_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def favorite_exists(self, url: str) -> bool:
        """Verifica si una URL ya está en favoritos."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM favorites WHERE url = ?", (url,))
        return cursor.fetchone() is not None
    
    def increment_play_count(self, favorite_id: int) -> None:
        """Incrementa el contador de reproducciones de un favorito."""
        cursor = self.conn.cursor()
        cursor.execute(
            """UPDATE favorites 
               SET play_count = play_count + 1, last_played = ?
               WHERE id = ?""",
            (datetime.now().isoformat(), favorite_id)
        )
        self.conn.commit()
    
    def reorder_favorites(self, order_map: Dict[int, int]) -> None:
        """
        Reordena los favoritos.
        
        Args:
            order_map: Diccionario {favorite_id: new_order}
        """
        cursor = self.conn.cursor()
        for fav_id, new_order in order_map.items():
            cursor.execute(
                'UPDATE favorites SET "order" = ? WHERE id = ?',
                (new_order, fav_id)
            )
        self.conn.commit()
    
    def move_favorite(self, favorite_id: int, direction: int) -> bool:
        """
        Mueve un favorito arriba o abajo en la lista.
        
        Args:
            favorite_id: ID del favorito a mover.
            direction: -1 para arriba, 1 para abajo.
            
        Returns:
            True si se movió correctamente.
        """
        favorites = self.get_favorites()
        idx = next((i for i, f in enumerate(favorites) if f.id == favorite_id), None)
        
        if idx is None:
            return False
        
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(favorites):
            return False
        
        # Intercambiar posiciones
        favorites[idx], favorites[new_idx] = favorites[new_idx], favorites[idx]
        
        # Actualizar órdenes
        order_map = {f.id: i for i, f in enumerate(favorites)}
        self.reorder_favorites(order_map)
        
        return True
    
    def search_favorites(self, query: str) -> List[Favorite]:
        """Busca favoritos por nombre."""
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT * FROM favorites 
               WHERE name LIKE ? 
               ORDER BY "order", name""",
            (f"%{query}%",)
        )
        rows = cursor.fetchall()
        
        return [
            Favorite(
                id=row["id"],
                name=row["name"],
                url=row["url"],
                station_uuid=row["station_uuid"],
                category_id=row["category_id"],
                order=row["order"],
                play_count=row["play_count"],
                last_played=datetime.fromisoformat(row["last_played"])
                    if row["last_played"] else None,
                notes=row["notes"],
                created_at=datetime.fromisoformat(row["created_at"])
                    if row["created_at"] else None
            )
            for row in rows
        ]
    
    # === Operaciones de Historial ===
    
    def add_to_history(self, station: Station) -> int:
        """
        Añade una reproducción al historial.
        
        Args:
            station: Estación reproducida.
            
        Returns:
            ID del registro de historial.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO history (station_name, station_url, station_uuid)
               VALUES (?, ?, ?)""",
            (station.name, station.url, station.stationuuid)
        )
        self.conn.commit()
        return cursor.lastrowid
    
    def get_history(
        self,
        limit: int = 50,
        offset: int = 0
    ) -> List[PlaybackHistory]:
        """
        Obtiene el historial de reproducción.
        
        Args:
            limit: Número máximo de registros.
            offset: Desplazamiento para paginación.
            
        Returns:
            Lista de registros del historial.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT * FROM history 
               ORDER BY played_at DESC 
               LIMIT ? OFFSET ?""",
            (limit, offset)
        )
        rows = cursor.fetchall()
        
        return [
            PlaybackHistory(
                id=row["id"],
                station_name=row["station_name"],
                station_url=row["station_url"],
                station_uuid=row["station_uuid"],
                played_at=datetime.fromisoformat(row["played_at"])
                    if row["played_at"] else None,
                duration_seconds=row["duration_seconds"]
            )
            for row in rows
        ]
    
    def clear_history(self, older_than_days: Optional[int] = None) -> int:
        """
        Limpia el historial.
        
        Args:
            older_than_days: Si se especifica, solo elimina registros
                           más antiguos que esta cantidad de días.
                           
        Returns:
            Número de registros eliminados.
        """
        cursor = self.conn.cursor()
        
        if older_than_days is not None:
            cutoff_date = datetime.now() - timedelta(days=older_than_days)
            cursor.execute(
                "DELETE FROM history WHERE played_at < ?",
                (cutoff_date.isoformat(),)
            )
        else:
            cursor.execute("DELETE FROM history")
        
        self.conn.commit()
        return cursor.rowcount
    
    def get_most_played_stations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Obtiene las emisoras más reproducidas del historial."""
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT station_name, station_url, station_uuid, 
                      COUNT(*) as play_count
               FROM history 
               GROUP BY station_url 
               ORDER BY play_count DESC 
               LIMIT ?""",
            (limit,)
        )
        rows = cursor.fetchall()
        
        return [
            {
                "name": row["station_name"],
                "url": row["station_url"],
                "uuid": row["station_uuid"],
                "play_count": row["play_count"]
            }
            for row in rows
        ]
    
    # === Operaciones de Caché ===
    
    def cache_countries(self, countries: List[Dict[str, Any]]) -> None:
        """Almacena los países en caché."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM cache_countries")
        
        for country in countries:
            cursor.execute(
                """INSERT OR REPLACE INTO cache_countries 
                   (code, name, station_count, updated_at)
                   VALUES (?, ?, ?, ?)""",
                (country.get("iso_3166_1", ""),
                 country.get("name", ""),
                 country.get("stationcount", 0),
                 datetime.now().isoformat())
            )
        
        self.conn.commit()
    
    def get_cached_countries(self) -> List[Dict[str, Any]]:
        """Obtiene los países del caché."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM cache_countries ORDER BY name"
        )
        return [dict(row) for row in cursor.fetchall()]
    
    def is_cache_valid(self, table: str, max_age_days: int = 3) -> bool:
        """Verifica si el caché de una tabla es válido."""
        cursor = self.conn.cursor()
        cursor.execute(
            f"SELECT MAX(updated_at) FROM {table}"
        )
        result = cursor.fetchone()[0]
        
        if result is None:
            return False
        
        last_update = datetime.fromisoformat(result)
        return (datetime.now() - last_update) < timedelta(days=max_age_days)
    
    # === Exportación/Importación ===
    
    def export_favorites_json(self) -> str:
        """Exporta todos los favoritos a JSON."""
        import json
        
        favorites = self.get_favorites()
        categories = self.get_categories()
        
        data = {
            "version": "1.0",
            "exported_at": datetime.now().isoformat(),
            "categories": [
                {
                    "name": c.name,
                    "description": c.description,
                    "color": c.color
                }
                for c in categories
            ],
            "favorites": [
                {
                    "name": f.name,
                    "url": f.url,
                    "station_uuid": f.station_uuid,
                    "notes": f.notes
                }
                for f in favorites
            ]
        }
        
        return json.dumps(data, indent=2, ensure_ascii=False)
    
    def import_favorites_json(self, json_data: str) -> Tuple[int, int]:
        """
        Importa favoritos desde JSON.
        
        Returns:
            Tupla (categorías_importadas, favoritos_importados)
        """
        import json
        
        data = json.loads(json_data)
        categories_imported = 0
        favorites_imported = 0
        
        # Importar categorías
        for cat_data in data.get("categories", []):
            if not self._category_exists(cat_data["name"]):
                self.add_category(Category(
                    name=cat_data["name"],
                    description=cat_data.get("description", ""),
                    color=cat_data.get("color", "#0078D4")
                ))
                categories_imported += 1
        
        # Importar favoritos
        for fav_data in data.get("favorites", []):
            if not self.favorite_exists(fav_data["url"]):
                self.add_favorite(Favorite(
                    name=fav_data["name"],
                    url=fav_data["url"],
                    station_uuid=fav_data.get("station_uuid"),
                    notes=fav_data.get("notes", "")
                ))
                favorites_imported += 1
        
        return categories_imported, favorites_imported
    
    def _category_exists(self, name: str) -> bool:
        """Verifica si existe una categoría con ese nombre."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT 1 FROM categories WHERE name = ?",
            (name,)
        )
        return cursor.fetchone() is not None
