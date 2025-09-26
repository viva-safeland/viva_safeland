import viva

env = viva.DroneEnv(
    render_mode="human",
    video=r"/media/user/HDD/Videos_Dron/AgsExedra_DJI_20240914133357_0010_D.MP4",
)

obs, info = env.reset()
end = False

while not end:
    action = [0.0, 0.0, 0.0, -0.1] # Slow descent
    obs, end, info = env.step(action)