import numpy as np
import cv2

class MotionBlur:
    def __init__(self, output_size=(480, 288), shutter_factor=0.5):
        self.w, self.h = output_size
        self.shutter_factor = shutter_factor
        self.f = self.w / (2 * np.tan(np.radians(41.05)))
        self.cx, self.cy = self.w / 2.0, self.h / 2.0
        self.xx, self.yy = np.meshgrid(np.arange(self.w), np.arange(self.h))
        self.x_rel = self.xx - self.cx
        self.y_rel = self.yy - self.cy

    def apply(self, obs, info, fps):
        drone_state = info['drone_state']
        psi_deg = info['actions'][4]
        psi_vel_deg = info['actions'][2]
        altitude = drone_state.pos.z
        
        psi_rad = np.radians(psi_deg)
        vx_w, vy_w, vz_w = drone_state.vel.x, drone_state.vel.y, drone_state.vel.z
        v_f = vx_w * np.cos(psi_rad) + vy_w * np.sin(psi_rad)
        v_l = -vx_w * np.sin(psi_rad) + vy_w * np.cos(psi_rad)
        v_cam = np.array([-v_l, -v_f, -vz_w]) 
        w_cam = np.array([0, 0, np.radians(psi_vel_deg)])
        
        shutter_time = self.shutter_factor / fps
        steps = int(max(5, min(50, 10 * self.shutter_factor)))
        
        f = self.f
        du = ((1.0/altitude) * (-f * v_cam[0] + self.x_rel * v_cam[2]) + (self.y_rel * w_cam[2])) * shutter_time
        dv = ((1.0/altitude) * (-f * v_cam[1] + self.y_rel * v_cam[2]) + (-self.x_rel * w_cam[2])) * shutter_time
        
        accumulator = np.zeros_like(obs, dtype=np.float32)
        for i in range(steps):
            t_frac = -(i / max(1, steps - 1))
            map_x = (self.xx + du * t_frac).astype(np.float32)
            map_y = (self.yy + dv * t_frac).astype(np.float32)
            accumulator += cv2.remap(obs, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            
        return (accumulator / steps).astype(np.uint8)