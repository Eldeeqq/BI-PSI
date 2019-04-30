from commands import CMD
import socket
import re
import sys
import os
import random


class LogicError(Exception):
    pass

class SyntaxError(Exception):
    pass

class MessageFound(Exception):
    pass

def wrap_and_encode(message):
    return (str(message) + '\a\b').encode('ascii')

def compute_hash(bot_name):
    name_sum = 0
    name = bot_name[:-2]
    for char in name:
        name_sum += ord(char)

    name_sum = name_sum * 1000
    name_sum = name_sum % 65536

    return name_sum


stages = ['HASH_COMPUTE', 'CONF_CHECK', 'LOCATE', 'FIND_CORNER', 'MESSAGE' ]
stage_len = {'HASH_COMPUTE': 12, 'CONF_CHECK': 12, 'LOCATE': 12, 'FIND_CORNER': 12, 'MESSAGE': 100}
DIRECTIONS = ['UP', 'RIGHT', 'DOWN', 'LEFT']

class RobotHandler:

    def __init__(self, conn):
        self.connection = conn
        self.CHECKED = []
        self.actual_stage = 0
        self.message = ''
        self.buffered = ''

        self.hash = 0
        self.stage = 0
        self.random_id = random.randint(-1000,1000)
        self.robot_direction = 0

        self.desired_x = -2
        self.desired_y = -2
        self.recharging = False
        self.x, self.y = None, None

    def buffer(self):
        if '\a\b' not in self.message:
            while True:
                recieved = self.connection.recv(1024).decode('ascii')

                # nedostal jsem odpoved
                if not recieved:
                    break

                #print("["+str(self.random_id)+"] ","recieved: ", bytes(recieved, 'ascii'), len(bytes(recieved, 'ascii')))
                self.message += recieved

                # zprava prekrocila max. delku
                if len(recieved) >= stage_len[stages[self.stage]] and '\a\b' not in recieved:
                    raise SyntaxError

                # nacetl jsem zpravu
                if '\a\b' in recieved or '\a\b' in self.message:
                    break

        return

    def test_recharge(self, message):
        if self.recharging:
            if message == "FULL POWER\a\b":
                print("["+str(self.random_id)+"] ","full power")
                self.recharging = False
                self.connection.settimeout(1)
                return True
            else:
                raise LogicError
        if message == 'RECHARGING\a\b':
            print("["+str(self.random_id)+"] ","Start recharge")
            self.recharging = True
            self.connection.settimeout(5)
            message = self._get_message()
            print("["+str(self.random_id)+"] ","After recharging: ",bytes(message, 'ascii'))
            return self.test_recharge(message)
        print("["+str(self.random_id)+"] ","message ok", message)
        return False

    def _get_message(self):
        self.buffer()
        delimeter_idx = self.message.find('\a\b')
        if delimeter_idx == -1:
            return ''
        delimeter_idx += 2
        message = self.message[:delimeter_idx]
        #print("["+str(self.random_id)+"] ","buffer ", self.message)
        self.message = self.message[delimeter_idx:]
        return message

    def get_message(self):
        message = self._get_message()
        if self.test_recharge(message):
            message = self._get_message()
        print("["+str(self.random_id)+"] ",message)
        return message



    def incorrect_step_len(self, message):
        return len(message) <= stage_len[stages[self.actual_stage]]


    def test_response(self, response):
        return self.incorrect_step_len(response) and response[-2:] == '\a\b'

    def check_ok(self, message):
        if message[:2] != 'OK':
            raise SyntaxError
        if message[-2:] != '\a\b':
            raise SyntaxError
        pattern = re.compile('^-?\d+\s-?\d+$')
        if not pattern.match(message[3:-2]):
            raise SyntaxError

    def direction(self, a, b):
        # vertikalni pohyn
        if a[0] == b[0]:
            if a[1] > b[1]:
                self.robot_direction = 2
            if a[1] < b[1]:
                self.robot_direction = 0

        # horizontalni pohyn
        if a[1] == b[1]:
            if a[0] > b[0]:
                self.robot_direction = 3
            if a[0] < b[0]:
                self.robot_direction = 1

    def in_range(self):
        return -2 <= self.x <= 2 and -2 <= self.y <= 2

    def locate_robot(self):
        self.connection.send(CMD['move'])
        position = self.get_message()
        self.check_ok(position)
        self.connection.send(CMD['move'])
        position2 = self.get_message()
        self.check_ok(position2)
        pos1 = [int(x) for x in position[3:-2].split(' ')]
        pos2 = [int(x) for x in position2[3:-2].split(' ')]
        self.direction(pos1, pos2)
        self.x = pos2[0]
        self.y = pos2[1]

        print("["+str(self.random_id)+"] ","Robot direction: ", DIRECTIONS[self.robot_direction])

    def rotate(self, desired):
        while DIRECTIONS[self.robot_direction] != desired:
            self.connection.sendall(CMD['turn_r'])
            message = self.get_message()
            print("Rotate message: ", message)
            self.check_ok(message)
            print("check")
            self.robot_direction += 1
            self.robot_direction %= 4
            print("["+str(self.random_id)+"] ","ROTATING, facing " + DIRECTIONS[self.robot_direction])

    def go(self):
        self.connection.sendall(CMD['move'])
        message = self.get_message()
        self.check_ok(message)
        pos = [int(x) for x in message[3:-2].split(' ')]
        self.x = pos[0]
        self.y = pos[1]
        if [self.x, self.y] not in self.CHECKED and self.in_range():
            self.connection.sendall(CMD['pick'])
            message = self.get_message()
            if message[:-2] != '':
                self.message = message[:-2]
                raise MessageFound
            self.CHECKED.append([self.x, self.y])
        print("["+str(self.random_id)+"] ","CURRENT ", self.x, self.y)

    def get_to_desired_location(self):
        print("["+str(self.random_id)+"] ","Actual location: ", self.x, ",", self.y)
        if self.y != self.desired_x:
            self.rotate('UP') if self.y < self.desired_y else self.rotate('DOWN')
            while self.y != self.desired_y:
                self.go()
                #print(self.y," -> ", self.desired_y)

        print("["+str(self.random_id)+"] ","Actual location: ", self.x, ",", self.y)
        if self.x != self.desired_x:
            self.rotate('RIGHT') if self.x < self.desired_x else self.rotate('LEFT')
            while self.x != self.desired_x:
                self.go()
                #print(self.x, " -> ", self.desired_x)

        print("["+str(self.random_id)+"] ","Corner - > ", self.x, ",", self.y)
        return

    def auth(self):
        bot_name = self.get_message()
        if not self.test_response(bot_name):
            raise SyntaxError
        self.hash = compute_hash(bot_name)
        to_send = (self.hash + 54621) % 65536
        self.connection.sendall(wrap_and_encode(to_send))
        response = self.get_message()
        #print(bytes(response, 'ascii'))

        if not self.test_response(response):  # or len(response) > 7:
            raise SyntaxError

        if not response[:-2].isdigit():
            raise SyntaxError

        if int(response[:-2]) > 99999:
            raise SyntaxError

        to_check = (self.hash + 45328) % 65536
        if response[:-2] == str(to_check):
            self.connection.sendall(CMD['ok'])
            #print("User auth ok")
            return True
        else:
            self.connection.sendall(CMD['login_fail'])
            return False
        pass

    def pick_message(self):
        print("L1")
        self.rotate('RIGHT')
        while self.x != 2:
            self.go()
        print("L2")

        self.rotate('UP')
        while self.y != 2:
            self.go()

        self.rotate('LEFT')
        while self.x != -2:
            self.go()

        self.rotate('DOWN')
        while self.y != -1:
            self.go()

        self.rotate('RIGHT')
        while self.x != 1:
            self.go()

        self.rotate('UP')
        while self.y != 1:
            self.go()
        self.rotate('LEFT')
        while self.x != -1:
            self.go()
        self.rotate('DOWN')
        while self.y != 0:
            self.go()
        self.rotate('RIGHT')
        while self.x != 0:
            self.go()

    def handle(self):
        try:
            while True:
                if self.stage == 0:
                    if not self.auth():
                        break
                    print("auth")
                    self.stage += 1
                if self.stage == 1:
                    self.locate_robot()
                    print("locate")
                    self.stage += 1

                if self.stage == 2:
                    self.get_to_desired_location()
                    print("desired")

                    self.stage += 1
                if self.stage == 3:
                    self.pick_message()
                    print("pick")


        except socket.timeout:
            print("timeout")
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)

        except LogicError:
            self.connection.sendall(CMD['logic'])
            print("logic error")

        except SyntaxError:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)
            self.connection.sendall(CMD['syntax'])
            print("syntax error")

        except MessageFound:
            self.connection.sendall(CMD['done'])
            print("MESSAGE FOUND")

        finally:
            self.connection.close()
            print("Server closed.")
            return
