import asyncio
import random
from collections.abc import Awaitable, Callable


class SimulatedGateway:
    def __init__(
        self,
        *,
        rng: Callable[[], float] = random.random,
        uniform: Callable[[float, float], float] = random.uniform,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._rng = rng
        self._uniform = uniform
        self._sleeper = sleeper

    async def process(self) -> str:
        await self._sleeper(self._uniform(2.0, 5.0))
        return "succeeded" if self._rng() < 0.9 else "failed"
