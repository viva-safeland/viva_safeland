from typing import Optional

import typer

from viva.env import DroneEnv
from viva.modules.hmi import HMI

app = typer.Typer()


@app.command()
def main(
    video_path: str = typer.Argument(
        ..., help="Path to the background video file (e.g., videos/drone.MP4)"
    ),
    render_fps: int = typer.Option(
        30, help="Frames per second for rendering"
    ),
    fixed: bool = typer.Option(
        False, help="Whether the background is a fixed image or a video"
    ),
    rel_alt_value: Optional[float] = typer.Option(
        None,
        help="Initial relative altitude of the drone. If not provided, it will be extracted from the video metadata or SRT file.",
    ),
    show_fps_flag: bool = typer.Option(False, help="Whether to display the FPS"),
):
    """Run the ViVa SAFELAND simulation."""
    try:
        env = DroneEnv(
            render_mode="human",
            video=video_path,
            render_fps=render_fps,
            fixed=fixed,
            rel_alt_value=rel_alt_value,  # Set to None to use the height from the video metadata
            show_fps_flag=show_fps_flag,
        )
    except Exception as e:
        typer.echo(f"Error initializing environment: {e}")
        raise typer.Exit(code=1)

    obs, info = env.reset()
    terminated = False

    hmi = HMI()
    while hmi.active and not terminated:
        actions, reset, terminated_command = hmi()
        if reset:
            obs, info = env.reset()
        try:
            obs, terminated, info = env.step(actions)
            terminated = terminated or terminated_command
        except Exception as e:
            typer.echo(f"Error during step: {e}")
            hmi.quit()
            raise typer.Exit(code=1)
    hmi.quit()

if __name__ == "__main__":
    app()
