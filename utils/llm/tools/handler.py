from .time import get_time_response
from .weather import get_weather_response
from .front_windshield import front_defrost_on_response
from .temperature import set_temp_response
from .fan import set_fan_speed_response
from .google_map import google_map_response


async def handle_function(function_name, tool_call_id, args, llm, context, result_callback):
    if function_name == "front_defrost_on":
        response = await front_defrost_on_response(args)
        print(f"❄️ Front defrost: {response}")
        await result_callback(response)

    elif function_name == "set_temp":
        response = await set_temp_response(args)
        print(f"🌡️ Temperature setting: {response}")
        await result_callback(response)

    elif function_name == "set_fan_speed":
        response = await set_fan_speed_response(args)
        print(f"💨 Fan speed setting: {response}")
        await result_callback(response)

    elif function_name == "google_map":
        response = await google_map_response(args)
        print(f"🗺️ Google Maps query: {response}")
        await result_callback(response)

    if function_name == "get_current_weather":
        response = await get_weather_response(args)
        print(f"🌤️ Weather query: {response}")
        await result_callback(response)

    elif function_name == "get_current_time":
        response = await get_time_response(args)
        print(f"🕐 Time query: {response}")
        await result_callback(response)

    else:
        print(f"❌ Unknown function: {function_name}")
        await result_callback({"error": f"Unknown function {function_name}"})
