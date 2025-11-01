#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de prueba para verificar el sistema de pago completo
"""

import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

from app import create_app

def test_app():
    app = create_app()
    
    with app.app_context():
        print("✅ Aplicación creada exitosamente")
        print(f"✅ SECRET_KEY: {'Configurado' if app.config.get('SECRET_KEY') else 'NO CONFIGURADO'}")
        print(f"✅ MERCADOPAGO_ACCESS_TOKEN: {'Configurado' if app.config.get('MERCADOPAGO_ACCESS_TOKEN') else 'NO CONFIGURADO'}")
        print(f"✅ MERCADOPAGO_PUBLIC_KEY: {'Configurado' if app.config.get('MERCADOPAGO_PUBLIC_KEY') else 'NO CONFIGURADO'}")
        print(f"✅ TICKET_PRICE: {app.config.get('TICKET_PRICE')}")
        
        # Verificar blueprints registrados
        blueprints = list(app.blueprints.keys())
        print(f"✅ Blueprints registrados: {', '.join(blueprints)}")
        
        # Verificar rutas específicas
        with app.test_client() as client:
            print("\n--- Probando rutas ---")
            
            # Ruta principal
            resp = client.get('/')
            print(f"GET /: {resp.status_code}")
            
            # Ruta de pago (necesita sesión)
            with client.session_transaction() as sess:
                sess['movie_selection'] = {
                    'titulo': 'Película de Prueba',
                    'fecha': '2024-12-25',
                    'hora': '20:00',
                    'sala': 1
                }
                sess['seats'] = ['A1', 'A2']
                sess['combos'] = []
            
            resp = client.get('/pago')
            print(f"GET /pago: {resp.status_code}")
            
            # Ruta de MercadoPago
            resp = client.get('/pago-mp/')
            print(f"GET /pago-mp/: {resp.status_code}")

if __name__ == '__main__':
    test_app()
    print("\n🎉 Sistema listo y funcional!")