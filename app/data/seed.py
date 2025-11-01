# app/data/seed.py
BRANCHES = ["Cine Pelagio B. Luna 960", "Cine San Martín 62"]

MOVIES = [
    {
        "id": "m1",
        "titulo": "Nebula 9",
        "poster_url": "https://picsum.photos/seed/nebula9/300/450",
        "sinopsis": "Una misión a la estación Nebula 9 se complica cuando un fallo de IA amenaza la tripulación.",
        "duracion_min": 118,
        "clasificacion": "+13",
        "genero": "Ciencia Ficción",
        "funciones": [
            {"fecha": "2025-09-29", "hora": "18:30", "sala": "Sala 1"},
            {"fecha": "2025-09-29", "hora": "21:00", "sala": "Sala 1"},
            {"fecha": "2025-09-30", "hora": "19:00", "sala": "Sala 2"},
            {"fecha": "2025-09-30", "hora": "21:30", "sala": "Sala 1"},
            {"fecha": "2025-10-01", "hora": "16:00", "sala": "Sala 1"},
        ],
    },
    {
        "id": "m2",
        "titulo": "Risas en la Oficina",
        "poster_url": "https://picsum.photos/seed/officefun/300/450",
        "sinopsis": "Comedia sobre un equipo que intenta lanzar un producto imposible en un deadline ridículo.",
        "duracion_min": 102,
        "clasificacion": "ATP",
        "genero": "Comedia",
        "funciones": [
            {"fecha": "2025-09-30", "hora": "18:00", "sala": "Sala 3"},
            {"fecha": "2025-10-01", "hora": "20:00", "sala": "Sala 3"},
        ],
    },
    {
        "id": "m3",
        "titulo": "Furia en la Ruta",
        "poster_url": "https://picsum.photos/seed/roadfury/300/450",
        "sinopsis": "Un piloto retirado vuelve a las pistas para una última carrera a través del desierto.",
        "duracion_min": 109,
        "clasificacion": "+16",
        "genero": "Acción",
        "funciones": [
            {"fecha": "2025-09-29", "hora": "22:00", "sala": "Sala 2"},
            {"fecha": "2025-10-02", "hora": "22:30", "sala": "Sala 2"},
        ],
    },
]

COMBOS_CATALOG = [
    {"id": 1, "nombre": "Combo 1", "descripcion": "Pochoclo + Bebida", "precio": 1500},
    {"id": 2, "nombre": "Combo 2", "descripcion": "1× Pochoclo + 2× Bebida", "precio": 2500},
    {"id": 3, "nombre": "Combo 3", "descripcion": "Pochoclo + Dorito + Bebida", "precio": 2000},
]
