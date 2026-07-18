# Deploying EventFlow to AWS Elastic Beanstalk

This document records every command used to deploy this app to Elastic Beanstalk (EB), what each one does, and the two real bugs we hit along the way so future-you (or a teammate) doesn't have to rediscover them.

## Architecture

- **Backend** (FastAPI + Motor/MongoDB) → its own EB environment, `eventflow-prod`, deployed straight from `backend/Dockerfile` (single container, no `docker-compose`).
- **Frontend** (Next.js) → its own EB environment, `eventflow-web`, deployed straight from `frontend/Dockerfile`.
- **Database** → MongoDB Atlas (free M0 cluster) — not hosted on EB.
- Each service is a **separate EB environment**. This matters: EB's built-in nginx reverse proxy only auto-configures itself when a directory has exactly one `Dockerfile` and no `docker-compose.yml`. Point `eb init`/`eb deploy` at a directory containing a multi-service `docker-compose.yml` (e.g. the repo root) and EB happily runs every service, but never wires up nginx to route port 80 anywhere — see the "Bug #2" section below for how we found this out the hard way.

## Prerequisites

**IAM policy** for the AWS user running these commands: `AWSElasticBeanstalkFullAccess`. It covers EB itself plus EC2/ASG/ELB/S3/CloudFormation/CloudWatch, and includes a scoped `iam:CreateRole`/`iam:PassRole` grant so EB can bootstrap its own service roles (`aws-elasticbeanstalk-service-role`, `aws-elasticbeanstalk-ec2-role`) automatically on first `eb create`.

**MongoDB Atlas**: free M0 cluster, a database user (username/password — this is separate from your Atlas login), and Network Access set to `0.0.0.0/0` so EB's EC2 instances (which get dynamic IPs) can always reach it.

## Commands used, in order

### 1. Initialize the EB CLI workspace (once per service directory)

```bash
cd backend
eb init eventflow --platform "Docker running on 64bit Amazon Linux 2023" --region ap-south-1 -k eventflow-eb
```

- `eb init` creates a local `.elasticbeanstalk/config.yml` binding *this directory* to an EB **application** (a named container for one or more environments/versions — `eventflow` here).
- `--platform` picks the EB-managed OS+Docker runtime image. We chose the AL2023 Docker platform (current/non-deprecated) over ECS or AL2 (deprecated) — it just runs your `Dockerfile` directly, no cluster/task-definition config needed.
- `-k eventflow-eb` sets the default EC2 keypair name so later `eb ssh` works without re-prompting.
- Run this **once inside each service directory** (`backend/` and `frontend/`) that you intend to `eb deploy` independently — each gets its own `.elasticbeanstalk/config.yml`, but they can (and here, do) point at the same application.

### 2. Create the environment (one per service)

```bash
eb create eventflow-prod --single --instance_type t3.micro   # from backend/
eb create eventflow-web  --single --instance_type t3.micro   # from frontend/
```

- An **environment** is the actual running thing: EC2 instance(s), security group, and (optionally) a load balancer.
- `--single` = single-instance environment, **no load balancer**. This is the cheap/free-tier-friendly option — a load-balanced environment adds an ALB, which is still mostly free-tier eligible for 12 months but is unnecessary complexity for a personal project.
- `--instance_type t3.micro` is the free-tier-eligible instance size.
- Each `eb create` builds the `Dockerfile` in the current directory into an image, runs it, and (for a single, non-compose `Dockerfile`) auto-configures nginx to reverse-proxy external port 80 to whatever port your `Dockerfile` declares with `EXPOSE`.

### 3. Set environment variables

```bash
eb setenv MONGO_URI="mongodb+srv://user:pass@cluster0.xxxxx.mongodb.net/?appName=Cluster0" \
  DATABASE_NAME=event_participation \
  JWT_SECRET="<random 32-byte hex>" \
  JWT_ALGORITHM=HS256 \
  ACCESS_TOKEN_EXPIRE_MINUTES=1440 \
  FEEDBACK_SWEEP_SECONDS=60 \
  CORS_ORIGINS="http://eventflow-web.eba-....elasticbeanstalk.com" \
  ADMIN_EMAILS="admin@example.com,other@example.com" \
  SUPER_ADMIN_EMAIL="admin@example.com" \
  SMTP_HOST=smtp.gmail.com \
  SMTP_PORT=587 \
  SMTP_USERNAME="you@gmail.com" \
  SMTP_PASSWORD="<gmail app password>" \
  SMTP_FROM_EMAIL="you@gmail.com" \
  FRONTEND_URL="http://eventflow-web.eba-....elasticbeanstalk.com"
```

