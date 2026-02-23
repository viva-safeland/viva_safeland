import argparse
import select
import sys
import zmq

from viva.env import DroneEnv
from viva.modules.hmi import HMI

def main():
    parser = argparse.ArgumentParser(description="Viva ZMQ Server")
    parser.add_argument("video_path", type=str, help="Path to the background video file")
    parser.add_argument("--port-sub", type=int, default=5555, help="Port to listen for commands (SUB)")
    parser.add_argument("--port-pub", type=int, default=5557, help="Port to publish HMI commands (PUB)")
    
    args = parser.parse_args()
    
    video_path = args.video_path
    port_sub = args.port_sub
    port_pub = args.port_pub
    print(f"Starting Viva ZMQ Server...")
    print(f"Command Port (REP) [Receive Pose]: {port_sub}")
    print(f"Stream Port (PUB) [Send Actions]: {port_pub}")

    # Initialize ZMQ context and sockets
    context = zmq.Context()
    
    # Socket to receive commands/poses (SUB pattern)
    socket_sub = context.socket(zmq.SUB)
    socket_sub.setsockopt(zmq.CONFLATE, 1)
    socket_sub.bind(f"tcp://*:{port_sub}")
    socket_sub.subscribe("")
    
    # Socket to publish HMI actions (PUB pattern)
    socket_pub = context.socket(zmq.PUB)
    socket_pub.setsockopt(zmq.SNDHWM, 1)
    socket_pub.bind(f"tcp://*:{port_pub}")

    # Initialize Environment
    try:
        env = DroneEnv(
            render_mode="human",
            video=video_path,
            fixed=False,
            hover_z=False,
            hover_xy=False,
        )
    except Exception as e:
        print(f"Error initializing environment: {e}")
        return

    obs, info = env.reset()
    hmi = HMI()
    
    while hmi.active:
        try:
            try:
                message = socket_sub.recv_json(flags=zmq.NOBLOCK)
                if "pose" in message:
                    pose = message["pose"]
                    obs, terminated, info = env.set_state(*pose)
                elif "reset" in message and message["reset"]:
                    obs, info = env.reset()
            except zmq.Again:
                import time
                time.sleep(1.0 / 30)
                pass
            actions, command, terminated_command = hmi()
            
            if command == "reset":
                obs, info = env.reset()

            if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                line = sys.stdin.readline().strip()
                if line.startswith("command:"):
                    cmd_text = line.split(":")[1].strip().lower()
                    if cmd_text == "takeoff":
                        command = "takeoff"
                    elif cmd_text == "landing" or cmd_text == "land":
                        command = "land"
                    print(f"Received terminal command: {command}")

            msg = {
                "action": actions.tolist(),
                "command": command
            }
            socket_pub.send_json(msg)

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error in loop: {e}")
            break

    hmi.quit()
    print("Viva Server stopped.")

if __name__ == "__main__":
    main()
