from app.services.gateway import SimulatedGateway


async def test_gateway_uses_injected_rng_and_sleeper() -> None:
    delays: list[float] = []

    async def sleeper(delay: float) -> None:
        delays.append(delay)

    gateway = SimulatedGateway(rng=lambda: 0.95, uniform=lambda _a, _b: 3.0, sleeper=sleeper)

    assert await gateway.process() == "failed"
    assert delays == [3.0]
