FROM node:22-bookworm-slim AS dependencies
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

FROM dependencies AS build
COPY frontend/ ./
ARG CLUTCH_ALLOW_LOCAL_ANONYMOUS=false
ENV CLUTCH_ALLOW_LOCAL_ANONYMOUS=$CLUTCH_ALLOW_LOCAL_ANONYMOUS
ENV NEXT_TELEMETRY_DISABLED=1 CLUTCH_STANDALONE=true
RUN npm run build

FROM node:22-bookworm-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN groupadd --gid 10001 clutch && useradd --uid 10001 --gid clutch clutch
COPY --from=build --chown=clutch:clutch /app/.next/standalone ./
COPY --from=build --chown=clutch:clutch /app/.next/static ./.next/static
USER clutch
EXPOSE 3000
CMD ["node", "server.js"]
