from openai.types.chat import ChatCompletionToolParam

from src.llm.connects import pg_connect

# Tool parameter definition
set_temp_tool = ChatCompletionToolParam(
    type="function",
    function={
        "name": "set_temp",
        "description": "Set the car's air conditioner to the target temperature",
        "parameters": {
            "type": "object",
            "properties": {
                "temp": {
                    "type": "integer",
                    "description": "Target temperature in Celsius, if user provide a floating point, please round it to an integer.",
                }
            },
            "required": ["temp"],
        },
    },
)


# Get temp
def get_temp():
    cur = pg_connect()
    try:
        cur.execute("SELECT temperature FROM ac_settings")
        result = cur.fetchone()
        if result:
            return result[0]
        return None
    finally:
        cur.close()


# 絕對溫度設定
async def set_temp_response(args) -> str:
    # temp = int(round(args["temp"]))  # Round to integer as specified
    temp = int(args["temp"])  # Directly convert to integer
    temp = max(min(temp, 30), 16)  # Ensure temp is between 16 and 30
    # if not isinstance(temp, int):
    #     raise TypeError("Temperature must be an integer.")

    # if 16 <= temp <= 30:
    cur = pg_connect()
    cur.execute("UPDATE ac_settings SET temperature = %s", (temp,))
    cur.connection.commit()
    cur.close()
    return f"The temperature was set successfully. Current AC temperature: {temp}°C"
    # raise ValueError("Temperature must be an integer between 16 and 30.")
