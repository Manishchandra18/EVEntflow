    # Event Participation and Feedback System

A compact full-stack application using FastAPI, MongoDB, and Next.js. It supports authenticated users, admin event creation, event registration, gated feedback after event completion, one feedback response per user per event, pagination, async APIs, and MongoDB indexes for stable performance around 1000 users.

## Architecture

- `backend/`: FastAPI app with Motor async MongoDB driver.
- `frontend/`: Next.js app with a small client-side UI.
- `docker-compose.yml`: MongoDB, API, and frontend services.

The feedback workflow is time-gated in two ways:

- A background FastAPI task periodically marks completed events as `feedback_open`.
- Every feedback read/write still checks the event end time, registration, and one-response constraint so access stays correct even if a sweep is delayed.

## Run With Docker

```bash
docker compose up --build
```

Open:

- Frontend: `http://localhost:3000`
- Backend docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

## Run Locally

Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

MongoDB must be running locally at `mongodb://localhost:27017`, or update `backend/.env`.

If you run the backend locally and see `localhost:27017: Connection refused`, start MongoDB first:

```bash
docker compose up -d mongo
```

Then run the backend and frontend in separate terminals.

## User Flow

1. Register or sign in.
2. Users whose email is listed in `ADMIN_EMAILS` become admins on signup.
3. Admin users create events from the main event screen.
4. Users register for upcoming events.
5. After `end_at`, feedback becomes available automatically for registered users.
6. A unique MongoDB index guarantees one feedback submission per user per event.
7. Admins open an event and view response counts, average rating, and comments.

## Scalability Notes

- All database calls use async Motor operations.
- Paginated event listing caps `page_size` at 50.
- MongoDB indexes cover auth lookup, event time scans, user registrations, and feedback summaries.
- Feedback availability is swept in the background and also enforced on access.
- Request handlers do not perform heavy computations; feedback averages are calculated with a MongoDB aggregation.
