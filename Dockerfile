FROM ghcr.io/astral-sh/uv:0.12.6-python3.13-trixie-slim AS build

WORKDIR /workspace

COPY . .

RUN uv lock --check
RUN uv build --out-dir /artifacts

FROM scratch AS artifacts

COPY --from=build /artifacts/*.whl /
COPY --from=build /artifacts/*.tar.gz /
