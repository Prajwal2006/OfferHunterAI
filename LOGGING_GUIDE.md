# OfferHunter AI - Comprehensive Logging System

## Overview

This document describes the comprehensive logging system implemented for OfferHunter AI. The system logs every user interaction, API call, backend process, and LLM call with full context and timestamps.

## Log Storage

All logs are stored in the `logs/` directory at the root of the repository:

```
logs/
├── api-requests.jsonl              # All incoming API requests
├── api-responses.jsonl             # All API responses with status codes and duration
├── llm-calls.jsonl                 # All LLM (OpenAI) calls with full prompts
├── llm-responses.jsonl             # All LLM responses with tokens used
├── database-operations.jsonl       # All database operations (SELECT, INSERT, UPDATE, DELETE)
├── business-logic.jsonl            # Business logic events (company discovery, email generation, etc)
├── agent-events.jsonl              # Agent-specific events and status updates
├── errors.jsonl                    # Error logs with full context and stack traces
├── performance.jsonl               # Performance metrics and slow operation tracking
├── frontend-events.jsonl           # All frontend events (clicks, errors, etc)
├── api-calls.jsonl                 # Legacy format for backward compatibility
├── backend-actions.jsonl           # Legacy format for backward compatibility
├── frontend-api.jsonl              # Legacy format for frontend API calls
└── frontend-actions.jsonl          # Legacy format for frontend actions
```

## Log Format

All logs are stored in JSONL format (one JSON object per line). Each entry includes:
- `timestamp`: ISO 8601 formatted timestamp (UTC)
- `session_id`: Unique session ID for tracking related logs
- Additional context-specific fields

### Example Log Entries

**API Request:**
```json
{
  "timestamp": "2024-05-11T14:23:45.123456",
  "session_id": "session-123abc",
  "request_id": "req-456def",
  "endpoint": "/outreach/drafts/generate",
  "method": "POST",
  "user_id": "user-789ghi",
  "body": {"user_id": "user-789ghi", "company_id": "company-012jkl"},
  "client_host": "127.0.0.1",
  "user_agent": "Mozilla/5.0..."
}
```

**LLM Call:**
```json
{
  "timestamp": "2024-05-11T14:23:46.234567",
  "session_id": "session-123abc",
  "call_id": "llm-789xyz",
  "provider": "openai",
  "model": "gpt-4o-mini",
  "system_prompt": "You are an expert email writer...",
  "user_prompt": "Write a cold email to John Smith at ACME Corp...",
  "temperature": 0.35,
  "max_tokens": 2200,
  "user_id": "user-789ghi",
  "context": {...}
}
```

**LLM Response:**
```json
{
  "timestamp": "2024-05-11T14:23:49.345678",
  "session_id": "session-123abc",
  "call_id": "llm-789xyz",
  "response": "Dear John,\n\nI noticed your work on...",
  "response_json": {...},
  "tokens_used": 487,
  "tokens_prompt": 234,
  "tokens_completion": 253,
  "duration_ms": 3111.5,
  "error": null
}
```

**Button Click:**
```json
{
  "timestamp": "2024-05-11T14:23:50.456789",
  "session_id": "session-123abc",
  "event_type": "button_click",
  "component": "CompanyCard",
  "action": "generate_email",
  "details": {
    "company_id": "company-012jkl",
    "company_name": "ACME Corporation",
    "element": "btn-generate-email"
  },
  "level": "info"
}
```

## Backend Logging Usage

### 1. Basic Logging Service

```python
from services.logger_service import get_logger

logger = get_logger()

# Log API requests
logger.log_api_request(
    endpoint="/my-endpoint",
    method="POST",
    user_id="user-123",
    body={"key": "value"}
)

# Log API responses
logger.log_api_response(
    request_id="req-456",
    status_code=200,
    duration_ms=123.5
)

# Log errors
logger.log_error(
    error_type="database_connection_failed",
    message="Could not connect to Supabase",
    user_id="user-123",
    context={"attempt": 3},
    severity="error"
)

# Log performance
logger.log_performance(
    operation="company_discovery",
    duration_ms=5432.1,
    user_id="user-123",
    metadata={"companies_found": 42}
)
```

### 2. LLM Logging with OpenAI

