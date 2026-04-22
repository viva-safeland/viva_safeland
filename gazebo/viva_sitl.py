from viva.env import DroneEnv
import gazebo.pymavlink_px4_interface as px4
import argparse, sys
import numpy as np


def main():
    """Run the ViVa SAFELAND simulation."""
    parser = argparse.ArgumentParser(description="Run the ViVa SAFELAND simulation.")
    parser.add_argument("video_path", help="Path to the background video file (e.g., videos/drone.MP4)")
    parser.add_argument("--render-fps", type=int, default=30, help="Frames per second for rendering")
    parser.add_argument("--fixed", action="store_true", help="Whether the background is a fixed image or a video")
    parser.add_argument("--rel-alt-value", type=float, default=None, help="Initial relative altitude of the drone. If not provided, it will be extracted from the video metadata or SRT file.")
    parser.add_argument("--show-fps-flag", action="store_true", help="Whether to display the FPS")
    parser.add_argument("--hover-z", action="store_true", help="Enable automatic altitude control (Z axis).")
    parser.add_argument("--hover-xy", action="store_true", help="Enable automatic position control (X and Y axes).")
    parser.add_argument("--no-perspective", action="store_true", help="Disable perspective transformation.")
    parser.add_argument("--baudrate", type=int, default=57600, help="Baudrate for the serial connection.")
    parser.add_argument("--direction", type=str, default='udpin:127.0.0.1:14540', help="Direction for the UAV connection.")

    args = parser.parse_args()

    video_path = args.video_path
    render_fps = args.render_fps
    fixed = args.fixed
    rel_alt_value = args.rel_alt_value
    show_fps_flag = args.show_fps_flag
    hover_z = args.hover_z
    hover_xy = args.hover_xy
    no_perspective = args.no_perspective
    baudrate = args.baudrate
    direction = args.direction

    try:
        env = DroneEnv(
            render_mode="human",
            video=video_path,
            render_fps=render_fps,
            fixed=fixed,
            rel_alt_value=rel_alt_value,  # Set to None to use the height from the video metadata
            show_fps_flag=show_fps_flag,
            hover_z= hover_z,
            hover_xy= hover_xy,
            perspective= not no_perspective,
        )
    except Exception as e:
        print(f"Error initializing environment: {e}")
        sys.exit(1)


    obs, info = env.reset()
    end = False

    quad = px4.PX4DroneControl(connection_string=direction, baudrate=baudrate)
    quad.start_offboard_streaming()
    
    roll, pitch, yaw = quad.current_attitude
    print(roll, pitch, yaw)
    yaw_offset = -yaw
    lat_offset, lon_offset, alt_offset = quad.gps_location
    quad.arm()
    quad.takeoff_gps(5)

    off_vel = 56
    off_pos = 7
    off_yaw = 1024
    off_yaw_rate = 2048

    while not end:
        lat, lon, alt = quad.gps_location
        pos_x = 2.0 * np.pi * 6371000.0 * (lat - lat_offset) / 360.0
        pos_y = 2.0 * np.pi * 6371000.0 * np.cos(lat) * (lon - lon_offset) / 360.0
        #print(pos_x, pos_y)
        roll, pitch, yaw = quad.current_attitude
        roll_deg = roll * 180 / np.pi
        pitch_deg = pitch * 180 / np.pi
        yaw_deg = yaw * 180 / np.pi
        yaw_deg = -yaw_deg - (yaw_offset*180/np.pi)
        #attitude = (roll_deg, pitch_deg, yaw_deg)

        x = pos_x*np.cos(yaw_offset) + pos_y*np.sin(yaw_offset)
        y = -pos_x*np.sin(yaw_offset) + pos_y*np.cos(yaw_offset)
        #position = (x, y, alt)
        #print(position)
        quad.current_setpoint = (off_vel, off_yaw_rate, 0.5, 0, 0, 0.2) 
        quad.set_mode_offboard()
        
        obs, end, info = env.set_state(x, y, alt, roll_deg, -pitch_deg, yaw_deg, 0.0)


if __name__ == "__main__":
    main()