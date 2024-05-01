FROM python-datamodels

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-interaction --no-ansi --no-dev

COPY producenews.py sources.json ./
RUN chmod +x producenews.py

CMD python3 producenews.py