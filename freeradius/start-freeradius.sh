#!/bin/sh
set -eu
mkdir -p /etc/freeradius/3.0/clients.d/pamirnet
touch /etc/freeradius/3.0/clients.d/pamirnet/pamirnet.conf
chmod 600 /etc/freeradius/3.0/clients.d/pamirnet/pamirnet.conf
exec freeradius -f
