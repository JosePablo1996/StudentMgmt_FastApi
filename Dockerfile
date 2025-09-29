FROM python:3.11-slim

WORKDIR /app

# Instalar solo lo esencial y limpiar cache
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar solo los archivos necesarios
COPY main.py .
COPY .env .  # Si usas .env en producción, sino quita esta línea

# Crear usuario no-root para seguridad
RUN useradd -m -u 1000 renderuser && chown -R renderuser:renderuser /app
USER renderuser

EXPOSE 8000

# Comando para producción
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]