FROM python-datamodels

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-interaction --no-ansi --no-dev

COPY initdb.py ./
RUN chmod +x initdb.py

CMD python3 initdb.py