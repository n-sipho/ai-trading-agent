import asyncio
import websockets

async def listen():
    async with websockets.connect('ws://localhost:8765') as ws:
        for _ in range(10):
            message = await ws.recv()
            print(message)

if __name__ == "__main__":
    asyncio.run(listen())
