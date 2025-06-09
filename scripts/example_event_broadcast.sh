curl -X POST "http://localhost:8100/api/event/broadcast" \
  -H "Content-Type: application/json" \
  -d '{"message": "Tire pressure too low"}'
