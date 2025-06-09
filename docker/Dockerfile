FROM python:3.12.9 AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

FROM builder AS prod
WORKDIR /app
# Copy the rest of the application code
COPY . .
RUN uv export --no-dev --no-hashes --output-file ./requirements.lock && \
    uv pip install --no-cache --system -r requirements.lock && \
    uv cache clean

# Expose the port the app runs on
EXPOSE 8100

# Define the command to run your app
CMD ["python", "server.py"]
