# -*- coding: utf-8 -*-
"""Headless smoke test: build the tuner window, pump the event loop, destroy.

Catches Tk / PIL / ImageTk mistakes without a human sitting in front of it.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import tkinter as tk
import fpv_tuner


def fake_mainloop(self):
    end = time.time() + 1.5
    while time.time() < end:
        try:
            self.update_idletasks()
            self.update()
        except tk.TclError:
            break
        time.sleep(0.02)
    try:
        self.destroy()
    except tk.TclError:
        pass


tk.Tk.mainloop = fake_mainloop
fpv_tuner.gui(fpv_tuner.find_geo())
print('gui smoke ok')
