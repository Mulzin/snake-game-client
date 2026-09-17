import threading
import pygame
import websockets
import asyncio
import json
import secrets
import logging
import argparse
from pathlib import Path
from typing import Dict, Optional
from pygame.locals import (
    K_UP,
    K_DOWN,
    K_LEFT,
    K_RIGHT,
    K_ESCAPE,
    KEYDOWN,
    QUIT,
)

logging.basicConfig(level=logging.INFO)

parser = argparse.ArgumentParser()
parser.add_argument('--tokenpath', default='ws-token.json')
args = parser.parse_args()

token_path = args.tokenpath

def init_token():
    token_file = Path(token_path)
    if token_file.exists():
        with open(token_file, 'r') as f:
            old_token = json.load(f)
            return old_token['token']
    else:
        new_token = secrets.token_urlsafe(32)
        with open(token_file, 'w') as f:
            json.dump({'token': new_token}, f, indent=2)
        return new_token

WEBSOCKET_TOKEN = init_token()

class Client:
    def __init__(self):
        self.running = True
        self.websocket: Optional[websockets.ClientConnection] = None
        self.websocket_thread = threading.Thread(target=self.start_websocket, daemon=True)
        self.send_queue: asyncio.Queue = None

    def start_client(self):
        logging.info("Starting client")
        self.websocket_thread.start()
        # Keep main thread alive
        try:
            while self.running:
                threading.Event().wait(1)
        except KeyboardInterrupt:
            self.running = False

    def start_websocket(self):
        asyncio.run(self.websocket_loop())

    async def websocket_loop(self):
        uri = "ws://127.0.0.1:8000/ws"
        try:
            async with websockets.connect(uri) as ws:
                self.websocket = ws
                await self.initialize_client()

                # Run send and receive concurrently
                self.send_queue = asyncio.Queue()
                await asyncio.gather(
                    self.send_loop(),
                    self.receive_loop(),
                )
        except Exception as e:
            logging.error(f"WebSocket error: {e}")

    async def initialize_client(self):
        package = {
            'token': WEBSOCKET_TOKEN,
            'type': 'initclient',
            'data': None
        }
        await self.send_json(package)
        response = await self.receive_json()
        logging.info(f"Init response: {response}")

    async def send_json(self, package: Dict):
        if self.websocket:
            await self.websocket.send(json.dumps(package))

    async def receive_json(self) -> Dict:
        raw = await self.websocket.recv()
        return json.loads(raw)

    async def send_loop(self):
        """Periodically send status to server."""
        while self.running:
            try:
                await self.send_json({'client': 'here'})
            except Exception as e:
                logging.error(f"Send error: {e}")
                break
            await asyncio.sleep(1)

    async def receive_loop(self):
        """Continuously receive server messages."""
        while self.running:
            try:
                message = await self.receive_json()
                logging.info(f"Received: {message}")
            except Exception as e:
                logging.error(f"Receive error: {e}")
                break

if __name__ == '__main__':
    client = Client()
    client.start_client()