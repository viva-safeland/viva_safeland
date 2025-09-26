import tkinter as tk, webbrowser, os, re, subprocess, json
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk
from glob import glob

class GUI:
    def __init__(self):
        # Init configuration
        self.root = tk.Tk()
        self.root.title("ViVa SAFELAND")
        self.root.geometry("400x580")

        # Make window stay on top and resizable
        # self.root.attributes('-topmost', True)
        self.root.resizable(True, True)

        # Set the theme
        theme_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "GUI", "forest-dark.tcl")
        self.root.tk.call('source', theme_path)
        style = ttk.Style()
        style.theme_use('forest-dark')

        # Configure fonts
        self.FONT = ("Arial", 10)
        self.FONT_BOLD = ("Arial", 11, 'bold')
        self._configure_fonts(style)

        # GUI variables
        self.dir_var = tk.StringVar()
        self.video_var = tk.StringVar()
        self.fps_var = tk.IntVar(value=30)
        self.fixed_var = tk.BooleanVar(value=False)
        self.altitude_var = tk.DoubleVar(value=50.0)
        self.use_auto_altitude = tk.BooleanVar(value=True)
        self.show_fps_var = tk.BooleanVar(value=False)
        self.selected_video = None
        self.current_process = None  # Track running process
        self.ui_widgets = []  # Track widgets to enable/disable
        
        # Configuration file path - in the project directory
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_file = os.path.join(project_dir, "last_video_dir.json")
        
        # Load saved configuration
        self._load_config()

        self._setup_ui()
        
        # Handle window closing
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _configure_fonts(self, style):
        """Configure fonts for cross-platform compatibility."""
        style.configure('TLabel', font=self.FONT)
        style.configure('TButton', font=self.FONT)
        style.configure('TEntry', font=self.FONT)
        style.configure('TCheckbutton', font=self.FONT)
        style.configure('TRadiobutton', font=self.FONT)
        style.configure('TScale', font=self.FONT)
        style.configure('TSpinbox', font=self.FONT)
        style.configure('TCombobox', font=self.FONT)
        style.configure('TLabelframe.Label', font=self.FONT_BOLD)

    def _load_config(self):
        """Load configuration from file."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    
                # Load video directory if it exists
                if 'video_directory' in config and os.path.exists(config['video_directory']):
                    self.dir_var.set(config['video_directory'])
                    
                # print(f"Configuration loaded from {self.config_file}")
        except Exception as e:
            print(f"Error loading configuration: {e}")

    def _save_config(self):
        """Save configuration to file."""
        try:
            config = {
                'video_directory': self.dir_var.get()
            }
            
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
                
            # print(f"Configuration saved to {self.config_file}")
        except Exception as e:
            print(f"Error saving configuration: {e}")


    def _setup_ui(self):
        """Setup the user interface."""
        self._setup_header_menu()

        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._setup_logo(main_frame)
        self._setup_video_config(main_frame)
        self._setup_environment_controls(main_frame)
        self._setup_start_simulation(main_frame)

    # --- Header menu setup ---
    def _setup_header_menu(self):
        """Setup the header menu."""
        menubar = tk.Menu(
            self.root,
            bg='#5e9b18',
            fg='white',
            activebackground='#4a7c14',
            activeforeground='white',
            font=self.FONT
        )
        self.root.config(menu=menubar)

        # Create Help menu
        help_menu = tk.Menu(
            menubar, 
            tearoff=0,
            bg='#5e9b18',
            fg='white',
            activebackground='#4a7c14',
            activeforeground='white',
            font=self.FONT
        )
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Documentation", command=self._open_documentation)

    def _open_documentation(self):
        """Open the documentation website."""
        try:
            webbrowser.open("https://viva-safeland.github.io/viva_safeland/")
        except Exception as e:
            print(f"Error opening documentation: {e}")
            messagebox.showerror("Error", "Could not open documentation in browser")

    # --- Logo setup ---
    def _setup_logo(self, parent):
        """Setup the ViVa SAFELAND logo, resized to fit."""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(script_dir, "..", "docs", "assets", "viva_logo.png")
        image = Image.open(os.path.normpath(logo_path))
        image.thumbnail((400, 100), Image.Resampling.LANCZOS)
        self.logo = ImageTk.PhotoImage(image)
        logo_label = ttk.Label(parent, image=self.logo)
        logo_label.pack(pady=0)

    # --- Video configuration setup ---
    def _setup_video_config(self, parent):
        """Setup the video config."""
        dir_video_frame = ttk.LabelFrame(parent, text="Video Drone Configuration", padding=10)
        dir_video_frame.pack(fill=tk.X, pady=10)

        # Setup dir
        dir_frame = ttk.Frame(dir_video_frame)
        dir_frame.pack(fill=tk.X, pady=5)
        ttk.Label(dir_frame, text="Video Directory:", font=self.FONT).pack(anchor="w", padx=5, pady=5)

        self.dir_entry = ttk.Entry(dir_frame, textvariable=self.dir_var, state="readonly", font=self.FONT)
        self.dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)

        self.browse_btn = ttk.Button(dir_frame, text="Browse", style="Accent.TButton", command=self._browse_path)
        self.browse_btn.pack(side=tk.RIGHT, padx=5)

        # Setup video
        video_frame = ttk.Frame(dir_video_frame)
        video_frame.pack(fill=tk.X, pady=5)

        ttk.Label(video_frame, text="Video File:", font=self.FONT).pack(anchor="w", padx=5, pady=5)
        self.video_combo = ttk.Combobox(video_frame, textvariable=self.video_var, state="readonly", font=self.FONT)
        self.video_combo.pack(fill=tk.X, padx=5, pady=5)
        self.video_combo.bind("<<ComboboxSelected>>", self._on_video_selected)
        
        # Add widgets to the list for enable/disable control
        self.ui_widgets.extend([self.browse_btn, self.video_combo])
        
        # Load videos from saved directory if available
        if self.dir_var.get():
            self.load_mp4_videos()

    def _browse_path(self):
        """Browse for a video file and set the directory."""
        filepath = filedialog.askopenfilename(
            title="Select a video file",
            initialdir=self.dir_var.get(),
            filetypes=(("MP4 files", "*.mp4 *.MP4"),)
        )
        if filepath:
            directory = os.path.dirname(filepath)
            filename = os.path.basename(filepath)
            
            self.dir_var.set(directory)
            self.load_mp4_videos()
            
            self.video_var.set(filename)
            self._on_video_selected()
            
            self._save_config()

    def load_mp4_videos(self):
        """Load MP4 videos from selected directory."""
        directory = self.dir_var.get()
        if not directory:
            return

        video_extensions = ['*.mp4', '*.MP4']
        video_files = []
        
        for ext in video_extensions:
            video_files.extend(glob(os.path.join(directory, ext)))
        
        # Remove duplicates that might arise from case-insensitivity of filesystem
        video_files = list(set(video_files))
        
        video_files.sort(key=lambda x: [int(text) if text.isdigit() else text.lower() 
                                    for text in re.split('([0-9]+)', os.path.basename(x))])
        
        video_names = [os.path.basename(f) for f in video_files]
        self.video_combo['values'] = video_names

    def _on_video_selected(self, event=None):
        """Handle video selection."""
        selected_video = self.video_var.get()
        if not selected_video:
            return
            
        directory = self.dir_var.get()
        self.selected_video = os.path.join(directory, selected_video)

    # --- Environment Controls
    def _setup_environment_controls(self, parent):
        """Setup environment configuration controls"""
        env_frame = ttk.LabelFrame(parent, text="Environment Configuration", padding=10)
        env_frame.pack(fill=tk.X, pady=10)

        # FPS configuration
        fps_frame = ttk.Frame(env_frame)
        fps_frame.pack(fill=tk.X, pady=5)
        ttk.Label(fps_frame, text="FPS:", font=self.FONT).pack(side=tk.LEFT, padx=5)
        self.fps_spinbox = ttk.Spinbox(fps_frame, from_=1, to=120, increment=1, textvariable=self.fps_var, font=self.FONT, width=10)
        self.fps_spinbox.pack(side=tk.LEFT, padx=5, pady=5)
        self.fixed_check = ttk.Checkbutton(fps_frame, text="Fixed", variable=self.fixed_var, style="Accent.TCheckbutton")
        self.fixed_check.pack(side=tk.RIGHT, padx=5, pady=5)
        self.show_fps_check = ttk.Checkbutton(fps_frame, text="Show FPS", variable=self.show_fps_var, style="Accent.TCheckbutton")
        self.show_fps_check.pack(side=tk.RIGHT, padx=5, pady=5)

        # Altitude configuration
        altitude_frame = ttk.Frame(env_frame)
        altitude_frame.pack(fill=tk.X, pady=5)
        self.auto_altitude_check = ttk.Checkbutton(altitude_frame, text="Use Auto Altitude", variable=self.use_auto_altitude, style="Accent.TCheckbutton", command=self._toggle_altitude_mode)
        self.auto_altitude_check.pack(side=tk.LEFT, padx=5, pady=5)
        self.altitude_fixed_frame = ttk.Frame(altitude_frame)
        self.altitude_fixed_frame.pack(side=tk.RIGHT)
        ttk.Label(self.altitude_fixed_frame, text="Altitude (m):", font=self.FONT).pack(side=tk.LEFT, padx=5)
        self.altitude_spinbox = ttk.Spinbox(self.altitude_fixed_frame, from_=0, to=200, increment=5, textvariable=self.altitude_var, font=self.FONT)
        self.altitude_spinbox.pack(side=tk.LEFT, padx=5, pady=5)
        self._toggle_altitude_mode()

        # Add widgets to the list for enable/disable control
        self.ui_widgets.extend([self.fps_spinbox, self.show_fps_check, self.auto_altitude_check, self.altitude_spinbox, self.fixed_check])

    def _toggle_altitude_mode(self):
        """Toggle between auto and fixed altitude modes."""
        if self.use_auto_altitude.get():
            for widget in self.altitude_fixed_frame.winfo_children():
                widget.configure(state="disabled")
        else:
            for widget in self.altitude_fixed_frame.winfo_children():
                widget.configure(state="normal")

    def _enable_ui(self):
        """Enable all UI controls."""
        for widget in self.ui_widgets:
            try:
                widget.configure(state="normal")
            except:
                pass  # Some widgets might not support state changes
        
        # Special handling for start/stop buttons
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        
        # Re-apply altitude mode logic
        self._toggle_altitude_mode()

    def _disable_ui(self):
        """Disable all UI controls except stop button."""
        for widget in self.ui_widgets:
            try:
                widget.configure(state="disabled")
            except:
                pass  # Some widgets might not support state changes
        
        # Special handling for start/stop buttons
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")

    # --- Start Simulation ---
    def _setup_start_simulation(self, parent):
        """ Setup start simulation"""
        # Create a frame for the buttons
        button_frame = ttk.Frame(parent)
        button_frame.pack(pady=20)
        
        # Start button
        self.start_btn = ttk.Button(button_frame, text="Start Simulation", style="Accent.TButton", command=self._start_simulation)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        # Stop button
        self.stop_btn = ttk.Button(button_frame, text="Stop Simulation", style="Accent.TButton", command=self._stop_simulation, state="disabled")
        self.stop_btn.pack(side=tk.LEFT, padx=5)

    def _start_simulation(self):
        """Start the simulation."""
        if not self.selected_video:
            messagebox.showwarning("No Video Selected", "Please select a video before starting the simulation.")
            return
            
        # Check if a process is already running
        if self.current_process and self.current_process.poll() is None:
            messagebox.showwarning("Simulation Running", "A simulation is already running. Stop it first.")
            return
            
        try:
            cmd = ["uv", "run", "viva", self.selected_video, "--render-fps", str(self.fps_var.get())]
            if not self.use_auto_altitude.get():
                cmd.extend(["--rel-alt-value", str(self.altitude_var.get())])
            if self.show_fps_var.get():
                cmd.append("--show-fps-flag")
            if self.fixed_var.get():
                cmd.append("--fixed")

            print(" ".join(cmd))

            self.current_process = subprocess.Popen(cmd)
            
            self._disable_ui()
            
            # Check process status periodically
            self.root.after(1000, self._check_process_status)
            

        except Exception as e:
            messagebox.showerror("Error", f"Failed to start simulation: {e}")
            # Reset UI state on error
            self._enable_ui()
            return

    def _stop_simulation(self):
        """Stop the running simulation."""
        if self.current_process and self.current_process.poll() is None:
            try:
                self.current_process.terminate()
                try:
                    self.current_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # If it doesn't terminate gracefully, force kill it
                    self.current_process.kill()
                    self.current_process.wait()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to stop simulation: {e}")
        
        # Re-enable all UI controls
        self._enable_ui()
        self.current_process = None

    def _check_process_status(self):
        """Check if the simulation process is still running."""
        if self.current_process:
            if self.current_process.poll() is not None:
                # Process has finished - re-enable all UI controls
                self._enable_ui()
                
                # Get the return code for debugging
                return_code = self.current_process.returncode
                if return_code != 0:
                    print(f"Simulation ended with return code: {return_code}")
                
                self.current_process = None
            else:
                # Process is still running, check again later
                self.root.after(1000, self._check_process_status)

    def _on_closing(self):
        """Handle window closing event."""
        # Save configuration before closing
        self._save_config()
        
        # Stop any running simulation before closing
        if self.current_process and self.current_process.poll() is None:
            if messagebox.askokcancel("Quit", "A simulation is running. Do you want to stop it and exit?"):
                self._stop_simulation()
                self.root.destroy()
        else:
            self.root.destroy()

if __name__ == "__main__":
    gui = GUI()
    gui.root.mainloop()