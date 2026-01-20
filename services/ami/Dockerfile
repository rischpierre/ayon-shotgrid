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
ENV AMI_SERVER_HOST="0.0.0.0"
ENV AMI_SERVER_PORT="45139"

# Install python/pip and uv
RUN apk add --update --no-cache git curl build-base libffi-dev
ENV UV_INSTALL_DIR=/usr/local/bin
ENV UV_PYTHON_INSTALL_DIR=/opt/uv/python

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/usr/local/bin:${PATH}"


# Create Working directory `/service` and copy `transmitter`
RUN mkdir /service
COPY ami/pyproject.toml /service/pyproject.toml
WORKDIR /service

# Install dependencies with uv
RUN uv sync

# Remove unnecessary packages to make the image smaller
RUN apk del git curl build-base libffi-dev
RUN uv cache clean

# Create a group and user: ayonuser with home directory
RUN addgroup -S ayonuser && adduser -S ayonuser -G ayonuser
RUN chmod -R 775 /opt/uv

COPY shotgrid_common /service
COPY ami/ami /service/ami

# Set ownership after all files are copied
RUN chown ayonuser:ayonuser -R /service
RUN chown ayonuser:ayonuser -R /home/ayonuser

# Tell docker that all future commands should run as the appuser user
USER ayonuser

CMD ["uv", "run", "-m", "ami"]

