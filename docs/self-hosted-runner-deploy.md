# ClawMarket self-hosted runner deployment

This path avoids SSH-based deployment.
You do one-time server bootstrap from your cloud provider's web console, then GitHub Actions deploys directly on the remote Linux host through a self-hosted runner.

## What this sets up

- A Linux GitHub Actions runner with the custom label `clawmarket`
- Docker Engine + Docker Compose Plugin on the server
- A GitHub workflow at `.github/workflows/deploy-self-hosted.yml`
- Automatic deployment on pushes to `master`
- Manual deployment from the Actions tab with `workflow_dispatch`

## Server prerequisites

- Ubuntu 22.04+ or Debian 12+ is recommended
- A non-root user with `sudo`
- Docker Engine installed
- Docker Compose Plugin installed
- `curl`, `tar`, and `git` installed

Example Ubuntu bootstrap:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg git

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker "$USER"
newgrp docker
docker --version
docker compose version
```

## Create the runner

Open your GitHub repository:

- `Settings`
- `Actions`
- `Runners`
- `New self-hosted runner`
- Choose `Linux` and `x64`

GitHub will show commands similar to:

```bash
mkdir -p ~/actions-runner && cd ~/actions-runner
curl -o actions-runner-linux-x64-<version>.tar.gz -L <download-url>
tar xzf ./actions-runner-linux-x64-<version>.tar.gz
./config.sh --url https://github.com/<owner>/<repo> --token <runner-token> --labels clawmarket
sudo ./svc.sh install
sudo ./svc.sh start
```

Use the `clawmarket` label exactly.
The workflow is configured with:

```yaml
runs-on: [self-hosted, linux, x64, clawmarket]
```

## Required GitHub secrets

Add these repository secrets:

- `ROOT_ENV_FILE`
  Put the contents of your repo root `.env` here.
- `BACKEND_ENV_FILE`
  Put the contents of `backend/.env` here if you use extra backend-only settings.
- `FRONTEND_ENV_FILE`
  Optional. Use only if you need a dedicated `frontend/.env`, for example Clerk keys.

Minimum `ROOT_ENV_FILE` example:

```env
FRONTEND_PORT=3000
BACKEND_PORT=8000
POSTGRES_DB=mission_control
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_PORT=5432
BASE_URL=http://your-server-ip-or-domain:8000
CORS_ORIGINS=http://your-server-ip-or-domain:3000
DB_AUTO_MIGRATE=true
LOG_LEVEL=INFO
AUTH_MODE=local
LOCAL_AUTH_TOKEN=replace-with-a-long-random-token-at-least-50-chars
NEXT_PUBLIC_API_URL=auto
CLAWMARKET_ORG_NAME=ClawMarket Marketplace
CLAWMARKET_PLATFORM_FEE_BPS=2000
CLAWMARKET_UPLOAD_DIR=/app/storage/clawmarket
CLAWMARKET_MAX_ATTACHMENT_BYTES=5242880
PAYMENT_PROVIDER=mock
PAYMENT_CURRENCY=cny
STRIPE_API_BASE=https://api.stripe.com/v1
STRIPE_SECRET_KEY=
STRIPE_TEST_PAYMENT_METHOD=pm_card_visa
```

Example `BACKEND_ENV_FILE`:

```env
CLAWMARKET_ORG_NAME=ClawMarket Marketplace
CLAWMARKET_UPLOAD_DIR=/app/storage/clawmarket
CLAWMARKET_MAX_ATTACHMENT_BYTES=5242880
CLAWMARKET_PLATFORM_FEE_BPS=2000
PAYMENT_PROVIDER=mock
PAYMENT_CURRENCY=cny
STRIPE_API_BASE=https://api.stripe.com/v1
STRIPE_SECRET_KEY=
STRIPE_TEST_PAYMENT_METHOD=pm_card_visa
```

## Deployment flow

After the runner is online and secrets are configured:

1. Push this repository to GitHub.
2. Merge or push to `master`.
3. GitHub Actions will pick up the job on your remote Linux runner.
4. The workflow writes env files locally on the server.
5. The workflow runs:

```bash
docker compose -f compose.yml --env-file .env up -d --build
```

6. The workflow waits for:
   - `http://127.0.0.1:${BACKEND_PORT}/healthz`
   - `http://127.0.0.1:${FRONTEND_PORT}`

## Manual deploy

You can also deploy manually:

- Open `Actions`
- Select `Deploy (Self-Hosted Runner)`
- Click `Run workflow`

## Troubleshooting

- If the job never starts, the runner labels do not match.
- If `docker compose` fails, check Docker permissions for the runner service account.
- If the app starts but health checks fail, inspect:

```bash
docker compose -f compose.yml --env-file .env ps
docker compose -f compose.yml --env-file .env logs --tail=300 backend frontend db redis webhook-worker
```

- If you rotate secrets, rerun the workflow manually to rewrite `.env` files on the server.

## Official references

- [Adding self-hosted runners](https://docs.github.com/actions/hosting-your-own-runners/adding-self-hosted-runners)
- [Using labels with self-hosted runners](https://docs.github.com/actions/hosting-your-own-runners/using-labels-with-self-hosted-runners)
- [Self-hosted runners reference](https://docs.github.com/en/actions/reference/runners/self-hosted-runners)
