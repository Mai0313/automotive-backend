from openai.types.chat import ChatCompletionToolParam

from llm.connects import pg_connect

# Tool parameter definition
front_defrost_on_tool = ChatCompletionToolParam(
    type="function",
    function={
        "name": "front_defrost_on",
        "description": "Turn on the front defrost of the car",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "boolean",
                    "description": "`True` stands for turn on the defrost, and `False` stands for turn off the defrost.",
                }
            },
            "required": ["status"],
        },
    },
)


def get_front_defrost_status() -> str | None:
    cur = pg_connect()
    try:
        cur.execute("SELECT front_defrost_on FROM ac_settings")
        result = cur.fetchone()
        if result:
            return "on" if result[0] else "off"
        return None
    finally:
        cur.close()


# 除霜開關
async def front_defrost_on_response(args) -> str:
    status = args["status"]

    # handle string inputs for boolean
    if isinstance(status, str):
        if status.lower() == "true":
            status = True
        elif status.lower() == "false":
            status = False

    # ensure status is boolean
    if not isinstance(status, bool):
        raise TypeError("Front defrost must be Boolean.")

    cur = pg_connect()
    cur.execute("UPDATE ac_settings SET front_defrost_on = %s", (status,))
    cur.connection.commit()
    cur.close()
    return f"Finished front defrost settings. Current Windshield defrost: {'on' if status else 'off'}."
