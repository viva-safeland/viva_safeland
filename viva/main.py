import argparse, sys
from typing import Optional

from viva.env import DroneEnv
from viva.modules.hmi import HMI


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

    args = parser.parse_args()

    video_path = args.video_path
    render_fps = args.render_fps
    fixed = args.fixed
    rel_alt_value = args.rel_alt_value
    show_fps_flag = args.show_fps_flag
    hover_z = args.hover_z
    hover_xy = args.hover_xy
    no_perspective = args.no_perspective

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
    terminated = False

    hmi = HMI()
    while hmi.active and not terminated:
        actions, command, terminated_command = hmi()
        if command == "reset":
            obs, info = env.reset()
        try:
            obs, terminated, info = env.step(actions)
            terminated = terminated or terminated_command
        except Exception as e:
            print(f"Error during step: {e}")
            hmi.quit()
            sys.exit(1)
    hmi.quit()

if __name__ == "__main__":
    main()
