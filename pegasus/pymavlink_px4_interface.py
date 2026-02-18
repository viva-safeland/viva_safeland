import time
import threading
from pymavlink import mavutil

class PX4DroneControl:
    def __init__(self, connection_string):
        print(f"Connecting to {connection_string}...")
        self.master = mavutil.mavlink_connection(connection_string)
        self.master.wait_heartbeat()
        print(f"Connection established! System: {self.master.target_system}, Component: {self.master.target_component}")
        
        self.current_setpoint = (0, 0, 0) # x, y, z (NED)
        self.running = True
        self.offboard_streaming = False
        self.altitude = 2.0
        
        # Constantly send setpoints (PX4 requirement)
        self.send_thread = threading.Thread(target=self._send_position_loop)
        self.send_thread.daemon = True
        self.send_thread.start()

    def _send_position_loop(self):
        """
        PX4 requires receiving SET_POSITION_TARGET_LOCAL_NED messages 
        at >2Hz to allow and maintain OFFBOARD mode.
        """
        while self.running:
            if self.offboard_streaming:
                x, y, z = self.current_setpoint
                # Mask: Ignore vx, vy, vz, ax, ay, az, yaw, yaw_rate
                # Only use Position (bits 0,1,2 = 0, others 1)
                type_mask = 0b110111111000 # 3576 decimal
                
                self.master.mav.set_position_target_local_ned_send(
                    0, # time_boot_ms
                    self.master.target_system,
                    self.master.target_component,
                    mavutil.mavlink.MAV_FRAME_LOCAL_NED,
                    type_mask,
                    x, y, z,
                    0, 0, 0, # Velocities
                    0, 0, 0, # Accelerations
                    0, 0     # Yaw, Yaw rate
                )
            time.sleep(0.1) # 10 Hz (safe for PX4)

    def get_gps_location(self):
        print("Waiting for GPS fix...")
        while True:
            msg = self.master.recv_match(type='GLOBAL_POSITION_INT', blocking=True)
            if msg:
                lat = msg.lat / 1e7
                lon = msg.lon / 1e7
                alt = msg.relative_alt / 1000.0
                print(f"GPS Obtained: Lat={lat}, Lon={lon}, Alt={alt}m")
                return lat, lon, alt

    def arm(self):
        print("Arming...")
        self.master.mav.command_long_send(
            self.master.target_system, self.master.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0, 1, 0, 0, 0, 0, 0, 0
        )
        self.master.motors_armed_wait()
        print("Arming confirmed!")

    def takeoff_gps(self, altitude):
        """
        In PX4, we first use the standard TAKEOFF mode.
        """
        lat, lon, _ = self.get_gps_location()
        self.master.mav.command_long_send(
            self.master.target_system, self.master.target_component,
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            0, 0, 0, 0, 0, lat, lon, 0
        )
        print("Takeoff")
        
        self.altitude = altitude
        self.go_to_local_xyz(0, 0, -self.altitude)

        while True:
            msg = self.master.recv_match(type='GLOBAL_POSITION_INT', blocking=True)
            if msg and (msg.relative_alt/1000.0) > (0.9 * self.altitude):
                break
            time.sleep(0.5)

    def go_to_local_xyz(self, x, y, z=None):
        """
        Changes to OFFBOARD and moves the drone.
        """
        if z is None:
            z = -self.altitude
        self.current_setpoint = (x, y, z)
        self.offboard_streaming = True
        time.sleep(1)
        self.set_mode_offboard()
        print(f"Go to N={x}, E={y}, D={z}")

    def set_mode(self, mode_id):
        """
        Changes the PX4 mode.
        """
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_DO_SET_MODE,
            0,
            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            mode_id, 
            0, 0, 0, 0, 0
        )

    def set_mode_offboard(self):
        self.set_mode(6)

    def set_mode_posctl(self):
        print("Switching to POSITION control mode")
        self.offboard_streaming = False # Stop sending setpoints
        self.set_mode(3)

    def stop_offboard_streaming(self):
        self.offboard_streaming = False

    def land(self):
        print("\nLanding!")
        self.running = False # Stop offboard stream
        self.master.mav.command_long_send(
            self.master.target_system, self.master.target_component,
            mavutil.mavlink.MAV_CMD_NAV_LAND,
            0, 0, 0, 0, 0, 0, 0, 0
        )
        self.master.motors_disarmed_wait()
        print("Drone on the ground.")


    def send_manual_control(self, x, y, z, r):
        """
        Sends manual control inputs (joystick).
        x, y, z, r: -1000 to 1000
        """
        
        self.master.mav.manual_control_send(
            self.master.target_system,
            x, y, z, r,
            0 # buttons
        )

if __name__ == "__main__":
    drone = PX4DroneControl('udpin:127.0.0.1:14540')
    
    try:
        drone.arm()
        drone.takeoff_gps(altitude=3.0)
        drone.go_to_local_xyz(3, 0)
        
        print("ctrl+c to land")
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        drone.land()
    except Exception as e:
        print(f"Error: {e}")
        drone.land()