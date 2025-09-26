from typing import Any, Dict, Tuple

import cv2
import numpy as np


class RenderDrone:
    """Handles the rendering of the drone and its environment."""

    def __init__(
        self,
        frame_size: Tuple[int, int] = (3840, 2160),
        drone_view_size: Tuple[int, int] = (480, 288),
        window_size: Tuple[int, int] = (1280, 720),
    ):
        """Initializes the RenderDrone.

        Args:
            frame_size (Tuple[int, int]): The size of the background frame.
            drone_view_size (Tuple[int, int]): The size of the drone's camera view.
            window_size (Tuple[int, int]): The size of the display window.
        """
        self.colors = {
            "white": (255, 255, 255),
            "black": (0, 0, 0),
            "red": (0, 0, 255),
            "green": (0, 255, 0),
            "blue": (255, 0, 0),
        }

        self.fonts_params = {
            "font": cv2.FONT_HERSHEY_SIMPLEX,
            "font_scale": 0.75,
            "thickness": 1,
        }

        self.window_size = window_size
        self.frame_factor = 0.7 * window_size[0] / frame_size[0]
        self.drone_view_factor = 0.29 * window_size[0] / drone_view_size[0]

        self.frame_resized_size = cv2.resize(
            np.zeros((frame_size[1], frame_size[0], 3), np.uint8),
            None,
            fx=self.frame_factor,
            fy=self.frame_factor,
        ).shape[:2][::-1]
        self.drone_view_resized_size = cv2.resize(
            np.zeros((drone_view_size[1], drone_view_size[0], 3), np.uint8),
            None,
            fx=self.drone_view_factor,
            fy=self.drone_view_factor,
        ).shape[:2][::-1]

        self.frame_y = (self.window_size[1] - self.frame_resized_size[1]) // 2
        self.drone_view_x_init = self.window_size[0] - self.drone_view_resized_size[0]

    def _draw_drone_state(self, frame: np.ndarray, info: Dict[str, Any]) -> np.ndarray:
        """Draws the drone's state on the frame.

        Args:
            frame (np.ndarray): The background frame.
            info (Dict[str, Any]): A dictionary containing drone state information.

        Returns:
            np.ndarray: The frame with the drone state drawn on it.
        """
        drone_state = info["drone_state"]
        points = info["points"]
        circle_color = (
            self.colors["green"] if drone_state.vel.z > 0 else self.colors["red"]
        )
        center = np.int32(np.mean(points, axis=0))
        cv2.circle(
            frame, center, np.int32(np.abs(drone_state.vel.z * 500)), circle_color, 3
        )
        magnitude = np.int32(
            np.linalg.norm([drone_state.vel.x, drone_state.vel.y]) * 10
        )
        angle = np.arctan2(drone_state.vel.y, drone_state.vel.x) + np.pi / 2
        cv2.arrowedLine(
            frame,
            center,
            np.int32(center + magnitude * np.array([np.cos(angle), -np.sin(angle)])),
            self.colors["blue"],
            10,
            tipLength=0.5,
        )
        cv2.polylines(frame, [points], True, self.colors["green"], 5)
        return frame

    def _info(self, info: Dict[str, Any]) -> None:
        """Draws informational text on the canvas."""
        phi, theta, psi_vel, fk, psi = info["actions"]
        drone_state = info["drone_state"]

        control_text = [
            "Angles are in degrees",
            f"Phi: {phi:.2f}",
            f"Theta: {theta:.2f}",
            f"Psi: {psi:.2f}",
            "",
            f"Psi Vel: {psi_vel:.2f}",
            f"Fk: {fk:.2f}",
        ]

        drone_state_text = [
            f"Pos. X: {drone_state.pos.x:.2f}",
            f"Pos. Y: {drone_state.pos.y:.2f}",
            f"Pos. Z: {drone_state.pos.z:.2f}",
            f"Vel. X: {drone_state.vel.x:.2f}",
            f"Vel. Y: {drone_state.vel.y:.2f}",
            f"Vel. Z: {drone_state.vel.z:.2f}",
        ]

        start_x = self.drone_view_x_init
        line_height = 30  # Height between lines
        start_y = self.frame_y + self.drone_view_resized_size[1] + line_height * 2

        for i, text in enumerate(control_text):
            position = (start_x + i // 4 * 200, start_y + i % 4 * line_height)
            cv2.putText(
                self.canvas,
                text,
                position,
                self.fonts_params["font"],
                self.fonts_params["font_scale"],
                self.colors["white"],
                self.fonts_params["thickness"],
                cv2.LINE_AA,
            )

        for i, text in enumerate(drone_state_text):
            position = (
                start_x + i // 3 * 200,
                start_y + i % 3 * line_height + (len(control_text) - 1) * line_height,
            )
            cv2.putText(
                self.canvas,
                text,
                position,
                self.fonts_params["font"],
                self.fonts_params["font_scale"],
                self.colors["white"],
                self.fonts_params["thickness"],
                cv2.LINE_AA,
            )

    def render(
        self, frame: np.ndarray, drone_view: np.ndarray, info: Dict[str, Any]
    ) -> np.ndarray:
        """Renders the main canvas.

        Args:
            frame (np.ndarray): The background frame.
            drone_view (np.ndarray): The drone's camera view.
            info (Dict[str, Any]): A dictionary containing drone state information.

        Returns:
            np.ndarray: The final rendered canvas.
        """
        self.canvas = np.zeros((self.window_size[1], self.window_size[0], 3), np.uint8)
        frame = self._draw_drone_state(frame, info)
        frame_resized = cv2.resize(
            frame, None, fx=self.frame_factor, fy=self.frame_factor
        )
        drone_view_resized = cv2.resize(
            drone_view, None, fx=self.drone_view_factor, fy=self.drone_view_factor
        )
        self._info(info)
        self.canvas[
            self.frame_y : self.frame_y + self.frame_resized_size[1],
            : self.frame_resized_size[0],
        ] = frame_resized
        self.canvas[
            self.frame_y : self.frame_y + self.drone_view_resized_size[1],
            self.drone_view_x_init : self.drone_view_x_init
            + self.drone_view_resized_size[0],
        ] = drone_view_resized
        return self.canvas


if __name__ == "__main__":
    print("Aqui no hay nada rey")
