import threading
import pygame
import websockets
import asyncio
import json
import secrets
import time
import argparse
from pathlib import Path
from typing import Dict
from pygame.locals import (
    K_UP,
    K_DOWN,
    K_LEFT,
    K_RIGHT,
    K_ESCAPE,
    KEYDOWN,
    QUIT,
)

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

#WS
INIT_CLIENT_CMD = 'initClientCmd'

CLIENT_GAME_KEY = 'clientGameKey'

WS_TOKEN = init_token()

WS_TICK_RATE = 12

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

INPUT_INDEV_SPACE = 'indevSpace'

class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH,SCREEN_HEIGHT))
        self.running = True
        self.sprites_dict: Dict[str,Cell] = {}
        self.requests_thread = threading.Thread(target=self.start_websocket,daemon=True)
        self.last_arrow_pressed = None

        self.player_id = ''

    def start(self):
        pygame.init()

        self.requests_thread.start()

        self.game_loop()

        pygame.quit()

    async def websocket_loop(self):
        uri = "ws://18.221.38.228:8000/ws"
        #uri = "ws://127.0.0.1:8000/ws"
        async with websockets.connect(uri) as ws:
            await self.initialize_client(ws)
            a = asyncio.get_event_loop().time()
            while self.running:
                start_time = asyncio.get_event_loop().time()

                print(asyncio.get_event_loop().time()-a)
                a = asyncio.get_event_loop().time()

                msg = {WS_TOKEN:self.last_arrow_pressed}
                response = await self.send_msg(ws,msg)
                self.parse_delta(response)

                elapsed = asyncio.get_event_loop().time() - start_time
                remaining = (1.0 / WS_TICK_RATE) - elapsed
                
                if remaining > 0:
                    await asyncio.sleep(remaining)

    async def initialize_client(self,ws: websockets.ClientConnection):
        msg = {WS_TOKEN:INIT_CLIENT_CMD}
        response = await self.send_msg(ws,msg)
        self.player_id = response[CLIENT_GAME_KEY]
        print(self.player_id)

    async def send_msg(self,ws,msg):
            await ws.send(json.dumps(msg))
            response = await ws.recv()
            response_dict = json.loads(response)
            return response_dict

    def parse_delta(self,response):
        for key,value in response.items():
            if key in self.sprites_dict:
                self.sprites_dict[key].update_coords(x=value['x'],y=value['y'])
            else:
                self.sprites_dict[key] = Cell(x=value['x'],y=value['y'])

    def start_websocket(self):
        asyncio.run(self.websocket_loop())  
    
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

class Cell(pygame.sprite.Sprite):
    def __init__(self,x,y):
        super(Cell, self).__init__()
        self.surf = pygame.Surface((CELL_WIDTH,CELL_HEIGHT))
        self.surf.fill(CELL_BG)
        self.rect = self.surf.get_rect()
        self.rect.x = x*CELL_WIDTH
        self.rect.y = y*CELL_HEIGHT

    def blit(self,screen):
        screen.blit(self.surf,self.rect)

    def update_coords(self,x,y):
        self.rect.x=x*CELL_WIDTH
        self.rect.y=y*CELL_HEIGHT

    def add_tail(self):
        print(self.rect.x,self.rect.y)
        if self.tail:
            self.tail.add_tail()
            return
        x=self.rect.x-self.angle[0]*CELL_WIDTH
        y=self.rect.y-self.angle[1]*CELL_HEIGHT
        self.tail = Cell(x=x,y=y,angle=self.angle,tick_count=self.tick_count)
        print(self.tail.angle)

if __name__ == '__main__':
    game=Game()
    game.start()