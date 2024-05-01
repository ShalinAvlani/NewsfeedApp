FROM python:3.11.9

RUN pip3 install poetry

ENV POETRY_VIRTUALENVS_CREATE=false
ENV PYTHONUNBUFFERED=0

WORKDIR /app/datamodels

COPY articleobjects.py ./

CMD ["python3"]