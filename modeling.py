import sys
from random import randint

import simpy
from matplotlib import pyplot as plt

# system characteristics
CAPACITY = 10
NUM_ELEVATORS = 6
NUM_FLOORS = 8
NUM_PEOPLE = 500
SPEED = 1  # floors per tick

# timeouts
DECISION_MAKING_TIME_MAX = 10
OPEN_CLOSE_TIMEOUT = 3
COME_IN_TIMEOUT = 2
WAIT_TIMEOUT = 5


class Elevator:
    def __init__(self, id):
        self.id = id
        self.cur_floor = 0
        self.target_floor = -1
        self.state = 'vacant'
        self.people = []
        self.sleep_process = env.process(self.sleep())
        self.on_the_go_stops = [0 for i in range(NUM_FLOORS)]  # where the elevator needs to stop to pick up passengers

    def is_full(self):
        return len(self.people) >= CAPACITY

    def is_moving_up(self):
        return self.target_floor > self.cur_floor

    def is_moving_down(self):
        return self.target_floor < self.cur_floor

    def start_movement(self):
        while self.cur_floor != self.target_floor:
            yield env.timeout(SPEED)
            cur_floor_old = self.cur_floor
            if self.is_moving_up():
                self.cur_floor = min(self.cur_floor + SPEED, self.target_floor)
            elif self.is_moving_down():
                self.cur_floor = max(self.cur_floor - SPEED, self.target_floor)
            else:
                raise "err"
            # stop to enter companions
            if int(cur_floor_old) != int(self.cur_floor) and self.on_the_go_stops[int(self.cur_floor)]:
                # enter passengers to the elevator
                yield env.timeout(OPEN_CLOSE_TIMEOUT * 2 + self.on_the_go_stops[int(self.cur_floor)] * COME_IN_TIMEOUT)
                for passenger in self.people:
                    if passenger.cur_floor == int(self.cur_floor):
                        passenger.stop_waiting()
                self.on_the_go_stops[int(self.cur_floor)] = 0

        # we've arrived
        yield env.timeout(OPEN_CLOSE_TIMEOUT)
        # Come out
        for passenger in people:
            yield env.timeout(COME_IN_TIMEOUT)
            passenger.release()
        yield env.timeout(OPEN_CLOSE_TIMEOUT)

        self.people.clear()
        self.state = "vacant"
        self.cur_floor = self.target_floor  # floor may not be int...
        self.target_floor = -1
        print("Elevator {} is free. Debug: self.on_the_go_stops".format(self.id), file=sys.stderr)
        self.sleep_process = env.process(self.sleep())

    # adding person to SCHEDULE
    def add_person(self, person):
        self.people.append(person)

        # person.t0 = env.now
        # person.elevator_waiting = env.now - person.t0

    def sleep(self):
        while True:
            yield env.timeout(1)


class Person:
    def __init__(self, id):
        self.id = id
        self.cur_floor = randint(0, NUM_FLOORS - 1)
        self.target_floor = -1
        self.process = env.process(self.process())

    def decide(self):
        while self.target_floor == self.cur_floor or self.target_floor < 0:
            self.target_floor = randint(0, NUM_FLOORS - 1)
        yield env.timeout(randint(0, DECISION_MAKING_TIME_MAX))

    def process(self):
        # TODO: while True:
        yield from self.decide()
        # print(person.id + ' decided to go from %d to  %d' % (person.cur_floor, person.target_floor))

        # since this moment control flow lefts person.
        yield from system.call_elevator(self)
        print("passenger ", str(self.id), " arrived. Next iter...")


class ElevatorSystem:
    def __init__(self):
        self.elevators = [Elevator(i + 1) for i in range(NUM_ELEVATORS)]

    def choose_elevator(self, person_cur_floor, target_floor):
        vacants = []
        for elevator in self.elevators:
            if elevator.is_full():
                continue
            if elevator.state == "on-the-go" and \
                            elevator.target_floor == target_floor and \
                    ((elevator.cur_floor < elevator.target_floor and elevator.cur_floor <= person_cur_floor) or \
                    (elevator.cur_floor > elevator.target_floor and elevator.cur_floor >= person_cur_floor)):
                return elevator
            else:
                vacants.append(elevator)
        if len(vacants) == 0:
            return None
        else:
            min_val = NUM_FLOORS + 1
            elevator = None
            for vacant in vacants:
                if abs(vacant.cur_floor - person_cur_floor) < min_val:
                    min_val = abs(vacant.cur_floor - person_cur_floor)
                    elevator = vacant
            elevator.sleep_process.interrupt()
            return elevator

    def call_elevator(self, person):
        elevator = None
        while True:
            elevator = self.choose_elevator(person.cur_floor, person.target_floor)
            if elevator is not None:
                break
            # print('Elevators are not available at %d. Please wait' % env.now)
            yield env.timeout(WAIT_TIMEOUT)
        elevator.add_person(person)
        if elevator.state == "vacant":
            elevator.state = "on-the-go"
            elevator.target_floor = person.target_floor  # FIXME: cur, not target!
            elevator.on_the_go_stops[person.cur_floor] += 1
            elevator.start_movement()


env = simpy.Environment()

# generate elevators
system = ElevatorSystem()

# generate persons
people = [Person(i) for i in range(NUM_PEOPLE)]

# start simulation
env.run(until=1200)





