FROM python-datamodels

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-interaction --no-ansi --no-dev

COPY settopic.py ./
RUN chmod +x settopic.py

ENTRYPOINT python3 settopic.py