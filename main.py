from fastapi import FastAPI, HTTPException, UploadFile, File, Form, status
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
import os
from dotenv import load_dotenv
from typing import Optional
import uuid
from pydantic import BaseModel
import io

# Cargar variables de entorno
load_dotenv()

app = FastAPI(
    title="API Gestión de Usuarios",
    description="API para CRUD de usuarios con Supabase Storage",
    version="1.0.0"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configurar Supabase
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")

if not supabase_url or not supabase_key:
    raise ValueError("SUPABASE_URL y SUPABASE_KEY deben estar configurados en el archivo .env")

supabase: Client = create_client(supabase_url, supabase_key)

# Configuración del bucket de Storage
BUCKET_NAME = "StudentMgmt_FastApi"

# Modelos Pydantic
class UserBase(BaseModel):
    nombre: str
    email: str
    telefono: str

class User(UserBase):
    id: int
    foto_url: Optional[str] = None
    creado_en: Optional[str] = None

    class Config:
        from_attributes = True

class SuccessResponse(BaseModel):
    message: str
    success: bool = True

async def subir_imagen_supabase(file: UploadFile) -> str:
    """
    Sube una imagen al bucket de Supabase Storage y retorna la URL pública
    """
    try:
        if not file.content_type.startswith('image/'):
            raise ValueError("El archivo debe ser una imagen")
        
        # Generar nombre único para el archivo
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
        filename = f"usuarios/{uuid.uuid4().hex[:8]}.{file_extension}"
        
        # Leer el contenido del archivo
        file_content = await file.read()
        
        # Subir a Supabase Storage
        response = supabase.storage.from_(BUCKET_NAME).upload(
            file=file_content,
            path=filename,
            file_options={"content-type": file.content_type}
        )
        
        # Obtener URL pública de la imagen
        public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(filename)
        
        return public_url
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al subir imagen: {str(e)}")

async def eliminar_imagen_supabase(image_url: str):
    """
    Elimina una imagen del Supabase Storage
    """
    try:
        if image_url and BUCKET_NAME in image_url:
            # Extraer el nombre del archivo de la URL
            filename = image_url.split(f"/{BUCKET_NAME}/")[-1]
            # Eliminar el archivo
            supabase.storage.from_(BUCKET_NAME).remove([filename])
    except Exception as e:
        print(f"⚠️  Error al eliminar imagen: {e}")

# ==============================
# ENDPOINTS REQUERIDOS
# ==============================

@app.get("/")
async def root():
    return {
        "message": "API de Gestión de Usuarios con Supabase Storage",
        "endpoints": {
            "crear_usuario": "POST /api/usuarios",
            "listar_usuarios": "GET /api/usuarios", 
            "editar_usuario": "PUT /api/usuarios/{id}",
            "eliminar_usuario": "DELETE /api/usuarios/{id}"
        },
        "storage_bucket": BUCKET_NAME
    }

# ✅ 1. LISTAR USUARIOS
@app.get("/api/usuarios", response_model=list[User])
async def listar_usuarios():
    """
    Listar todos los usuarios registrados
    """
    try:
        response = supabase.table("usuarios").select("*").order("creado_en", desc=True).execute()
        
        if hasattr(response, 'error') and response.error:
            raise HTTPException(status_code=500, detail=response.error.message)
            
        return response.data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener usuarios: {str(e)}")

# ✅ 2. CREAR USUARIO
@app.post("/api/usuarios", response_model=User, status_code=status.HTTP_201_CREATED)
async def crear_usuario(
    nombre: str = Form(..., min_length=1, max_length=100),
    email: str = Form(..., regex=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'),
    telefono: str = Form(..., min_length=1, max_length=20),
    foto: Optional[UploadFile] = File(None)
):
    """
    Crear un nuevo usuario con la información proporcionada
    - Nombre completo
    - Correo electrónico 
    - Teléfono
    - Fotografía (opcional) - Se almacena en Supabase Storage
    """
    try:
        foto_url = None
        
        # Subir imagen a Supabase Storage si se proporciona
        if foto:
            foto_url = await subir_imagen_supabase(foto)
        
        # Preparar datos del usuario
        user_data = {
            "nombre": nombre.strip(),
            "email": email.lower().strip(),
            "telefono": telefono.strip(),
            "foto_url": foto_url
        }
        
        # Insertar en Supabase
        response = supabase.table("usuarios").insert(user_data).execute()
        
        if hasattr(response, 'error') and response.error:
            if "duplicate key" in response.error.message.lower():
                raise HTTPException(status_code=400, detail="El correo electrónico ya está registrado")
            raise HTTPException(status_code=500, detail=response.error.message)
            
        if not response.data:
            raise HTTPException(status_code=400, detail="No se pudo crear el usuario")
        
        return response.data[0]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al crear usuario: {str(e)}")

# ✅ 3. EDITAR USUARIO  
@app.put("/api/usuarios/{usuario_id}", response_model=User)
async def editar_usuario(
    usuario_id: int,
    nombre: str = Form(..., min_length=1, max_length=100),
    email: str = Form(..., regex=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'),
    telefono: str = Form(..., min_length=1, max_length=20),
    foto: Optional[UploadFile] = File(None)
):
    """
    Editar la información de un usuario existente
    - Actualizar nombre, email, teléfono
    - Actualizar fotografía (opcional) - Se almacena en Supabase Storage
    """
    try:
        # Verificar que el usuario existe
        existing_response = supabase.table("usuarios").select("*").eq("id", usuario_id).execute()
        
        if hasattr(existing_response, 'error') and existing_response.error:
            raise HTTPException(status_code=500, detail=existing_response.error.message)
            
        if not existing_response.data:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        existing_user = existing_response.data[0]
        update_data = {
            "nombre": nombre.strip(),
            "email": email.lower().strip(),
            "telefono": telefono.strip()
        }
        
        # Procesar nueva imagen si se proporciona
        if foto:
            # Eliminar imagen anterior si existe
            if existing_user.get("foto_url"):
                await eliminar_imagen_supabase(existing_user["foto_url"])
            
            # Subir nueva imagen
            foto_url = await subir_imagen_supabase(foto)
            update_data["foto_url"] = foto_url
        
        # Actualizar en Supabase
        response = supabase.table("usuarios").update(update_data).eq("id", usuario_id).execute()
        
        if hasattr(response, 'error') and response.error:
            if "duplicate key" in response.error.message.lower():
                raise HTTPException(status_code=400, detail="El correo electrónico ya está registrado en otro usuario")
            raise HTTPException(status_code=500, detail=response.error.message)
            
        if not response.data:
            raise HTTPException(status_code=400, detail="No se pudo actualizar el usuario")
        
        return response.data[0]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar usuario: {str(e)}")

# ✅ 4. ELIMINAR USUARIO (OPCIONAL)
@app.delete("/api/usuarios/{usuario_id}", response_model=SuccessResponse)
async def eliminar_usuario(usuario_id: int):
    """
    Eliminar un usuario por su ID (opcional)
    """
    try:
        # Verificar que el usuario existe
        existing_response = supabase.table("usuarios").select("*").eq("id", usuario_id).execute()
        
        if hasattr(existing_response, 'error') and existing_response.error:
            raise HTTPException(status_code=500, detail=existing_response.error.message)
            
        if not existing_response.data:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        existing_user = existing_response.data[0]
        
        # Eliminar imagen del storage si existe
        if existing_user.get("foto_url"):
            await eliminar_imagen_supabase(existing_user["foto_url"])
        
        # Eliminar usuario
        response = supabase.table("usuarios").delete().eq("id", usuario_id).execute()
        
        if hasattr(response, 'error') and response.error:
            raise HTTPException(status_code=500, detail=response.error.message)
        
        return SuccessResponse(message="Usuario eliminado correctamente")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar usuario: {str(e)}")

# Endpoint adicional para obtener usuario específico (útil para editar)
@app.get("/api/usuarios/{usuario_id}", response_model=User)
async def obtener_usuario(usuario_id: int):
    """
    Obtener un usuario específico por ID (útil para precargar formulario de edición)
    """
    try:
        response = supabase.table("usuarios").select("*").eq("id", usuario_id).execute()
        
        if hasattr(response, 'error') and response.error:
            raise HTTPException(status_code=500, detail=response.error.message)
            
        if not response.data:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
            
        return response.data[0]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener usuario: {str(e)}")

# Endpoint para verificar configuración de storage
@app.get("/storage/status")
async def storage_status():
    """
    Verificar estado del bucket de storage
    """
    try:
        # Intentar listar archivos en el bucket
        response = supabase.storage.from_(BUCKET_NAME).list()
        return {
            "status": "connected",
            "bucket": BUCKET_NAME,
            "message": "Conexión a Supabase Storage exitosa"
        }
    except Exception as e:
        return {
            "status": "error",
            "bucket": BUCKET_NAME,
            "message": f"Error conectando al bucket: {str(e)}"
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )