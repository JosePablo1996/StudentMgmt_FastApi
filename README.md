# API de Gestión de Estudiantes

API REST desarrollada con FastAPI para la gestión de estudiantes con fotografías.

## Características

- ✅ Crear, leer, actualizar y eliminar estudiantes
- ✅ Campos: Nombre completo, correo electrónico, teléfono, edad y fotografía
- ✅ Subida de imágenes desde galería o cámara
- ✅ Validación de correo electrónico único
- ✅ Servicio de archivos estáticos para imágenes
- ✅ CORS habilitado para aplicaciones móviles

## Tecnologías

- FastAPI
- SQLAlchemy
- PostgreSQL
- Python 3.11
- Docker

## Instalación local

1. Clonar el repositorio
2. Crear entorno virtual:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows