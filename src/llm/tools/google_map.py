import random

from openai.types.chat import ChatCompletionToolParam

# Tool parameter definition
google_map_tool = ChatCompletionToolParam(
    type="function",
    function={
        "name": "google_map",
        "description": "Navigate to or find the target location with Google Maps.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "Target location that users are looking for (e.g., 'gas station', 'coffee shop', 'restaurant', 'convenience store', etc.)",
                }
            },
            "required": ["location"],
        },
    },
)


# 簡易 Google map 位置
async def google_map_response(args) -> str:
    location = args["location"]
    num = round(random.uniform(1, 10), 1)
    return f"The nearest {location} is {num} kilometers away. I will navigate you to the {location} now. Please follow the directions on the map."
