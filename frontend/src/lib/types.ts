export type User = {
  id: string;
  name: string;
  email: string;
  role: "user" | "admin";
  is_superadmin: boolean;
};

export type Session = {
  title: string;
  start_at: string;
  end_at: string;
  location: string;
};

export type EventItem = {
  id: string;
  event_code: string;
  title: string;
  description: string;
  location: string;
  start_at: string;
  end_at: string;
  google_form_url?: string | null;
  feedback_questions: string[];
  sessions: Session[];
  feedback_open: boolean;
  registration_count: number;
  is_registered: boolean;
  has_feedback: boolean;
  created_by: string;
};

export type PaginatedEvents = {
  items: EventItem[];
  total: number;
  page: number;
  page_size: number;
};

export type FeedbackResponse = {
  id: string;
  event_id: string;
  user_id: string;
  user_name: string;
  rating: number;
  comment: string;
  answers: Record<string, string>;
  submitted_at: string;
};

export type FeedbackSummary = {
  event_id: string;
  event_title: string;
  response_count: number;
  average_rating: number | null;
  responses: FeedbackResponse[];
};

export type Registration = {
  id: string;
  user_id: string;
  user_name: string;
  user_email: string;
  registered_at: string;
};
