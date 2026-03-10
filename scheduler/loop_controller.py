class LoopController:
    def __init__(self, enable_loop=False, max_rounds=1,
                 enable_region_switch=False):
        self.enable_loop = enable_loop
        self.max_rounds = max_rounds
        self.enable_region_switch = enable_region_switch
        self.current_round = 0

    @property
    def should_continue(self):
        if not self.enable_loop:
            return self.current_round == 0
        return self.current_round < self.max_rounds

    def next_round(self):
        self.current_round += 1