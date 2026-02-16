# pad

`pad` is an ultralight collaborative scratchpad with live text sync and simple file upload sharing.

## Setup

### Start it

```bash
cd /home/saahas/pad
uv run pad.py
```

Open `http://localhost:8000`.

### Run as a service (systemd)

```bash
sudo tee /etc/systemd/system/pad.service >/dev/null <<'UNIT'
[Unit]
Description=pad service
After=network.target

[Service]
User=saahas
WorkingDirectory=/home/saahas/pad
ExecStart=/home/saahas/.local/bin/uv run pad.py
Restart=always

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable --now pad
sudo systemctl status pad
```

## Optional: Nginx integration

Use Nginx in front of the app and proxy everything to `pad` (including `/media/*` files):

```nginx
server {
    listen 80;
    server_name pad.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```
