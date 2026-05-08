# CORS Deployment Guide - Production Verification

## Status: ✅ COMPLETE

All CORS issues have been fixed for Vercel production deployment.

---

## Backend Fixes Implemented

### 1. CORS Middleware Configuration
**File:** [backend/main.py](backend/main.py#L162-L173)

✅ **Explicit Origins (No Wildcard)**
```python
ALLOWED_CORS_ORIGINS = _build_allowed_cors_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_CORS_ORIGINS,  # Explicit list, not "*"
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization", "Content-Type", "Accept", "Origin",
        "Cache-Control", "Pragma", "Last-Event-ID", "X-Requested-With",
    ],
    expose_headers=["Content-Type", "Cache-Control", "Connection", "X-Accel-Buffering"],
    max_age=600,
)
```

**Default Allowed Origins:**
- `https://offerhunterai.vercel.app`
- `https://www.offerhunterai.vercel.app`
- `http://localhost:3000`, `http://127.0.0.1:3000` (dev)
- `http://localhost:3001`, `http://127.0.0.1:3001` (dev)
- `http://localhost:5173`, `http://127.0.0.1:5173` (dev)
- `http://localhost:4173`, `http://127.0.0.1:4173` (dev)
- `http://localhost:8000`, `http://127.0.0.1:8000` (dev)

### 2. Environment-Driven Origin Configuration
**Function:** [_build_allowed_cors_origins()](backend/main.py#L58-L71)

✅ **Dynamic Configuration via Environment Variables**
```python
def _build_allowed_cors_origins() -> list[str]:
    defaults = { /* defaults above */ }
    configured = {
        value.strip().rstrip("/")
        for value in (os.getenv("CORS_ALLOW_ORIGINS", "") + "," + 
                     os.getenv("FRONTEND_URL", "")).split(",")
        if value.strip()
    }
    return sorted(defaults | configured)
```

### 3. SSE Endpoint CORS Headers
**File:** [backend/main.py](backend/main.py#L344-L391)

✅ **Streaming Response with Proper CORS Headers**
```python
@app.get("/agent-events/stream")
async def stream_agent_events(request: Request):
    # ... event generator setup ...
    
    request_origin = (request.headers.get("origin") or "").rstrip("/")
    allow_origin = request_origin if request_origin in ALLOWED_CORS_ORIGINS else ALLOWED_CORS_ORIGINS[0]

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Access-Control-Allow-Origin": allow_origin,
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Vary": "Origin",
        },
    )
```

---

## Frontend Fixes Implemented

### 1. Centralized API URL Builder
**File:** [frontend/lib/api.ts](frontend/lib/api.ts#L1-L4)

✅ **Normalized Base URL with Trailing Slash Removal**
```typescript
const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000")
  .replace(/\/+$/, "");

export function buildApiUrl(path: string): string {
  return `${API_URL}/${path.replace(/^\/+/, "")}`;
}
```

### 2. EventSource Using Normalized URL
**File:** [frontend/lib/api.ts](frontend/lib/api.ts#L108-L109)

✅ **SSE Connection with Proper CORS**
```typescript
export function createEventSource(onMessage: (event: MessageEvent) => void) {
  const es = new EventSource(buildApiUrl("/agent-events/stream"));
  es.onmessage = onMessage;
  return es;
}
```

### 3. All API Calls Using buildApiUrl
**File:** [frontend/app/company-finder/page.tsx](frontend/app/company-finder/page.tsx)

✅ **No Raw URL Concatenation**
- All fetch calls use `buildApiUrl(path)` helper
- Eliminates double-slash URL issues
- Consistent API URL construction across frontend

---

## Deployment Checklist

### ✅ Code Changes (Already Complete)
- [x] Backend CORS middleware configured with explicit origins
- [x] SSE endpoint returns proper CORS headers
- [x] Frontend API URL centralized in `buildApiUrl()` helper
- [x] All frontend fetch calls use normalized URLs
- [x] No wildcard CORS origins in production
- [x] Middleware registered before route declarations
- [x] All code passes validation (py_compile, TypeScript)
- [x] Frontend builds successfully (pnpm build)

### 📋 Vercel Backend Project Configuration

Set these environment variables in Vercel backend project settings:

**Required:**
```
CORS_ALLOW_ORIGINS=https://offerhunterai.vercel.app
FRONTEND_URL=https://offerhunterai.vercel.app
```

**Optional (for preview deployments):**
```
CORS_ALLOW_ORIGINS=https://offerhunterai-preview.vercel.app,https://offerhunterai.vercel.app
```

### 📋 Vercel Frontend Project Configuration

Verify this environment variable is set:

**Required:**
```
NEXT_PUBLIC_API_URL=https://offer-hunter-ai-uuj1.vercel.app
```

**⚠️ Important:** Do NOT include a trailing slash. The `buildApiUrl()` function handles path joining.

---

## Production Verification Steps

After deployment to Vercel:

1. **Open browser DevTools** on https://offerhunterai.vercel.app
2. **Navigate to company-finder page**
3. **Open Network tab** in DevTools
4. **Initiate a company finder session** (click "Start Discovery")
5. **Look for `/agent-events/stream` request**
   - Should show **200 OK** status
   - Should have headers:
     ```
     access-control-allow-origin: https://offerhunterai.vercel.app
     content-type: text/event-stream
     cache-control: no-cache, no-transform
     connection: keep-alive
     ```
6. **Check Console** - should see no CORS errors
7. **Verify SSE events** - real-time agent updates should appear

---

## Troubleshooting

### Issue: CORS Error in Browser Console

**Symptom:** `"No 'Access-Control-Allow-Origin' header is present"`

**Solution:**
1. Verify `CORS_ALLOW_ORIGINS` env var is set in Vercel backend project
2. Check env var value matches frontend URL (https://offerhunterai.vercel.app)
3. Redeploy backend after env var changes
4. Clear browser cache (Ctrl+Shift+Delete)
5. Check backend logs at https://vercel.com/dashboard → Backend Project → Logs

### Issue: EventSource Connection Fails

**Symptom:** SSE connection times out, no real-time updates

**Solution:**
1. Verify `/agent-events/stream` endpoint returns `text/event-stream` content type
2. Check `X-Accel-Buffering: no` header is present
3. Verify backend is running (check health endpoint: `/health`)
4. Look for proxy/firewall blocks on `agent-events` endpoint

### Issue: Double-Slash URLs Causing 404s

**Symptom:** API requests to `https://...//path/resource` fail

**Solution:**
- ✅ Already fixed: `buildApiUrl()` removes double slashes
- All fetch calls use the helper function
- No raw `process.env.NEXT_PUBLIC_API_URL` concatenation

---

## Files Modified

| File | Changes |
|------|---------|
| [backend/main.py](backend/main.py) | CORS middleware with explicit origins, SSE endpoint headers |
| [frontend/lib/api.ts](frontend/lib/api.ts) | `buildApiUrl()` helper, URL normalization |
| [frontend/app/company-finder/page.tsx](frontend/app/company-finder/page.tsx) | All API calls use `buildApiUrl()` |

---

## Technical Details

### Why Explicit Origins Instead of Wildcard?

Browsers reject `allow_origins=["*"]` with `allow_credentials=True` because:
- Wildcard origins cannot be combined with credentialed requests
- Frontend needs to send credentials (auth tokens)
- Production requires explicit origin validation

**Our Solution:** Dynamic origin building from env vars allows flexibility without compromising security.

### Why SSE Endpoint Needs Explicit CORS Headers?

FastAPI's CORSMiddleware only handles standard HTTP requests. For Server-Sent Events:
- Browser initiates HTTP GET request (catches preflight issues)
- Server streams responses indefinitely
- Response headers must include CORS headers for browser to accept

**Our Solution:** Manually inject CORS headers in StreamingResponse

### Why URL Normalization?

Scattered raw env URL concatenation across frontend caused:
- Double-slash URLs: `https://url//path`
- Hardcoded localhost fallbacks
- Inconsistent URL formatting

**Our Solution:** Centralized `buildApiUrl()` ensures consistent, properly formatted URLs everywhere.

---

## Next Steps

1. **Push code to GitHub** (all changes ready)
2. **Deploy both projects to Vercel** (automatic on push)
3. **Set environment variables** in Vercel project settings
4. **Verify production CORS** using browser DevTools
5. **Monitor logs** for any CORS-related errors

---

**Last Updated:** May 9, 2026  
**Status:** Ready for Production Deployment ✅
