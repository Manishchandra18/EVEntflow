"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AuthGate } from "@/components/AuthGate";
import { Header } from "@/components/Header";
import { ToastStack, type ToastItem } from "@/components/Toast";
import { api, getStoredUser } from "@/lib/api";
import type { EventItem, FeedbackResponse, User } from "@/lib/types";

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function toDateTimeLocal(iso: string) {
  const d = new Date(iso);
  const offset = d.getTimezoneOffset();
  return new Date(d.getTime() - offset * 60 * 1000).toISOString().slice(0, 16);
}

export default function EventDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [event, setEvent] = useState<EventItem | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState("");

  const [editing, setEditing] = useState(false);
  const [editError, setEditError] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const addToast = useCallback((message: string, type: ToastItem["type"]) => {
    setToasts((prev) => [...prev, { id: crypto.randomUUID(), message, type }]);
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  async function load() {
    try {
      setError("");
      setEvent(await api<EventItem>(`/events/${params.id}`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load event");
    }
  }

  useEffect(() => {
    setUser(getStoredUser());
    load();
  }, [params.id]);

  async function register() {
    if (user?.role === "admin") {
      setError("Admins cannot register for events");
      return;
    }
    try {
      const updated = await api<EventItem>(`/events/${params.id}/register`, { method: "POST" });
      setEvent(updated);
      addToast(`You're registered for "${updated.title}"!`, "success");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not register");
    }
  }

  async function submitFeedback(formEvent: FormEvent<HTMLFormElement>) {
    formEvent.preventDefault();
    const formElement = formEvent.currentTarget;
    const form = new FormData(formElement);
    const answers = Object.fromEntries(
      event?.feedback_questions.map((q) => [q, String(form.get(`question:${q}`) || "")]) ?? []
    );
    try {
      setError("");
      await api<FeedbackResponse>(`/events/${params.id}/feedback`, {
        method: "POST",
        body: JSON.stringify({
          rating: Number(form.get("rating")),
          comment: form.get("comment"),
          answers,
        }),
      });
      addToast("Feedback submitted. Thank you!", "success");
      formElement.reset();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not submit feedback");
    }
  }

  async function saveEdit(formEvent: FormEvent<HTMLFormElement>) {
    formEvent.preventDefault();
    setSaving(true);
    setEditError("");
    const form = new FormData(formEvent.currentTarget);
    try {
      const body: Record<string, unknown> = {
        title: form.get("title"),
        description: form.get("description"),
        location: form.get("location"),
        google_form_url: form.get("google_form_url") || null,
        feedback_questions: String(form.get("feedback_questions") || "")
          .split("\n")
          .map((q) => q.trim())
          .filter(Boolean),
      };
      const startVal = String(form.get("start_at"));
      const endVal = String(form.get("end_at"));
      if (startVal) body.start_at = new Date(startVal).toISOString();
      if (endVal) body.end_at = new Date(endVal).toISOString();

      setEvent(await api<EventItem>(`/events/${params.id}`, { method: "PATCH", body: JSON.stringify(body) }));
      setEditing(false);
    } catch (err) {
      setEditError(err instanceof Error ? err.message : "Could not save changes");
    } finally {
      setSaving(false);
    }
  }

  async function confirmDelete() {
    if (!confirm("Delete this event permanently? This cannot be undone.")) return;
    setDeleting(true);
    try {
      await api(`/events/${params.id}`, { method: "DELETE" });
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete event");
      setDeleting(false);
    }
  }

  const isOwner = user?.role === "admin" && event?.created_by === user?.id;
  const isSuperadmin = user?.is_superadmin === true;

  return (
    <AuthGate>
      <Header />
      <main className="shell">
        <Link href="/" className="muted">Back to events</Link>
        {error ? <p className="danger">{error}</p> : null}
        <ToastStack toasts={toasts} onDismiss={dismissToast} />
        {event ? (
          <div className="twoColumn" style={{ marginTop: 20 }}>
            <section className="panel">
              <div className="row" style={{ justifyContent: "space-between" }}>
                <h1>{event.title}</h1>
                <span className={`status ${event.feedback_open ? "statusOpen" : "statusClosed"}`}>
                  {event.feedback_open ? "Feedback open" : "Upcoming"}
                </span>
              </div>
              <p className="muted">{event.event_code} · {event.location || "Online"}</p>
              <p>{event.description}</p>
              <p><strong>Starts:</strong> {formatDate(event.start_at)}</p>
              <p><strong>Ends:</strong> {formatDate(event.end_at)}</p>
              <p className="muted">{event.registration_count} registered</p>
              <div className="actions">
                {user?.role !== "admin" ? (
                  <button disabled={event.is_registered || new Date(event.end_at) <= new Date()} onClick={register}>
                    {event.is_registered ? "Registered" : "Register"}
                  </button>
                ) : null}
                {user?.role === "admin" ? (
                  <Link className="button ghost" href={`/admin/events/${event.id}`}>Responses</Link>
                ) : null}
                {isOwner ? (
                  <button className="ghost" onClick={() => { setEditing((v) => !v); setEditError(""); }}>
                    {editing ? "Cancel edit" : "Edit"}
                  </button>
                ) : null}
                {isSuperadmin ? (
                  <button
                    className="ghost"
                    style={{ color: "var(--danger)", borderColor: "var(--danger)" }}
                    disabled={deleting}
                    onClick={confirmDelete}
                  >
                    {deleting ? "Deleting…" : "Delete event"}
                  </button>
                ) : null}
              </div>

              {/* Inline edit form */}
              {editing && isOwner ? (
                <form className="grid" style={{ marginTop: 20 }} onSubmit={saveEdit}>
                  <h2 style={{ margin: 0 }}>Edit event</h2>
                  {editError ? <p className="danger">{editError}</p> : null}
                  <label>Title<input name="title" defaultValue={event.title} required /></label>
                  <label>Location<input name="location" defaultValue={event.location} /></label>
                  <label>Start<input name="start_at" type="datetime-local" defaultValue={toDateTimeLocal(event.start_at)} /></label>
                  <label>End<input name="end_at" type="datetime-local" defaultValue={toDateTimeLocal(event.end_at)} /></label>
                  <label>Description<textarea name="description" defaultValue={event.description} /></label>
                  <label>Google Form URL<input name="google_form_url" type="url" defaultValue={event.google_form_url ?? ""} placeholder="https://forms.gle/..." /></label>
                  <label>
                    Custom feedback questions
                    <textarea name="feedback_questions" defaultValue={event.feedback_questions.join("\n")} placeholder="One question per line" />
                  </label>
                  <button disabled={saving}>{saving ? "Saving…" : "Save changes"}</button>
                </form>
              ) : null}
            </section>

            {event.sessions.length > 0 ? (
              <section className="panel" style={{ gridColumn: "1 / -1" }}>
                <h2>Schedule</h2>
                <table className="table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Session</th>
                      <th>Start</th>
                      <th>End</th>
                      <th>Location</th>
                    </tr>
                  </thead>
                  <tbody>
                    {event.sessions.map((s, i) => (
                      <tr key={i}>
                        <td className="muted">{i + 1}</td>
                        <td>{s.title}</td>
                        <td>{formatDate(s.start_at)}</td>
                        <td>{formatDate(s.end_at)}</td>
                        <td className="muted">{s.location || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>
            ) : null}

            <aside className="panel">
              <h2>Feedback</h2>
              {!event.is_registered ? <p className="muted">Register for this event to receive the feedback form.</p> : null}
              {event.is_registered && !event.feedback_open ? <p className="muted">The form opens automatically after the event ends.</p> : null}
              {event.has_feedback ? <p>Feedback already submitted.</p> : null}
              {event.is_registered && event.feedback_open && event.google_form_url ? (
                <a className="button ghost" href={event.google_form_url} target="_blank" rel="noreferrer">
                  Open Google Form
                </a>
              ) : null}
              {event.is_registered && event.feedback_open && !event.has_feedback ? (
                <form className="grid" onSubmit={submitFeedback}>
                  <label>
                    Rating
                    <select name="rating" defaultValue="5">
                      <option value="5">5 - Excellent</option>
                      <option value="4">4 - Good</option>
                      <option value="3">3 - Fine</option>
                      <option value="2">2 - Poor</option>
                      <option value="1">1 - Bad</option>
                    </select>
                  </label>
                  {event.feedback_questions.map((q) => (
                    <label key={q}>{q}<textarea name={`question:${q}`} /></label>
                  ))}
                  <label>Comment<textarea name="comment" /></label>
                  <button>Submit feedback</button>
                </form>
              ) : null}
            </aside>
          </div>
        ) : null}
      </main>
    </AuthGate>
  );
}