The `OpenAIJsonClient` automatically logs all LLM interactions:

```python
from services.ai_common_logged import OpenAIJsonClient

client = OpenAIJsonClient()

# Automatically logs the call, response, and metrics
response = await client.create_json(
    system="You are an email writer",
    user="Write an email to John",
    user_id="user-123",
    context_metadata={"company": "ACME", "role": "CEO"}
)
```

This logs:
- **LLM Call**: Full prompt (system + user), model, temperature, max_tokens, user context
- **LLM Response**: Full response text, token usage, duration, any errors
- **Performance**: Total duration and whether it exceeded thresholds

### 3. Database Operation Logging

```python
logger.log_database_operation(
    operation="SELECT",  # SELECT, INSERT, UPDATE, DELETE
    table="companies",
    user_id="user-123",
    filters={"user_id": "user-123", "archived": False},
    result_count=42,
    duration_ms=123.5
)
```

### 4. Business Logic Logging

```python
logger.log_business_logic(
    action="company_discovered",
    user_id="user-123",
    details={
        "company_name": "ACME Corp",
        "domain": "acme.com",
        "source": "linkedin",
        "confidence_score": 0.95
    },
    level="INFO"
)
```

### 5. Agent Events

```python
logger.log_agent_event(
    agent_name="CompanyFinderAgent",
    event_type="started",
    user_id="user-123",
    task_id="task-789",
    message="Starting company discovery",
    status="processing",
    metadata={"count": 50}
)
```

## Frontend Logging Usage

### 1. Basic Client Logger

```typescript
import clientLogger from "@/lib/client-logger";
import { useTracking } from "@/lib/use-tracking";

// In a React component
export function MyComponent() {
  const { trackClick, trackEvent, trackError } = useTracking({
    component: "MyComponent",
    userId: currentUserId
  });

  const handleClick = () => {
    trackClick("button_clicked", {
      button_name: "generate_email",
      company_id: "123"
    });
  };

  const handleAction = async () => {
    trackEvent("user_action", "started_process", {
      process_name: "email_generation"
    });
    
    try {
      // Do something
    } catch (error) {
      trackError(error, { context: "email_generation" });
    }
  };

  return (
    <button onClick={handleClick}>Generate Email</button>
  );
}
```

### 2. API Call Logging

All API calls made through the enhanced `api.ts` are automatically logged:

```typescript
import { apiFetch, runAgents } from "@/lib/api";

// Automatically logs:
// - API request started
// - API response received (status, duration)
// - Any errors with full context
const response = await runAgents({
  skills: ["Python", "JavaScript"],
  job_title: "Software Engineer",
  company_count: 50
});
```

### 3. Performance Tracking

```typescript
const { trackPerformance } = useTracking({
  component: "CompanyLister"
});

const startTime = performance.now();
const companies = await loadCompanies();
const duration = performance.now() - startTime;

trackPerformance("load_companies", duration, 1000); // 1000ms threshold
```

### 4. Manual Direct Logging

```typescript
// Button click
clientLogger.logButtonClick(
  "CompanyCard",
  "like_button_clicked",
  { company_id: "123", company_name: "ACME" }
);

// API call
clientLogger.logApiCall("/outreach/drafts/generate", "POST", {
  user_id: "user-123"
});

// Error
clientLogger.logError(
  "email_generation_failed",
  "Connection timeout",
  { attempt: 2, endpoint: "/outreach/drafts/generate" }
);

// Performance
clientLogger.logPerformance(
  "render_company_list",
  234.5,
  1000 // threshold in ms
);
```

## Analyzing Logs

### Using Command Line

```bash
# View all API requests
cat logs/api-requests.jsonl | head -10

# Count LLM calls
wc -l logs/llm-calls.jsonl

# Find errors for a specific user
grep "user-123" logs/errors.jsonl

# Search for slow operations
grep -E '"is_slow": true' logs/performance.jsonl

# Parse and pretty-print JSON
cat logs/llm-calls.jsonl | jq '.'

# Filter by timestamp range
grep "2024-05-11T14:2" logs/llm-responses.jsonl

# Find all errors from a specific user
grep "user-123" logs/errors.jsonl | jq '.message'
```

### Log Query Examples

