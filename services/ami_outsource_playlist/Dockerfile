FROM python:3.13-alpine3.24
ENV PYTHONUNBUFFERED=1
ENV HTTP_PROXY=http://proxy-srv.eu.rvx.is:3128
ENV HTTPS_PROXY=http://proxy-srv.eu.rvx.is:3128
ENV http_proxy=http://proxy-srv.eu.rvx.is:3128
ENV https_proxy=http://proxy-srv.eu.rvx.is:3128
ENV no_proxy=localhost,127.0.0.0/8,172.16.0.0/12,192.168.0.0/16,10.0.0.0/8,.local,.eu.rvx.is
ENV NO_PROXY=localhost,127.0.0.0/8,172.16.0.0/12,192.168.0.0/16,10.0.0.0/8,.local,.eu.rvx.is
ENV LOGLEVEL=DEBUG
ENV SG_URL="https://apavatn.shotgrid.autodesk.com"
ENV AMI_OUTSOURCE_PLAYLIST_PLAYLIST_PORT=45142

RUN apk add --update --no-cache git curl build-base libffi-dev
ENV UV_INSTALL_DIR=/usr/local/bin
ENV UV_PYTHON_INSTALL_DIR=/opt/uv/python

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/usr/local/bin:${PATH}"

RUN mkdir /service
COPY ami_create_delivery_playlist/pyproject.toml /service/pyproject.toml
WORKDIR /service

RUN uv sync

RUN apk del git curl build-base libffi-dev
RUN uv cache clean

RUN addgroup -S ayonuser && adduser -S ayonuser -G ayonuser

COPY ami_common /service
COPY ami_create_delivery_playlist/ami_create_delivery_playlist /service/ami_create_delivery_playlist

RUN chown ayonuser:ayonuser -R /service
RUN chown ayonuser:ayonuser -R /home/ayonuser

USER ayonuser
CMD ["uv", "run", "-m", "ami_outsource_playlist"]
