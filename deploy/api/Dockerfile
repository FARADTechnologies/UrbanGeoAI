# UrbanGeoAI API — Google Cloud Run imajı.
#
# Paket (out/api) boru hattının çıktısıdır; imaj onu kopyalar ve başlarken
# ham verilere ya da Overpass'a gitmez. Depo kökünden kurulur:
#
#   python scripts/build_api_bundle.py
#   docker build -f deploy/api/Dockerfile -t urbangeoai-api .
#   docker run -p 8080:8080 urbangeoai-api
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# Yalnız API'nin kullandığı paketler; geopandas ve pyproj gerekmez.
RUN pip install --no-cache-dir \
    "pandas>=2.0" "numpy>=1.24" "h3>=4.0" "scikit-learn>=1.3" \
    "fastapi>=0.110" "uvicorn>=0.29" "PyYAML>=6.0"

COPY pyproject.toml README.md ./
COPY src ./src
COPY scripts/serve_api.py ./scripts/serve_api.py
RUN pip install --no-cache-dir --no-deps .

COPY out/api ./bundle

EXPOSE 8080
CMD ["python", "scripts/serve_api.py", "--bundle", "bundle", "--host", "0.0.0.0"]
