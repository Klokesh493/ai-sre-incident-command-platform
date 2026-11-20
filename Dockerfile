FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && mkdir /data && chown 10001:10001 /data
COPY --chown=10001:10001 ops_platform ops_platform
COPY --chown=10001:10001 tools tools
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "ops_platform.service:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
