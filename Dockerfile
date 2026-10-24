FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app ./app
# Lesbar für den App-Benutzer, egal mit welchen Rechten die Dateien ausgecheckt wurden
RUN chmod -R a+rX /srv/app
RUN useradd --create-home parawerk && mkdir -p /data && chown parawerk /data
EXPOSE 8080
# Startet als root nur, um das Volume /data (Verbrauchs-Datenbank) dem App-Benutzer zu geben; die App selbst läuft als parawerk.
CMD ["sh", "-c", "chown parawerk /data && exec setpriv --reuid=parawerk --regid=parawerk --init-groups uvicorn app.main:app --host 0.0.0.0 --port 8080 --proxy-headers --forwarded-allow-ips '*'"]
