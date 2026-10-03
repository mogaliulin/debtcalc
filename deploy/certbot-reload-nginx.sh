#!/bin/sh
# Хук certbot: после продления сертификата перечитать его в nginx без остановки сайта.
# Установка на сервере (путь к проекту поправьте при необходимости):
#   sudo install -m 755 deploy/certbot-reload-nginx.sh /etc/letsencrypt/renewal-hooks/deploy/reload-debtcalc.sh
set -e
PROJECT_DIR="${PROJECT_DIR:-/opt/debtcalc}"
cd "$PROJECT_DIR"
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T frontend nginx -s reload
