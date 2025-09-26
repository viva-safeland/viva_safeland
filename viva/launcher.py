import sys

def main():
    """Main launcher that decides between GUI and CLI based on arguments."""
    
    # If no arguments are provided, launch the GUI
    if len(sys.argv) == 1:
        try:
            from viva.gui import GUI
            gui = GUI()
            gui.root.mainloop()
        except ImportError as e:
            print(f"Error importing GUI: {e}")
            print("Please install GUI dependencies (tkinter, PIL)")
            sys.exit(1)
        except Exception as e:
            print(f"Error launching GUI: {e}")
            sys.exit(1)
    else:
        # Arguments provided, use the original CLI interface
        from viva.main import app
        app()

if __name__ == "__main__":
    main()
