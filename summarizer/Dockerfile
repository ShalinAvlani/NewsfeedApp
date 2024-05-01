FROM python-datamodels

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-interaction --no-ansi --no-dev

COPY summarizestory.py ./
RUN chmod +x summarizestory.py

CMD python3 summarizestory.py