from socket import *
import RobotHandler
import threading


def listen(soc):
    while True:
        connection, address = soc.accept()
        connection.settimeout(1)
        thread = threading.Thread(target=RobotHandler.RobotHandler(connection).handle)
        thread.start()
        print("New Thread started.")


if __name__ == "__main__":
    host = ('127.0.0.1', 7777)
    socket = socket(AF_INET, SOCK_STREAM)
    print("Running at ", host[0], host[1])
    socket.bind(host)
    socket.listen(1)
    try:
        listen(socket)
    except OSError:
        listen(('127.0.0.1', 8888))