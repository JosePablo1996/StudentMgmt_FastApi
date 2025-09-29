from fastapi import FastAPI, HTTPException, UploadFile, File, Form, status
from fastapi.middleware.cors import CORSMiddleware
import os
from typing import Optional
import uuid
from pydantic import BaseModel
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Intentar importar Supabase
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
    logger.info("✅ Supabase importado correctamente")
except ImportError as e:
    SUPABASE_AVAILABLE = False
    logger.warning(f"⚠️  Supabase no disponible: {e}")

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
supabase = None
BUCKET_NAME = "StudentMgmt_FastApi"

if SUPABASE_AVAILABLE:
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    # Log de las variables (sin mostrar valores completos por seguridad)
    logger.info(f"SUPABASE_URL configurado: {'Sí' if supabase_url else 'No'}")
    if supabase_key:
        logger.info(f"SUPABASE_KEY configurado: Sí (longitud: {len(supabase_key)})")
    else:
        logger.info("SUPABASE_KEY configurado: No")

    if supabase_url and supabase_key:
        try:
            supabase = create_client(supabase_url, supabase_key)
            logger.info("✅ Conectado a Supabase correctamente")
            
            # Test de conexión
            try:
                response = supabase.table("usuarios").select("count", count="exact").limit(1).execute()
                logger.info("✅ Conexión a la base de datos verificada")
            except Exception as e:
                logger.warning(f"⚠️  Tabla 'usuarios' podría no existir: {e}")
                
        except Exception as e:
            logger.error(f"❌ Error conectando a Supabase: {e}")
            supabase = None
    else:
        logger.warning("⚠️  Variables de entorno de Supabase no configuradas")
        logger.info("💡 Configure SUPABASE_URL y SUPABASE_KEY en Render")
else:
    logger.warning("⚠️  Supabase no disponible - Modo sin base de datos")

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

class HealthResponse(BaseModel):
    status: str
    database: str
    timestamp: str
    environment: str

async def subir_imagen_supabase(file: UploadFile) -> str:
    """Sube una imagen al bucket de Supabase Storage"""
    if not supabase:
        raise HTTPException(status_code=500, detail="Servicio de almacenamiento no disponible")
    
    try:
        if not file.content_type.startswith('image/'):
            raise ValueError("El archivo debe ser una imagen")
        
        # Generar nombre único
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
        filename = f"usuarios/{uuid.uuid4().hex[:8]}.{file_extension}"
        
        # Leer contenido
        file_content = await file.read()
        
        # Subir a Supabase Storage
        response = supabase.storage.from_(BUCKET_NAME).upload(
            file=file_content,
            path=filename,
            file_options={"content-type": file.content_type}
        )
        
        # Obtener URL pública
        public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(filename)
        logger.info(f"✅ Imagen subida: {filename}")
        
        return public_url
        
    except Exception as e:
        logger.error(f"❌ Error subiendo imagen: {e}")
        raise HTTPException(status_code=400, detail=f"Error al subir imagen: {str(e)}")

async def eliminar_imagen_supabase(image_url: str):
    """Elimina una imagen del Supabase Storage"""
    if not supabase or not image_url:
        return
        
    try:
        if BUCKET_NAME in image_url:
            filename = image_url.split(f"/{BUCKET_NAME}/")[-1]
            supabase.storage.from_(BUCKET_NAME).remove([filename])
            logger.info(f"✅ Imagen eliminada: {filename}")
    except Exception as e:
        logger.warning(f"⚠️  Error eliminando imagen: {e}")

# ==============================
# ENDPOINTS
# ==============================

@app.get("/")
async def root():
    """Endpoint raíz - Información de la API"""
    db_status = "conectado" if supabase else "no conectado"
    environment = "production" if os.getenv("RENDER") else "development"
    
    return {
        "message": "API de Gestión de Usuarios",
        "version": "1.0.0",
        "environment": environment,
        "database": db_status,
        "endpoints": {
            "crear_usuario": "POST /api/usuarios",
            "listar_usuarios": "GET /api/usuarios", 
            "editar_usuario": "PUT /api/usuarios/{id}",
            "eliminar_usuario": "DELETE /api/usuarios/{id}",
            "health": "GET /health",
            "storage_status": "GET /storage/status",
            "docs": "GET /docs"
        },
        "storage_bucket": BUCKET_NAME
    }

