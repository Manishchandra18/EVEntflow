"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AuthGate } from "@/components/AuthGate";
import { Header } from "@/components/Header";
import { ToastStack, type ToastItem } from "@/components/Toast";
import { api, getStoredUser } from "@/lib/api";
import type { EventItem, PaginatedEvents, User } from "@/lib/types";

type SessionMode = "none" | "recurrence" | "manual";

type RecurrenceState = {
  pattern: "daily" | "weekly" | "weekdays";
  count: number;
  duration_minutes: number;
  first_start_at: string;
  title_prefix: string;
};

type SessionDraft = {
  title: string;
  start_at: string;
  end_at: string;
  location: string;
};

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export default function HomePage() {
  const [events, setEvents] = useState<PaginatedEvents | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const creatingRef = useRef(false);

  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const addToast = useCallback((message: string, type: ToastItem["type"]) => {
    setToasts((prev) => [...prev, { id: crypto.randomUUID(), message, type }]);
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const [sessionMode, setSessionMode] = useState<SessionMode>("none");
  const [recurrence, setRecurrence] = useState<RecurrenceState>({
    pattern: "daily",
    count: 5,
    duration_minutes: 60,
    first_start_at: "",
    title_prefix: "Session",
  });
  const [manualSessions, setManualSessions] = useState<SessionDraft[]>([]);

  const minDateTime = useMemo(() => {
    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    return now.toISOString().slice(0, 16);
  }, []);

  async function load(nextPage: number) {
    try {
      setLoading(true);
      setError("");
      const data = await api<PaginatedEvents>(
        `/events?page=${nextPage}&page_size=5`,
      );
      setEvents(data);
      setPage(nextPage);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load events");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setUser(getStoredUser());
    load(1);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!events || !user || user.role === "admin") return;
    const check = () => {
      const now = Date.now();
      const oneHour = 60 * 60 * 1000;
      for (const ev of events.items) {
        if (!ev.is_registered) continue;
        const start = new Date(ev.start_at).getTime();
        if (start > now && start - now <= oneHour) {
          const key = `reminder-${ev.id}`;
          if (!sessionStorage.getItem(key)) {
            sessionStorage.setItem(key, "1");
            const mins = Math.round((start - now) / 60_000);
            addToast(`"${ev.title}" starts in ${mins} minute${mins !== 1 ? "s" : ""}!`, "warning");
          }
        }
      }
    };
    check();
    const interval = setInterval(check, 60_000);
    return () => clearInterval(interval);
  }, [events, user, addToast]);

  function addManualSession() {
    setManualSessions((prev) => [
      ...prev,
      { title: "", start_at: "", end_at: "", location: "" },
    ]);
  }

  function removeManualSession(index: number) {
    setManualSessions((prev) => prev.filter((_, i) => i !== index));
  }

  function updateManualSession(
    index: number,
    field: keyof SessionDraft,
    value: string,
  ) {
    setManualSessions((prev) =>
      prev.map((s, i) => (i === index ? { ...s, [field]: value } : s)),
    );
  }

  async function createEvent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (creatingRef.current) return;
    creatingRef.current = true;
    setCreating(true);
    setError("");
    const formElement = event.currentTarget;
    const form = new FormData(formElement);

    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const body: any = {
        title: form.get("title"),
        description: form.get("description"),
        location: form.get("location"),
        google_form_url: form.get("google_form_url") || null,
        feedback_questions: String(form.get("feedback_questions") || "")
          .split("\n")
          .map((q) => q.trim())
          .filter(Boolean),
        idempotency_key: crypto.randomUUID(),
      };

      if (sessionMode === "recurrence") {
        if (!recurrence.first_start_at) {
          setError("First session start time is required");
          return;
        }
        if (new Date(recurrence.first_start_at) < new Date()) {
          setError("First session must be in the future");
          return;
        }
        body.recurrence = {
          pattern: recurrence.pattern,
          count: recurrence.count,
          duration_minutes: recurrence.duration_minutes,
          first_start_at: new Date(recurrence.first_start_at).toISOString(),
          title_prefix: recurrence.title_prefix || "Session",
        };
      } else {
        const start = new Date(String(form.get("start_at")));
        const end = new Date(String(form.get("end_at")));
        if (start < new Date()) {
          setError("Start time must be present or future");
          return;
        }
        if (end <= start) {
          setError("End time must be after start time");
          return;
        }
        body.start_at = start.toISOString();
        body.end_at = end.toISOString();

        if (sessionMode === "manual" && manualSessions.length > 0) {
          body.sessions = manualSessions
            .filter((s) => s.title && s.start_at && s.end_at)
            .map((s) => ({
              title: s.title,
              start_at: new Date(s.start_at).toISOString(),
              end_at: new Date(s.end_at).toISOString(),
              location: s.location,
            }));
        }
      }

      await api<EventItem>("/events", {
        method: "POST",
        body: JSON.stringify(body),
      });
      formElement.reset();
      setSessionMode("none");
      setManualSessions([]);
      setRecurrence({
        pattern: "daily",
        count: 5,
        duration_minutes: 60,
        first_start_at: "",
        title_prefix: "Session",
      });
      await load(1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create event");
    } finally {
      creatingRef.current = false;
      setCreating(false);
    }
  }

  return (
    <AuthGate>
      <Header />
      <main className="shell">
        <ToastStack toasts={toasts} onDismiss={dismissToast} />
        <h1>Events</h1>
        <div className="twoColumn">
        <section>
          {error ? <p className="danger">{error}</p> : null}
          {events ? (
            events.items.length ? (
              <div className="grid">
                {events.items.map((item) => (
                  <article className="eventCard" key={item.id}>
                    <div
                      className="row"
                      style={{ justifyContent: "space-between" }}
                    >
                      <h2>{item.title}</h2>
                      <span
                        className={`status ${item.feedback_open ? "statusOpen" : "statusClosed"}`}
                      >
                        {item.feedback_open ? "Feedback open" : "Upcoming"}
                      </span>
                    </div>
                    <p className="muted">
                      {item.event_code} · {item.location || "Online"} ·{" "}
                      {formatDate(item.start_at)}
                    </p>
                    <p>{item.description}</p>
                    <div className="actions">
                      <Link className="button" href={`/events/${item.id}`}>
                        Open
                      </Link>
                      <span className="muted">
                        {item.registration_count} registered
                      </span>
                      {item.sessions.length > 0 && (
                        <span className="muted">
                          {item.sessions.length} session
                          {item.sessions.length !== 1 ? "s" : ""}
                        </span>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <p className="muted">There are no events right now.</p>
            )
          ) : (
            <p className="muted">Loading events…</p>
          )}
          <div className="actions" style={{ marginTop: 16 }}>
            <button
              className="ghost"
              disabled={loading || page <= 1}
              onClick={() => load(page - 1)}
            >
              Previous
            </button>
            <span className="muted">
              {events
                ? `Page ${events.page} of ${Math.ceil(events.total / events.page_size) || 1}`
                : "Loading…"}
            </span>
            <button
              className="ghost"
              disabled={loading || !events || events.page >= Math.ceil(events.total / events.page_size)}
              onClick={() => load(page + 1)}
            >
              Next
            </button>
          </div>
        </section>

        {user?.role === "admin" ? (
          <aside className="panel" style={{ alignSelf: "center" }}>
            <h2>Create event</h2>
            <form className="grid" onSubmit={createEvent}>
              <label>
                Title
                <input name="title" required />
              </label>
              <label>
                Location
                <input name="location" />
              </label>

              {/* Show event-level start/end only when not using recurrence */}
              {sessionMode !== "recurrence" && (
                <>
                  <label>
                    Start
                    <input
                      name="start_at"
                      type="datetime-local"
                      min={minDateTime}
                      required
                    />
                  </label>
                  <label>
                    End
                    <input
                      name="end_at"
                      type="datetime-local"
                      min={minDateTime}
                      required
                    />
                  </label>
                </>
              )}

              <label>
                Description
                <textarea name="description" />
              </label>
              <label>
                Google Form URL
                <input
                  name="google_form_url"
                  type="url"
                  placeholder="https://forms.gle/..."
                />
              </label>
              <label>
                Custom feedback questions
                <textarea
                  name="feedback_questions"
                  placeholder="One question per line"
                />
              </label>

              {/* Session mode selector */}
              <label>
                Sessions
                <select
                  value={sessionMode}
                  onChange={(e) => {
                    setSessionMode(e.target.value as SessionMode);
                    setManualSessions([]);
                  }}
                >
                  <option value="none">No sessions</option>
                  <option value="recurrence">Auto-generate (recurrence)</option>
                  <option value="manual">Add manually</option>
                </select>
              </label>

              {/* Recurrence form */}
              {sessionMode === "recurrence" && (
                <div
                  className="grid"
                  style={{
                    background: "var(--bg)",
                    borderRadius: 6,
                    padding: 12,
                  }}
                >
                  <label>
                    First session start
                    <input
                      type="datetime-local"
                      min={minDateTime}
                      value={recurrence.first_start_at}
                      onChange={(e) =>
                        setRecurrence((r) => ({
                          ...r,
                          first_start_at: e.target.value,
                        }))
                      }
                      required
                    />
                  </label>
                  <label>
                    Pattern
                    <select
                      value={recurrence.pattern}
                      onChange={(e) =>
                        setRecurrence((r) => ({
                          ...r,
                          pattern: e.target.value as RecurrenceState["pattern"],
                        }))
                      }
                    >
                      <option value="daily">Daily</option>
                      <option value="weekly">Weekly</option>
                      <option value="weekdays">Weekdays only</option>
                    </select>
                  </label>
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "1fr 1fr",
                      gap: 8,
                    }}
                  >
                    <label>
                      Sessions
                      <input
                        type="number"
                        min={1}
                        max={52}
                        value={recurrence.count}
                        onChange={(e) =>
                          setRecurrence((r) => ({
                            ...r,
                            count: Number(e.target.value),
                          }))
                        }
                        required
                      />
                    </label>
                    <label>
                      Duration (min)
                      <input
                        type="number"
                        min={5}
                        max={480}
                        value={recurrence.duration_minutes}
                        onChange={(e) =>
                          setRecurrence((r) => ({
                            ...r,
                            duration_minutes: Number(e.target.value),
                          }))
                        }
                        required
                      />
                    </label>
                  </div>
                  <label>
                    Title prefix
                    <input
                      value={recurrence.title_prefix}
                      onChange={(e) =>
                        setRecurrence((r) => ({
                          ...r,
                          title_prefix: e.target.value,
                        }))
                      }
                      placeholder="e.g. Day, Week, Session"
                    />
                  </label>
                  <p className="muted" style={{ margin: 0, fontSize: 13 }}>
                    Generates {recurrence.count} × {recurrence.duration_minutes}
                    -min sessions labeled &ldquo;
                    {recurrence.title_prefix || "Session"} 1&rdquo;, &ldquo;
                    {recurrence.title_prefix || "Session"} 2&rdquo;, …
                  </p>
                </div>
              )}

              {/* Manual sessions */}
              {sessionMode === "manual" && (
                <div className="grid">
                  {manualSessions.map((s, i) => (
                    <div
                      key={i}
                      className="grid"
                      style={{
                        background: "var(--bg)",
                        borderRadius: 6,
                        padding: 12,
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                        }}
                      >
                        <strong style={{ fontSize: 13 }}>
                          Session {i + 1}
                        </strong>
                        <button
                          type="button"
                          className="ghost"
                          style={{ padding: "2px 8px", fontSize: 13 }}
                          onClick={() => removeManualSession(i)}
                        >
                          Remove
                        </button>
                      </div>
                      <label>
                        Title
                        <input
                          value={s.title}
                          onChange={(e) =>
                            updateManualSession(i, "title", e.target.value)
                          }
                          required
                        />
                      </label>
                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns: "1fr 1fr",
                          gap: 8,
                        }}
                      >
                        <label>
                          Start
                          <input
                            type="datetime-local"
                            min={minDateTime}
                            value={s.start_at}
                            onChange={(e) =>
                              updateManualSession(i, "start_at", e.target.value)
                            }
                            required
                          />
                        </label>
                        <label>
                          End
                          <input
                            type="datetime-local"
                            min={minDateTime}
                            value={s.end_at}
                            onChange={(e) =>
                              updateManualSession(i, "end_at", e.target.value)
                            }
                            required
                          />
                        </label>
                      </div>
                      <label>
                        Location (optional)
                        <input
                          value={s.location}
                          onChange={(e) =>
                            updateManualSession(i, "location", e.target.value)
                          }
                        />
                      </label>
                    </div>
                  ))}
                  <button
                    type="button"
                    className="ghost"
                    onClick={addManualSession}
                  >
                    + Add session
                  </button>
                </div>
              )}

              <button disabled={creating}>
                {creating ? "Creating..." : "Create"}
              </button>
            </form>
          </aside>
        ) : (
          <aside className="panel" style={{ alignSelf: "center" }}>
            <h2>Your flow</h2>
            <p className="muted">
              Register before an event ends. Feedback appears automatically
              after completion.
            </p>
          </aside>
        )}
        </div>
      </main>
    </AuthGate>
  );
}
