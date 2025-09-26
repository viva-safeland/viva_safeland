from dataclasses import dataclass, field
from typing import List, Tuple

import cv2
import numpy as np


@dataclass
class Vector3D:
    """Represents a 3D vector."""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


@dataclass
class StateElement:
    """Represents an element of the drone's state (position and velocity)."""

    pos: Vector3D
    vel: Vector3D = field(default_factory=Vector3D)


class Drone:
    """Simulates the drone's physics and movement."""

    def __init__(self, fps) -> None:
        """Initializes the Drone."""
        self.mass: float = 0.468                    # Mass of a real drone in kg
        self.g: float = 9.81                        # Gravitational acceleration in m/s^2
        self.kd: float = 0.15                       # Friction force
        self.state: List[StateElement] = []         # Drone state (position and velocity)
        self.dt: float = 1 / fps                    # Delta time
        self.per: List[float] = [0.0, 0.0, 0.0]     # Perturbations
        self.fkeq: float = self.g * self.mass       # Equilibrium force
        self.psi_deg: float = 0.0                   # Yaw angle in degrees

    def _calculate_unit_vectors(
        self, phi_deg: float, theta_deg: float, psi_deg: float
    ) -> Tuple[float, float, float]:
        """Calculates the unit vectors based on the drone's orientation."""
        (sin_phi, cos_phi), (sin_theta, cos_theta), (sin_psi, cos_psi) = [
            (np.sin(np.radians(x)), np.cos(np.radians(x)))
            for x in [phi_deg, theta_deg, psi_deg]
        ]

        # Please read README.md to understand the following equations
        ux = cos_phi * sin_theta * cos_psi + sin_phi * sin_psi
        uy = cos_phi * sin_theta * sin_psi - sin_phi * cos_psi
        uz = cos_phi * cos_theta

        return ux, uy, uz

    def _update_state(
        self, phi_deg: float, theta_deg: float, psi_deg_vel: float, fk: float
    ) -> None:
        """Updates the drone's state using Verlet integration."""
        self.psi_deg = (self.psi_deg + psi_deg_vel * self.dt) % 360
        ux, uy, uz = self._calculate_unit_vectors(phi_deg, theta_deg, self.psi_deg)
        for axis, u, per in zip(["x", "y", "z"], [ux, uy, uz], self.per):
            velocity = (
                getattr(self.state[1].pos, axis) - getattr(self.state[2].pos, axis)
            ) / self.dt
            thrust_force = u * (self.fkeq + fk)
            friction_force = -self.kd * velocity
            gravity_force = -self.mass * self.g if axis == "z" else 0.0
            net_force = thrust_force + friction_force + gravity_force + per
            acceleration = net_force / self.mass
            setattr(
                self.state[0].pos,
                axis,
                2 * getattr(self.state[1].pos, axis)
                - getattr(self.state[2].pos, axis)
                + acceleration * self.dt**2,
            )
            setattr(
                self.state[0].vel,
                axis,
                (getattr(self.state[0].pos, axis) - getattr(self.state[1].pos, axis))
                / self.dt,
            )

    def _shift_states(self) -> None:
        """Shifts the state history for the Verlet integration."""
        self.state[2].pos = Vector3D(
            self.state[1].pos.x, self.state[1].pos.y, self.state[1].pos.z
        )
        self.state[1].pos = Vector3D(
            self.state[0].pos.x, self.state[0].pos.y, self.state[0].pos.z
        )

    def reset(self, x_ini: float, y_ini: float, z_ini: float, psi_deg_init: float) -> None:
        """Resets the drone's state to an initial position."""
        self.state = [
            StateElement(
                pos=Vector3D(x=x_ini, y=y_ini, z=z_ini),
                vel=Vector3D(x=0.0, y=0.0, z=0.0),
            )
            for _ in range(3)
        ]
        self.psi_deg = psi_deg_init % 360

    def move(self, phi_deg: float, theta_deg: float, psi_deg_vel: float, fk: float) -> None:
        """Moves the drone for one time step."""
        assert self.state is not None, "You must call reset before calling move"
        self._update_state(phi_deg, theta_deg, psi_deg_vel, fk)
        self._shift_states()


