"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { AuthGate } from "@/components/AuthGate";
import { Header } from "@/components/Header";
import { api } from "@/lib/api";
import type { FeedbackSummary, Registration } from "@/lib/types";

export default function AdminResponsesPage() {
  const params = useParams<{ id: string }>();
  const [summary, setSummary] = useState<FeedbackSummary | null>(null);
  const [registrations, setRegistrations] = useState<Registration[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      api<FeedbackSummary>(`/events/${params.id}/feedback/responses`),
      api<Registration[]>(`/events/${params.id}/registrations`),
    ])
      .then(([feedback, registered]) => {
        setSummary(feedback);
        setRegistrations(registered);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load admin details"));
  }, [params.id]);

  return (
    <AuthGate>
      <Header />
      <main className="shell">
        <Link href={`/events/${params.id}`} className="muted">Back to event</Link>
        {error ? <p className="danger">{error}</p> : null}
        {summary ? (
          <div className="grid" style={{ marginTop: 20 }}>
            <section className="panel">
              <h1>{summary.event_title}</h1>
              <div className="row">
                <strong>{registrations.length} registered students</strong>
                <strong>{summary.response_count} responses</strong>
                <strong>Average rating: {summary.average_rating ?? "No ratings"}</strong>
              </div>
            </section>

            <section className="panel">
              <h2>Registered students</h2>
              <table className="table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Registered</th>
                  </tr>
                </thead>
                <tbody>
                  {registrations.map((registration) => (
                    <tr key={registration.id}>
                      <td>{registration.user_name}</td>
                      <td>{registration.user_email}</td>
                      <td>{new Date(registration.registered_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>

            <section className="panel">
              <h2>Feedback responses</h2>
              <table className="table">
                <thead>
                  <tr>
                    <th>User</th>
                    <th>Rating</th>
                    <th>Answers</th>
                    <th>Comment</th>
                    <th>Submitted</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.responses.map((response) => (
                    <tr key={response.id}>
                      <td>{response.user_name}</td>
                      <td>{response.rating}</td>
                      <td>
                        {Object.entries(response.answers || {}).map(([question, answer]) => (
                          <p key={question}><strong>{question}</strong><br />{answer || "No answer"}</p>
                        ))}
                      </td>
                      <td>{response.comment || "No comment"}</td>
                      <td>{new Date(response.submitted_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          </div>
        ) : null}
      </main>
    </AuthGate>
  );
}
