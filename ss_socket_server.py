import socketserver
import threading
import json
import time
import os

# List to store client connections
socket_list = []

messages_lock = threading.Lock()
messages = []

stats_lock = threading.Lock()
stats = {
    'File Name': "None",
    'Score': 0,
    'HP': 10,
    'Max HP': 10,
    'Attack': 1,
    'Coins': 0,
    '3D Bar': 10,
    'Level': 99,
    'FlipFlop Pipe': 0,
    'Low HP Textbox': 16,
}

players_3D_bit = {}
is_someone_in_3D = False
flip_timer = time.time() + 1

previous_level = 1

score_required = []
xp = 0
for i in range(-1, 100):
    xp += ((i // 2) + 1) * 10000
    score_required.append(xp)

def manual_levelup_check():
    global stats, previous_level
    max_hp = 10
    attack = 1
    
    level = 1
    for i in range(1, len(score_required)):
        if stats['Score'] >= score_required[i]:
            level += 1
        else:
            break

    for i in range(1, level + 1):
        if i % 2 != 0 and i != 1:
            attack += 1
        elif i != 1:
            max_hp += 5
    print(stats['File Name'])
    if stats['Max HP'] != max_hp:
        stats['Max HP'] = max_hp
        print("Stats were fixed from desyncronization")
    if stats['Attack'] != attack:
        stats['Attack'] = attack
        print("Stats were fixed from desyncronization")
    if stats['HP'] > stats["Max HP"]:
        stats['HP'] = stats["Max HP"]
        print("Stats were fixed from desyncronization")

# File path for the stats save file
SAVE_FILE_PATH = 'stats.json'

# Locks for thread synchronization
save_file_lock = threading.Lock()

# Define a custom handler class inheriting from socketserver.BaseRequestHandler
class MyTCPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        global messages
        global stats
        global is_someone_in_3D
        is_someone_in_3D_last = False
        # Add client connection to the list
        socket_list.append(self.request)

        # Loop to continuously handle client requests
        while True:
            try:
                # Receive data from the client
                data = self.request.recv(4096)
                if not data:
                    continue

                # Split the received data by newline character
                parts = data.decode().split('\n')

                # Process each received JSON string individually
                for part in parts:
                    if not part:
                        continue
                    try:
                        # Parse the JSON string into a Python object
                        data = json.loads(part)

                        if 'message' in data:
                            with messages_lock:
                                messages.extend(data['message'])

                        if 'data' in data and data['data'] and data['data']['Score'] >= 0:
                            with stats_lock:
                                # Check if the data changed is in the stats dictionary
                                for key in data['data']:
                                    if key in stats:
                                        if key == "HP" and data['data'][key] != 0:
                                            stats['3D Bar'] = 10
                                        
                                        stats[key] += data['data'][key]
                        
                        if '3dBit' in data and 'user' in data:
                            players_3D_bit[str(self.client_address)] = data['3dBit']
                    except json.JSONDecodeError:
                        pass
                        # print(f"Invalid JSON data received from client {addr}. Skipping.")
                
                is_someone_in_3D = False

                for key in players_3D_bit:
                    if players_3D_bit[key] == True:
                        is_someone_in_3D = True
                        break

                if is_someone_in_3D_last != is_someone_in_3D:
                    is_someone_in_3D_changed(is_someone_in_3D)
                
                is_someone_in_3D_last = is_someone_in_3D
                
            except (ConnectionResetError, ConnectionAbortedError):
                # Client disconnected
                print(f"Client {self.client_address} disconnected.")
                # Remove client from the socket list
                if self.request in socket_list:
                    socket_list.remove(self.request)
                if self.request in players_3D_bit:
                    players_3D_bit.pop(str(self.client_address))
                break

def is_someone_in_3D_changed(value):
    global flip_timer
    print("3D set to", value)
    flip_timer = time.time() + 1

def countdown_flip_timer():
    global is_someone_in_3D
    global flip_timer
    global stats

    while True:
        # print(is_someone_in_3D, flip_timer)
        if time.time() > flip_timer:
            if is_someone_in_3D:
                stats['3D Bar'] -= 1

                if stats['3D Bar'] < 0:
                    stats['3D Bar'] = 0
            elif stats['3D Bar'] < 10:
                stats['3D Bar'] += 1

                if stats['3D Bar'] > 10:
                    stats['3D Bar'] = 10
                    
            flip_timer = time.time() + 1

# Function to periodically save stats
def save_stats_periodically():
    global stats
    manual_levelup_check()
    while True:
        try:
            time.sleep(10)  # Save stats every 10 seconds
            with open(SAVE_FILE_PATH, 'w') as file:
                stats_save = stats.copy()
                stats_save["3D Bar"] = 10

                json.dump(stats_save, file)
                print('[Stats Saved]')
                print(stats_save)
        except Exception as e:
            print(f"An error occurred while saving stats: {e}")

# Function to send data to all connected clients
def send_data():
    global messages
    global stats
    while True:
        time.sleep(0.1)

        with messages_lock:
            with stats_lock:
                if stats:
                    sending = {
                        'data': stats.copy(),
                        'message': messages.copy(),
                    }
                    messages.clear()

                    if socket_list:
                        # Send dictionary over a socket
                        json_data = json.dumps(sending)
                        message = json_data + '\n'

                        # Send data to all connected clients
                        for connection in socket_list:
                            try:
                                connection.sendall(message.encode())
                            except BrokenPipeError:
                                # Handle broken pipe error
                                print("Broken pipe error. Client disconnected.")
                                connection.close()
                                if connection in socket_list:
                                    socket_list.remove(connection)

def main():
    # Load stats from save file
    load_stats()

    # Create the server, set this to your public IP or cloud server, and change the port to an open port on your network/cloud service.
    with ThreadedTCPServer(("0.0.0.0", 5556), MyTCPHandler) as server:
        print("Server started. Listening for connections...")
        
        # Start a thread to save stats periodically
        saving_thread = threading.Thread(target=save_stats_periodically)
        saving_thread.start()

        # Start a thread to send data to clients
        manual_levelup_check()
        sending_thread = threading.Thread(target=send_data)
        sending_thread.start()

        flip_timer_thread = threading.Thread(target=countdown_flip_timer)
        flip_timer_thread.start()
        
        # Activate the server; this will keep running until you interrupt the program with Ctrl-C
        server.serve_forever()

def load_stats():
    global stats
    try:
        with open(SAVE_FILE_PATH, 'r') as file:
            saved_stats = json.load(file)
            stats.update(saved_stats)
            print("Stats loaded from:", os.path.abspath(SAVE_FILE_PATH))
    except (FileNotFoundError, json.JSONDecodeError):
        print("Save file not found or invalid format. Using default stats.")

class ThreadedTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True

if __name__ == "__main__":
    main()