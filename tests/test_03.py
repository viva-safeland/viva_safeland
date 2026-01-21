from viva import DroneEnv
from viva import HMI
from viva.modules.motion_blur import MotionBlur
import cv2

env = DroneEnv(
    render_mode="human", 
    video=r"//media/juls/Storage/Videos_Dron/Completos/AgsExedra_DJI_20240914133357_0010_D_alt130m/AgsExedra_DJI_20240914133357_0010_D.MP4",
    hover_xy=True,
    hover_z=True,
    perspective=True,
)
env.reset(psi_deg_init=0.0)
control = HMI()
blur_engine = MotionBlur(shutter_factor=10.5)
terminated = False
while not terminated:
    action, reset, terminated_command = control()
    if reset: 
        env.reset()
    obs, env_terminated, info = env.step(action)

    blurred_obs = blur_engine.apply(obs, info, fps=env.render_fps)

    cv2.imshow("Original View", obs)
    cv2.imshow("Motion Blur View", blurred_obs)

    terminated = env_terminated or terminated_command

    if cv2.waitKey(1)  == 27: # ESC
        terminated = True

cv2.destroyAllWindows()
