import clingo
import time

class Solver:
    def __init__(self, horizon=0):
        self.__horizon = horizon
        self.__prg = clingo.Control(['-t4'])
        self.__future = None
        self.__solution = None
        self.__assign = []
        self.__last_position = dict()

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
        # print parts
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

    def start(self, pos, target):
        self.__assign = []
        for (robot, x, y) in pos:
            self.__last_position[robot] = (x, y)
            self.__assign.append(clingo.Function("pos", [clingo.Function(robot), x, y, 0]))
        print target
        self.__assign.append(clingo.Function("target", 
            [ clingo.Function(target[0]),
            target[1],
            target[2]
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
                # c, x, y, t = [str(n) for n in atom.arguments]
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
        for n in self.__solution:
            print 'move' + str(n)

    def move(self, robot, dx, dy):
        (x, y) = self.__last_position[robot]
        x += dx
        y += dy
        self.__last_position[robot] = (x, y)

solver = Solver(horizon = 20)
initial_pos = [("red", 1, 1), ("blue",1,16), ("green",16,1), ("yellow",16,16)]
sequences = [("yellow", 15,13), ("blue", 12, 3)]
# sequences = [("yellow",15,13)]
for target in sequences:
    solver.start(initial_pos, target)
    while solver.busy():
        time.sleep(5)
    solution = solver.get()
    print solution
    # change position for next round
    for (r, dx, dy, T) in solution:
        solver.move(r, dx, dy)