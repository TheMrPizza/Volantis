import firebase_admin
from firebase_admin import credentials
from firebase_admin import storage
from firebase_admin import db

import socket
import select
from datetime import datetime

SERVER_ADDRESS = ('0.0.0.0', 1943)
KB = 1024


class Server(object):
    def __init__(self):
        # Initialize Firebase database and storage
        cred = credentials.Certificate(
            r'C:\Users\USER\Downloads\cyberproject-ec385-firebase-adminsdk-sxzt7-5b7e34d38f.json')
        firebase_admin.initialize_app(cred, {'databaseURL': 'https://cyberproject-ec385.firebaseio.com',
                                             'storageBucket': 'cyberproject-ec385.appspot.com'})
        self.bucket = storage.bucket()

        # Initialize the server socket
        self.socket = socket.socket()
        self.socket.bind(SERVER_ADDRESS)
        self.socket.listen(5)

        Server.remove_all_players()

        self.client_players = []  # The client socket and client's player username and room id
        self.waiting_data = []  # Data to send to clients

        while True:
            sockets = [i['socket'] for i in self.client_players]
            rlist, wlist, xlist = select.select(sockets + [self.socket], sockets, [])
            for i in rlist:  # Reading messages
                if i is self.socket:  # New client, adding to client players
                    print 'New client connected'
                    new_socket, address = self.socket.accept()
                    self.client_players.append({'socket': new_socket, 'username': '', 'room_id': '0'})
                    print 'New client added to list'
                else:  # Known client, receiving message
                    for j in self.client_players:
                        if i == j['socket']:
                            self.receive_message(j)
                            break

            for client_player, msg in self.waiting_data:  # Sending messages
                if client_player['socket'] in wlist:
                    self.send_message(client_player, msg['code'], msg['headers'], msg['data'])
                    self.waiting_data.remove([client_player, msg])

    def add_message(self, client_player, code, headers, data=''):
        self.waiting_data.append([client_player, {'code': code, 'headers': headers, 'data': data}])

    def send_message(self, client_player, code, headers, data=''):
        # Protocol
        headers['length'] = len(data)
        response = Server.message_format(code, headers, data)
        while response != '':
            try:
                client_player['socket'].send(response[:KB])
            except (socket.error, socket.timeout):
                self.quit_socket(client_player)
                return
            response = response[KB:]

    def receive_message(self, client_player):
        try:
            length = int(client_player['socket'].recv(10))
            msg = ''
            while len(msg) != length:
                if length - len(msg) < KB:
                    msg += client_player['socket'].recv(length - len(msg))
                else:
                    msg += client_player['socket'].recv(KB)
        except (socket.error, socket.timeout):
            self.quit_socket(client_player)
            return
        if msg == '':
            return
        lines = msg.split('\r\n')
        command = lines[0]
        headers = {}
        data = ''
        for i in xrange(1, len(lines)-1):
            if lines[i] == '':
                data = ''.join(lines[i + 1:])
                break
            parts = lines[i].split(': ')
            headers[parts[0]] = parts[1]
        print command

        if command == 'STORAGE':
            blob = self.bucket.get_blob(headers['item'])
            print headers['item']
            self.add_message(client_player, 'OK', {'time-created': blob.time_created, 'id': headers['id']},
                             blob.download_as_string())
        elif command == 'POS':
            ref = db.reference('users/' + headers['username'])
            pos = headers['pos'].split(' ')
            ref.update({'pos': [int(pos[0]), int(pos[1])]})
            for i in self.client_players:
                if i == client_player:
                    self.add_message(client_player, 'OK', {'command': command, 'id': headers['id']})
                elif i['room_id'] == client_player['room_id']:
                    self.add_message(i, 'POS', {'username': headers['username'], 'command': command}, headers['pos'])
        elif command == 'CREATE PLAYER':
            ref = db.reference('users/')
            ref.child(headers['username']).set({
                'body': headers['body'],
                'level': 1,
                'password': headers['password'],
                'coins': 200,
                'join_date': datetime.now().strftime('%d.%m.%Y'),
                'is_admin': False,
                'room_id': 201,
                'xp': 0,
                'pos': [23, 303]
            })
            self.add_message(client_player, 'OK', {'id': headers['id']})
        elif command == 'ADD PLAYER':
            # Delete player from the old room
            room_id = db.reference('users/' + headers['username'] + '/room_id').get()
            db.reference('rooms/' + str(room_id) + '/players/' + headers['username']).delete()

            # Add player to the new room
            db.reference('users/' + headers['username'] + '/room_id').set(int(headers['room_id']))
            ref = db.reference('rooms/' + headers['room_id'] + '/players')
            ref.child(headers['username']).set(True)

            for i in self.client_players:
                if i is client_player:  # It's the player, send him OK
                    i['room_id'] = headers['room_id']
                    self.add_message(client_player, 'OK', {'id': headers['id']})
                elif i['room_id'] == headers['room_id']:  # A player in the new room, say hello
                    self.add_message(i, 'ADD PLAYER', {'username': headers['username'],
                                                       'room_id': headers['room_id'], 'id': headers['id']})
        elif command == 'PLAYER INFO':
            ref = db.reference('users/' + headers['username']).get()
            info = {'username': headers['username']}
            for key, value in ref.iteritems():
                if type(key) is unicode:
                    key = str(key)
                if type(value) is unicode:
                    value = str(value)
                info[key] = value
            self.add_message(client_player, 'OK', {'id': headers['id']}, str(info))
        elif command == 'ITEM INFO':
            ref = db.reference('items/' + headers['item_id']).get()
            info = {'item_id': headers['item_id']}
            for key, value in ref.iteritems():
                if type(key) is unicode:
                    key = str(key)
                if type(value) is unicode:
                    value = str(value)
                info[key] = value
            self.add_message(client_player, 'OK', {'id': headers['id']}, str(info))
        elif command == 'CHANGE ITEM':
            ref = db.reference('users/' + headers['username'] + '/items/' + headers['item_id'] + '/is_used')
            ref.set(not ref.get())
            for i in self.client_players:
                if i is client_player:
                    self.add_message(client_player, 'OK', {'id': headers['id']})
                elif i['room_id'] == client_player['room_id']:
                    self.add_message(i, 'CHANGE ITEM', {'username': headers['username'], 'item_id': headers['item_id'],
                                                        'command': command})
        elif command == 'ROOM PLAYERS':
            ref = db.reference('rooms/' + headers['room_id'] + '/players').get()
            if ref:
                self.add_message(client_player, 'OK', {'id': headers['id']}, ' '.join(ref))
            else:
                self.add_message(client_player, 'OK', {'id': headers['id']})
        elif command == 'ACTIVITY REQUEST':
            for i in self.client_players:
                if i['username'] == headers['addressee']:
                    self.add_message(i, 'ACTIVITY REQUEST',
                                     {'activity': headers['activity'], 'sender': headers['sender'],
                                      'addressee': headers['addressee'], 'command': command})
                    break
            self.add_message(client_player, 'OK', {'id': headers['id']})
        elif command == 'ACTIVITY RESPONSE':
            for i in self.client_players:
                if i['username'] == headers['sender']:
                    self.add_message(i, 'ACTIVITY RESPONSE',
                                     {'activity': headers['activity'], 'sender': headers['sender'],
                                      'addressee': headers['addressee'],
                                      'is_accepted': headers['is_accepted'], 'command': command})
                    break
            self.add_message(client_player, 'OK', {'id': headers['id']})
        elif command == 'PLACE ITEM':
            for i in self.client_players:
                if i['username'] == headers['username']:
                    self.add_message(i, 'PLACE ITEM', {'item': headers['item']})
                    break
            self.add_message(client_player, 'OK', {'id': headers['id']})
        elif command == 'REMOVE ITEM':
            for i in self.client_players:
                if i['username'] == headers['username']:
                    self.add_message(i, 'REMOVE ITEM', {'index': headers['index']})
                    break
            self.add_message(client_player, 'OK', {'id': headers['id']})
        elif command == 'ACCEPT TRADE':
            for i in self.client_players:
                if i['username'] == headers['username']:
                    self.add_message(i, 'ACCEPT TRADE', {})
                    break
            self.add_message(client_player, 'OK', {'id': headers['id']})
        elif command == 'DECLINE TRADE':
            for i in self.client_players:
                if i['username'] == headers['username']:
                    self.add_message(i, 'DECLINE TRADE', {})
                    break
            self.add_message(client_player, 'OK', {'id': headers['id']})
        elif command == 'MAKE TRADE':
            self.add_message(client_player, 'OK', {'id': headers['id']})
            for i in self.client_players:
                if i['username'] == headers['username']:
                    for j in headers['self_items'].split():
                        amount = db.reference('users/' + client_player['username'] + '/items/' + j + '/amount').get()
                        if amount > 1:
                            db.reference('users/' + client_player['username'] + '/items/' + j + '/amount').set(amount - 1)
                        else:
                            db.reference('users/' + client_player['username'] + '/items/' + j).delete()

                        amount = db.reference('users/' + headers['username'] + '/items/' + j + '/amount').get()
                        if amount:
                            db.reference('users/' + headers['username'] + '/items/' + j + '/amount').set(amount + 1)
                        else:
                            db.reference('users/' + headers['username'] + '/items').child(j).set({'is_used': False, 'amount': 1})
                    for j in headers['player_items'].split():
                        amount = db.reference('users/' + headers['username'] + '/items/' + j + '/amount').get()
                        if amount > 1:
                            db.reference('users/' + headers['username'] + '/items/' + j + '/amount').set(amount - 1)
                        else:
                            db.reference('users/' + headers['username'] + '/items/' + j).delete()

                        amount = db.reference('users/' + client_player['username'] + '/items/' + j + '/amount').get()
                        if amount:
                            db.reference('users/' + client_player['username'] + '/items/' + j + '/amount').set(amount + 1)
                        else:
                            db.reference('users/' + client_player['username'] + '/items').child(j).set({'is_used': False, 'amount': 1})
                if i['room_id'] == client_player['room_id']:
                    self.add_message(i, 'MAKE TRADE',
                                     {'user1': client_player['username'], 'user2': headers['username'],
                                      'items1': headers['self_items'], 'items2': headers['player_items'],
                                      'command': command})
        elif command == 'XO TURN':
            for i in self.client_players:
                if i['username'] == headers['username']:
                    self.add_message(i, 'XO TURN', {'letter': headers['letter'], 'row': headers['row'],
                                                    'col': headers['col']})
                    break
            self.add_message(client_player, 'OK', {'id': headers['id']})
        elif command == 'UPDATE MISSION':
            db.reference('users/' + headers['username'] + '/missions/' +
                         headers['mission_id']).set(headers['value'] == 'True')
            self.add_message(client_player, 'OK', {'id': headers['id']})
        elif command == 'ADD REWARDS':
            if headers['xp'] != '0':
                xp = db.reference('users/' + headers['username'] + '/xp').get()
                db.reference('users/' + headers['username'] + '/xp').set(xp + int(headers['xp']))
            if headers['items'] != '0':
                amount = db.reference('users/' + headers['username'] + '/items/' + headers['items'] + '/amount').get()
                if amount:
                    db.reference('users/' + headers['username'] + '/items/' + headers['items'] +
                                 '/amount').set(amount + 1)
                else:
                    db.reference('users/' + headers['username'] +
                                 '/items').child(headers['items']).set({'is_used': False, 'amount': 1})
            if headers['coins'] != '0':
                coins = db.reference('users/' + headers['username'] + '/coins').get()
                db.reference('users/' + headers['username'] + '/coins').set(coins + int(headers['coins']))
            self.add_message(client_player, 'OK', {'id': headers['id']})
        elif command == 'CHECK USERNAME':
            ref = db.reference('users/' + headers['username']).get()
            if ref:
                self.add_message(client_player, 'OK', {'id': headers['id']}, 'True')
            else:
                self.add_message(client_player, 'OK', {'id': headers['id']}, 'False')
        elif command == 'CONNECT':
            print 'Received connect of ' + headers['username']
            password = db.reference('users/' + headers['username'] + '/password').get()
            if password and str(password) == headers['password']:
                room_id = db.reference('users/' + headers['username'] + '/room_id').get()
                ref = db.reference('rooms/' + str(room_id) + '/players')
                ref.child(headers['username']).set(True)
                Server.add_socket_details(client_player, headers['username'], str(room_id))
                for i in self.client_players:
                    if i is client_player:
                        self.add_message(client_player, 'OK', {'id': headers['id']})
                    elif int(i['room_id']) == room_id:
                        self.add_message(i, 'ADD PLAYER', {'username': headers['username'],
                                                           'room_id': room_id, 'command': 'ADD PLAYER'})
            else:
                self.add_message(client_player, 'OK', {'id': headers['id']}, 'Error')
        elif command == 'QUIT':
            ref = db.reference('rooms/' + headers['room_id'] + '/players/' + headers['username'])
            ref.delete()
            for i in self.client_players:
                self.add_message(i, 'QUIT', {'username': headers['username'], 'command': command})
            self.add_message(client_player, 'OK', {'id': headers['id']})
        elif command == 'CHAT':
            for i in self.client_players:
                if i is client_player:
                    self.add_message(client_player, 'OK', {'id': headers['id']})
                else:
                    self.add_message(i, 'CHAT', {'username': headers['username'],
                                                 'message': headers['message'], 'command': command})

    def quit_socket(self, client_player):
        self.client_players.remove(client_player)
        print 'Error: No client communication!'
        print 'QUIT', client_player['username']
        db.reference('rooms/' + client_player['room_id'] + '/players/' + client_player['username']).delete()
        for i in self.client_players:
            self.add_message(i, 'QUIT', {'username': client_player['username']})

    @staticmethod
    def add_socket_details(client_player, username, room_id):
        client_player['username'] = username
        client_player['room_id'] = room_id

    @staticmethod
    def remove_all_players():
        db.reference('rooms').delete()

    @staticmethod
    def message_format(command, headers, data):
        msg = command + '\r\n'
        for i in headers:
            msg += str(i) + ': ' + str(headers[i]) + '\r\n'
        msg += '\r\n' + data
        return str(len(msg)).rjust(10, '0') + msg


def main():
    Server()


if __name__ == '__main__':
    main()
