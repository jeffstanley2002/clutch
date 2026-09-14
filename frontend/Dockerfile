FROM python:3.11.16-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_HEADLESS=true

WORKDIR /app

COPY frontend/requirements.txt ./frontend/requirements.txt
RUN python -m pip install --no-cache-dir -r frontend/requirements.txt

COPY frontend ./frontend
COPY .streamlit/config.toml ./.streamlit/config.toml

RUN addgroup --system --gid 10001 clutch \
    && adduser --system --uid 10001 --ingroup clutch clutch \
    && chown -R clutch:clutch /app

USER 10001:10001
EXPOSE 8501

CMD ["streamlit", "run", "frontend/app.py", "--server.address=0.0.0.0", "--server.port=8501"]
