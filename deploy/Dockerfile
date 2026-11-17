# VectorDrugMatch research inference API - CPU image, one immutable model bundle per image (tag = bundle version).
# Built by deploy/build_image.sh from a minimal staging context (serving code + lock file + bundle only).
FROM python:3.10.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 OMP_NUM_THREADS=2
WORKDIR /app
COPY requirements-serving.lock .
RUN pip install --no-deps -r requirements-serving.lock && useradd --create-home --uid 10001 vdm
COPY src/ src/
COPY bundle/ bundle/
ENV VDM_BUNDLE_DIR=/app/bundle VDM_MAX_PAIRS=1000 VDM_MAX_TOP_K=500
USER vdm
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=4).status==200 else 1)"
CMD ["uvicorn", "src.serving.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-server-header", "--no-access-log"]
