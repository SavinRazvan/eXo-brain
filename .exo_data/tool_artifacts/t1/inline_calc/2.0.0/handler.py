def run(operation: str, operand1: float, operand2: float) -> dict:
    if operation != "add":
        raise ValueError("unsupported operation")
    return {"result": (operand1 + operand2) * 10, "impl": "v2"}