- These become real process environment variables inside the running container. The app reads them via `pydantic-settings` (`backend/app/core/config.py`) — **not** from a `.env` file, since `.env` is excluded by `.dockerignore` and never makes it into the image. `eb setenv` is the deployed equivalent of your local `backend/.env`.
- **Important gotcha**: `eb setenv` takes **space-separated** `KEY=VALUE` pairs, not comma-separated. `ADMIN_EMAILS` itself contains a comma (multiple emails) — if you tried to pass all vars as one comma-joined string (as `eb create --envvars` does), that comma would be misread as a new variable boundary and break parsing.
- Running `eb setenv` triggers an automatic config-only redeploy (fast — no image rebuild, just restarts the app with new env vars).
- Generated the random JWT secret with:
  ```bash
  openssl rand -hex 32
  ```
  A 32-byte random hex string used to sign JWTs. Never reuse the `replace-this-in-production` placeholder from `.env.example` in a real deployment — anyone who found that default could forge valid login tokens.

### 4. Deploy code changes

```bash
eb deploy
```

- Zips the current directory (respecting `.dockerignore`/`.gitignore`-like exclusion via `.ebignore` if present), uploads it as a new "application version," rebuilds the Docker image on the instance, and restarts the container. Use this after any source code change (as opposed to `eb setenv`, which only changes env vars).

### 5. Check status/logs/health

```bash
eb status                       # quick summary: app name, region, CNAME, health
eb health eventflow-prod --refresh   # live per-instance health + request metrics
eb events -e eventflow-prod --follow # streams deployment/lifecycle events in real time
eb logs                         # pulls recent logs (nginx, docker stdout/stderr) into a local bundle
```

- `eb health --refresh` was how we caught the environment stuck on `Health: Red` after a botched deploy, and later confirmed `Health: Ok` once fixed.
- `eb events --follow` is the right tool while waiting on a slow `eb create`/rebuild — it shows *why* it's taking time (instance launch → bootstrap → image build → health check warch-up) instead of leaving you guessing.
- `eb logs` was how we found the actual Python traceback (`pymongo.errors.ServerSelectionTimeoutError: SSL handshake failed`) that pointed at Bug #1 below.

### 6. SSH into the instance directly

```bash
eb ssh eventflow-prod -c "sudo docker ps -a; sudo systemctl status nginx"
```

- `-c/--command` runs one non-interactive command over SSH instead of opening a shell — useful for scripted checks.
- We used this (plus raw `ssh -i ~/.ssh/eventflow-eb ec2-user@<ip>`) to directly inspect what was running on the box: `docker ps -a` to see which containers were actually up, `systemctl status nginx` to check the reverse proxy, and `ss -tlnp` to see what ports were actually listening — this is what exposed Bug #2.
- First connection to a given IP needs its host key trusted; `ssh-keygen -R <ip>` clears a stale/conflicting entry from `~/.ssh/known_hosts` if the instance was recreated and got a new host key.

### 7. Inspecting AWS resources directly (bypassing EB CLI)

```bash
aws elasticbeanstalk describe-environments --environment-names eventflow-prod
aws elasticbeanstalk describe-environment-resources --environment-name eventflow-prod
aws ec2 describe-instances --instance-ids <id>
aws ec2 describe-security-groups --group-ids <sg-id>
```

- Used to confirm the environment was single-instance (no load balancer), get the instance's public IP, and confirm the security group actually allowed inbound port 80/22 from `0.0.0.0/0` — ruling out a network/firewall cause before looking deeper.

## Bugs we hit and how we found them

### Bug #1 — MongoDB TLS handshake failure

**Symptom**: `eb health` showed `Red`; `eb logs` showed:
```
pymongo.errors.ServerSelectionTimeoutError: SSL handshake failed: cluster0-shard-00-01.....mongodb.net:27017: [SSL: TLSV1_ALERT_INTERNAL_ERROR]
```
**Cause**: MongoDB Atlas's Network Access allow-list didn't yet include the EB instance's IP (or the entry hadn't finished propagating). Atlas answers un-allow-listed connections with a generic TLS-level rejection rather than a clean TCP refusal, which is why it looks like a driver/SSL bug rather than an access-control one.
**Fix**: Add `0.0.0.0/0` under Atlas → Network Access, confirm the entry shows **Active** (not "Pending"), then force the app to retry by restarting the container (`eb ssh` + `docker restart`, or a console "Restart App Server(s)").

### Bug #2 — nginx never started (port 80 "connection refused")