```bash
# Find all button clicks on a specific component
grep "button_click" logs/frontend-events.jsonl | grep "CompanyCard"

# Analyze OpenAI token usage
cat logs/llm-responses.jsonl | jq '[.tokens_used] | add'

# Find slow API endpoints
jq 'select(.duration_ms > 1000) | .endpoint' logs/api-responses.jsonl | sort | uniq -c

# Track user journey for specific user
grep "user-789ghi" logs/*.jsonl | sort -k2

# Find failed LLM calls with retry attempts
grep "error" logs/llm-responses.jsonl | jq '.error, .duration_ms, .call_id'
```

## Log Levels

All logs use one of these levels:
- `debug`: Detailed diagnostic information
- `info`: General informational messages (default)
- `warning`: Warning messages for potentially problematic situations
- `error`: Error messages for failures

## Performance Considerations

1. **Log Truncation**: Values larger than their max_chars limit are truncated to prevent log bloat
2. **Async Flushing**: Frontend logs are batched and sent to the backend periodically (5s or 50 logs)
3. **Backward Compatibility**: Legacy log formats are maintained for existing log processors
4. **Selective Logging**: Sensitive headers (Authorization) and large binary payloads are excluded

## Sensitive Data Handling

The logging system automatically excludes:
- Authorization headers
- Cookie headers
- Passwords and API keys
- Binary file contents (marked as `[binary body omitted]`)

## Accessing Logs in Development

```bash
# Docker Compose
docker-compose logs backend | tail -100

# Local development
tail -f logs/*.jsonl

# Real-time filtering
tail -f logs/llm-calls.jsonl | jq '.model'
```

## Exporting Logs

```bash
# Export logs for analysis (e.g., to CSV)
cat logs/api-responses.jsonl | jq -r '.endpoint,.status_code,.duration_ms' | paste - - - > responses.csv

# Archive old logs
tar -czf logs-backup-2024-05-11.tar.gz logs/*.jsonl

# Send logs to external service
curl -X POST -H "Content-Type: application/json" \
  --data-binary @logs/errors.jsonl \
  https://logs-service.example.com/api/logs
```

## Integration Examples

### Monitoring Email Generation Quality

```bash
# Track email generation metrics
cat logs/llm-calls.jsonl logs/llm-responses.jsonl | \
  jq -s 'group_by(.call_id) | map({
    call_id: .[0].call_id,
    duration_ms: .[1].duration_ms,
    tokens: .[1].tokens_used,
    model: .[0].model
  })' | jq '.[] | select(.duration_ms > 5000)'
```

### Tracing User Actions

```bash
# Complete trace of one user's session
USER_ID="user-123"
grep "$USER_ID" logs/*.jsonl | jq -s 'sort_by(.timestamp) | .[] | "\(.timestamp) | \(.event_type // .kind) | \(.action // .event // .endpoint)"'
```

### Cost Analysis

```bash
# Calculate LLM API costs
cat logs/llm-responses.jsonl | jq -s '[.[] | select(.tokens_used) | .tokens_used] | add' | awk '{print "Total tokens: " $1 ", Estimated cost: $" ($1 / 1000 * 0.00150)}'
```

## Troubleshooting

### Logs not appearing

1. Check that `logs/` directory exists: `ls -la logs/`
2. Verify logger service is imported: Check `backend/main.py` imports
3. Check file permissions: `ls -la logs/api-requests.jsonl`
4. Monitor frontend logs endpoint: Check network tab in browser DevTools

### Large log files

1. Archive old logs: `tar -czf logs-backup.tar.gz logs/*.jsonl && rm logs/*.jsonl`
2. Implement log rotation (consider adding to deployment)
3. Use grep/jq to extract relevant subset

### Missing LLM details

1. Ensure `OpenAIJsonClient` is used (not old `OpenAIJsonClient`)
2. Verify `user_id` and `context_metadata` are passed
3. Check that API key is set in environment variables

## Future Enhancements

Potential improvements to the logging system:
- [ ] Real-time log dashboard
- [ ] Automated alerts for errors or slow operations
- [ ] Log aggregation service integration
- [ ] Structured log querying interface
- [ ] Automatic cost tracking and budget alerts
- [ ] User journey visualization
