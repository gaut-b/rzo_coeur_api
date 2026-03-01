FROM almir/webhook

# Switch to root to install packages
USER root

# Install envsubst (provided by gettext package)
RUN apk add --no-cache gettext

# Switch back to the default non-root user
USER webhook

# Copy the hooks template
COPY hooks.json /etc/webhook/hooks.json.tpl

# Generate hooks.json from template at startup using envsubst,
# then start the webhook server
CMD ["/bin/sh", "-c", "envsubst < /etc/webhook/hooks.json.tpl > /tmp/hooks.json && webhook -hooks=/tmp/hooks.json -verbose"]
