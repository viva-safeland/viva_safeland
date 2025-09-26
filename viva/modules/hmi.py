from typing import Tuple, Dict
import pygame, numpy as np
import pygame._sdl2.controller as controller
from pygame.locals import (
    K_DOWN, K_ESCAPE, K_LEFT, K_RIGHT, K_UP,
    KEYDOWN, KEYUP, K_a, K_d, K_r, K_s, K_w,
)


class HMI:
    """Human-Machine Interface for controlling drone environments.

    This class handles both joystick controller and keyboard inputs to generate
    control actions for a simulation. It provides universal controller
    support with consistent mappings across different controller types.
    """

    def __init__(self, dead_zone: float = 0.1) -> None:
        """Initializes the HMI system and the controller interface.

        Args:
            dead_zone: The dead zone threshold for joystick analog inputs (0.0 to 1.0).
        """
        # Control state variables
        self.active: bool = True
        self.phi: float = 0.0           # Pitch (degrees)
        self.theta: float = 0.0         # Roll (degrees)
        self.psi_velocity: float = 0.0  # Yaw velocity (degrees per second)
        self.fk: float = 0.0            # Thrust
        self.reset_commanded: bool = False

        # Initialize pygame and controller system
        pygame.init()
        controller.init()
        controller.set_eventstate(True)

        # Active controllers dictionary
        self.controllers: Dict[int, controller.Controller] = {}
        self.dead_zone: float = dead_zone

        # SDL2 Controller button and axis mapping - Universal across all controllers
        self.button_map = {
            pygame.CONTROLLER_BUTTON_A: "A",
            pygame.CONTROLLER_BUTTON_B: "B",
            pygame.CONTROLLER_BUTTON_X: "X",
            pygame.CONTROLLER_BUTTON_Y: "Y",
            pygame.CONTROLLER_BUTTON_LEFTSHOULDER: "LB",
            pygame.CONTROLLER_BUTTON_RIGHTSHOULDER: "RB",
            pygame.CONTROLLER_BUTTON_BACK: "BACK",
            pygame.CONTROLLER_BUTTON_START: "START",
            pygame.CONTROLLER_BUTTON_GUIDE: "GUIDE",
            pygame.CONTROLLER_BUTTON_LEFTSTICK: "LS",
            pygame.CONTROLLER_BUTTON_RIGHTSTICK: "RS",
            pygame.CONTROLLER_BUTTON_DPAD_UP: "DPAD_UP",
            pygame.CONTROLLER_BUTTON_DPAD_DOWN: "DPAD_DOWN",
            pygame.CONTROLLER_BUTTON_DPAD_LEFT: "DPAD_LEFT",
            pygame.CONTROLLER_BUTTON_DPAD_RIGHT: "DPAD_RIGHT",
        }

        self.axis_map = {
            pygame.CONTROLLER_AXIS_LEFTX: "LEFT_X",
            pygame.CONTROLLER_AXIS_LEFTY: "LEFT_Y",
            pygame.CONTROLLER_AXIS_RIGHTX: "RIGHT_X",
            pygame.CONTROLLER_AXIS_RIGHTY: "RIGHT_Y",
            pygame.CONTROLLER_AXIS_TRIGGERLEFT: "LEFT_TRIGGER",
            pygame.CONTROLLER_AXIS_TRIGGERRIGHT: "RIGHT_TRIGGER",
        }
        
        self._scan_controllers()

    def _scan_controllers(self) -> None:
        """Scans for and initializes available controllers.

        Detects newly connected controllers and adds them to the active
        controllers dictionary. Removes any that have been disconnected.
        """
        disconnected = [
            idx for idx, ctrl in self.controllers.items()
            if not ctrl.attached()
        ]
        for idx in disconnected:
            self.controllers[idx].quit()
            del self.controllers[idx]

        count = controller.get_count()

        if not count:
            print("No controllers connected, using keyboard input")

        for i in range(count):
            if i not in self.controllers and controller.is_controller(i):
                try:
                    ctrl = controller.Controller(i)
                    if ctrl.attached():
                        self.controllers[i] = ctrl
                        name = controller.name_forindex(i) or f"Controller {i}"
                        print(f"Controller connected: {name}")
                except Exception as e:
                    print(f"Failed to initialize controller {i}: {e}")

    def _apply_deadzone(self, value: float) -> float:
        """Applies dead zone filtering to an analog input value.

        Args:
            value: The raw analog input value (-1.0 to 1.0).

        Returns:
            The filtered value with the dead zone applied.
        """
        if abs(value) < self.dead_zone:
            return 0.0
        sign = 1 if value > 0 else -1
        scaled = (abs(value) - self.dead_zone) / (1.0 - self.dead_zone)
        return sign * scaled

    def _normalize_axis(self, raw_value: int) -> float:
        """Converts a raw axis value to a normalized float.

        Args:
            raw_value: The raw axis value from the controller (-32768 to 32767).

        Returns:
            A normalized value between -1.0 and 1.0.
        """
        return raw_value / 32767.0

    def _normalize_trigger(self, raw_value: int) -> float:
        """Converts a raw trigger value to a normalized float.

        Args:
            raw_value: The raw trigger value from the controller (0 to 32767).

        Returns:
            A normalized value between 0.0 and 1.0.
        """
        return raw_value / 32767.0

    def _handle_controller_button_event(self, event: pygame.event.Event) -> None:
        """Handles controller button press events using the universal mapping.

        Args:
            event: The Pygame controller button event to process.
        """
        if event.type == pygame.CONTROLLERBUTTONDOWN:
            button_name = self.button_map.get(event.button, f"UNKNOWN_{event.button}")
            if button_name == "B":
                self.active = False
            elif button_name == "BACK":
                self.reset_commanded = True
                self.psi = 0.0

    def _handle_controller_axis_event(self, event: pygame.event.Event) -> None:
        """Handles controller axis motion events using the universal mapping.

        Args:
            event: The Pygame controller axis motion event to process.
        """
        if event.type == pygame.CONTROLLERAXISMOTION:
            axis_name = self.axis_map.get(event.axis, f"UNKNOWN_{event.axis}")

            if axis_name in ["LEFT_TRIGGER", "RIGHT_TRIGGER"]:
                normalized_value = self._normalize_trigger(event.value)
            else:
                normalized_value = self._normalize_axis(event.value)
            
            filtered_value = self._apply_deadzone(normalized_value)

            if axis_name == "RIGHT_X":
                self.theta = filtered_value
            elif axis_name == "RIGHT_Y":
                self.phi = -filtered_value
            elif axis_name == "LEFT_X":
                self.psi_velocity = -filtered_value
            elif axis_name == "LEFT_Y":
                self.fk = -filtered_value

    def _handle_keyboard_events(self, event: pygame.event.Event) -> None:
        """Handles keyboard input events.

        Args:
            event: The Pygame keyboard event to process.
        """
        if event.type == KEYDOWN:
            if event.key == K_UP: self.phi = 1.0
            if event.key == K_DOWN: self.phi = -1.0
            if event.key == K_RIGHT: self.theta = 1.0
            if event.key == K_LEFT: self.theta = -1.0
            if event.key == K_d: self.psi_velocity = -1.0
            if event.key == K_a: self.psi_velocity = 1.0
            if event.key == K_w: self.fk = 1.0
            if event.key == K_s: self.fk = -1.0
            
            if event.key == K_r:
                self.reset_commanded = True
                self.psi = 0.0
            if event.key == K_ESCAPE:
                self.active = False

        elif event.type == KEYUP:
            if event.key in (K_UP, K_DOWN): self.phi = 0.0
            if event.key in (K_RIGHT, K_LEFT): self.theta = 0.0
            if event.key in (K_a, K_d): self.psi_velocity = 0.0
            if event.key in (K_w, K_s): self.fk = 0.0

    def _handle_events(self) -> None:
        """Processes all pygame events for input handling.
        
        Handles controller connection/disconnection, button presses, axis motion,
        and keyboard input events via the event queue.
        """
        self.reset_commanded = False
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.active = False
            elif event.type in (pygame.CONTROLLERDEVICEADDED, pygame.CONTROLLERDEVICEREMOVED):
                self._scan_controllers()
            elif event.type == pygame.CONTROLLERBUTTONDOWN:
                self._handle_controller_button_event(event)
            elif event.type == pygame.CONTROLLERAXISMOTION:
                self._handle_controller_axis_event(event)
            # elif event.type in (KEYDOWN, KEYUP) and not self.controllers: # Uses keyboard if no controllers are connected
            #     self._handle_keyboard_events(event)
            elif event.type in (KEYDOWN, KEYUP):                        # Always uses keyboard
                self._handle_keyboard_events(event)

    def __call__(self) -> Tuple[np.ndarray, bool, bool]:
        """Processes input and returns the current control state.

        This method makes the HMI instance callable and should be used in
        the main control loop. It processes all pending events and updates
        control variables.

        Returns:
            A tuple containing:

                - actions (np.ndarray): Control values [theta, phi, psi_velocity, fk].
                    - actions[0]: theta (pitch) in degrees.
                    - actions[1]: phi (roll) in degrees.
                    - actions[2]: psi_velocity (yaw rate) in degrees per second.
                    - actions[3]: fk (Thrust) in newtons.
                - reset_commanded (bool): True if a reset was requested.
                - exit_requested (bool): True if an exit was requested.
        """
        self._handle_events()
        actions = np.array([self.theta, self.phi, self.psi_velocity, self.fk])
        return actions, self.reset_commanded, not self.active

    def quit(self) -> None:
        """
        Cleans up and shuts down the HMI system.
        """
        for ctrl in self.controllers.values():
            ctrl.quit()
        self.controllers.clear()
        
        controller.quit()
        pygame.quit()