**Symptom**: the EB CNAME gave "connection refused" on port 80, even though `eb health` reported the environment as `Ok`.
**Root cause**: `eb init`/`eb create` had originally been run from the **repository root**, which contains a `docker-compose.yml` defining both `backend` and `frontend` services. EB happily built and ran *both* containers — but its automatic "point nginx at your app" logic only exists for the simple case (one `Dockerfile`, no compose file); it has no way to guess which of two compose services should receive port-80 traffic, so it left nginx unconfigured and inactive entirely.
**How we found it**: `eb ssh` + `docker ps -a` showed two containers running (`current-backend`, `current-frontend`) instead of one, and `systemctl status nginx` showed `inactive (dead)`. Checking `/var/app/current/docker-compose.yml` on the instance confirmed the deployed bundle was the whole repo, not just `backend/`.
**Fix**: Re-ran `eb init` from inside `backend/` specifically (binding that directory to the same EB application), attached it to the existing `eventflow-prod` environment with `eb use eventflow-prod`, and ran `eb deploy` from there — this redeployed *only* the backend Dockerfile as a proper single-container app, which let EB auto-configure nginx correctly. Did the equivalent for the frontend in its own environment.

### Bug #3 — wrong EB environment bound in a service directory (`eb deploy` hit the wrong environment)

**Symptom**: running `eb deploy` from `frontend/` deployed the frontend's Docker image onto the **backend** environment (`eventflow-prod`), taking the live backend down — `/health` started returning a Next.js 404 page instead of the FastAPI JSON response.
**Cause**: `frontend/.elasticbeanstalk/config.yml`'s `branch-defaults.default.environment` had ended up set to `eventflow-prod` instead of `eventflow-web`, even though `eventflow-web` was created from that same directory. Both service directories share one EB **application** (`eventflow`), and the CLI's notion of "current/active environment" for a directory can end up pointing at the wrong one if it isn't explicitly set.
**How we found it**: `eb status` run from `frontend/` showed `Environment details for: eventflow-prod` — the giveaway that the directory's binding was wrong.
**Fix**: `eb list` (shows all environments in the app, with `*` marking the one considered "current"), then `eb use eventflow-web` from inside `frontend/` to explicitly rebind that directory to the correct environment, confirmed by re-checking `.elasticbeanstalk/config.yml`. Then re-deployed the backend from `backend/` to restore it, and re-deployed the frontend from `frontend/` to its now-correctly-bound environment.
**Lesson**: after `eb create <name>` in a directory that shares an application with other directories, run `eb list` and `eb status` to confirm the binding before the next `eb deploy` — don't assume it stuck.

### Bug #4 — Cloudflare CORS/530 errors from a typo'd CNAME target

**Symptom**: after wiring up the custom domain, requests failed with either a CORS error (`No 'Access-Control-Allow-Origin' header is present`) or Cloudflare error **530 / 1016 (Origin DNS error)**, inconsistently, depending on which record was affected.
**Cause**: a trailing slash had been accidentally included in the CNAME record's **target** value in Cloudflare (e.g. `eventflow-prod.eba-....elasticbeanstalk.com/` instead of the bare hostname). A trailing slash isn't valid in a hostname, so Cloudflare's edge couldn't resolve/reach the origin at all — it terminated the HTTPS request fine (valid cert), then failed the moment it tried to connect onward, surfacing as error 1016.
**How we found it**: `curl -v` against the custom domain showed the TLS handshake succeeding (`SSL certificate verify ok`) but the response itself was Cloudflare's own 530 error page (`server: cloudflare`, `error code: 1016`) — proof the failure was between Cloudflare and the origin, not in the app.
**Fix**: removed the trailing slash from the CNAME target field in Cloudflare.
**Lesson**: a CNAME target must be a bare hostname — no scheme (`https://`), no path, no trailing slash. Cloudflare will accept a malformed value at save time without validating it's a resolvable hostname, so it fails silently until the first real request hits it.

## Remaining step: custom domain (Cloudflare)

Done — see `frontend/Dockerfile` (`NEXT_PUBLIC_API_URL` baked in at build time) and the backend's `CORS_ORIGINS`/`FRONTEND_URL` env vars, both pointing at the real `saiguturu.com` subdomains. Final reference for future changes:
1. `NEXT_PUBLIC_API_URL` in `frontend/Dockerfile` must be updated and the frontend redeployed (`eb deploy`) any time the backend's public URL changes — it's compiled into the JS bundle at build time, not read at runtime.
2. Cloudflare DNS: CNAME records for both subdomains, proxied (orange cloud), targets being the bare EB CNAMEs (see Bug #4 above for the exact gotcha to avoid).
3. Cloudflare SSL/TLS mode: **Flexible** (the EB origins only serve plain HTTP; no cert installed on the instances themselves).
4. Backend's `CORS_ORIGINS`/`FRONTEND_URL` env vars must match the frontend's real origin exactly (scheme + host), set via `eb setenv`.
