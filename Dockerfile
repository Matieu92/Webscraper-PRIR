# Użyj oficjalnego obrazu Pythona
FROM python:3.9-slim

# Aktualizacja pakietów + SQLite

RUN apt-get update
RUN apt-get install sqlite3

# Ustaw katalog roboczy
WORKDIR /app

# Skopiuj pliki zależności
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Skopiuj resztę projektu
COPY . .

# Inicjalizacja bazy SQLite z debugowaniem
RUN echo "Initializing database..." && \
    sqlite3 /app/frontend/users.db < /app/frontend/init.sql && \
    echo "Database initialized successfully" || echo "Database initialization failed"

# Ustaw zmienną środowiskową dla Flask
ENV FLASK_APP=main.py
ENV FLASK_RUN_HOST=0.0.0.0

# Uruchom aplikację
CMD ["flask", "run", "--host=0.0.0.0"]