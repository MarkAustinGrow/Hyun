#!/bin/bash
# Script to set up Nginx for serving videos from the Samba share

# Exit on error
set -e

# Check if running as root
if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root" >&2
    exit 1
fi

# Install Nginx if not already installed
if ! command -v nginx &> /dev/null; then
    echo "Installing Nginx..."
    apt update
    apt install -y nginx
else
    echo "Nginx is already installed."
fi

# Create Nginx configuration for serving videos
echo "Creating Nginx configuration..."
cat > /etc/nginx/sites-available/videos << 'EOF'
server {
    listen 80;
    server_name hyun.club;

    # Logging configuration
    access_log /var/log/nginx/hyun.club-access.log;
    error_log /var/log/nginx/hyun.club-error.log;

    # Serve videos from the Samba share
    location /videos/ {
        alias /data/videos/;
        autoindex off;
        
        # Set appropriate MIME types
        types {
            video/mp4 mp4;
            video/webm webm;
            video/ogg ogv;
        }
        
        # Enable CORS for video playback in browsers
        add_header Access-Control-Allow-Origin "*";
        add_header Access-Control-Allow-Methods "GET, OPTIONS";
        add_header Access-Control-Allow-Headers "Origin, X-Requested-With, Content-Type, Accept, Range";
        
        # Cache settings
        add_header Cache-Control "public, max-age=3600";
        expires 1h;
        
        # Enable byte-range requests for video seeking
        add_header Accept-Ranges bytes;
    }

    # Basic server configuration
    location / {
        return 404;
    }
}
EOF

# Enable the site
echo "Enabling the site..."
ln -sf /etc/nginx/sites-available/videos /etc/nginx/sites-enabled/

# Test the configuration
echo "Testing Nginx configuration..."
nginx -t

# Restart Nginx
echo "Restarting Nginx..."
systemctl restart nginx

# Allow HTTP through the firewall
echo "Configuring firewall..."
if command -v ufw &> /dev/null; then
    ufw allow 'Nginx HTTP'
    echo "Firewall configured."
else
    echo "UFW not installed. Please manually configure your firewall to allow HTTP traffic."
fi

echo "Nginx setup complete!"
echo "Videos are now accessible at: http://hyun.club/videos/"
echo ""
echo "To test, you can use:"
echo "curl -I http://hyun.club/videos/test.mp4"
echo ""
echo "Note: Make sure DNS is properly configured to point hyun.club to this server's IP address."
