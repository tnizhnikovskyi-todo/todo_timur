FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    RELAY_HOST=0.0.0.0 \
    RELAY_PORT=8000 \
    RELAY_PROFILE=office

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY fake_relay.py genset_model.py ./
COPY profiles ./profiles

EXPOSE 8000
CMD ["python", "fake_relay.py"]
