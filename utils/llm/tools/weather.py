import random

from openai.types.chat import ChatCompletionToolParam

get_current_weather = ChatCompletionToolParam(
    type="function",
    function={
        "name": "get_current_weather",
        "description": "Get the current weather",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City and state, e.g. San Francisco, CA"},
                "format": {"type": "string", "enum": ["celsius", "fahrenheit"], "description": "Temperature unit"},
            },
            "required": ["location", "format"],
        },
    },
)


async def get_weather_response(args):
    return {
        "location": args["location"],
        "conditions": random.choice(["sunny", "cloudy", "raining"]),
        "temperature": random.choice(["18", "22", "26", "30"]),
        "unit": args["format"],
    }
