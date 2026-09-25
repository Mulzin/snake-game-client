import time
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
    K_SPACE,
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
WEBSOCKET_TICK_RATE = 1/30

#GAME
CELL_WIDTH = 16
CELL_HEIGHT = 16

CELL_BG = (255,255,255)

SCREEN_WIDTH = 64*CELL_WIDTH
SCREEN_HEIGHT = 32*CELL_HEIGHT

SCREEN_BG = (0,0,0)

GAME_TICK_RATE = 30

INPUT_NONE = 'kNone'
INPUT_K_UP = 'kUp'
INPUT_K_DOWN = 'KDown'
INPUT_K_LEFT = 'kLeft'
INPUT_K_RIGHT = 'kRight'

INDEV_STAND_STILL = 'standStill'

class Cell(pygame.sprite.Sprite):
    def __init__(self,
            x,y,
            rgb=CELL_BG):
        super(Cell, self).__init__()
        self.surf = pygame.Surface((CELL_WIDTH,CELL_HEIGHT))
        self.surf.fill(rgb)
        self.rect = self.surf.get_rect()
        self.rect.x = x*CELL_WIDTH
        self.rect.y = y*CELL_HEIGHT

    def blit(self,screen):
        screen.blit(self.surf,self.rect)

    def update_coords(self,x,y):
        self.rect.x=x*CELL_WIDTH
        self.rect.y=y*CELL_HEIGHT

class Client:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH,SCREEN_HEIGHT))
        self.sprites_dict: Dict[str,Cell] = {}
        self.last_arrow_pressed = INPUT_K_RIGHT

        self.running = True

        self.websocket: Optional[websockets.ClientConnection] = None
        self.websocket_thread = threading.Thread(target=self.start_websocket, daemon=True)
        self.send_queue: asyncio.Queue = None

    def start_client(self):
        logging.info("Starting client")

        pygame.init()

        self.websocket_thread.start()
        
        self.game_loop()

    def game_loop(self):
        clock = pygame.time.Clock()

        while self.running:
            self.handle_events()

            self.handle_pressed_keys()

            self.screen.fill(SCREEN_BG)

            for sprite in self.sprites_dict.values(): sprite.blit(self.screen)
            
            pygame.display.flip()
            
            clock.tick(GAME_TICK_RATE)

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    self.running = False

    def handle_pressed_keys(self):
        pressed_keys = pygame.key.get_pressed()

        if pressed_keys[K_UP]: self.last_arrow_pressed = INPUT_K_UP
        elif pressed_keys[K_DOWN]: self.last_arrow_pressed = INPUT_K_DOWN
        elif pressed_keys[K_LEFT]: self.last_arrow_pressed = INPUT_K_LEFT
        elif pressed_keys[K_RIGHT]: self.last_arrow_pressed = INPUT_K_RIGHT
        elif pressed_keys[K_SPACE]: self.last_arrow_pressed = INDEV_STAND_STILL

    def start_websocket(self):
        asyncio.run(self.websocket_loop())

    async def websocket_loop(self):
        uri = "ws://127.0.0.1:8000/ws"
        try:
            async with websockets.connect(uri) as ws:
                self.websocket = ws

                await self.initialize_client()

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
        while self.running:
            start_time = asyncio.get_event_loop().time()
            
            package = {
                'token':WEBSOCKET_TOKEN,
                'type':'clientInput',
                'data':self.last_arrow_pressed
            }

            try:
                await self.send_json(package)
            except Exception as e:
                logging.error(f"Send error: {e}")
                break

            elapsed = asyncio.get_event_loop().time() - start_time
            remaining = (WEBSOCKET_TICK_RATE) - elapsed
            
            if remaining > 0:
                await asyncio.sleep(remaining)

    def parse_delta(self,package):
        for ent in package['data']['update']:
            ent_id = ent['entID']
            if ent_id in self.sprites_dict:
                self.sprites_dict[ent_id].update_coords(x=ent['x'],y=ent['y'])
            else:
                self.sprites_dict[ent_id] = Cell(x=ent['x'],y=ent['y'],rgb=ent['rgb'])

        for ent in package['data']['delete']:
            self.sprites_dict.pop(ent['tokenId'])

    async def receive_loop(self):
        while self.running:
            try:
                package = await self.receive_json()

                if package['type'] == 'delta': self.parse_delta(package)
                
            except Exception as e:
                logging.error(f"Receive error: {e}")
                break

if __name__ == '__main__':
    client = Client()
    client.start_client()