# app/data/seed.py
BRANCHES = ["Cine Pelagio B. Luna 960", "Cine San Martín 62"]

MOVIES = [
    {
        "id": "m1",
        "titulo": "Las Guerreras K-POP",
        "poster_url": "/static/img/cartelera/kpop-demon-hunters.jpg",
        "trailer_url": "https://www.youtube.com/watch?v=nmt594aKD9U&t=2s",
        "sinopsis": "Rumi, Mira y Zoey son ídolas del K-pop y cazadoras de amenazas sobrenaturales decididas a proteger a sus fans.",
        "duracion_min": 99,
        "clasificacion": "10+",
        "genero": "Animación • Aventura • Fantasía • Musical",
        "funciones": [
            {"fecha": "2025-11-01", "hora": "21:30", "sala": "Sala 1"},
            {"fecha": "2025-11-02", "hora": "16:30", "sala": "Sala 3"},
        ],
    },
    {
        "id": "m2",
        "titulo": "Lilo y Stitch (2025)",
        "poster_url": "/static/img/cartelera/lilo-stitch.jpg",
        "trailer_url": "https://www.youtube.com/watch?v=9JIyINjMfcc",
        "sinopsis": "Una niña hawaiana y un alienígena fugitivo descubren el verdadero significado de la \"ohana\" mientras intentan mantenerse unidos.",
        "duracion_min": 108,
        "clasificacion": "PG",
        "genero": "Familiar • Aventura • Ciencia ficción",
        "funciones": [
            {"fecha": "2025-11-01", "hora": "17:00", "sala": "Sala 3"},
            {"fecha": "2025-11-02", "hora": "19:00", "sala": "Sala 2"},
        ],
    },
    {
        "id": "m3",
        "titulo": "Teléfono Negro 2",
        "poster_url": "/static/img/cartelera/telefono-negro-2.jpg",
        "trailer_url": "https://www.youtube.com/watch?v=YvqwkLg9o6k",
        "sinopsis": "Gwen comienza a tener visiones con llamadas del teléfono negro y crímenes en Alpine Lake. Junto a Finn, enfrenta el regreso de un mal implacable.",
        "duracion_min": 102,
        "clasificacion": "+16",
        "genero": "Terror • Thriller • Acción • Terror sobrenatural",
        "funciones": [
            {"fecha": "2025-11-01", "hora": "21:30", "sala": "Sala 1"},
            {"fecha": "2025-11-02", "hora": "22:00", "sala": "Sala 2"},
        ],
    },
]

COMBOS_CATALOG = [
    {"id": 1, "nombre": "Combo 1", "descripcion": "Pochoclo + Bebida", "precio": 1500},
    {"id": 2, "nombre": "Combo 2", "descripcion": "1× Pochoclo + 2× Bebida", "precio": 2500},
    {"id": 3, "nombre": "Combo 3", "descripcion": "Pochoclo + Dorito + Bebida", "precio": 2000},
]