# In order for this Dockerfile to work it needs to be built from the `services` directory
FROM python:3.11-alpine3.18
ENV PYTHONUNBUFFERED=1
ENV HTTP_PROXY=http://proxy-srv.eu.rvx.is:3128
ENV HTTPS_PROXY=http://proxy-srv.eu.rvx.is:3128
ENV http_proxy=http://proxy-srv.eu.rvx.is:3128
ENV https_proxy=http://proxy-srv.eu.rvx.is:3128
ENV no_proxy=localhost,127.0.0.0/8,172.16.0.0/12,192.168.0.0/16,10.0.0.0/8,.local,.eu.rvx.is
ENV NO_PROXY=localhost,127.0.0.0/8,172.16.0.0/12,192.168.0.0/16,10.0.0.0/8,.local,.eu.rvx.is
ENV LOGLEVEL=DEBUG
ENV SG_URL="https://apavatn.shotgrid.autodesk.com"
ENV WHITEBOARD_SERVER_HOST="0.0.0.0"
ENV WHITEBOARD_SERVER_PORT="45140"

# installs
RUN apk add --no-cache nodejs npm
RUN apk add --update --no-cache git curl build-base libffi-dev
RUN python -m ensurepip
RUN python -m pip install --no-cache --upgrade pip setuptools poetry pip-autoremove && ln -sf pip3 /usr/bin/pip

RUN mkdir /service
COPY whiteboard /service

# Install dependencies with poetry
WORKDIR /service/backend
RUN poetry config virtualenvs.create false
RUN poetry install --no-interaction --no-ansi --only main

WORKDIR /service/frontend
RUN npm ci --no-audit --no-fund
RUN npm run build

# Remove unnecessary packages to make the image smaller
RUN apk del git curl build-base libffi-dev nodejs npm
RUN python -m pip cache purge
RUN pip-autoremove -y setuptools poetry
RUN python -m pip uninstall -y pip pip-autoremove

RUN addgroup -S ayonuser && adduser -SH ayonuser -G ayonuser
RUN chown ayonuser:ayonuser -R /service
RUN chmod 777 -R /service

USER ayonuser

CMD ["python", "-m", "whiteboard"]

