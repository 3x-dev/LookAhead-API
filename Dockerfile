FROM python:3.11.6-slim-bullseye

ENV APP_HOME /app
ENV PORT 8080
ENV PYTHONUNBUFFERED True
ENV PYTHONDONTWRITEBYTECODE True

COPY requirements.txt .

RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . $APP_HOME
WORKDIR $APP_HOME

EXPOSE $PORT

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT}
