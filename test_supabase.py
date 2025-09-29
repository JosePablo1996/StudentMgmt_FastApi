import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")

print(f"URL: {supabase_url}")
print(f"KEY: {supabase_key[:20]}...")  # Mostrar solo primeros 20 caracteres

try:
    supabase = create_client(supabase_url, supabase_key)
    
    # Test de conexión
    response = supabase.table('usuarios').select('*').limit(1).execute()
    print("✅ Conexión exitosa!")
    
except Exception as e:
    print(f"❌ Error: {e}")