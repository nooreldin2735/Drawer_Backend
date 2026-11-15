FROM nginx:1.27-alpine

# Copy customized Nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Expose standard HTTP port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

