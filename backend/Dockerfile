FROM python:3.11-slim

WORKDIR /app

# Runtime tools used by diagnostics (ping, traceroute) and shorewall control.
RUN apt-get update \
    && apt-get install -y --no-install-recommends iputils-ping traceroute \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
ENV OMR_DASHBOARD_DATA_DIR=/var/opt/omr-dashboard
CMD ["uvicorn", "omr_dashboard_api:app", "--host", "0.0.0.0", "--port", "8000"]
