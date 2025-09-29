FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements primero para mejor cache
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto de los archivos
COPY . .

# Exponer puerto
EXPOSE 8000

# Comando para producción
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]