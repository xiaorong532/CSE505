import clingo
import time

class Board:
    def __init__(self):
        self.size           = 1
        self.blocked        = set()
        self.barriers       = set()
        self.targets        = set()
        self.pos            = dict()
        self.robots         = [{}]
        self.moves          = []
        self.current_target = None
        self.solution       = None

        ctl = clingo.Control()
        ctl.load("board.lp")
        ctl.ground([("base", [])])
        ctl.solve(on_model=self.__on_model)

    def __on_model(self, m):
        for atom in m.symbols(atoms=True):
            if atom.name == "barrier" and len(atom.arguments) == 4:
                x, y, dx, dy = [n.number for n in atom.arguments]
                self.blocked.add((x - 1     , y - 1     ,  dx,  dy))
                self.blocked.add((x - 1 + dx, y - 1     , -dx,  dy))
                self.blocked.add((x - 1     , y - 1 + dy,  dx, -dy))
                self.blocked.add((x - 1 + dx, y - 1 + dy, -dx, -dy))
                if dy == 0:
                    self.barriers.add(('west', x if dx == 1 else x - 1, y - 1))
                else:
                    self.barriers.add(('north', x - 1, y if dy == 1 else y - 1))
            elif atom.name == "dim" and len(atom.arguments) == 1:
                self.size = max(self.size, atom.arguments[0].number)
            elif atom.name == "available_target" and len(atom.arguments) == 4:
                c, s, x, y = [(n.number if n.type == clingo.SymbolType.Number else str(n)) for n in atom.arguments]
                self.targets.add((c, s, x - 1, y - 1))
            elif atom.name == "initial_pos" and len(atom.arguments) == 3:
                c, x, y = [(n.number if n.type == clingo.SymbolType.Number else str(n)) for n in atom.arguments]
                self.pos[c] = (x - 1, y - 1)
        for d in range(0, self.size):
            self.blocked.add((d            ,             0,  0, -1))
            self.blocked.add((d            , self.size - 1,  0,  1))
            self.blocked.add((0            ,             d, -1,  0))
            self.blocked.add((self.size - 1,             d,  1,  0))

    def move(self, robot, dx, dy):
        x, y = self.pos[robot]
        while (not (x, y, dx, dy) in self.blocked and
                not (x + dx, y + dy) in self.pos.values()):
            x += dx
            y += dy
        self.pos[robot] = (x, y)
        if (self.solution is not None and
                len(self.solution) > 0 and
                self.solution[0][0] == robot and
                self.solution[0][1] == dx and
                self.solution[0][2] == dy):
            self.solution.pop(0)
            if len(self.solution) == 0:
                self.solution = None
        else:
            self.solution = None

    def won(self):
        r, _, x, y = self.current_target
        return self.pos[r] == (x, y)

class Solver:
    def __init__(self, horizon=0):
        self.__horizon = horizon
        self.__prg = clingo.Control(['-t4'])
        self.__future = None
        self.__solution = None
        self.__assign = []

        self.__prg.load("board.lp")
        self.__prg.load("ricochet.lp")
        parts = [ ("base", [])
                , ("check", [0])
                , ("state", [0])
                ]
        for t in range(1, self.__horizon+1):
            parts.extend([ ("trans", [t])
                         , ("check", [t])
                         , ("state", [t])
                         ])
        self.__prg.ground(parts)
        self.__prg.assign_external(clingo.Function("horizon", [self.__horizon]), True)

    def __next(self):
        assert(self.__horizon < 30)
        self.__prg.assign_external(clingo.Function("horizon", [self.__horizon]), False)
        self.__horizon += 1
        self.__prg.ground([ ("trans", [self.__horizon])
                          , ("check", [self.__horizon])
                          , ("state", [self.__horizon])
                          ])
        self.__prg.assign_external(clingo.Function("horizon", [self.__horizon]), True)

    def start(self, board):
        self.__assign = []
        for robot, (x, y) in board.pos.items():
            # print x,y
            self.__assign.append(clingo.Function("pos", [clingo.Function(robot), x+1, y+1, 0]))
        print board.current_target[0]
        self.__assign.append(clingo.Function("target",
            [ clingo.Function(board.current_target[0])
            , board.current_target[2] + 1
            , board.current_target[3] + 1
            ]))
        for x in self.__assign:
            self.__prg.assign_external(x, True)
        self.__solution = None
        self.__future = self.__prg.solve(on_model=self.__on_model, async=True)

    def busy(self):
        if self.__future is None:
            return False
        if self.__future.wait(0):
            if self.__solution is None:
                self.__next()
                self.__future = self.__prg.solve(on_model=self.__on_model, async=True)
                return True
            else:
                self.__future = None
                return False
        return True

    def stop(self):
        if self.__future is not None:
            self.__future.cancel()
            self.__future.wait()
            self.__future = None
            self.get()

    def get(self):
        solution = self.__solution
        self.__solution = None
        for x in self.__assign:
            self.__prg.assign_external(x, False)
        self.__assign = []
        return solution

    def __on_model(self, m):
        self.__solution = []
        for atom in m.symbols(atoms=True):
            # print atom
            if atom.name == "move" and len(atom.arguments) == 4:
                c, x, y, t = [(n.number if n.type == clingo.SymbolType.Number else str(n)) for n in atom.arguments]
                self.__solution.append((c, x, y, t))
        self.__solution.sort(key=lambda x: x[3])
        p = None
        i = 0
        for x in self.__solution:
            if p is not None and \
               p[0] == x[0]  and \
               p[1] == x[1]  and \
               p[2] == x[2]:
                break
            p = x
            i += 1
        del self.__solution[i:]

board  = Board()
board.current_target = ("yellow", '',14,12)
solver = Solver(horizon = 10)
solver.start(board)
while solver.busy():
    time.sleep(5)
solution = solver.get()
print solution