# --- build stage --------------------------------------------------------------
# CGO is required because the real whatsmeow path uses mattn/go-sqlite3.
FROM golang:1.26-bookworm AS build

ENV CGO_ENABLED=1
WORKDIR /src

# Cache module downloads.
COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN go build -trimpath -ldflags="-s -w" -o /out/wa-bridge .

# --- runtime stage ------------------------------------------------------------
FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=build /out/wa-bridge /app/wa-bridge

# Defaults: FAKE mode on so the container is runnable without a phone/QR.
# The whatsmeow session is persisted under /data (mount a volume there).
ENV PORT=8081 \
    BRIDGE_FAKE=1 \
    WHATSAPP_SESSION_DIR=/data

EXPOSE 8081
VOLUME ["/data"]

ENTRYPOINT ["/app/wa-bridge"]
