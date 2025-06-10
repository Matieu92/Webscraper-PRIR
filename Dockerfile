# Użyj oficjalnego obrazu Pythona
FROM python:3.9-slim

# Ustaw katalog roboczy
WORKDIR /app

# Skopiuj pliki zależności
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Skopiuj resztę projektu
COPY . .

# Ustaw zmienną środowiskową dla Flask
ENV FLASK_APP=main.py
ENV FLASK_RUN_HOST=0.0.0.0

# Uruchom aplikację
CMD ["flask", "run", "--host=0.0.0.0"]