# Stable approach check
# Based on Flight Safety Foundation stabilized approach criteria

def check_approach(airspeed, target_speed, sink_rate, altitude_agl):
    warnings = []

    if airspeed > target_speed + 10:
        warnings.append("Too fast")
    if airspeed < target_speed - 5:
        warnings.append("Too slow")
    if sink_rate > 1000:
        warnings.append("Sink rate too high")

    if warnings and altitude_agl < 500:
        return "UNSTABLE: go around. " + ", ".join(warnings)
    if warnings:
        return "Caution: " + ", ".join(warnings)
    return "Stable"


print(check_approach(airspeed=78, target_speed=65, sink_rate=800, altitude_agl=400))
