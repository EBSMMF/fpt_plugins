from ctypes import *
from random import random
from FFxivPythonTrigger import *
from FFxivPythonTrigger.memory.StructFactory import OffsetStruct, EnumStruct

command = "@CTT"

recv_opcode = 403  # cn5.55

# recv_opcode = 0x335  # cn5.5
# send_opcode = 0x105  # cn5.5

# recv_opcode = 0x360  # cn5.45
# send_opcode = 0x39d  # cn5.45
#
# send_event_start_opcode = 0x3c3  # cn5.45
# send_event_finish_opcode = 0x20B  # cn5.45

# recv_opcode = 789  # cn5.41
# send_opcode = 843  # cn5.41

SendEventStartPack = OffsetStruct({
    'target_id': c_uint,
    'unk0': c_uint,  # 0 or any
    'event_id': c_ushort,  # 6
    'category': c_ushort,  # 36
    'unk3': c_uint,  # 0 or any
}, 16)
SendEventFinishPack = OffsetStruct({
    'event_id': c_ushort,  # 6
    'category': c_ushort,  # 36
    'unk2': c_uint,  # fix 14
    'unk3': c_uint,  # 0 or any
    'unk4': c_uint,  # 0 or any
}, 16)
recv_packet = OffsetStruct({
    'cut_result': (EnumStruct(c_ubyte, {
        0x0: "Fail",
        0x1: "Normal",
        0x2: "Great",
        0x3: "Perfect"
    }), 12),
    'progress_result': (c_ubyte, 16),
    'round': (c_ubyte, 28),
    'current_profit': (c_ushort, 36),
    'future_profit': (c_ushort, 40),
})
send_packet = OffsetStruct({
    'event_id': c_ushort,  # 6
    'category': c_ushort,  # 36
    'unk0': c_ushort,  # 14
    'game_state': EnumStruct(c_ubyte, {
        0x07: "Start Game",
        0x09: "Difficulty choice",
        0x0A: "Felling",
        0x0B: "Start Next Round"
    }),
    'unk1': c_ubyte,  # 0 when next else 1
    'param': c_ubyte,
    'unk2': c_ubyte,  # 0
    'unk3': c_ushort,  # 0
    'unk4': c_uint,  # 0 when start or next else 522
}, 16)

MAX = 101

send_start_msg = send_packet(event_id=6, category=36, unk0=14, unk1=1)
send_start_msg.game_state.set("Start Game")
send_difficulty_msg = send_packet(event_id=6, category=36, unk0=14, unk1=1, unk4=522, param=2)
send_difficulty_msg.game_state.set("Difficulty choice")
send_next_round_msg = send_packet(event_id=6, category=36, unk0=14)
send_next_round_msg.game_state.set("Start Next Round")
send_fell_msg = send_packet(event_id=6, category=36, unk0=14, unk1=1, unk4=522)
send_fell_msg.game_state.set("Felling")
start_msg = SendEventStartPack(event_id=6, category=36)
finish_msg = SendEventFinishPack(event_id=6, category=36, unk2=14)


class Solver(object):
    def __init__(self):
        self.pool = self.history = list()
        self.prev = self.step = self.progress = self.count = 0
        self.reset()

    def reset(self):
        self.pool = list(range(MAX))
        self.prev = None
        self.history = list()
        self.step = 10
        self.progress = 10
        self.count = 0

    def score(self, score, progress):
        if not score: return
        self.progress = progress
        self.history.append((self.prev, score))
        if score == "Fail":
            self.pool = [i for i in self.pool if abs(i - self.prev) >= 20]
        elif score == "Normal":
            self.pool = [i for i in self.pool if 10 <= abs(i - self.prev) <= 20]
            self.step = min(self.step, 5)
        elif score == "Great":
            self.pool = [i for i in self.pool if 0 < abs(i - self.prev) <= 10]
            self.step = min(self.step, 3)
        elif score == "Perfect":
            self.pool = [self.prev]

    def solve(self):
        self.count += 1
        if self.count >= 9:
            return
        if self.prev is None:
            ans = 80 if random() > 0.5 else 20
        elif len(self.pool) == 1:
            ans = self.pool[0]
        elif not self.pool:
            raise Exception("No ans")
        elif self.progress < 5 and [i for i in self.history if i[1] == "Great"]:
            ans = [i[0] for i in self.history if i[1] == "Great"][-1]
        else:
            p, s = (self.pool, self.pool[0]) if random() > 0.5 else (reversed(self.pool), self.pool[-1])
            ans = [i for i in p if abs(i - s) <= self.step][-1]
        self.prev = ans
        return self.prev


