import argparse, subprocess
from zros import zNode

from viva.env import DroneEnv
from viva.modules.hmi import HMI

def start_zroscore():
    return subprocess.Popen(["uv", "run", "zroscore"])

class VivaBridgeNode(zNode):
    def __init__(self, env: DroneEnv, hmi: HMI):
        super().__init__("viva_bridge")
        self.env = env
        self.hmi = hmi
        
        self.pub_control = self.create_publisher("/drone/control")
        self.create_subscriber("/drone/pose", self.pose_callback)
        
        self.create_timer(1 / 60.0, self.timer_callback)
        self.obs, self.info = self.env.reset()

    def pose_callback(self, msg: dict):
        pose = msg.get("pose")
        if pose is not None:
            self.obs, terminated, self.info = self.env.set_state(*pose)
            
    def timer_callback(self):
        if not self.hmi.active:
            self.running = False
            return
            
        actions, command, terminated_command = self.hmi()
        
        if command == "reset":
            self.obs, self.info = self.env.reset()

        msg = {
            "action": actions.tolist(),
            "command": command
        }
        self.pub_control.publish(msg)

def main():
    parser = argparse.ArgumentParser(description="Bridge viva-pegasus")
    parser.add_argument("video_path", type=str, help="Path to the background video file")
    args = parser.parse_args()
    video_path = args.video_path

    start_zroscore()

    try:
        env = DroneEnv(
            render_mode="human",
            video=video_path,
            fixed=False,
        )
    except Exception as e:
        print(f"Error initializing environment: {e}")
        return

    hmi = HMI()
    node = VivaBridgeNode(env, hmi)
    
    try:
        node.spin()
    except KeyboardInterrupt:
        pass
    finally:
        hmi.quit()
        print("Bridge viva-pegasus stopped.")

if __name__ == "__main__":
    main()
