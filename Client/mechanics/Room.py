from MapObject import MapObject
from Client.mechanics.TextBox import TextBox
from Client.mechanics.ImageButton import ImageButton
from Client.mechanics.SelfInfoMenu import SelfInfoMenu
from Client.mechanics.PlayerInfoMenu import PlayerInfoMenu
from Client.mechanics.TradeRequest import TradeRequest
from Player import Player
from Client.mechanics.AStar.Search import search_path
from Screen import Screen


class Room(Screen):
    def __init__(self, world, room_id, bg_image, path, out):
        Screen.__init__(self, world, room_id, bg_image)
        self.path = MapObject(self.world, [0, 0], image=path, size=world.SIZE, is_visible=False)
        self.out = out
        self.chat_box = TextBox(self.world, [None, 540], 720, middle=self.bg_image)
        self.bag_button = ImageButton(self.world, [900, 540], 'images/test_text_box.9.png', [50, 50], 'images/bag.png')
        self.bag = MapObject(self.world, [600, 540], image='images/bag.png')
        self.self_info_menu = SelfInfoMenu(world)
        self.player_info_menu = PlayerInfoMenu(world)
        self.trade_requests = []

        self.world.cur_player = Player(world, data=self.world.client.player_info(self.world.cur_player.username))
        self.players = [self.world.cur_player]
        for i in self.world.client.find_players(room_id):
            if i != self.world.cur_player.username:
                self.players.append(Player(world, data=self.world.client.player_info(i)))

    def execute(self):
        update = self.world.client.updates
        for i in update:
            if i['code'] == 'POS':
                for j in self.players:
                    if i['headers']['username'] == j.username:
                        pos = [int(i['data'].split(' ')[0]) + j.width / 2, int(i['data'].split(' ')[1]) + j.height / 2]
                        path = search_path(self.world, (j.pos[0] + j.width / 2, j.pos[1] + j.height / 2), pos)
                        j.walking_path = path
                        update.remove(i)
                        break
            elif i['code'] == 'CONNECT':
                info = self.world.client.player_info(i['headers']['username'])
                self.players.append(Player(self.world, info))
                update.remove(i)
            elif i['code'] == 'QUIT':
                print 'someone quited'
                for j in self.players:
                    if i['headers']['username'] == j.username:
                        self.players.remove(j)
                        update.remove(i)
                        break
            elif i['code'] == 'CHAT':
                for j in self.players:
                    if i['headers']['username'] == j.username:
                        j.msg = i['headers']['message']
                        update.remove(i)
                        break
            elif i['code'] == 'ADD PLAYER':
                info = self.world.client.player_info(i['headers']['username'])
                self.players.append(Player(self.world, data=info))
                update.remove(i)
            elif i['code'] == 'REMOVE PLAYER':
                for j in self.players:
                    if i['headers']['username'] == j.username:
                        self.players.remove(j)
                        update.remove(i)
                        break
            elif i['code'] == 'CHANGE ITEM':
                for j in self.players:
                    if i['headers']['username'] == j.username:
                        for k in j.items:
                            if k.item_id == i['headers']['item_id']:
                                j.change_item(k)
                                break
                        update.remove(i)
                        break
            elif i['code'] == 'TRADE REQUEST':
                for j in self.players:
                    if i['headers']['sender'] == j.username:
                        self.trade_requests.append(TradeRequest(self.world, j, True))
                        update.remove(i)
                        break
            elif i['code'] == 'TRADE RESPONSE':
                for j in self.players:
                    if i['headers']['addressee'] == j.username:
                        for k in self.trade_requests:
                            if k.player == i['headers']['sender']:
                                self.trade_requests.remove(k)
                                break
                        print 'start trading!'
                        update.remove(i)
                        break

    def check_event(self, event, objects=None):
        if objects is None:
            objects = []

        buttons = []
        for i in self.trade_requests:
            for j in i.buttons:
                buttons.append(i.buttons[j])
        Screen.check_event(self, event, self.out + buttons + list(zip(*self.self_info_menu.cells)[1]) +
                           [self.path, self.bag_button, self.self_info_menu.x_button, self.player_info_menu.x_button, self.player_info_menu.trade_button]
                           + self.players + reduce(lambda t, s: t.buttons + s.buttons, self.trade_requests) + objects)

    def draw_screen(self, objects=None):
        for i in self.players:
            i.walk()
            i.check_message()

        if objects is None:
            objects = []
        Screen.draw_screen(self, self.out + self.trade_requests + [self.path, self.bag_button, self.self_info_menu, self.player_info_menu] + self.players + objects)

    def on_click(self, map_object, event):
        if map_object in [self.bag_button, self.self_info_menu.x_button]:
            self.self_info_menu.change_visible()
            self.self_info_menu.change_clickable()
        elif map_object is self.player_info_menu.x_button:
            self.player_info_menu.change_visible()
            self.player_info_menu.change_clickable()
        elif map_object is self.player_info_menu.trade_button:
            self.world.client.trade_request(self.world.cur_player.username, self.player_info_menu.player.username)
            self.trade_requests.append(TradeRequest(self.world, self.player_info_menu.player, False))
        for i in self.trade_requests:
            for j in i.buttons:
                if map_object is i.buttons[j]:
                    self.world.client.trade_response(i.player.username, self.world.cur_player.username, j == 'v')
                    if j == 'v':
                        print 'start trading!'
                    break
        for i in self.players:
            if map_object is i and i is not self.world.cur_player:
                self.player_info_menu.update_player(i)
                self.player_info_menu.change_visible()
                self.player_info_menu.change_clickable()
                break
        for i in self.self_info_menu.cells:
            if map_object is i[1] and map_object.front:
                for j in self.world.cur_player.items:
                    if j.item_id == i[0]:
                        self.world.cur_player.change_item(j)
                        break
                break

    def on_type(self, map_object, event):
        raise NotImplementedError
