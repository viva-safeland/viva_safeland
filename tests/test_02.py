from viva import DroneEnv
from viva import HMI

env = DroneEnv(
    render_mode="human",
    video="/media/user/HDD/Videos_Dron/DJI_20240910181532_0005_D.MP4",
)
env.reset(psi_deg_init=0.0)
control = HMI()
terminated = False
while not terminated:
    action, reset, terminated_command = control()
    if reset:
        env.reset()
    obs, terminated, info = env.step(action)
    terminated = terminated or terminated_command
