FROM nginx:alpine

COPY . /usr/share/nginx/html

EXPOSE 80

# Reemplaza el placeholder con la URL real del backend al arrancar
CMD ["/bin/sh", "-c", "sed -i \"s|BACKEND_URL_PLACEHOLDER|${BACKEND_URL}|g\" /usr/share/nginx/html/app.js && nginx -g 'daemon off;'"]
