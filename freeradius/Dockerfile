FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        freeradius \
        freeradius-rest \
        freeradius-utils \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY clients.conf /etc/freeradius/3.0/clients.conf
COPY pamirnet_rest /etc/freeradius/3.0/mods-available/pamirnet_rest
COPY start-freeradius.sh /usr/local/bin/start-freeradius.sh
COPY watch-clients.sh /usr/local/bin/watch-clients.sh

RUN chmod +x /usr/local/bin/start-freeradius.sh /usr/local/bin/watch-clients.sh \
    && ln -s /etc/freeradius/3.0/mods-available/pamirnet_rest \
        /etc/freeradius/3.0/mods-enabled/pamirnet_rest \
    && sed -i '/^[[:space:]]*authorize[[:space:]]*{/a\        pamirnet_rest' \
        /etc/freeradius/3.0/sites-enabled/default \
    && sed -i '/^[[:space:]]*post-auth[[:space:]]*{/a\        pamirnet_rest' \
        /etc/freeradius/3.0/sites-enabled/default \
    && mkdir -p /etc/freeradius/3.0/clients.d/pamirnet \
    && touch /etc/freeradius/3.0/clients.d/pamirnet/pamirnet.conf

EXPOSE 1812/udp 1813/udp
CMD ["/usr/local/bin/start-freeradius.sh"]
