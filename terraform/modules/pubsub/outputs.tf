output "topic_name" {
  value = google_pubsub_topic.topic_tickets.name
}

output "topic_id" {
  value = google_pubsub_topic.topic_tickets.id
}

output "subscription_name" {
  value = google_pubsub_subscription.sub_tickets.name
}
