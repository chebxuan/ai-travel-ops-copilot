FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home app
COPY backend /app/backend
COPY scripts/normalize_product_library.py scripts/maintain_database.py /app/scripts/
COPY data/products /app/data/products
COPY deploy/runtime.py /app/deploy/runtime.py
RUN mkdir -p /app/logs && chown app:app /app/logs
USER app
EXPOSE 8000
ENTRYPOINT ["python", "-m", "deploy.runtime"]
CMD ["serve"]
