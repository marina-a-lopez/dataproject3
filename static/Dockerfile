FROM mirror.gcr.io/library/nginx:alpine

COPY . /usr/share/nginx/html

# Copia la configuración personalizada de Nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

# Reemplaza el placeholder con la URL real del backend al arrancar
CMD ["/bin/sh", "-c", "sed -i \"s|BACKEND_URL_PLACEHOLDER|${BACKEND_URL}|g\" /usr/share/nginx/html/app.js && nginx -g 'daemon off;'"]