class CutTheTree(PluginBase):
    name = "CutTheTree"
    git_repo = 'nyouoG/fpt_plugins'
    repo_path = 'CutTheTree.py'
    hash_path = __file__

    def __init__(self):
        super().__init__()
        self.enable = False
        self.game_cnt = 0

        self.solver = Solver()

        self.register_event(f'network/recv/{recv_opcode}', self.recv_work, limit_sec=0)
        self.register_event('network/send_event_action', self.send_work, limit_sec=0)
        api.XivNetwork.register_makeup("EventAction", self.makeup_data)
        api.command.register(command, self.process_command)

    def process_command(self, args):
        if args:
            if args[0] == 'on':
                self.enable = True
            elif args[0] == 'off':
                self.enable = False
            else:
                api.Magic.echo_msg("unknown args: %s" % args[0])
        else:
            self.enable = not self.enable
        api.Magic.echo_msg("CutTheTree: [%s]" % ('enable' if self.enable else 'disable'))
        self.start_new()

    def _onunload(self):
        api.XivNetwork.unregister_makeup("EventAction", self.makeup_data)
        api.command.unregister(command)

    def send(self, msg):
        api.XivNetwork.send_messages([("EventAction", bytearray(msg))])

    def start_new(self, evt=None):
        if self.enable:
            target = find_nearest_tree()
            if target is not None:
                self.game_cnt += 1
                self.logger.debug(f"start game #{self.game_cnt}")
                start_msg.target_id = target.id
                api.XivNetwork.send_messages([("EventStart", bytearray(start_msg))])
                self.send(send_start_msg)
                self.send(send_difficulty_msg)

    def send_fell(self):
        send_fell_msg.param = self.solver.solve()
        self.send(send_fell_msg)

    def recv_work(self, event):
        data = recv_packet.from_buffer(event.raw_msg)
        res = data.cut_result.value()
        # self.logger.debug(f"Felling >> {res} ({10 - data.progress_result}/10)")
        self.solver.score(res, data.progress_result)
        if self.enable:
            if data.progress_result:
                self.send_fell()
            elif data.future_profit:
                self.send(send_next_round_msg)
            else:
                self.logger.debug(f"finish game #{self.game_cnt}")
                sleep(3)
                api.XivNetwork.send_messages([("EventFinish", bytearray(finish_msg))])
                self.start_new()

    def send_work(self, event):
        data = send_packet.from_buffer(bytearray(event.raw_msg))
        msg = data.game_state.value()
        if msg == "Felling" or msg == "Difficulty choice":
            msg = f"{msg} << {data.param}"
        # self.logger.debug(msg)
        key = data.game_state.value()
        if key == "Difficulty choice" or key == "Start Next Round":
            self.last_start = perf_counter()
            self.solver.reset()
        if key == "Start Next Round" and self.enable:
            self.send_fell()

    def makeup_data(self, header, raw):
        data = send_packet.from_buffer(raw)
        key = data.game_state.value()
        if key == "Difficulty choice":
            data.param = 2
        elif key == "Felling":
            ans = self.solver.solve()
            # self.logger(self.solver.pool)
            if ans is not None:
                data.param = ans
        return header, bytearray(data)


NPC_Name = "孤树无援"


def find_nearest_tree():
    nearest = None
    nearest_dis = 9999
    me = api.XivMemory.actor_table.get_me()
    for a1 in api.XivMemory.actor_table.get_actors_by_name(NPC_Name):
        dis1 = me.absolute_distance_xy(a1)
        if dis1 < nearest_dis:
            nearest = a1
            nearest_dis = dis1
    return nearest
