FROM python:3.11-slim

WORKDIR /app

# Runtime tools: ping/traceroute for diagnostics, and shorewall so firewall
# changes written to the host-mounted /etc/shorewall can actually be applied.
# Requires network_mode: host + cap NET_ADMIN (see docker-compose.yml) so the
# reload manipulates the host's iptables, not an empty container namespace.
RUN apt-get update \
    && apt-get install -y --no-install-recommends iputils-ping traceroute shorewall \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
ENV OMR_DASHBOARD_DATA_DIR=/var/opt/omr-dashboard
CMD ["uvicorn", "omr_dashboard_api:app", "--host", "0.0.0.0", "--port", "8000"]