class Camera:
    """Simulates the drone's camera and perspective transformation."""

    def __init__(
        self,
        input_size: Tuple[int, int],
        output_size: Tuple[int, int],
        height_dron: float,
    ):
        """Initializes the Camera."""
        self.input = np.array(input_size, dtype=np.int32)
        self.output = np.array(output_size, dtype=np.int32)
        self.height_dron = height_dron                          # Height at which the video was taken

    def _camera_relation(self, state: StateElement) -> np.ndarray:
        """Calculates the camera-to-world relation."""
        # Axes convention (x: forward, y: left, z: up)
        # Horizontal
        fy = self.input[0] / (2 * np.tan(np.radians(41.05)))
        ynorm = state.pos.y / state.pos.z
        vp = fy * ynorm
        # Vertical
        fovx = 2 * np.arctan(np.tan(np.radians(41.05)) * 9 / 16)
        fx = self.input[1] / (2 * np.tan(fovx / 2))
        xnorm = state.pos.x / state.pos.z
        up = fx * xnorm
        return np.array([-vp, up], np.float32)

    @staticmethod
    def _rotate_point(
        x: float, y: float, cx: float, cy: float, angle_deg: float
    ) -> np.ndarray:
        """Rotates a point around a center."""
        radians = np.deg2rad(angle_deg)
        cos = np.cos(radians)
        sin = np.sin(radians)
        nx = cos * (x - cx) - sin * (y - cy) + cx
        ny = sin * (x - cx) + cos * (y - cy) + cy
        return np.int32([nx, ny])

    def get_drone_view(
        self, frame: np.ndarray, drone_state: StateElement, psi_deg: float
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Calculates the drone's camera view based on its state."""
        # Scale factor based on drone height and pixels per meter
        scale_factor = max(1e-8, drone_state.pos.z / self.height_dron)
        up, vp = self._camera_relation(drone_state)

        rect_dims = np.int32(self.input * scale_factor)
        rect_pos = np.int32(
            (self.input - rect_dims) / 2 + np.array([up, -vp]) * scale_factor
        )
        center = rect_pos + rect_dims // 2  # Center of the rectangle

        # Calculate the four corners of the rectangle after rotation
        top_left = self._rotate_point(*rect_pos, *center, psi_deg)
        top_right = self._rotate_point(
            rect_pos[0] + rect_dims[0], rect_pos[1], *center, psi_deg
        )
        bottom_right = self._rotate_point(*rect_pos + rect_dims, *center, psi_deg)
        bottom_left = self._rotate_point(
            rect_pos[0], rect_pos[1] + rect_dims[1], *center, psi_deg
        )

        # Calculate the transformation matrix and obtain the camera view
        src_pts = np.array([top_left, top_right, bottom_right, bottom_left], np.float32)
        dst_pts = np.array(
            [
                [0, 0],
                [self.output[0] - 1, 0],
                [self.output[0] - 1, self.output[1] - 1],
                [0, self.output[1] - 1],
            ],
            np.float32,
        )
        M = cv2.getPerspectiveTransform(src_pts, dst_pts)
        drone_view = cv2.warpPerspective(frame, M, self.output, borderValue=(255, 0, 0))

        return drone_view, src_pts.astype(np.int32)


class Simulator:
    """Main simulator class that combines the drone and camera."""

    def __init__(
        self,
        input_size: Tuple[int, int],
        output_size: Tuple[int, int],
        height_dron: float,
        fps: int,
    ):
        """Initializes the Simulator."""
        self.drone = Drone(fps=fps)
        self.camera = Camera(input_size, output_size, height_dron)

    def reset(self, x_ini: float, y_ini: float, z_ini: float, psi_deg_init: float) -> None:
        """Resets the simulator."""
        self.drone.reset(x_ini, y_ini, z_ini, psi_deg_init)

    def step(
        self, theta_deg: float, phi_deg: float, psi_deg_vel: float, fk: float, frame: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, StateElement]:
        """Executes one simulation step."""
        self.drone.move(theta_deg, phi_deg, psi_deg_vel, fk)
        drone_view, points = self.camera.get_drone_view(frame, self.drone.state[0], -self.drone.psi_deg)
        return drone_view, points, self.drone.state[0]
    
if __name__ == "__main__":
    frame_size = np.array((3840, 2160))
    window_size = np.array((1280, 720))
    drone_view_size = np.array((480, 288))
    drone = Drone(fps=30)
    drone.reset(0.0, 0.0, 10.0, 0.0)
    for _ in range(10):
        drone.move(0.0, 0.0, -1.0, 0.5)
        print(drone.psi_deg)