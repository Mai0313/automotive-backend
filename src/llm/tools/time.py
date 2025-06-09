import datetime
from datetime import UTC

from openai.types.chat import ChatCompletionToolParam

get_current_time = ChatCompletionToolParam(
    type="function",
    function={
        "name": "get_current_time",
        "description": "Get the current local time of a user-specified city",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "City name to get time for"}},
            "required": ["city"],
        },
    },
)


async def get_time_response(args):
    now = datetime.datetime.now(UTC)
    return {"city": args["city"], "utc_time": now.strftime("%Y-%m-%d %H:%M:%S UTC")}
