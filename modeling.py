import sys
from random import randint
from functools import reduce
import itertools

import simpy
import numpy as np

# system characteristics
CAPACITY = 10
NUM_ELEVATORS = 6
NUM_FLOORS = 8
NUM_PEOPLE = 500
SPEED = 0.3  # floors per tick (as sec)

# timeouts
# min correct timeout == 1
DECISION_MAKING_TIME_MAX = 100
OPEN_TIMEOUT = 3
COME_IN_TIMEOUT = 2
WAIT_TIMEOUT = 5


class ElevatorSystem:
    def __init__(self):
        self.elevators = [Elevator(i + 1) for i in range(NUM_ELEVATORS)]

    def choose_elevator(self, person_start_floor, target_floor):
        vacants = []
        for elevator in self.elevators:
            if elevator.is_full() or elevator.state == Elevator.states["go-to-the-first-person"]:
                continue
            if elevator.state == Elevator.states["on-the-go"] and \
                            elevator.target_floor == target_floor and \
                    ((elevator.is_moving_up() and elevator.cur_floor <= person_start_floor) or \
                    (elevator.is_moving_down() and elevator.cur_floor >= person_start_floor)):
                return elevator
            elif elevator.state == Elevator.states["vacant"]:
                vacants.append(elevator)
        if len(vacants) == 0:
            return None
        else:
            min_val = 2 * NUM_FLOORS
            elevator = None
            for vacant in vacants:
                if abs(vacant.cur_floor - person_start_floor) < min_val:
                    min_val = abs(vacant.cur_floor - person_start_floor)
                    elevator = vacant
            return elevator

    def call_elevator(self, person):
        elevator = None
        while True:
            elevator = self.choose_elevator(person.start_floor, person.target_floor)
            if elevator is not None:
                break
            # print('Elevators are not available at %d. Please wait' % env.now)
            yield env.timeout(WAIT_TIMEOUT)
        elevator.go_to_person(person)


class Elevator:
    states = {"vacant": 0, "go-to-the-first-person": 1, "on-the-go": 2}

    def __init__(self, id):
        self.id = id
        self.cur_floor = 0
        self.target_floor = -1
        self.state = Elevator.states["vacant"]
        self.people = []
        self.process_holder = env.process(self.process())
        self.on_the_go_stops = [0 for i in range(NUM_FLOORS)]  # where the elevator needs to stop to pick up passengers
        self.memory = []

    def is_full(self):
        return len(self.people) >= CAPACITY

    def is_moving_up(self):
        return self.target_floor > self.cur_floor

    def is_moving_down(self):
        return self.target_floor < self.cur_floor

    def move(self):
        assert self.target_floor >= 0
        yield env.timeout(SPEED)
        if self.is_moving_up():
            self.cur_floor = min(self.cur_floor + SPEED, self.target_floor)
        elif self.is_moving_down():
            self.cur_floor = max(self.cur_floor - SPEED, self.target_floor)
        else:
            raise "err"
    
    def process(self):
        while True:
            # sleep waiting for a call
            while not self.people:
                yield env.timeout(WAIT_TIMEOUT / 10)

            # start moving to the first person
            assert self.state == Elevator.states["go-to-the-first-person"]
            assert self.target_floor >= 0
            while self.cur_floor != self.target_floor:
                yield from self.move()
            self.state = Elevator.states["on-the-go"]

            # arrived to the first person
            assert len(self.people) == 1
            assert self.state == Elevator.states["on-the-go"]
            self.target_floor = self.people[0].target_floor
            cur_floor_old = -1
            # enter first person and start moving to the target floor
            while self.cur_floor != self.target_floor:
                # stop to enter passengers
                if int(cur_floor_old) != int(self.cur_floor) and self.on_the_go_stops[int(self.cur_floor)]:
                    # enter passengers to the elevator
                    yield env.timeout(
                        OPEN_TIMEOUT * 2 + self.on_the_go_stops[int(self.cur_floor)] * COME_IN_TIMEOUT)
                    for passenger in self.people:
                        if passenger.start_floor == int(self.cur_floor):
                            passenger.enter()
                    self.on_the_go_stops[int(self.cur_floor)] = 0
                cur_floor_old = self.cur_floor
                yield from self.move()

            # arrived to the target floor
            yield env.timeout(OPEN_TIMEOUT)
            # Come out
            for passenger in self.people:
                yield env.timeout(COME_IN_TIMEOUT)
                passenger.release()
            yield env.timeout(OPEN_TIMEOUT)

            self.memory.append(len(self.people))
            self.people.clear()
            self.state = Elevator.states["vacant"]
            self.target_floor = -1
            self.cur_floor = self.target_floor  # cur_floor might not be int...
            for i in range(len(self.on_the_go_stops)):
                self.on_the_go_stops[i] = 0
            # print("Elevator {} is free. self.on_the_go_stops: {}".format(self.id, self.on_the_go_stops), file=sys.stderr)
    #         Elevator 1 is free. self.on_the_go_stops: [0, 1]

    # add person to SCHEDULE
    #
    # Here we chenge internal state of the elevator object. Consequently, the loop in the elevator process will be breaked, and elevator will start moving.
    def go_to_person(self, person):
        # print("go_to_person", self.people, file=sys.stderr)
        self.people.append(person)
        if self.state == Elevator.states["vacant"]:
            self.state = Elevator.states["go-to-the-first-person"]
            self.target_floor = person.start_floor
            assert not sum(self.on_the_go_stops)
        elif self.state == Elevator.states["go-to-the-first-person"]:
            raise "err: adding passenger on the go to the first passenger is not supported"
        self.on_the_go_stops[person.start_floor] += 1
        # person.t0 = env.now
        # person.elevator_waiting = env.now - person.t0


class Person:
    def __init__(self, id):
        self.id = id
        self.start_floor = randint(0, NUM_FLOORS - 1)
        self.process_holder = env.process(self.process())

        self.target_floor = -1
        self.t0 = int()
        self.waiting_time = int()
        self.moving_time = int()

    def decide(self):
        yield env.timeout(randint(0, DECISION_MAKING_TIME_MAX))
        while self.target_floor == self.start_floor or self.target_floor < 0:
            self.target_floor = randint(0, NUM_FLOORS - 1)

    def process(self):
        yield from self.decide()
        # print(person.id + ' decided to go from %d to  %d' % (person.cur_floor, person.target_floor))

        self.t0 = env.now
        yield from system.call_elevator(self)
        # end of process

        #
        # while self.cur_floor != self.target_floor:
        #     env.timeout(1)
        # print("passenger ", str(self.id), " arrived. Next iter...")

    def release(self):
        self.start_floor = self.target_floor
        self.moving_time = env.now - self.t0

    def enter(self):
        self.waiting_time = env.now - self.t0
        self.t0 = env.now


def check(people):
    for person in people:
        assert person.start_floor == person.target_floor


def analyse(people, system):
    mean_waiting_time = np.mean([person.waiting_time for person in people])
    mean_moving_time = np.mean([person.moving_time for person in people])
    m = []
    for elevator in system.elevators:
        for elem in elevator.memory:
            m.append(elem)
    mean_people_number = np.mean(m)

    print("Mean Summarized Time:", mean_waiting_time + mean_moving_time)
    print("Mean Waiting time:", mean_waiting_time)
    print("Mean Trip Time:", mean_moving_time)
    print("Mean People Number:", mean_people_number)


env = simpy.Environment()

# generate elevators
system = ElevatorSystem()

# generate persons
people = [Person(i) for i in range(NUM_PEOPLE)]

# start simulation
env.run(until=1200)

check(people)

analyse(people, system)








