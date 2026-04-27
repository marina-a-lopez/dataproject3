# Etapa 1: Compilación de React (Build)
FROM node:18-alpine AS build
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .
# Usa "npm run build" si es Create React App o Vite
RUN npm run build

# Etapa 2: Servidor Web Ultraligero (Nginx)
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["/bin/sh", "-c", "sed -i \"s|__API_BASE_URL__|$BACKEND_URL|g\" /usr/share/nginx/html/assets/*.js && nginx -g 'daemon off;'"]
