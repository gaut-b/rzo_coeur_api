FROM python:3.13.0-alpine3.20

ENV PYTHONUNBUFFERED 1

COPY ./requirements.txt /requirements.txt

ENV PATH="/py/bin:$PATH"
RUN python -m venv /py && \
    pip install --upgrade pip && \
    apk add --update --upgrade --no-cache postgresql-client && \
    apk add --update --upgrade --no-cache --virtual .tmp \
        build-base postgresql-dev

RUN pip install -r /requirements.txt && apk del .tmp

# copy entrypoint.sh

COPY . /api
WORKDIR /api
RUN chmod +x /api/entrypoint.sh


# run entrypoint.sh
ENTRYPOINT ["/api/entrypoint.sh"]