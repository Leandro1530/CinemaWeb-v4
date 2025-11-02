#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para migrar funciones desde seed.py a la base de datos
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from app import create_app
from app.data.seed import MOVIES
import app.db as db_mod

def migrar_funciones_seed():
    """Migra las funciones desde seed.py a la base de datos"""
    
    app = create_app()
    
    with app.app_context():
        print("🎬 Migrando funciones desde seed.py a la base de datos...")
        
        try:
            # Limpiar funciones existentes (opcional)
            # db_mod.execute("DELETE FROM funciones", commit=True)
            
            funciones_creadas = 0
            
            for movie in MOVIES:
                movie_id = movie["id"]
                titulo = movie["titulo"]
                genero = movie["genero"]
                duracion = movie["duracion_min"]
                clasificacion = movie["clasificacion"]
                poster = movie["poster_url"]
                sinopsis = movie["sinopsis"]
                
                # Crear una función por cada horario
                for funcion in movie["funciones"]:
                    fecha = funcion["fecha"]
                    hora = funcion["hora"]
                    sala = funcion["sala"]
                    precio = 1000  # Precio por defecto
                    
                    # Verificar si ya existe esta función
                    existe = db_mod.query_one("""
                        SELECT id FROM funciones 
                        WHERE pelicula_id = ? AND fecha = ? AND hora = ? AND sala = ?
                    """, [movie_id, fecha, hora, sala])
                    
                    if not existe:
                        # Insertar la función
                        db_mod.execute("""
                            INSERT INTO funciones (
                                pelicula_id, titulo, genero, duracion, clasificacion,
                                poster, descripcion, trailer_url, fecha, hora, sala, precio
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, [movie_id, titulo, genero, duracion, clasificacion, 
                              poster, sinopsis, movie.get("trailer_url", ""), fecha, hora, sala, precio], commit=True)
                        
                        funciones_creadas += 1
                        print(f"✅ Creada: {titulo} - {fecha} {hora} ({sala})")
                    else:
                        # Actualizar la función existente con trailer_url si no lo tiene
                        trailer_url = movie.get("trailer_url", "")
                        if trailer_url:
                            db_mod.execute("""
                                UPDATE funciones 
                                SET trailer_url = ?
                                WHERE pelicula_id = ? AND fecha = ? AND hora = ? AND sala = ?
                                AND (trailer_url IS NULL OR trailer_url = '')
                            """, [trailer_url, movie_id, fecha, hora, sala], commit=True)
                            print(f"🔄 Actualizada con trailer: {titulo} - {fecha} {hora} ({sala})")
                        else:
                            print(f"⏭️ Ya existe: {titulo} - {fecha} {hora} ({sala})")
            
            print(f"\n🎉 Migración completada: {funciones_creadas} funciones creadas")
            
            # Mostrar resumen
            total_funciones = db_mod.query_one("SELECT COUNT(*) as count FROM funciones")
            print(f"📊 Total de funciones en la base de datos: {total_funciones['count']}")
            
        except Exception as e:
            print(f"❌ Error durante la migración: {e}")

if __name__ == "__main__":
    migrar_funciones_seed()