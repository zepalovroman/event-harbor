def requires_gateway(status: str) -> bool:
    return status == "pending"


def retry_queue_name(attempt: int) -> str | None:
    if attempt == 1:
        return "payments.retry.2"
    if attempt == 2:
        return "payments.retry.4"
    return None
