FROM nginx:alpine

# Copia todo el contenido de la carpeta static al servidor web de Nginx
COPY . /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]