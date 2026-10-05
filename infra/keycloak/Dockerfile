# Мок IdP «ФСП ID» (§9.3): realm fsp импортируется при каждом старте, данные — во встроенной H2 без volume.
FROM quay.io/keycloak/keycloak:26.4

ENV KC_DB=dev-file \
    KC_CACHE=local \
    KC_HEALTH_ENABLED=true \
    KC_HTTP_RELATIVE_PATH=/fsp-id
RUN /opt/keycloak/bin/kc.sh build

COPY fsp-realm.json /opt/keycloak/data/import/fsp-realm.json

ENTRYPOINT ["/opt/keycloak/bin/kc.sh"]
CMD ["start", "--optimized", "--import-realm"]
