FROM python-datamodels

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-interaction --no-ansi --no-dev

COPY extractstory.py ./
RUN chmod +x extractstory.py

CMD python3 extractstory.py