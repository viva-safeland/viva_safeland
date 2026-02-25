#!/usr/bin/env python

import carb
from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": False})
import omni.timeline
from omni.isaac.core.world import World
# from omni.isaac.core.utils.rotations import quat_to_euler_angles, euler_angles_to_quat

# Import the Pegasus API for simulating drones
from pegasus.simulator.params import ROBOTS, SIMULATION_ENVIRONMENTS
from pegasus.simulator.logic.backends.px4_mavlink_backend import PX4MavlinkBackend, PX4MavlinkBackendConfig
from pegasus.simulator.logic.vehicles.multirotor import Multirotor, MultirotorConfig
from pegasus.simulator.logic.interface.pegasus_interface import PegasusInterface

import time, threading
from scipy.spatial.transform import Rotation
from pymavlink_px4_interface import PX4DroneControl
from zros import zNode

class PegasusVivaApp:
    def __init__(self):
        self.timeline = omni.timeline.get_timeline_interface()
        self.pg = PegasusInterface()
        self.pg._world = World(**self.pg._world_settings)
        self.world = self.pg.world
        self.pg.load_environment(SIMULATION_ENVIRONMENTS["Curved Gridroom"])

        config_multirotor = MultirotorConfig()
        mavlink_config = PX4MavlinkBackendConfig({
            "vehicle_id": 0,
            "px4_autolaunch": True,
            "px4_dir": self.pg.px4_path,
            "px4_vehicle_model": self.pg.px4_default_airframe
        })
        config_multirotor.backends = [PX4MavlinkBackend(mavlink_config)]
        
        self.drone_prim_path = "/World/quadrotor"
        self.drone = Multirotor(
            self.drone_prim_path,
            ROBOTS['Iris'],
            0,
            [0.0, 0.0, 0.07],
            Rotation.from_euler("XYZ", [0.0, 0.0, 0.0], degrees=True).as_quat(),
            config=config_multirotor,
        )

        self.world.reset()

        # ZROS Setup
        self.znode = zNode("pegasus_node")
        self.pub_pose = self.znode.create_publisher("/drone/pose")
        self.znode.create_subscriber("/drone/control", self.viva_callback, queue_size=10)
        self.action, self.command = None, None
        self.viva_timestamp = time.time()

        self.zros_thread = threading.Thread(target=self.znode.spin, daemon=True)
        self.zros_thread.start()

    def viva_callback(self, msg: dict):
        self.action = msg.get("action")
        self.command = msg.get("command")
        self.viva_timestamp = msg.get("timestamp", time.time())

    def run_control_logic(self):
        """
        Thread that runs the high-level control logic using pymavlink.
        Receives commands from Viva via ZMQ and forwards to PX4.
        """
        
        try:
            ctrl = PX4DroneControl('udpin:127.0.0.1:14540')
            print("Control Interface Ready. Waiting for commands...")
            
            # Default state
            takeoff_done = False

            while simulation_app.is_running():
                if self.command == "takeoff":
                    if not takeoff_done:
                        print("Executing Takeoff...")
                        ctrl.arm()
                        ctrl.takeoff_gps(altitude=3.0)
                        takeoff_done = True
                        ctrl.set_mode_posctl()
                        self.command = None
                            
                elif self.command == "land":
                    print("Executing Landing...")
                    ctrl.land()
                    takeoff_done = False
                    self.command = None
                            
                if self.action is not None and takeoff_done:
                    command_age = time.time() - self.viva_timestamp
                    if command_age > 0.5:
                        # Hover if command is too old (>0.5s) to avoid executing outdated inputs
                        x, y, r = 0, 0, 0
                        z = 500
                        ctrl.send_manual_control(x, y, z, r)
                    else:
                        roll, pitch, yaw, thrust = self.action             

                        # PX4 MANUAL_CONTROL: x, y, z, r in [-1000, 1000]
                        # x: pitch (forward > 0)
                        # y: roll (right > 0)
                        # z: thrust (0 to 1000 for throttle in manual modes)
                        # r: yaw (clockwise > 0)
                        
                        x = int(pitch * 1000)
                        y = int(roll * 1000)
                        r = int(-yaw * 1000) # Viva +yaw is Left, PX4 +r is Right(CW)
                        
                        # Throttle mapping: 
                        # If using POSCTL, z is centered at 500 (hold altitude).
                        # Viva fk is [-1, 1].
                        z = int((thrust + 1.0) * 500.0)
                        z = max(0, min(1000, z))

                        ctrl.send_manual_control(x, y, z, r)

                time.sleep(0.02) # ~50Hz

        except Exception as e:
            carb.log_warn(f"Control Thread Error: {e}")
        finally:
            print("Control sequence finished.")

    def run(self):
        self.timeline.play()

        # Start Control Thread
        control_thread = threading.Thread(target=self.run_control_logic, daemon=True)
        control_thread.start()

        while simulation_app.is_running():
            self.world.step(render=True)
            
            # Send Pose to Viva
            pos, quat = self.drone.get_world_pose()
            quat_scipy = [quat[1], quat[2], quat[3], quat[0]] # x,y,z,w
            
            r = Rotation.from_quat(quat_scipy)
            roll, pitch, yaw = r.as_euler("xyz", degrees=True)
            
            controls = list(self.action) if self.action is not None else [0.0, 0.0, 0.0, 0.0]

            msg = {
                "pose": pos.tolist() + [roll, pitch, yaw],
                "controls": controls,
                "timestamp": time.time()
            }
            self.pub_pose.publish(msg)
        
        # Cleanup
        carb.log_warn("PegasusVivaApp is closing.")
        self.timeline.stop()
        simulation_app.close()


if __name__ == "__main__":
    app = PegasusVivaApp()
    app.run()
