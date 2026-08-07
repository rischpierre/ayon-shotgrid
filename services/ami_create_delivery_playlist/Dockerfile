# Build from services directory: docker build -t ami-create-delivery-playlist -f ami_create_delivery_playlist/Dockerfile .
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
ENV AMI_CREATE_DELIVERY_PLAYLIST_PORT=45141

# Install python/pip and uv
RUN apk add --update --no-cache git curl build-base libffi-dev
ENV UV_INSTALL_DIR=/usr/local/bin
ENV UV_PYTHON_INSTALL_DIR=/opt/uv/python

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/usr/local/bin:${PATH}"

# Setup service directory
RUN mkdir /service
COPY ami_create_delivery_playlist/pyproject.toml /service/pyproject.toml
WORKDIR /service

# Install dependencies
RUN uv sync

# Remove build dependencies
RUN apk del git curl build-base libffi-dev
RUN uv cache clean

# Create non-root user
RUN addgroup -S ayonuser && adduser -S ayonuser -G ayonuser

# Copy service code
COPY ami_common /service
COPY ami_create_delivery_playlist/ami_create_delivery_playlist /service/ami_create_delivery_playlist

# Set ownership
RUN chown ayonuser:ayonuser -R /service
RUN chown ayonuser:ayonuser -R /home/ayonuser

USER ayonuser
CMD ["uv", "run", "-m", "ami_create_delivery_playlist"]
