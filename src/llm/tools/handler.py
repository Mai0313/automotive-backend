from .fan import set_fan_speed_response
from .time import get_time_response
from .weather import get_weather_response
from .google_map import google_map_response
from .temperature import set_temp_response
from .front_windshield import front_defrost_on_response


async def handle_function(
    function_name, tool_call_id, args, llm, context, result_callback
) -> None:
    if function_name == "front_winshield_defroster":
        response = await front_defrost_on_response(args)
        await result_callback(response)

    elif function_name == "set_temp":
        response = await set_temp_response(args)
        await result_callback(response)

    elif function_name == "set_fan_speed":
        response = await set_fan_speed_response(args)
        await result_callback(response)

    elif function_name == "google_map":
        response = await google_map_response(args)
        await result_callback(response)

    elif function_name == "get_current_weather":
        response = await get_weather_response(args)
        await result_callback(response)

    elif function_name == "get_current_time":
        response = await get_time_response(args)
        await result_callback(response)

    else:
        print(f"❌ Unknown function: {function_name}")
        await result_callback({"error": f"Unknown function {function_name}"})
