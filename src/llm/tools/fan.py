from openai.types.chat import ChatCompletionToolParam

from src.llm.connects import pg_connect

# Tool parameter definition
set_fan_speed_tool = ChatCompletionToolParam(
    type="function",
    function={
        "name": "set_fan_speed",
        "description": "Set the car's fan to the target fan speed, fan speed can only between 0 and 5.",
        "parameters": {
            "type": "object",
            "properties": {
                "fan_speed": {
                    "type": "integer",
                    "description": "Target fan speed, if user provide a floating point, please round it to an integer. If the fan speed is outside the range of 0-5, please set 0 if below, and set 5 if above.",
                }
            },
            "required": ["fan_speed"],
        },
    },
)


def get_fan_speed():
    cur = pg_connect()
    try:
        cur.execute("SELECT fan_speed FROM ac_settings")
        result = cur.fetchone()
        if result:
            return result[0]
        return None
    finally:
        cur.close()


async def set_fan_speed_response(args) -> str:
    fan_upper_limit = 5
    fan_lower_limit = 0
    fan_speed = int(args["fan_speed"])  # Directly convert to integer
    fan_speed = max(min(fan_speed, fan_upper_limit), fan_lower_limit)

    if not isinstance(fan_speed, int):
        raise TypeError("Fan speed must be an integer.")

    # if 0 <= fan_speed <= 5:
    cur = pg_connect()
    cur.execute("UPDATE ac_settings SET fan_speed = %s", (fan_speed,))
    cur.connection.commit()
    cur.close()
    return f"The fan speed was set successfully. Current Fan speed: {fan_speed}"
    # raise ValueError(
    #     f"Fan speed must be an integer between {fan_lower_limit} and {fan_upper_limit}."
    # )
