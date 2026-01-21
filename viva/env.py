import re
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np
import pygame

from viva.modules.render_drone import RenderDrone
from viva.modules.simulator import Simulator


class DroneEnv:
    """A simulated environment for validating vision-based drone navigation.

    This class provides a Gymnasium-like environment for a drone navigating in a
    simulated world. It handles rendering, physics, and state management.
    """

    def __init__(
        self,
        render_mode: Optional[str] = None,
        video: str = "",
        render_fps: int = 30,
        terminated_step: int = 3600,
        fixed: bool = False,
        rel_alt_value: Optional[float] = None,
        show_fps_flag: bool = False,
        hover_z: bool = True,
        hover_xy: bool = True,
        perspective: bool = True,
    ):
        """Initializes the DroneEnv.

        Args:
            render_mode (Optional[str]): The rendering mode ('human' or 'rgb_array').
            video (str): The path to the background video.
            render_fps (int): The frames per second for rendering.
            terminated_step (int): The step at which the environment is considered terminated (at 30 FPS 3600 are 2 minutes).
            fixed (bool): Whether the background is a fixed image or a video.
            rel_alt_value (Optional[float]): Initial relative altitude of the drone in meters. If not provided, it will be extracted from the video metadata or SRT file.
            show_fps_flag (bool): Whether to display the FPS on terminal.
            hover_z (bool): Whether to enable automatic altitude control (Z axis).
            hover_xy (bool): Whether to enable automatic position control (X and Y axes).
            perspective (bool): Whether to enable the perspective transformation. If False, only yaw rotation is used.
        """
        super(DroneEnv, self).__init__()
        self.render_mode = render_mode
        self.render_fps = render_fps

        self.frame_size = np.array((3840, 2160))
        self.window_size = np.array((1280, 720))
        self.drone_view_size = np.array((480, 288))

        # Get the initial height of the drone
        if rel_alt_value is None:
            self.height = None
            srt_found = False
            for ext in [".SRT", ".srt"]:
                srt_path = video.split(".")[0] + ext
                try:
                    self.height = self._get_height(srt_path)
                    srt_found = True  # File was found and read
                    if self.height is not None:
                        break  # Altitude found, exit loop
                except FileNotFoundError:
                    continue  # Try next extension

            if self.height is None:
                if srt_found:
                    # Case: SRT found, but no altitude inside.
                    print("WARNING: Could not extract relative altitude from SRT file.")
                    print("         Defaulting to an altitude of 50m.")
                    print(
                        "         If this is not desired, please select a different altitude in the GUI or use the --rel-alt-value option in the CLI."
                    )
                # Case: SRT not found (srt_found is False) OR (SRT found but no altitude)
                # In both cases, we default to 50.
                self.height = 50.0
        else:
            self.height = rel_alt_value

        self.simulator = Simulator(
            input_size=self.frame_size,
            output_size=self.drone_view_size,
            height_dron=self.height,
            fps=render_fps,
            perspective=perspective,
        )
        self.renderer: Optional[RenderDrone] = None

        self.background_path: str = video
        self.cam: Optional[cv2.VideoCapture] = None
        self.frame: Optional[np.ndarray] = None
        self.fixed: bool = fixed

        self.window: Optional[pygame.Surface] = None
        self.clock: Optional[pygame.time.Clock] = None

        self.linear_factor: float = 7.5 # Degrees
        self.angular_factor: float = 15.0 # Degrees per second
        self.fk_factor: float = 0.5
        self.current_step: int = 0
        self.terminated_step: int = terminated_step

        self.show_fps_flag: bool = show_fps_flag
        if self.show_fps_flag:
            self.prev = cv2.getTickCount()
        self.resolution_warning_shown: bool = False
        self.hover_z = hover_z
        self.hover_xy = hover_xy

    def _get_height(self, srt_path: str) -> Optional[float]:
        """Extracts the relative altitude from an SRT file.

        Args:
            srt_path (str): The path to the SRT file.

        Returns:
            Optional[float]: The relative altitude, or None if not found.
        """
        pat_rel_alt = re.compile(r"rel_alt:\s*([\d\.]+)")
        rel_alt_value = None
        with open(srt_path, "r", encoding="utf-8") as f:
            for line in f:
                match = pat_rel_alt.search(line)
                if match:
                    rel_alt_value = float(match.group(1))
                    break
        return rel_alt_value

    def _show_fps(self) -> None:
        """Calculates and prints the current FPS."""
        current = cv2.getTickCount()
        fps = cv2.getTickFrequency() / (current - self.prev)
        self.prev = current
        print(f"FPS: {fps:.2f}")

    def _update_frame(self, reset: bool = False) -> None:
        """Updates the background frame from the video or image.

        Args:
            reset (bool): Whether to force a reset of the video capture.
        """
        if self.fixed and self.frame is None:
            self.cam = cv2.VideoCapture(self.background_path)
            ret, self.frame = self.cam.read()
            self.cam.release()
        elif not self.fixed:
            if reset and self.cam is not None:
                self.cam.release()
                self.cam = None
            if self.cam is None:
                self.cam = cv2.VideoCapture(self.background_path)
            ret, self.frame = self.cam.read()
            if not ret:
                # Reset the reader if we reach the end of the video
                self.cam.release()
                self.cam = cv2.VideoCapture(self.background_path)
                ret, self.frame = self.cam.read()

        #! TODO configure equations for different resolutions (temporal solution)
        if self.frame is not None:
            h, w, _ = self.frame.shape
            if (w, h) != tuple(self.frame_size):
                if not self.resolution_warning_shown:
                    print("WARNING: This is not the recommended resolution.")
                    self.resolution_warning_shown = True
                self.frame = cv2.resize(
                    self.frame, tuple(self.frame_size), interpolation=cv2.INTER_AREA
                )

    def reset(
            self, 
            x: Optional[float]=None, 
            y: Optional[float]=None, 
            z: Optional[float]=None,
            psi_deg_init: Optional[float]=None
        ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Resets the environment to an initial state.

        Args:
            x (Optional[float]): Initial x position of the drone in meters. If None, a random value is chosen.
            y (Optional[float]): Initial y position of the drone in meters. If None, a random value is chosen.
            z (Optional[float]): Initial z position of the drone in meters. If None, a random value is chosen between 20 and (min(60, self.height - 1)).
            psi_deg_init (Optional[float]): Initial yaw in degrees. If None, a random value is chosen between 0 and 360.

        Returns:
            observation (np.ndarray): The current drone camera view (RGB image).
            info (Dict[str, Any]): A dictionary containing auxiliary information,
                such as 'points' (coordinates for rendering), 'drone_state' (position and velocity),
                and 'actions' (the actions taken).
        """
        self.current_step = 0
        self._update_frame(reset=True)

        try:
            frame = self.frame.copy()
        except AttributeError:
            raise RuntimeError("Failed to read the background video or image, verify the file path")
        
        z_ini = z if z is not None else np.random.uniform(20, min(60, self.height - 1))
        psi_deg_init = psi_deg_init if psi_deg_init is not None else np.random.uniform(0, 360)

        lim_y = np.tan(np.radians(41.05)) * self.height
        lim_x = lim_y * 9 / 16

        view_half_y = np.tan(np.radians(41.05)) * z_ini
        view_half_x = view_half_y * 9 / 16

        psi_rad = np.radians(psi_deg_init)
        bounding_half_x = view_half_x * abs(np.cos(psi_rad)) + view_half_y * abs(np.sin(psi_rad))
        bounding_half_y = view_half_x * abs(np.sin(psi_rad)) + view_half_y * abs(np.cos(psi_rad))

        max_abs_x = lim_x - bounding_half_x
        max_abs_y = lim_y - bounding_half_y

        x_ini = x if x is not None else np.random.uniform(-max_abs_x + 1, max_abs_x - 1)
        y_ini = y if y is not None else np.random.uniform(-max_abs_y + 1, max_abs_y - 1)

        self.simulator.reset(x_ini, y_ini, z_ini, psi_deg_init=psi_deg_init)
        actions = np.array([0.0, 0.0, 0.0, 0.0])

        observation, points, drone_state, nadir_point = self.simulator.step(*actions, frame=frame)
        info = {
            "points": points,
            "drone_state": drone_state,
            "actions": actions.tolist() + [self.simulator.drone.psi_deg],
            "nadir_point": nadir_point,
        }

        # Globals for rendering
        self.drone_view = observation
        self.info = info

        if self.render_mode == "human":
            self._render_frame()

        return observation, info

    def step(self, actions: np.ndarray) -> Tuple[np.ndarray, bool, Dict[str, Any]]:
        """Executes one time step in the environment.

        Args:
            actions (np.ndarray): The actions to take in the environment:

                - actions[0]: phi (roll) in degrees.
                - actions[1]: theta (pitch) in degrees.
                - actions[2]: psi velocity (yaw rate) in degrees per second.
                - actions[3]: fk (Thrust) in newtons.

        Returns:
            observation (np.ndarray): The current drone camera view (RGB image).
            terminated (bool): Whether the episode has terminated. This occurs when:

                - The simulation reaches 5000 steps (approximately 166 seconds at 30 FPS).
                - The virtual drone moves outside the simulation boundaries.

            info (Dict[str, Any]): A dictionary containing auxiliary information:
            
                - 'points' (coordinates for rendering).
                - 'drone_state' (position and velocity).
                - 'actions' (the actions taken, including the current yaw angle).
        """
        self._update_frame()
        frame = self.frame.copy()
        if isinstance(actions, list):
            actions = np.array(actions)

        # Hover xy
        if self.hover_xy and np.all(actions[:2] == 0):
            drone = self.simulator.drone
            drone_state = drone.state[0]
            kp_brake = 0.25 # Smooth braking
            
            psi_rad = np.radians(drone.psi_deg)
            cos_psi = np.cos(psi_rad)
            sin_psi = np.sin(psi_rad)
            
            v_body_x = drone_state.vel.x * cos_psi + drone_state.vel.y * sin_psi
            v_body_y = -drone_state.vel.x * sin_psi + drone_state.vel.y * cos_psi
            
            actions[0] = np.clip(kp_brake * v_body_y, -1.0, 1.0)  # Roll (phi)
            actions[1] = np.clip(-kp_brake * v_body_x, -1.0, 1.0) # Pitch (theta)

        actions[:2] *= self.linear_factor
        actions[2] *= self.angular_factor
        actions[3] *= self.fk_factor
        
        # Hover Z
        fk_input = actions[3]
        if self.hover_z:
            drone = self.simulator.drone
            drone_state = drone.state[0]
            # compensate for tilt: uz = cos(roll)*cos(pitch)
            uz = np.cos(np.radians(drone.roll_deg)) * np.cos(np.radians(drone.pitch_deg))
            uz = max(uz, 0.1)
            
            # Base hover to counteract gravity
            base_hover_fk = (1 / uz - 1)
            
            # Additional damping if no input is provided
            damping_fk = 0.0
            if fk_input == 0:
                # Kd for vertical braking.
                kd_z = 0.25
                damping_fk = -kd_z * drone_state.vel.z
            
            actions[3] = (base_hover_fk + fk_input + damping_fk) * (drone.g * drone.mass)
        else:
            actions[3] *= self.simulator.drone.g * self.simulator.drone.mass

        observation, points, drone_state, nadir_point = self.simulator.step(*actions, frame=frame)
        info = {
            "points": points,
            "drone_state": drone_state,
            "actions": actions.tolist() + [self.simulator.drone.psi_deg],
            "nadir_point": nadir_point,
        }

        self.current_step += 1
        lim_y = np.tan(np.radians(41.05)) * self.height
        lim_x = lim_y * 9 / 16
        terminated = self.current_step >= self.terminated_step
        if (
            abs(drone_state.pos.x) > lim_x
            or abs(drone_state.pos.y) > lim_y
            or drone_state.pos.z >= self.height
            or drone_state.pos.z <= 2
        ):
            terminated = True

        # Globals for rendering
        self.drone_view = observation
        self.info = info

        if self.show_fps_flag:
            self._show_fps()
        if self.render_mode == "human":
            self._render_frame()

        return observation, terminated, info

    def render(self) -> Optional[np.ndarray]:
        """Renders the environment.

        Returns:
            Optional[np.ndarray]: The rendered frame, if render_mode is 'rgb_array'.

        Example:
            You can see an example of the rendering method on [usage documentation](usage.md#__tabbed_2_2).
        """
        if self.render_mode == "rgb_array":
            return self._render_frame()

    def _render_frame(self) -> Optional[np.ndarray]:
        """Renders a single frame.

        Returns:
            Optional[np.ndarray]: The rendered frame, if render_mode is 'rgb_array'.
        """
        if self.renderer is None:
            self.renderer = RenderDrone(
                frame_size=self.frame_size,
                drone_view_size=self.drone_view_size,
                window_size=self.window_size,
            )
        canvas = self.renderer.render(self.frame.copy(), self.drone_view, self.info)
        if self.render_mode == "human":
            if self.window is None:
                pygame.init()
                pygame.display.init()
                pygame.display.set_caption("ViVa-SAFELAND")
                self.window = pygame.display.set_mode(self.window_size)
                self.clock = pygame.time.Clock()
            canvas = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
            canvas = pygame.surfarray.make_surface(np.flip(np.rot90(canvas), 0))
            self.window.blit(canvas, canvas.get_rect())
            pygame.event.pump()
            pygame.display.update()
            self.clock.tick(self.render_fps)
            return None
        else:
            return cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
