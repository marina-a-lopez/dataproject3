resource "google_pubsub_topic" "topic_tickets" {
  name = "topic-tickets"
}

resource "google_pubsub_subscription" "sub_tickets" {
  name  = "sub-tickets"
  topic = google_pubsub_topic.topic_tickets.name

  ack_deadline_seconds       = 60
  message_retention_duration = "604800s"
}
