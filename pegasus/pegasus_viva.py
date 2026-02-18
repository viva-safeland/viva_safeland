#!/usr/bin/env python

import carb
from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": False})
import omni.timeline
from omni.isaac.core.world import World
from omni.isaac.core.utils.rotations import quat_to_euler_angles

# Import the Pegasus API for simulating drones
from pegasus.simulator.params import ROBOTS, SIMULATION_ENVIRONMENTS
from pegasus.simulator.logic.state import State
from pegasus.simulator.logic.backends.px4_mavlink_backend import PX4MavlinkBackend, PX4MavlinkBackendConfig
from pegasus.simulator.logic.vehicles.multirotor import Multirotor, MultirotorConfig
from pegasus.simulator.logic.interface.pegasus_interface import PegasusInterface
from pegasus.simulator.logic.graphical_sensors.monocular_camera import MonocularCamera

# Auxiliary modules
import os.path
import numpy as np
import threading
import time
import zmq
import sys
from scipy.spatial.transform import Rotation

from pymavlink_px4_interface import PX4DroneControl

class PegasusVivaApp:
    def __init__(self):
        self.timeline = omni.timeline.get_timeline_interface()
        self.pg = PegasusInterface()
        self.pg._world = World(**self.pg._world_settings)
        self.world = self.pg.world
        self.pg.load_environment(SIMULATION_ENVIRONMENTS["Curved Gridroom"])

        # Create the vehicle
        config_multirotor = MultirotorConfig()
        mavlink_config = PX4MavlinkBackendConfig({
            "vehicle_id": 0,
            "px4_autolaunch": True,
            "px4_dir": self.pg.px4_path,
            "px4_vehicle_model": self.pg.px4_default_airframe
        })
        config_multirotor.backends = [PX4MavlinkBackend(mavlink_config)]
        
        # Add the camera to the vehicle
        # config_multirotor.graphical_sensors = [MonocularCamera("camera", config={"orientation": [0.0, 0.0, -90.0]})]

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
        self.stop_sim = False

        # ZMQ Setup
        self.zmq_context = zmq.Context()
        
        # 1. Pose Publisher (PUB) -> Send State to Viva
        self.zmq_pub = self.zmq_context.socket(zmq.PUB)
        self.zmq_pub.setsockopt(zmq.SNDHWM, 1)
        self.zmq_pub.connect("tcp://localhost:5555") 
        
        # 2. Command Subscriber (SUB) <- Receive Actions from Viva
        self.zmq_sub = self.zmq_context.socket(zmq.SUB)
        # Removed CONFLATE to ensure commands are not missed
        self.zmq_sub.connect("tcp://localhost:5557")
        self.zmq_sub.subscribe("")

        time.sleep(1) # Wait for connections
        self.viva_connected = True
        print("Pegasus: Connected to Viva ZMQ Server (PUB: 5555, SUB: 5557)")

    def run_control_logic(self):
        """
        Thread that runs the high-level control logic using pymavlink.
        Receives commands from Viva via ZMQ and forwards to PX4.
        """
        # Wait a bit for the simulator to settle and PX4 to start
        time.sleep(10)
        
        try:
            ctrl = PX4DroneControl('udpin:127.0.0.1:14540')
            print("Control Interface Ready. Waiting for commands...")
            
            # Default state
            takeoff_done = False
            in_manual_mode = False

            while not self.stop_sim:
                # 1. Drain the ZMQ queue to get the LATEST state and any discrete commands
                latest_actions = None
                pending_command = None
                
                while True:
                    try:
                        message = self.zmq_sub.recv_json(flags=zmq.NOBLOCK)
                        # Commands are discrete, don't miss them
                        if message.get("command"):
                            pending_command = message.get("command")
                        # Actions are continuous, only keep latest
                        if message.get("action"):
                            latest_actions = message.get("action")
                    except zmq.Again:
                        break
                    except Exception as e:
                        print(f"Error reading ZMQ: {e}")
                        break

                # 2. Process discrete command
                if pending_command == "takeoff":
                    if not takeoff_done:
                        print("Executing Takeoff...")
                        ctrl.arm()
                        ctrl.takeoff_gps(altitude=3.0)
                        takeoff_done = True
                        ctrl.set_mode_posctl()
                        in_manual_mode = True
                            
                elif pending_command == "land":
                    print("Executing Landing...")
                    ctrl.land()
                    takeoff_done = False
                    in_manual_mode = False
                            
                # 3. Process continuous actions
                if latest_actions is not None and takeoff_done:
                    # In POSCTL/ALTCTL, roll/pitch stick inputs are typically interpreted as lean angles
                    # Throttle is typically interpreted as vertical velocity.
                    
                    raw_roll = latest_actions[0]    # theta
                    raw_pitch = latest_actions[1]   # phi
                    raw_yaw = latest_actions[2]     # psi_vel
                    raw_thrust = latest_actions[3]  # fk

                    # PX4 MANUAL_CONTROL: x, y, z, r in [-1000, 1000]
                    # x: pitch (forward > 0)
                    # y: roll (right > 0)
                    # z: thrust (0 to 1000 for throttle in manual modes)
                    # r: yaw (clockwise > 0)
                    
                    x = int(raw_pitch * 1000)
                    y = int(raw_roll * 1000)
                    r = int(-raw_yaw * 1000) # Viva +yaw is Left, PX4 +r is Right(CW)
                    
                    # Throttle mapping: 
                    # If using POSCTL, z is centered at 500 (hold altitude).
                    # Viva fk is [-1, 1].
                    z = int((raw_thrust + 1.0) * 500.0)
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
        control_thread = threading.Thread(target=self.run_control_logic)
        control_thread.daemon = True
        control_thread.start()

        while simulation_app.is_running() and not self.stop_sim:
            self.world.step(render=True)
            
            # Send Pose to Viva
            pos, quat = self.drone.get_world_pose()
            quat_scipy = [quat[1], quat[2], quat[3], quat[0]] # x,y,z,w
            
            r = Rotation.from_quat(quat_scipy)
            roll, pitch, yaw = r.as_euler("xyz", degrees=True)
            
            if self.viva_connected:
                try:
                    msg = {
                        "pose": [
                            float(pos[0]), 
                            float(pos[1]), 
                            float(pos[2]), 
                            float(roll), 
                            float(pitch), 
                            float(yaw)
                        ]
                    }
                    self.zmq_pub.send_json(msg)
                except zmq.ZMQError:
                    pass
        
        # Cleanup
        cv2.destroyAllWindows()
        carb.log_warn("PegasusVivaApp is closing.")
        self.timeline.stop()
        simulation_app.close()


if __name__ == "__main__":
    app = PegasusVivaApp()
    app.run()
