# Addon version resolution
# - You can override the version used for tagging by passing VERSION to make.
# - If VERSION is not provided, it falls back to the value from ../package.py.
# Examples:
#   make build SERVICE=leecher VERSION=prod
#   make build SERVICE=processor VERSION=0.2.3
ADDON_VERSION := $(if $(VERSION),$(VERSION),$(shell grep "version" ../package.py | cut -d' ' -f3 | tr -d '"'))
IMAGE := docker-internal.eu.rvx.is/rvx/ayon-shotgrid-$(SERVICE):$(ADDON_VERSION)
SERVICE = $(error Please specify the service to build with 'SERVICE', for example: 'make build SERVICE=leecher')

default:
	@echo ""
	@echo "AYON Shotgrid $(ADDON_VERSION) Service Builder"
	@echo ""
	@echo "Usage: make SERVICE=[service-name] [target]"
	@echo ""
	@echo "Version:"
	@echo "  Override with: VERSION=<value> (defaults to version from ../package.py when omitted)"
	@echo "  Example: make SERVICE=leecher VERSION=prod build"
	@echo ""
	@echo "Passing SERVICE is required for any of the targets to work, possible services:"
	@echo ""
	@echo "  leecher - Fetch Shotgrid Events into AYON."
	@echo "  processor - Process 'shotgrid.event's in AYON."
	@echo "  transmitter - Push AYON events to Shotgrid."
	@echo "  ami - Handle action menu items from shotgrid"
	@echo "  whiteboard - kanban webpage to assign artists to shots"
	@echo ""
	@echo "Targets:"
	@echo "  build        Build docker image."
	@echo "  build-all    Build docker image for 'leecher', 'procesor', 'transmitter', 'ami' and 'whiteboard'."
	@echo "  dist         Push docker image to DockerHub."
	@echo "  dist-all     Push docker image for 'leecher', 'procesor', 'transmitter', 'ami' and 'whiteboard'."
	@echo "  clean        Remove local images."
	@echo "  clean-build  Remove local images and build without docker cache."
	@echo "  dev          Run a service locally"


build:
	docker build -t $(IMAGE) -f $(SERVICE)/Dockerfile .

build-all:
	docker build -t docker-internal.eu.rvx.is/rvx/ayon-shotgrid-leecher:$(ADDON_VERSION) -f ./leecher/Dockerfile .
	docker build -t docker-internal.eu.rvx.is/rvx/ayon-shotgrid-processor:$(ADDON_VERSION) -f ./processor/Dockerfile .
	docker build -t docker-internal.eu.rvx.is/rvx/ayon-shotgrid-transmitter:$(ADDON_VERSION) -f ./transmitter/Dockerfile .
	docker build -t docker-internal.eu.rvx.is/rvx/ayon-shotgrid-ami:$(ADDON_VERSION) -f ./ami/Dockerfile .
	docker build -t docker-internal.eu.rvx.is/rvx/ayon-shotgrid-whiteboard:$(ADDON_VERSION) -f ./whiteboard/Dockerfile .

dist:
	docker push $(IMAGE)

dist-all:
	docker push docker-internal.eu.rvx.is/rvx/ayon-shotgrid-leecher:$(ADDON_VERSION)
	docker push docker-internal.eu.rvx.is/rvx/ayon-shotgrid-processor:$(ADDON_VERSION)
	docker push docker-internal.eu.rvx.is/rvx/ayon-shotgrid-transmitter:$(ADDON_VERSION)
	docker push docker-internal.eu.rvx.is/rvx/ayon-shotgrid-ami:$(ADDON_VERSION)
	docker push docker-internal.eu.rvx.is/rvx/ayon-shotgrid-whiteboard:$(ADDON_VERSION)

clean:
	if docker images "$(IMAGE)"; then \
		docker rmi $(IMAGE); \
	fi

clean-build: clean
	docker build --no-cache -t $(IMAGE) -f $(SERVICE)/Dockerfile .

clean-build-all:
	docker build --no-cache -t docker-internal.eu.rvx.is/rvx/ayon-shotgrid-leecher:$(ADDON_VERSION) -f ./leecher/Dockerfile .
	docker build --no-cache -t docker-internal.eu.rvx.is/rvx/ayon-shotgrid-processor:$(ADDON_VERSION) -f ./processor/Dockerfile .
	docker build --no-cache -t docker-internal.eu.rvx.is/rvx/ayon-shotgrid-transmitter:$(ADDON_VERSION) -f ./transmitter/Dockerfile .
	docker build --no-cache -t docker-internal.eu.rvx.is/rvx/ayon-shotgrid-whiteboard:$(ADDON_VERSION) -f ./whiteboard/Dockerfile .


dev:
	-ln -s $(CURDIR)/shotgrid_common/* $(CURDIR)/$(SERVICE)
	-docker run --rm -u ayonuser -ti \
		-v $(CURDIR)/shotgrid_common:$(CURDIR)/shotgrid_common:Z \
		-v $(CURDIR)/$(SERVICE):/service:Z \
		--env-file $(CURDIR)/$(SERVICE)/.env \
		--env AYON_ADDON_NAME=shotgrid \
		--env AYON_ADDON_VERSION=$(ADDON_VERSION) \
		--attach=stdin \
		--attach=stdout \
		--attach=stderr \
		$(IMAGE) python -m $(SERVICE)

	find $(CURDIR)/$(SERVICE) -type l -delete

dev-ami:
	-ln -s $(CURDIR)/shotgrid_common/* $(CURDIR)/ami
	-docker run --rm -u ayonuser -ti \
		-v $(CURDIR)/shotgrid_common:/service/shotgrid_common:Z \
		-v $(CURDIR)/ami/ami:/service/ami:Z \
		--env-file $(CURDIR)/ami/.env \
		--env AYON_ADDON_NAME=shotgrid \
		--env AYON_ADDON_VERSION=$(ADDON_VERSION) \
		--attach=stdin \
		--attach=stdout \
		--attach=stderr \
		$(IMAGE) uv run -m ami

	find $(CURDIR)/$(SERVICE) -type l -delete

shell:
	docker run --rm -u ayonuser -ti -v $(CURDIR)/$(SERVICE)/$(SERVICE):/service:Z $(IMAGE) /bin/sh

shell-ami:
	docker run --rm -u ayonuser -ti \
		-v $(CURDIR)/shotgrid_common:/service/shotgrid_common:Z \
		-v $(CURDIR)/ami/ami:/service/ami:Z \
		$(IMAGE) /bin/sh

dev-whiteboard:
	docker build -t whiteboard:dev -f ./whiteboard/Dockerfile .
	echo "open in browser: http://localhost:45140"
	docker run --rm -p 45140:45140 \
		--env-file $(CURDIR)/whiteboard/.env \
		--env AYON_ADDON_NAME=shotgrid \
		--env AYON_ADDON_VERSION=$(ADDON_VERSION) \
		whiteboard:dev
