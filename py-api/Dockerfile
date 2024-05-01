FROM python-datamodels

WORKDIR /app

EXPOSE 80

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-interaction --no-ansi --no-dev

COPY main.py ./
RUN chmod +x main.py

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]