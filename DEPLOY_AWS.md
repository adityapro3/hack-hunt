# AWS Deployment (Public IP, Nginx :80, PM2, Ollama)

These commands are for a fresh Ubuntu EC2 machine.

## 1) Install system packages

```bash
sudo apt update
sudo apt install -y git curl nginx python3 python3-venv python3-pip nodejs npm
sudo npm install -g pm2
```

## 2) Install PostgreSQL

```bash
sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable postgresql
sudo systemctl start postgresql

sudo -u postgres psql -c "CREATE USER oppora WITH PASSWORD 'oppora_password';"
sudo -u postgres psql -c "CREATE DATABASE hack_hunt OWNER oppora;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE hack_hunt TO oppora;"
```

## 3) Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable ollama
sudo systemctl start ollama
ollama pull nomic-embed-text:v1.5
```

## 4) Clone project and install dependencies

```bash
git clone <YOUR_REPO_URL> Oppora
cd Oppora

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium

cd frontend
npm install
npm run build
cd ..
```

## 5) Configure environment

```bash
cp .env.example .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Open `.env` and set at least:

- `API_KEY_ENCRYPTION_KEY=<generated-key>`
- `JWT_SECRET_KEY=<strong-random-secret>`
- `CORS_ORIGINS=http://<YOUR_PUBLIC_IP>`
- `COLDEMAIL_PROFILE_API_KEY=<your-ollama-cloud-api-key>`

Optional but recommended for production:

- `ACCESS_TOKEN_EXPIRE_MINUTES=1440`
- SMTP values for cold email sending.

## 6) Configure DB URL + run migrations

```bash
source .venv/bin/activate
sed -i 's|^DATABASE_URL=.*|DATABASE_URL=postgresql+psycopg://oppora:oppora_password@localhost:5432/hack_hunt|' .env
python -m cli db upgrade
```

## 7) Start backend + frontend with PM2

```bash
pm2 start ecosystem.config.cjs
pm2 save
pm2 startup
```

Run the printed `pm2 startup` command once with `sudo`.

## 8) Configure Nginx on port 80

```bash
sudo cp deploy/nginx/oppora.conf /etc/nginx/sites-available/oppora
sudo ln -sf /etc/nginx/sites-available/oppora /etc/nginx/sites-enabled/oppora
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx
```

## 9) Verify

```bash
pm2 status
curl http://127.0.0.1:8000/health
curl http://<YOUR_PUBLIC_IP>/health
```

Frontend should open at:

- `http://<YOUR_PUBLIC_IP>`

## Notes

- This setup uses Nginx as reverse proxy on port 80.
- SeerAI/ScribeAI free tier and ScrollAI use `COLDEMAIL_PROFILE_API_KEY` (Ollama Cloud).
- Local embedding generation uses Ollama at `http://localhost:11434`.
