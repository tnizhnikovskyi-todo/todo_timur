FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN useradd --uid 10002 --create-home collector
WORKDIR /app
COPY requirements.txt pyproject.toml ./
# pytest і тестові утиліти в образ не потрібні, але лишаються в requirements (єдиний файл)
RUN pip install --no-cache-dir -r requirements.txt
COPY collector ./collector
RUN pip install --no-cache-dir --no-deps . && mkdir -p /app/state && chown -R collector:collector /app/state
USER 10002:10002
EXPOSE 8080 9108
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9108/health', timeout=3)"]
CMD ["python", "-m", "collector", "run"]
