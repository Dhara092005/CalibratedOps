FROM caddy:2 AS gateway
FROM python:3.14-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=10000
WORKDIR /app
COPY --from=gateway /usr/bin/caddy /usr/bin/caddy
COPY calibrated_ops ./calibrated_ops
COPY scripts ./scripts
RUN mkdir -p /var/data
EXPOSE 10000
CMD ["python", "-m", "calibrated_ops.hosted"]
