def predict_temperature_excursion(temperature, threshold):
    """
    Basic threshold-based excursion check.

    Replace or extend this function with the trained
    machine-learning model when it is ready.
    """
    return {
        "temperature": temperature,
        "threshold": threshold,
        "excursion_detected": temperature > threshold,
    }