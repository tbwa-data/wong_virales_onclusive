import os
import requests
import pandas as pd
import time
from datetime import datetime
from urllib.parse import unquote
from requests.auth import HTTPBasicAuth
from supabase import create_client

# --- 1. CONFIGURACIÓN ---
URL = "http://social.digimind.com/d/ap4/api/mentions"
USER = "aperez@tbwaperu.com" 
PASSWORD = "Andre1come!"

# Configuración de Supabase
SUPABASE_URL = "https://nkepnerncodumcfirunn.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5rZXBuZXJuY29kdW1jZmlydW5uIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2OTYwODEyOCwiZXhwIjoyMDg1MTg0MTI4fQ.1Nsi48ci5CeOna2ndAjnZG1OOsoaVq3sY_7kCKkVgUw"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def ejecutar_extraccion():
    todos_los_datos = []
    token_actual = "*" 
    headers = {"Accept": "application/json"}
    filtros = ["mediatype:56", "entities:2208631", "trashed:false"]

    print(f"Iniciando extracción: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    while token_actual:
        payload = {
            "topic": "1",
            "sort": "date",
            "dateRangeType": "LAST_7_DAYS",
            "timeZone": "America/Lima",
            "maxResults": "100",
            "filter": filtros,
            "pageToken": token_actual
        }

        try:
            response = requests.post(
                URL, headers=headers, data=payload, 
                auth=HTTPBasicAuth(USER, PASSWORD), timeout=30
            )
            response.raise_for_status()
            data_json = response.json()
            menciones = data_json.get("mentions", [])
            
            if not menciones:
                break
                
            todos_los_datos.extend(menciones)
            next_token_raw = data_json.get("nextPageToken")
            
            if next_token_raw and next_token_raw != token_actual:
                token_actual = unquote(next_token_raw)
                time.sleep(3) 
            else:
                break
        except Exception as e:
            print(f"❌ Error en la API: {e}")
            break

    # --- 2. PROCESAMIENTO Y SUBIDA A SUPABASE ---
    if todos_los_datos:
        df = pd.DataFrame(todos_los_datos)
        
        # Conversión de fecha y preparación de columnas
        df['date'] = pd.to_datetime(df['date'], unit='ms').dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        
        # Mapeo de columnas según tu tabla 'wong_virales'
        # Aseguramos que existan las columnas, si no, las creamos como None
        df = df.rename(columns={
            'audience': 'audiencia', 
            'estimatedInteractions': 'interactions'
        })
        
        # Filtramos solo las columnas que existen en tu tabla de Supabase
        columnas_db = ['id', 'title', 'content', 'url', 'date', 'image', 'media', 'audiencia', 'interactions']
        # Asegurar que todas las columnas existan en el DF (rellenar con None si falta alguna)
        for col in columnas_db:
            if col not in df.columns:
                df[col] = None
                
        df_final = df[columnas_db]
        registros = df_final.to_dict(orient='records')
        
        # Subida a Supabase
        try:
            # Usamos upsert para evitar errores si el ID ya existe
            response = supabase.table("wong_virales").upsert(registros).execute()
            print(f"✅ Éxito: {len(registros)} registros sincronizados con Supabase.")
        except Exception as e:
            print(f"❌ Error al subir a Supabase: {e}")
    else:
        print("No hay datos nuevos para sincronizar.")

if __name__ == "__main__":
    ejecutar_extraccion()
