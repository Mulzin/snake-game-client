import websockets
import asyncio
import threading
import json
import secrets
import argparse
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--tokenpath', default='ws-token.json')

args=parser.parse_args()

token_path = args.tokenpath

def init_token():
    token_file = Path(token_path)
    if token_file.exists():
        with open(token_file,'r') as f:
            old_token = json.load(f)
            return old_token['token']
    else:
        new_token = secrets.token_urlsafe(32)
        with open(token_file, 'w') as f:
            json.dump({'token': new_token}, f, indent=2)
        return new_token

WS_TOKEN = init_token()

#WS_URI = "ws://18.221.38.228:8000/ws"
WS_URI = "ws://127.0.0.1:8000/ws"

class Game:
    def __init__(self):
        self.is_running = True
        self.websocket_thread = threading.Thread(target=self.start_websocket,daemon=True)
        self.ws: websockets.ClientConnection = None

    def start(self):
        print(0)
        self.websocket_thread.start()

        while self.is_running:
            time.sleep(1)

        #game loop

    async def websocket_loop(self):
        print(2)
        await self.initialize_websocket()

        await self.client_webhook()

    async def initialize_websocket(self):
        print(3)
        data = {'newClient':WS_TOKEN}
        try:
            self.ws = await websockets.connect(WS_URI)
            print(f'Connected to {WS_URI}')
            await self.ws.send(json.dumps(data))
            return True
        except Exception as e:
            print(f"Failed to connect to {WS_URI}: {e}")
            return False

    async def client_webhook(self):
        try:
            while self.is_running:
                data = await self.ws.recv()
                print(data)
        except Exception as e:
            print(f'Failed waiting for delta: {e}')

    def start_websocket(self):
        print(1)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(self.websocket_loop())
        finally:
            loop.close()

if __name__ == '__main__':
    game = Game()
    game.start()