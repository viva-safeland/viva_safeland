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
        self.psi_deg_vel_current: float = 0.0      # Current yaw velocity
        self.roll_deg: float = 0.0                  # Current roll in degrees
        self.pitch_deg: float = 0.0                 # Current pitch in degrees
        self.tau: float = 0.1                      # Time constant for attitude dynamics (seconds)
        self.tau_yaw: float = 0.2                  # Time constant for yaw dynamics (seconds)

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
        self, target_roll: float, target_pitch: float, target_psi_vel: float, fk: float
    ) -> None:
        """Updates the drone's state using Verlet integration and attitude dynamics."""
        # Smooth yaw velocity (angular inertia)
        alpha_yaw = self.dt / (self.tau_yaw + self.dt)
        self.psi_deg_vel_current += alpha_yaw * (target_psi_vel - self.psi_deg_vel_current)
        
        self.psi_deg = (self.psi_deg + self.psi_deg_vel_current * self.dt) % 360
        
        # Smooth roll and pitch (first-order lag)
        alpha = self.dt / (self.tau + self.dt)
        self.roll_deg += alpha * (target_roll - self.roll_deg)
        self.pitch_deg += alpha * (target_pitch - self.pitch_deg)

        ux, uy, uz = self._calculate_unit_vectors(self.roll_deg, self.pitch_deg, self.psi_deg)
        for axis, u, per in zip(["x", "y", "z"], [ux, uy, uz], self.per):
            velocity = (
                getattr(self.state[1].pos, axis) - getattr(self.state[2].pos, axis)
            ) / self.dt
            thrust_force = u * (self.fkeq + fk)
            if axis in ["x", "y"]: thrust_force *= 2.0 #! better performance
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
        self.psi_deg_vel_current = 0.0
        self.roll_deg = 0.0
        self.pitch_deg = 0.0

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


    @staticmethod
    def _rotate_3d(points: np.ndarray, roll: float, pitch: float, yaw: float) -> np.ndarray:
        """Rotates 3D points based on roll, pitch, and yaw (degrees)."""
        r, p, y = np.radians([roll, pitch, yaw])
        
        # Rotation matrix R = Rz(yaw) * Ry(pitch) * Rx(roll)
        cr, sr = np.cos(r), np.sin(r)
        cp, sp = np.cos(p), np.sin(p)
        cy, sy = np.cos(y), np.sin(y)

        Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
        Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
        Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])

        R = Rz @ Ry @ Rx
        return (R @ points.T).T

    def world_to_pixel(self, x: float, y: float) -> np.ndarray:
        """Converts world coordinates [x, y] to pixel coordinates [u, v]."""
        hfov = np.radians(82.1)
        meters_h = 2 * self.height_dron * np.tan(hfov / 2)
        scale = self.input[0] / meters_h
        center_px = self.input / 2
        
        u = center_px[0] - y * scale
        v = center_px[1] - x * scale
        return np.array([u, v], dtype=np.float32)

    def get_drone_view(
        self,
        frame: np.ndarray,
        drone_state: StateElement,
        roll: float,
        pitch: float,
        yaw: float,
        perspective: bool = True,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Calculates the drone's camera view based on its state and orientation."""
        if not perspective:
            roll = 0.0
            pitch = 0.0

        hfov = np.radians(82.1) # 2 * 41.05
        vfov = 2 * np.arctan(np.tan(hfov / 2) * (self.input[1] / self.input[0]))
        
        tan_h = np.tan(hfov / 2)
        tan_v = np.tan(vfov / 2)
        
        corners_c = np.array([
            [-tan_h, -tan_v, 1], # TL
            [ tan_h, -tan_v, 1], # TR
            [ tan_h,  tan_v, 1], # BR
            [-tan_h,  tan_v, 1]  # BL
        ])

        # X_b = -Y_c, Y_b = -X_c, Z_b = -Z_c
        # where b is Body Coords and c is Camera Coords
        corners_b = np.stack([-corners_c[:, 1], -corners_c[:, 0], -corners_c[:, 2]], axis=1)
        corners_w = self._rotate_3d(corners_b, roll, pitch, yaw)
        drone_pos = np.array([drone_state.pos.x, drone_state.pos.y, drone_state.pos.z])

        # Intersect rays with ground plane (z=0)
        # Ray: P = drone_pos + t * corners_w
        # z = drone_pos.z + t * corners_w.z = 0  => t = -drone_pos.z / corners_w.z
        ground_pts = []
        for i in range(4):
            if corners_w[i, 2] >= -1e-6: # Ray pointing up or parallel to ground
                t = 1000.0 
            else:
                t = -drone_pos[2] / corners_w[i, 2]
            
            p_ground = drone_pos + t * corners_w[i]
            ground_pts.append(p_ground[:2]) # [x, y] in world

        ground_pts = np.array(ground_pts, dtype=np.float32)
        src_pts = np.array([self.world_to_pixel(pt[0], pt[1]) for pt in ground_pts], dtype=np.float32)

        dst_pts = np.array([
            [0, 0],
            [self.output[0] - 1, 0],
            [self.output[0] - 1, self.output[1] - 1],
            [0, self.output[1] - 1],
        ], np.float32)

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
        perspective: bool = True,
    ):
        """Initializes the Simulator."""
        self.drone = Drone(fps=fps)
        self.camera = Camera(input_size, output_size, height_dron)
        self.perspective = perspective

    def reset(self, x_ini: float, y_ini: float, z_ini: float, psi_deg_init: float) -> None:
        """Resets the simulator."""
        self.drone.reset(x_ini, y_ini, z_ini, psi_deg_init)

    def step(
        self, phi_deg: float, theta_deg: float, psi_deg_vel: float, fk: float, frame: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, StateElement, np.ndarray]:
        """Executes one simulation step."""
        self.drone.move(phi_deg, theta_deg, psi_deg_vel, fk)
        
        # Use smoothed angles for the camera view
        drone_view, points = self.camera.get_drone_view(
            frame, 
            self.drone.state[0], 
            self.drone.roll_deg, 
            self.drone.pitch_deg, 
            self.drone.psi_deg,
            perspective=self.perspective
        )
        nadir_point = self.camera.world_to_pixel(self.drone.state[0].pos.x, self.drone.state[0].pos.y)
        return drone_view, points, self.drone.state[0], nadir_point.astype(np.int32)
    
if __name__ == "__main__":
    frame_size = np.array((3840, 2160))
    window_size = np.array((1280, 720))
    drone_view_size = np.array((480, 288))
    drone = Drone(fps=30)
    drone.reset(0.0, 0.0, 10.0, 0.0)
    for _ in range(10):
        drone.move(0.0, 0.0, -1.0, 0.5)
        print(drone.psi_deg)