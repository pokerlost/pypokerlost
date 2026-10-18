# syntax=docker/dockerfile:1.27.1@sha256:4edf897a3ffa55b89f906fc8cc78afdb3f1834cc9c7083565e611a8a7d5fe99e
FROM ghcr.io/astral-sh/uv:0.12.15@sha256:62f8c047d0a0e9ece6b53fc63df902585a67a47a7f318ddec4a37db586edc8e3 AS uv
FROM python:3.14.7-slim-trixie@sha256:82bc3c539b8813ada9d68c63b40158fa002f7f33de9bf3312a3dfdc0620dff56 AS build
WORKDIR /workspace
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never PYTHONDONTWRITEBYTECODE=1
COPY pyproject.toml uv.lock README.md .gitignore ./
RUN --mount=type=cache,id=sdk-development,target=/root/.cache/uv,sharing=locked \
    uv sync --locked --all-groups --no-install-project
COPY . .
RUN --mount=type=cache,id=sdk-build,target=/root/.cache/uv,sharing=locked \
    uv build --no-build-isolation --wheel --sdist --out-dir /artifacts

FROM build AS test
RUN uv pip install --python /workspace/.venv/bin/python --no-deps /artifacts/*.whl
WORKDIR /checks
COPY --exclude=pypokerlost --exclude=pypokerlost/** --chmod=u=rwX,go=rX . ./
ENV PATH="/workspace/.venv/bin:$PATH" COVERAGE_FILE=/checks/coverage/.coverage
USER 65532:65532
CMD ["python", "-m", "pytest", "--import-mode=importlib", "--cov", "--cov-report=term-missing", "--cov-report=json", "--cov-report=xml", "-p", "no:cacheprovider"]

FROM scratch AS artifacts
COPY --from=build /artifacts/ /
