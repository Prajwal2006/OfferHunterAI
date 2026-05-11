# OfferHunter AI Logging System - Quick Reference

## 🚀 Quick Start

### Where are logs stored?
```
logs/
├── api-requests.jsonl
├── api-responses.jsonl
├── llm-calls.jsonl
├── llm-responses.jsonl
├── database-operations.jsonl
├── business-logic.jsonl
├── agent-events.jsonl
├── errors.jsonl
├── performance.jsonl
├── frontend-events.jsonl
└── ... (more)
```

## 📝 Backend Logging

### Python: Import and use the logger
```python
from services.logger_service import get_logger

logger = get_logger()

# Log a business action
logger.log_business_logic(
    action="company_discovered",
    user_id="user-123",
    details={"company": "ACME", "score": 95}
)

# Log an error
logger.log_error(
    error_type="api_error",
    message="Failed to call LinkedIn API",
    user_id="user-123",
    severity="error"
)

# Log performance
logger.log_performance(
    operation="resume_parsing",
    duration_ms=1234.5,
    user_id="user-123"
)
```

### LLM Calls (Automatic Logging)
```python
from services.ai_common_logged import OpenAIJsonClient

client = OpenAIJsonClient()

# Automatically logs prompt, response, tokens, and duration
response = await client.create_json(
    system="You are a helpful assistant",
    user="Write me an email",
    user_id="user-123"  # Optional: for tracking
)
```

## 💻 Frontend Logging

### React: Import and use useTracking hook
```typescript
import { useTracking } from "@/lib/use-tracking";

export function MyComponent() {
  const { trackClick, trackEvent, trackError, trackPerformance } = useTracking({
    component: "MyComponent",
    userId: currentUserId
  });

  // Log button click
  const handleClick = () => {
    trackClick("action_name", { extra: "data" });
  };

  // Log user action
  const handleAction = () => {
    trackEvent("action_type", "action_name", { details: "here" });
  };

  // Log error
  const handleError = (error) => {
    trackError(error, { context: "what_I_was_doing" });
  };

  // Log performance
  const handleSlowOp = async () => {
    const start = performance.now();
    await slowOperation();
    const duration = performance.now() - start;
    trackPerformance("operation_name", duration, 1000); // 1000ms threshold
  };

  return <button onClick={handleClick}>Click me</button>;
}
```

### API Calls (Automatic Logging)
```typescript
import { runAgents, apiFetch } from "@/lib/api";

// All API calls via apiFetch are automatically logged
const response = await apiFetch("/api/endpoint", {
  method: "POST",
  body: JSON.stringify({ data: "value" })
});

// High-level API functions also log automatically
const result = await runAgents({
  skills: ["Python"],
  job_title: "Engineer",
  company_count: 50
});
```

## 📊 Viewing Logs

### Real-time monitoring (Linux/Mac)
```bash
# Watch all logs
tail -f logs/*.jsonl

# Watch only API requests
tail -f logs/api-requests.jsonl

# Watch only LLM calls
tail -f logs/llm-calls.jsonl

# Pretty print with jq
tail -f logs/llm-responses.jsonl | jq '.'

# Filter by user
tail -f logs/*.jsonl | grep "user-123"
```

### Search logs
```bash
# Find all errors
grep '"error"' logs/errors.jsonl

# Find slow operations (>1000ms)
grep -E '"is_slow": true' logs/performance.jsonl

# Count API calls
wc -l logs/api-requests.jsonl

# Find failed LLM calls
grep '"error"' logs/llm-responses.jsonl | jq '.error, .duration_ms'
```

### Analyze with jq
```bash
# List all unique endpoints
jq '.endpoint' logs/api-requests.jsonl | sort | uniq

# Calculate average API response time
jq '.duration_ms' logs/api-responses.jsonl | jq -s 'add/length'

# Count button clicks by component
grep "button_click" logs/frontend-events.jsonl | jq '.component' | sort | uniq -c

# Find most expensive LLM calls (tokens used)
jq '.tokens_used' logs/llm-responses.jsonl | sort -rn | head -10

# Group API calls by endpoint and count
jq '.endpoint' logs/api-requests.jsonl | sort | uniq -c | sort -rn
```

## 🔍 Common Queries

### Find what user "user-123" did
```bash
grep "user-123" logs/*.jsonl | jq '{timestamp, event_type, action, component}'
```

### Track an email generation flow
```bash
grep "generate_email" logs/*.jsonl | jq '{timestamp, source: .endpoint, status_code}'
```

### See all LLM calls for a user
```bash
grep "user-123" logs/llm-calls.jsonl | jq '{timestamp, model, tokens: .estimated_tokens}'
```

### Find slow API endpoints
```bash
jq 'select(.duration_ms > 2000) | {endpoint, method, duration_ms}' logs/api-responses.jsonl
```

### Trace a specific request
```bash
grep "req-id-123" logs/*.jsonl | sort -k2 | jq '{timestamp, event_type: .kind, status: .status_code}'
```

## 📈 Analytics

### Total API requests today
```bash
grep "$(date +%Y-%m-%d)" logs/api-requests.jsonl | wc -l
```

### Success rate
```bash
TOTAL=$(jq 'select(.status_code) | select(.status_code >= 200 and .status_code < 300)' logs/api-responses.jsonl | wc -l)
FAILED=$(jq 'select(.status_code) | select(.status_code >= 400)' logs/api-responses.jsonl | wc -l)
echo "Success rate: $(( TOTAL * 100 / (TOTAL + FAILED) ))%"
```

### Average response time by endpoint
```bash
jq '.endpoint + ": " + (.duration_ms|tostring) + "ms"' logs/api-responses.jsonl | \
  sed 's/"//g' | \
  awk '{sum[$1]+=$NF; count[$1]++} END {for (e in sum) print e " avg: " sum[e]/count[e] "ms"}'
```

### LLM cost estimate (GPT-4o-mini pricing)
```bash
# Assuming: input $0.15/1M tokens, output $0.60/1M tokens
cat logs/llm-responses.jsonl | jq '[.tokens_prompt * 0.15 + .tokens_completion * 0.60] | add / 1000000' 
```

## 🔐 What's NOT Logged

For privacy and security, the following are excluded:
- Authorization headers
- Cookie values
- Passwords and API keys
- Binary file contents
- Large email bodies (truncated)

## 🎯 Best Practices

1. **Always include user_id** when logging to track user actions
2. **Add context** - include relevant details like company names, job titles
3. **Use meaningful action names** - "company_liked" not just "click"
4. **Log errors with severity** - helps prioritize issues
5. **Monitor performance** - track operations that should be fast
6. **Batch frontend logs** - they're sent every 5 seconds or when buffer reaches 50

## 🚨 Troubleshooting

### Logs not appearing?
1. Check `logs/` directory exists: `ls -la logs/`
2. Check file permissions: `chmod 755 logs/`
3. Check backend console for errors
4. Verify logger service is imported in `backend/main.py`

### Frontend logs not being sent?
1. Open browser DevTools → Network tab
2. Look for POST to `/debug/logs/frontend`
3. Check response status (should be 200)
4. Manually flush: `clientLogger.flushNow()`

### Log files too large?
1. Archive old logs: `tar -czf logs-backup.tar.gz logs/*.jsonl`
2. Delete archived logs: `rm logs/*.jsonl`
3. Implement log rotation in deployment

## 📚 Full Documentation

See [LOGGING_GUIDE.md](./LOGGING_GUIDE.md) for comprehensive documentation including:
- Detailed log format specifications
- Advanced analytics examples
- Integration with external services
- Log retention strategies
