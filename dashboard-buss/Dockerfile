# Etapa 1: Compilación de React (Build)
FROM mirror.gcr.io/library/node:18-alpine AS build
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .
RUN npm run build

# Etapa 2: Servidor Web Ultraligero (Nginx)
FROM mirror.gcr.io/library/nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["/bin/sh", "-c", "sed -i \"s|BACKEND_URL_PLACEHOLDER|${BACKEND_URL}|g\" /usr/share/nginx/html/assets/*.js && nginx -g 'daemon off;'"]
