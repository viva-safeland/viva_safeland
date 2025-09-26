from typing import List, Tuple

import pygame
from pygame.locals import (
    JOYAXISMOTION,
    JOYBUTTONDOWN,
    JOYDEVICEADDED,
    JOYDEVICEREMOVED,
    K_DOWN,
    K_ESCAPE,
    K_LEFT,
    K_RIGHT,
    K_UP,
    KEYDOWN,
    KEYUP,
    K_a,
    K_d,
    K_r,
    K_s,
    K_w,
)


class HMI:
    """Human-Machine Interface for controlling the drone environment.

    This class handles joystick and keyboard inputs to generate control actions.
    It is designed to be used in a loop where it's called repeatedly.

    Attributes:
        active (bool): Flag to control the main loop. Set to False to exit.
    """

    def __init__(self):
        """Initializes the HMI, pygame, and joysticks."""
        self.active: bool = True
        self.phi: float = 0.0
        self.theta: float = 0.0
        self.psi: float = 0.0
        self.psi_velocity: float = 0.0
        self.fk: float = 0.0
        self.reset_commanded: bool = False

        pygame.init()
        pygame.joystick.init()

        # XboxOne Controller Mapping
        self.axis = {"LH": 0, "LV": 1, "RH": 3, "RV": 4, "LT": 2, "RT": 5}
        self.hats = {"HH": 0, "HV": 1}
        self.buttons = {
            "A": 0,
            "B": 1,
            "X": 2,
            "Y": 3,
            "LB": 4,
            "RB": 5,
            "BACK": 6,
            "START": 7,
            "XBOX": 8,
            "LS": 9,
            "RS": 10,
        }
        # self.joysticks: List[pygame.joystick.Joystick] = self._update_joystick_list()

    def _update_joystick_list(self) -> List[pygame.joystick.Joystick]:
        """Updates the list of connected joysticks.

        Returns:
            A list of initialized joystick objects.
        """
        joysticks = [
            pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())
        ]
        for joystick in joysticks:
            joystick.init()
            print(f"Joystick connected: {joystick.get_name()}")
        return joysticks

    def _handle_events(self) -> None:
        """Handles Pygame events for user input."""
        self.reset_commanded = False
        for event in pygame.event.get():
            if event.type == JOYDEVICEADDED or event.type == JOYDEVICEREMOVED:
                self.joysticks = self._update_joystick_list()

            if event.type == JOYBUTTONDOWN:
                if event.button == self.buttons["B"]:
                    self.active = False
                if event.button == self.buttons["BACK"]:
                    self.reset_commanded = True
                    self.psi = 0.0
            if event.type == JOYAXISMOTION:
                if event.axis == self.axis["RV"]:
                    self.phi = -event.value
                if event.axis == self.axis["RH"]:
                    self.theta = event.value
                if event.axis == self.axis["LH"]:
                    self.psi_velocity = -event.value
                if event.axis == self.axis["LV"]:
                    self.fk = -event.value

            if event.type == KEYDOWN:
                self.phi = (event.key == K_UP) - (event.key == K_DOWN)
                # self.theta = (event.key == K_LEFT) - (event.key == K_RIGHT)
                self.theta = (event.key == K_RIGHT) - (event.key == K_LEFT)
                self.psi_velocity = (event.key == K_a) - (event.key == K_d)
                self.fk = (event.key == K_w) - (event.key == K_s)
                if event.key == K_r:
                    self.reset_commanded = True
                    self.psi = 0.0
                if event.key == K_ESCAPE:
                    self.active = False
            if event.type == KEYUP:
                if event.key == K_UP or event.key == K_DOWN:
                    self.phi = 0.0
                if event.key == K_RIGHT or event.key == K_LEFT:
                    self.theta = 0.0
                if event.key == K_a or event.key == K_d:
                    self.psi_velocity = 0.0
                if event.key == K_w or event.key == K_s:
                    self.fk = 0.0

    def __call__(self) -> Tuple[List[float], bool]:
        """Handles events and returns actions and reset status.

        This makes the HMI instance callable. The loop should check `self.active`
        to continue running.

        Returns:
            A tuple containing the actions list and a boolean indicating if a
            reset was commanded.
        """
        self._handle_events()

        self.psi += self.psi_velocity
        self.psi = self.psi % 360
        # actions = [self.theta, self.phi, self.psi, self.fk]
        actions = [self.theta, self.phi, self.fk]
        return actions, self.reset_commanded, not self.active

    def quit(self):
        """Quits pygame."""
        pygame.quit()
