# nginx/Dockerfile
FROM nginx:alpine

# Копируем конфиг
COPY nginx.conf /etc/nginx/nginx.conf

# Создаём папки для логов
RUN mkdir -p /var/log/nginx

# Открываем порт
EXPOSE 80

# Запускаем nginx в фоне
CMD ["nginx", "-g", "daemon off;"]
