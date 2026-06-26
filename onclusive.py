import os
import requests
import pandas as pd
import time
import smtplib
from datetime import datetime
from urllib.parse import unquote
from requests.auth import HTTPBasicAuth
from supabase import create_client
from email.message import EmailMessage

# --- 1. CONFIGURACIÓN ---
URL = "http://social.digimind.com/d/ap4/api/mentions"
USER = "aperez@tbwaperu.com" 
PASSWORD = "Andre1come!"

# Configuración de Supabase
SUPABASE_URL = "https://nkepnerncodumcfirunn.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5rZXBuZXJuY29kdW1jZmlydW5uIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2OTYwODEyOCwiZXhwIjoyMDg1MTg0MTI4fQ.1Nsi48ci5CeOna2ndAjnZG1OOsoaVq3sY_7kCKkVgUw"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def enviar_alerta(nuevos_posts):
    if not nuevos_posts: return
    
    contenido = "Se han detectado nuevos posts en Wong Virales:\n\n"
    for post in nuevos_posts:
        contenido += f"Título: {post.get('title')}\nURL: {post.get('url')}\nInteracciones: {post.get('interactions')}\n\n"
    
    headers = {
        "Authorization": f"Bearer {os.environ.get('RESEND_API_KEY')}",
        "Content-Type": "application/json"
    }
    payload = {
        "from": "onboarding@resend.dev", 
        "to": os.environ.get("EMAIL_RECEIVER"),
        "subject": f"🚀 {len(nuevos_posts)} nuevo(s) viral(es) detectado(s)",
        "text": contenido
    }
    
    try:
        print(f"DEBUG: Resend Key length: {len(os.environ.get('RESEND_API_KEY', ''))}")
        response = requests.post("https://api.resend.com/emails", json=payload, headers=headers)
        if response.status_code == 200:
            print("✅ Correo enviado correctamente vía Resend.")
        else:
            print(f"❌ Error en Resend: {response.text}")
    except Exception as e:
        print(f"❌ Error al conectar con Resend: {e}")

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
            response = requests.post(URL, headers=headers, data=payload, auth=HTTPBasicAuth(USER, PASSWORD), timeout=30)
            response.raise_for_status()
            data_json = response.json()
            menciones = data_json.get("mentions", [])
            
            if not menciones: break
                
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

    # --- 2. PROCESAMIENTO Y FILTRADO DE NUEVOS DATOS ---
    if todos_los_datos:
        df = pd.DataFrame(todos_los_datos)
        df['date'] = pd.to_datetime(df['date'], unit='ms').dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        df = df.rename(columns={'audience': 'audiencia', 'estimatedInteractions': 'interactions'})
        
        columnas_db = ['id', 'title', 'content', 'url', 'date', 'image', 'media', 'audiencia', 'interactions']
        for col in columnas_db:
            if col not in df.columns: df[col] = None
        
        registros = df[columnas_db].to_dict(orient='records')
        
        # Comparación: Buscar IDs existentes en Supabase
        try:
            existentes = supabase.table("wong_virales").select("id").execute().data
            ids_db = [item['id'] for item in existentes]
            
            # Solo los que NO están en la base de datos
            nuevos = [r for r in registros if r['id'] not in ids_db]
            
            if nuevos:
                supabase.table("wong_virales").upsert(nuevos).execute()
                print(f"✅ Éxito: {len(nuevos)} registros nuevos sincronizados.")
                enviar_alerta(nuevos)
            else:
                print("No hay datos nuevos para sincronizar.")
        except Exception as e:
            print(f"❌ Error en la lógica de comparación/subida: {e}")
    else:
        print("No se encontraron registros en la API.")

if __name__ == "__main__":
    ejecutar_extraccion()
