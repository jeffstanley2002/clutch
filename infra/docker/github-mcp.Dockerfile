FROM python:3.11.16-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir .

RUN addgroup --system --gid 10001 clutch \
    && adduser --system --uid 10001 --ingroup clutch clutch \
    && chown -R clutch:clutch /app

USER 10001:10001
EXPOSE 8001

CMD ["clutch-github-mcp"]
