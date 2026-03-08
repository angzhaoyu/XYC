"""import tkinter as tk
from gui import FishingVillageGUI

if __name__ == "__main__":
    root = tk.Tk()
    app = FishingVillageGUI(root)
    root.mainloop()"""

from tasks.transport.transport  import TransportTask
from tasks.get_states import StateManager


if __name__ == "__main__":
    mgr = StateManager("tasks/states/states.txt", app_name="幸福小渔村")
    mgr.get_states()
    #transport_task = TransportTask(app_name="幸福小渔村")
    #transport_task.run()


