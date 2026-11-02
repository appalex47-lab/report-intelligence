# Report Intelligence: API + pantalla de revisión. SIN VERIFICAR en este entorno (no se construyó la imagen aquí).
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libreoffice-impress poppler-utils fonts-crosextra-carlito \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend backend
COPY profiles profiles
COPY frontend frontend
COPY tools tools
COPY docker/fonts.conf /etc/fonts/local.conf
ENV REPORT_RUNS_DIR=/data/runs REPORT_HISTORY_DB=/data/historial/historial.sqlite REPORT_TEMPLATES_DIR=/templates
VOLUME ["/data", "/templates"]
EXPOSE 8000
CMD ["uvicorn", "backend.app.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
