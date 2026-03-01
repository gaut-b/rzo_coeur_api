FROM almir/webhook

# Install envsubst (provided by gettext package)
RUN apk add --no-cache gettext

# Copy the hooks template
COPY hooks.json /etc/webhook/hooks.json.tpl

# Generate hooks.json from template at startup using envsubst,
# then start the webhook server
CMD ["/bin/sh", "-c", "envsubst < /etc/webhook/hooks.json.tpl > /etc/webhook/hooks.json && webhook -hooks=/etc/webhook/hooks.json -verbose"]
