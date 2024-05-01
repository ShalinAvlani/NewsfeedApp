FROM python-datamodels

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-interaction --no-ansi --no-dev

COPY generatetopics.py ./
RUN chmod +x generatetopics.py

CMD python3 generatetopics.py