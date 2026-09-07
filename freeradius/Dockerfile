FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends freeradius freeradius-utils ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY clients.conf /etc/freeradius/3.0/clients.conf
COPY start-freeradius.sh /usr/local/bin/start-freeradius.sh
COPY watch-clients.sh /usr/local/bin/watch-clients.sh
RUN chmod +x /usr/local/bin/start-freeradius.sh /usr/local/bin/watch-clients.sh

EXPOSE 1812/udp 1813/udp
CMD ["/usr/local/bin/start-freeradius.sh"]
