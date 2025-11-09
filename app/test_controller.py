from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import json
import asyncio

router = APIRouter()

# For SSE testing, send fake SSE messages
@router.get("/api/test-sse")
async def test_sse():
    response = StreamingResponse(generate_test_sse(), media_type="text/event-stream")
    response.headers["X-Accel-Buffering"] = "no"
    return response

async def generate_test_sse():
    duration = 60  # seconds
    interval = 0.05  # seconds
    iterations = int(duration / interval)

    for i in range(iterations):
        fake_message = {
            "type": "MESSAGE",
            "content": i + 1
        }
        yield f"data: {json.dumps(fake_message)}\n\n"
        await asyncio.sleep(interval)

    # Send final message
    final_message = {
        "type": "DONE",
        "total_messages": iterations
    }
    yield f"data: {json.dumps(final_message)}\n\n"
