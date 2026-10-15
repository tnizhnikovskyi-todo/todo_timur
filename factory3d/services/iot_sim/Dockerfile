FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN useradd --uid 10001 --create-home sim
WORKDIR /app
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt
COPY iot_sim ./iot_sim
COPY catalog ./catalog
RUN mkdir -p /app/state && chown -R sim:sim /app/state
USER 10001:10001
EXPOSE 8090
# curl в образі немає (X-90): перевірка через urllib; degraded/locked вважаються здоровими (HTTP 200)
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8090/sim/v1/health', timeout=3)"]
CMD ["python", "-m", "iot_sim", "run"]
