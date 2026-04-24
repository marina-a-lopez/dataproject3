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
CMD ["nginx", "-g", "daemon off;"]
