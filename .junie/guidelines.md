Project-specific development guidelines for AYON Shotgrid integration

Audience: Advanced contributors familiar with AYON, Python packaging, Docker, and pytest.

1) Build and configuration instructions

- Packaging the addon for an AYON server
  - The package version is defined in package.py (root).
  - Build the distributable zip with: python create_package.py
    - Output: ayon-shotgrid/package/shotgrid-{version}.zip
    - Upload the zip on your AYON server at Settings > Bundles (/settings/bundles) and restart when prompted.

- Server-side addon enablement
  - After restart: Settings > Bundles, create/duplicate a bundle, select addon "shotgrid" and the built version; mark the bundle as Production.
  - Configure Settings > Studio settings > Shotgrid:
    - Shotgrid URL: your SG instance base URL.
    - Shotgrid API Secret: create a Secret at Settings > Secrets with script_name and script_api_key (per Shotgrid docs) and select it here.
    - Project code field: defaults to code (customizable via sg_project_code_field).
    - Service polling interval: How often (sec) to query the Shotgrid DB.

- Local service execution without Docker
  - Use service_tools to run services from a virtual environment:
    - Make a venv and install service tools editable:
      - cd service_tools
      - make createenv  # creates service_tools/venv and installs editable package
    - Run a single service:
      - make processor [--variant development]
      - make leecher [--variant development]
      - make transmitter [--variant development]
    - Run all three concurrently:
      - make services [--variant development]
    - Notes:
      - AYON_ADDON_NAME and AYON_ADDON_VERSION are set by the Makefile based on package.py.
      - The variant is exported via ayon_api.constants.DEFAULT_VARIANT_ENV_KEY; use --variant to target a specific server settings variant.

- Local service execution with Docker
  - From services/, use per-service Dockerfiles and the shared Makefile.
  - Build: make SERVICE=<processor|leecher|transmitter> build
  - Dev run (bind mounts, env from .env): make SERVICE=<name> dev
  - Minimal .env for services/*/dev:
    - AYON_API_KEY=<service user API key>
    - AYON_SERVER_URL=<your AYON URL>
    - PYTHONDONTWRITEBYTECODE=1

- Desktop client integration
  - On first run, a Shotgrid login (username) is requested; this is used for publishing.

2) Testing information

- What the test suite covers
  - Location: services/tests
  - Tests assert core sync logic between AYON and Shotgrid using Mockgun (in-memory SG) and pytest-ayon fixtures for AYON. They do NOT require a FLOW/Shotgrid instance.
  - Key fixtures (services/tests/conftest.py):
    - mockgun_project: in-memory SG project with sg_ayon_auto_sync enabled.
    - hub_and_project: wires AyonShotgridHub to a mocked EntityHub and the Mockgun project.
  - Additional fixtures imported from pytest_ayon.plugin: empty_project, etc.

- Python and dependency requirements
  - For docs/build tooling at repo root: Python >= 3.11 (per root pyproject.toml).
  - For running services tests via service_tools: Python >= 3.10 (as noted in README). Using 3.11+ also works in practice with current dependencies.

- Recommended way to run tests (cross-platform wrappers)
  - Windows (PowerShell):
    - .\service_tools\manage.ps1 run-tests
      - This installs editable deps with the [test] extra and runs pytest for services/tests.
  - Linux/macOS (Make):
    - ./service_tools/make runtests  (alias for make -C service_tools runtests)
      - Creates service_tools/venv_test if missing, installs -e "." with [test], and runs pytest services/tests.
    - Note: The Makefile currently creates venv_test but activates venv during runtests. If venv is absent, run make createenv first, or activate your own venv and run pytest directly (below).

- Running tests directly with pytest
  - Create and activate a virtual environment of your choice, then install test deps:
    - python -m pip install -e service_tools/.[test]
  - Execute the suite:
    - python -m pytest services/tests -q
  - Run a subset (examples):
    - python -m pytest services/tests/test_sg_base.py::test_hub_initialization -q
    - python -m pytest -k match_ayon_hierarchy -q

- Environment required by tests
  - No real Shotgrid needed — Mockgun schemas are preloaded in services/tests/__init__.py.
  - AYON server is not contacted by unit tests; pytest_ayon provides in-memory fixtures.
  - You do not need AYON_API_KEY or AYON_SERVER_URL to run services/tests locally.

- Adding new tests
  - Place tests under services/tests in a meaningful subpackage (e.g., update_from_ayon/).
  - Reuse existing fixtures: import empty_project from pytest_ayon.plugin when you need a blank AYON project; or use hub_and_project from services/tests/conftest.py when you need both Mockgun and an AyonShotgridHub.
  - Example skeleton:
    - File: services/tests/my_area/test_something.py
      from pytest_ayon.plugin import empty_project  # noqa: F401
      def test_smoke(hub_and_project):
          data = hub_and_project["hub"].sg_project_name
          assert data == "test_project"
  - Run it with: python -m pytest services/tests/my_area/test_something.py -q

- Simple demonstration test run (no new files created)
  - To validate your setup, run an existing lightweight test:
    - python -m pytest services/tests/test_sg_base.py::test_hub_initialization -q
  - Expected: 1 passed

3) Additional development information

- Code layout overview
  - server/: AYON Backend Addon (settings and server bundle integration).
  - frontend/: Settings tab for Shotgrid within AYON server UI.
  - client/: Desktop integration hooks for publishing.
  - services/: Three background daemons (leecher, processor, transmitter) plus shared logic in services/shotgrid_common and service-specific entrypoints.
  - service_tools/: Developer helpers to run services locally and to run tests (Makefile, main.py, PowerShell script).

- Services bootstrap details
  - service_tools/main.py adds services/shotgrid_common and services/<service> to sys.path and dispatches to <service>.service_main().
  - DEFAULT_VARIANT_ENV_KEY from ayon_api.constants is used to select the settings variant; pass --variant to Makefile targets or scripts.

- Common pitfalls and tips
  - Version sourcing: Both Docker builds and service_tools pick version from package.py. Always update package.py when cutting releases.
  - Secrets: Create the Shotgrid API script and store script_name/script_api_key in Settings > Secrets; reference it in the Shotgrid settings page.
  - Project auto-sync flag: Only projects with the "Ayon Auto Sync" boolean enabled in Shotgrid are considered by leecher and transmitter.
  - When running services locally without Docker, ensure your sys.path includes services/shotgrid_common alongside the chosen service (service_tools takes care of this).
  - If you cannot use Makefiles, see README for equivalent docker and python invocations; manage.ps1 provides Windows-friendly wrappers.
  - Tests rely on pytest_ayon and shotgun_api3[Mockgun]; ensure the [test] extras are installed from service_tools.

- Code style and linting
  - ruff is configured at ruff.toml. Favor its defaults and fixers for quick iteration. Use it pre-commit if desired.

- Docs and site generation
  - mkdocs configuration lives at mkdocs.yml; dependencies are listed in the root pyproject.toml for local docs work. Generate docs with mkdocs serve/build if needed.

Housekeeping for this note
- No transient files were added as part of creating this guideline; only .junie/guidelines.md was created per the task requirement.
