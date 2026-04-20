import time
import threading
from pymavlink import mavutil
import numpy as np

class PX4DroneControl:
    def __init__(self, connection_string, baudrate):
        print(f"Connecting to {connection_string}...")
        self.master = mavutil.mavlink_connection(connection_string, baud=baudrate)
        self.master.wait_heartbeat()
        print(f"Connection established! System: {self.master.target_system}, Component: {self.master.target_component}")


        for i in [30,33]:
            self.master.mav.command_int_send(self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_FRAME_LOCAL_NED,
                mavutil.mavlink.MAV_CMD_GET_MESSAGE_INTERVAL,
                0, 0,            # Confirmation
                i,   # param1: Message ID
                0, 0, 0, 0, 0, 0 # param3-7
            )
            msg = self.master.recv_match(type='MESSAGE_INTERVAL', blocking=True)
            if msg:
                if msg.interval_us != 40000:
                    self.master.mav.command_int_send(self.master.target_system,
                        self.master.target_component,
                        mavutil.mavlink.MAV_FRAME_LOCAL_NED,
                        mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
                        0, 0,            # Confirmation
                        i,   # param1: Message ID
                        40000,  # param2: Interval in microseconds
                        0, 0, 0, 0, 0 # param3-7
                        )
                    print(f"Message ID: {msg.message_id}, Changed from interval: {msg.interval_us} to 40000")
                    time.sleep(0.5)

            
        
        self.current_setpoint = (56, 1024, 0, 0, 0, 0) # (pos or vel), (yaw or yaw_rate), x, y, z, yaw (NED)
        self.running = True
        self.offboard_streaming = False
        self.current_local_position = (0, 0, 0) # x, y, z (NED)
        self.current_attitude = (0, 0, 0) # roll, pitch, yaw (NED)
        self.gps_location = (0, 0, 0) # lat, lon, alt
        #self.current_quaternion = (1, 0, 0, 0) # q1, q2, q3, q4 (NED)

        # Constantly get position and attitude 
        self.get_position_thread = threading.Thread(target=self.get_local_position)
        self.get_position_thread.daemon = True
        self.get_position_thread.start()

        
        
        # Constantly send setpoints (PX4 requirement)
        self.send_thread = threading.Thread(target=self._send_pos_vel_acc_loop)
        self.send_thread.daemon = True
        self.send_thread.start()
        time.sleep(2)

    def _send_pos_vel_acc_loop(self):
        """
        PX4 requires receiving SET_POSITION_TARGET_LOCAL_NED messages 
        at >2Hz to allow and maintain OFFBOARD mode.
        """
        while self.running:
            if self.offboard_streaming:
                N, E, D, yaw = self.current_setpoint[2:]
                type_mask = 4095 - self.current_setpoint[0] - self.current_setpoint[1] # yaw_rate, yaw, accelaration(3), velocities(3), position(3) 
                
                self.master.mav.set_position_target_local_ned_send(
                    0, # time_boot_ms
                    self.master.target_system,
                    self.master.target_component,
                    mavutil.mavlink.MAV_FRAME_LOCAL_NED,
                    type_mask,
                    N, E, D,
                    N, E, D, # Velocities
                    0, 0, 0, # Accelerations
                    yaw, yaw # Yaw, Yaw rate (rad/seg)
                )

            time.sleep(0.1) # 10 Hz (safe for PX4)

    def get_gps_location(self):
        print("Waiting for GPS fix...")
        while True:
            msg = self.master.recv_match(type='GLOBAL_POSITION_INT', blocking=True)
            if msg:
                self.gps_location = (msg.lat/1e7, msg.lon/1e7, msg.relative_alt/1000.0)
                break

                
    def get_local_position(self):
        while self.running:
            #msg = self.master.recv_match(type='LOCAL_POSITION_NED', blocking=True) # estimated position with accelerometer and visual
            #if msg:
            #    self.current_position = (msg.x, msg.y, -msg.z)
            msg = self.master.recv_match(type='GLOBAL_POSITION_INT', blocking=True) # estimated position with GPS and accelerometer
            if msg:
                self.gps_location = (msg.lat/1e7, msg.lon/1e7, msg.relative_alt/1000.0)
            
            msg = self.master.recv_match(type='ATTITUDE', blocking=True)
            if msg:
                self.current_attitude = (msg.roll, msg.pitch, msg.yaw)
            
            #msg = self.master.recv_match(type='ATTITUDE_QUATERNION', blocking=True)
            #if msg:
            #    self.current_quaternion = (msg.q1, msg.q2, msg.q3, msg.q4)
            
            time.sleep(0.03)

    def arm(self):
        print("Arming...")
        self.master.mav.command_int_send(
            self.master.target_system, self.master.target_component,
            mavutil.mavlink.MAV_FRAME_LOCAL_NED,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0, 0, 1, 0, 0, 0, 0, 0, 0
        )
        self.master.motors_armed_wait()
        print("Arming confirmed!")

    def takeoff_gps(self, altitude):
        """
        In PX4, we first use the standard TAKEOFF mode.
        """
        self.get_gps_location()
        self.master.mav.command_int_send(
            self.master.target_system, 
            self.master.target_component,
            mavutil.mavlink.MAV_FRAME_LOCAL_NED,
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            0, 0, 0, 0, 0, 0, int(self.gps_location[0]*1e7), int(self.gps_location[1]*1e7), altitude
        )
        print("Takeoff")
        while True:
            if self.gps_location[2] > (0.9 * altitude):
                break
            time.sleep(0.5)

    def set_mode(self, mode_id):
        """
        Changes the PX4 mode.
        """
        self.master.mav.command_int_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_FRAME_LOCAL_NED,
            mavutil.mavlink.MAV_CMD_DO_SET_MODE,
            0, 0,
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
        
    def start_offboard_streaming(self):
        self.offboard_streaming = True

    def land(self):
        print("\nLanding!")
        self.running = False # Stop offboard stream
        self.master.mav.command_int_send(
            self.master.target_system, 
            self.master.target_component,
            mavutil.mavlink.MAV_FRAME_LOCAL_NED,
            mavutil.mavlink.MAV_CMD_NAV_LAND,
            0, 0, 0, 0, 0, 0, 0, 0, 0
        )
        self.master.motors_disarmed_wait()
        print("Drone on the ground.")



if __name__ == "__main__":
    drone = PX4DroneControl(connection_string='udpin:127.0.0.1:14540',baudrate=57600)
    
    try:
        drone.arm()
        #drone.takeoff_gps(altitude=3.0)
        #drone.go_to_local_xyz(3, 0)
        
        print("ctrl+c to land")
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        drone.land()
    except Exception as e:
        print(f"Error: {e}")
        drone.land()