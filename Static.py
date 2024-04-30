from gurobipy import Model, GRB


class ACP:
    def __init__(self, model_name, T, l, flight_schedule):
        self.model = Model(model_name)
        self.T = T  # Total time window [hrs]
        self.l = l  # Length of the considered time interval [hrs]
        self.N = int(self.T // self.l)  # Number of intervals
        self.flight_schedule = flight_schedule  # Dictionary of flight index as key and interval index as departure time in timewindow T
        self.J = len(flight_schedule)  # Total number of flights in T
        self.d = self.create_passenger_flow()

        self.initialize_data()
        self.setup_decision_variables()
        self.add_constraints()
        self.set_objective()

    def create_passenger_flow(self):
        d = {}
        for j, departure_time in self.flight_schedule.items():
            # Passengers start checking in up to 4 intervals before the flight and stop checking in after departure.
            start_time = max(departure_time - 4, 0)  # No earlier than the start of the day
            for t in range(self.N):
                if start_time <= t < departure_time:
                    # Assuming a linear decrease in the number of arriving passengers as the time approaches departure
                    passengers = max(0, (departure_time - t) * 10)  # 10 passengers per interval before the flight, decreasing
                else:
                    passengers = 0
                d[(j, t)] = passengers
        return d

    def initialize_data(self):
        # Costs and demands
        self.p = {j: 2 for j in range(self.J)}  # Service time per passenger for a specific aircraft
        self.d = self.d
        self.C = {t: 15 for t in range(self.N)}  # Desks available per interval
        self.I0 = {j: 30 for j in range(self.J)}  # Number of passengers waiting before desk opening per flight
        self.s = {j: 100 + 10 * j for j in range(self.J)}  # Desk opening costs for flight j
        self.h = {j: 5 + j for j in range(self.J)}  # Queue costs

        # Tj calculation
        early_limit = 4 / self.l  # passengers can not check-in before 4 hours in advance of departure
        late_limit = 0.75 / self.l  # passengers can not check-in after 45 minutes before departure
        Tj = dict()
        for j, t in flight_schedule.items():
            earliest_checkin_index = int(t - early_limit)
            latest_checkin_index = int(t - late_limit)
            non_checkin_intervals = set(range(earliest_checkin_index)) | set(range(latest_checkin_index + 1, self.N))
            Tj[j] = non_checkin_intervals
        self.Tj = Tj # For each flight j the set of time intervals in which it is not possible to check in

    def setup_decision_variables(self):
        # Decision variables
        self.q = self.model.addVars(self.J, self.N, vtype=GRB.INTEGER, name="q")
        self.x = self.model.addVars(self.J, self.N, vtype=GRB.BINARY, name="x")
        self.I = self.model.addVars(self.J, self.N, vtype=GRB.INTEGER, name="I")

    def add_constraints(self):
        # Initial conditions
        self.model.addConstrs((self.I[j, 0] == self.I0[j] for j in range(self.J)), "InitialQueue")

        # Queue dynamics
        self.model.addConstrs((self.I[j, t] == (self.I[j, t - 1] + self.d[j, t] - self.q[j, t])
                               for j in range(self.J) for t in range(1, self.N)), "QueueDynamics")

        # Check-in limits
        self.model.addConstrs((self.q[j, t] * self.p[j] <= self.C[t]
                               for j in range(self.J) for t in range(self.N)), "CheckInLimit")

        # Capacity limits
        self.model.addConstrs((sum(self.q[j, t] * self.p[j] for j in range(self.J)) <= self.C[t]
                               for t in range(self.N)), "CapacityLimit")

        #No passengers can ENTER queue when they are outside the check-in limits
        self.model.addConstrs((self.q[j, t] == 0
                               for j in range(self.J) for t in self.Tj), "CheckIn-Times")

    def set_objective(self):
        # Objective function
        self.model.setObjective(sum(self.h[j] * self.I[j, t] + self.s[j] * self.x[j, t]
                                    for j in range(self.J) for t in range(self.N)), GRB.MINIMIZE)

    def optimize(self):
        # Optimize the model
        self.model.setParam('OutputFlag', True)  # Enable detailed Gurobi output
        self.model.optimize()
        # Output results
        if self.model.status == GRB.OPTIMAL:
            for v in self.model.getVars():
                print(f"{v.VarName} = {v.x}")
            print("Optimal solution found!")
        elif self.model.status == GRB.INF_OR_UNBD:
            print("Model is infeasible or unbounded")
        elif self.model.status == GRB.INFEASIBLE:
            print("Model is infeasible")
        elif self.model.status == GRB.UNBOUNDED:
            print("Model is unbounded")
        else:
            print("Optimization ended with status ", self.model.Status)

'''
model_name options: "static_ACP", "dynamic_ACP" -> only static works for now
'''

# Example usage:
flight_schedule = {
    0: 16,   # Flight 0 departs at interval 16 (4 hours into the day)
    1: 48,   # Flight 1 departs at interval 48 (12 hours into the day)
    2: 80    # Flight 2 departs at interval 80 (20 hours into the day)
}

if __name__ == "__main__":
    acp_optimization = ACP("static_ACP", 24, 0.25, flight_schedule)
    acp_optimization.optimize()