@app.get("/health")
async def health_check():
    """Health check para monitorización"""
    db_status = "unhealthy"
    environment = "production" if os.getenv("RENDER") else "development"
    
    # Verificar conexión a Supabase
    if supabase:
        try:
            # Test simple de conexión
            supabase.table("usuarios").select("count", count="exact").limit(1).execute()
            db_status = "healthy"
        except Exception as e:
            db_status = f"unhealthy: {str(e)}"
    else:
        db_status = "not_configured"
    
    return {
        "status": "healthy",
        "database": db_status,
        "timestamp": datetime.now().isoformat(),
        "environment": environment,
        "service": "StudentMgmt API"
    }

@app.get("/storage/status")
async def storage_status():
    """Verificar estado del storage"""
    if not supabase:
        return {
            "status": "error",
            "message": "Supabase no configurado",
            "bucket": BUCKET_NAME
        }
    
    try:
        response = supabase.storage.from_(BUCKET_NAME).list()
        return {
            "status": "connected",
            "bucket": BUCKET_NAME,
            "files_count": len(response) if response else 0,
            "message": "Conexión a Supabase Storage exitosa"
        }
    except Exception as e:
        return {
            "status": "error", 
            "bucket": BUCKET_NAME,
            "message": f"Error conectando al bucket: {str(e)}"
        }

@app.get("/api/usuarios", response_model=list[User])
async def listar_usuarios():
    """Listar todos los usuarios registrados"""
    if not supabase:
        raise HTTPException(status_code=503, detail="Servicio de base de datos no disponible")
    
    try:
        response = supabase.table("usuarios").select("*").order("creado_en", desc=True).execute()
        
        if hasattr(response, 'error') and response.error:
            logger.error(f"❌ Error listando usuarios: {response.error.message}")
            raise HTTPException(status_code=500, detail=response.error.message)
            
        logger.info(f"✅ Usuarios listados: {len(response.data)} encontrados")
        return response.data
        
    except Exception as e:
        logger.error(f"❌ Error listando usuarios: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener usuarios: {str(e)}")

@app.get("/api/usuarios/{usuario_id}", response_model=User)
async def obtener_usuario(usuario_id: int):
    """Obtener un usuario específico por ID"""
    if not supabase:
        raise HTTPException(status_code=503, detail="Servicio de base de datos no disponible")
    
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
        logger.error(f"❌ Error obteniendo usuario {usuario_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener usuario: {str(e)}")

@app.post("/api/usuarios", response_model=User, status_code=status.HTTP_201_CREATED)
async def crear_usuario(
    nombre: str = Form(..., min_length=1, max_length=100),
    email: str = Form(..., regex=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'),
    telefono: str = Form(..., min_length=1, max_length=20),
    foto: Optional[UploadFile] = File(None)
):
    """Crear un nuevo usuario"""
    if not supabase:
        raise HTTPException(status_code=503, detail="Servicio de base de datos no disponible")
    
    try:
        foto_url = None
        
        # Subir imagen si se proporciona
        if foto:
            foto_url = await subir_imagen_supabase(foto)
        
        # Preparar datos
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
            logger.error(f"❌ Error creando usuario: {response.error.message}")
            raise HTTPException(status_code=500, detail=response.error.message)
            
        if not response.data:
            raise HTTPException(status_code=400, detail="No se pudo crear el usuario")
        
        logger.info(f"✅ Usuario creado: {email}")
        return response.data[0]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creando usuario: {e}")
        raise HTTPException(status_code=500, detail=f"Error al crear usuario: {str(e)}")

@app.put("/api/usuarios/{usuario_id}", response_model=User)
async def editar_usuario(
    usuario_id: int,
    nombre: str = Form(..., min_length=1, max_length=100),
    email: str = Form(..., regex=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'),
    telefono: str = Form(..., min_length=1, max_length=20),
    foto: Optional[UploadFile] = File(None)
):
    """Editar un usuario existente"""
    if not supabase:
        raise HTTPException(status_code=503, detail="Servicio de base de datos no disponible")
    
    try:
        # Verificar que existe
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
        
        # Procesar nueva imagen
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
        
        logger.info(f"✅ Usuario actualizado: {usuario_id}")
        return response.data[0]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error actualizando usuario {usuario_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error al actualizar usuario: {str(e)}")

@app.delete("/api/usuarios/{usuario_id}")
async def eliminar_usuario(usuario_id: int):
    """Eliminar un usuario (opcional)"""
    if not supabase:
        raise HTTPException(status_code=503, detail="Servicio de base de datos no disponible")
    
    try:
        # Verificar que existe
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
        
        logger.info(f"✅ Usuario eliminado: {usuario_id}")
        return {"message": "Usuario eliminado correctamente", "success": True}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error eliminando usuario {usuario_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error al eliminar usuario: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        reload=os.getenv("ENVIRONMENT") == "development"
    )