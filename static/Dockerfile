FROM nginx:alpine

# Copia todo el contenido de la carpeta static al servidor web de Nginx
COPY . /usr/share/nginx/html

# Copia la configuración personalizada de Nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]