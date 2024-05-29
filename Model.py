from gurobipy import Model, GRB
from data import *
import numpy as np

class ACP:
    def __init__(self, model_name, T, l, parameter_settings, flight_schedule=None, data_schiphol=None, schiphol_case=False):
        self.objective = None
        self.model_name = model_name
        self.model = Model(model_name)
        self.T = T  # Total time window [hrs]
        self.l = l  # Length of the considered time interval [hrs]
        self.N = int(self.T // self.l)  # Number of intervals
        self.schiphol_case = schiphol_case
        self.parameter_settings = parameter_settings

        if self.schiphol_case is False:
            self.flight_schedule = flight_schedule  # Dictionary of flight index as key and interval index as departure time in timewindow T
        else:
            self.flight_schedule = {i: (row['ETD_minutes'], row['MAX_PAX']) for i, row in data_schiphol.flights.iterrows()}

        self.J = len(self.flight_schedule)  # Total number of flights in T
        self.d, too_early = self.create_passenger_flow()
        self.I0 = {j: too_early[j] for j in range(self.J)}  # Number of passengers waiting before desk opening per flight
        # Tj calculation
        early_limit = 4 / self.l  # passengers can not check-in before 4 hours in advance of departure
        late_limit = 0.75 / self.l  # passengers can not check-in after 45 minutes before departure
        Tj = dict()
        for j, t in self.flight_schedule.items():
            earliest_checkin_index = int(round(t[0] / (self.l*60)) - early_limit)
            latest_checkin_index = int(round(t[0] / (self.l*60)) - late_limit)
            non_checkin_intervals = set(range(earliest_checkin_index)) | set(
                range(latest_checkin_index + 1, self.N))
            Tj[j] = non_checkin_intervals
        self.Tj = Tj  # For each flight j the set of time intervals in which it is not possible to check in

        self.initialize_data()
        self.setup_decision_variables()
        self.add_constraints()
        self.set_objective()

    def create_passenger_flow(self, t_interval=5, tot_m=24 * 60, mean_early_t=2 * 60, arrival_std=0.5,
                              last_checkin=45, earliest_checkin=4 * 60):
        flight_schedule = self.flight_schedule
        d, too_early = data.flights_to_d(flight_schedule, t_interval, tot_m, mean_early_t, arrival_std, last_checkin, earliest_checkin)
        return d, too_early

    def initialize_data(self):
        # Costs and demands
        self.p = {j: self.parameter_settings['p'] for j in range(self.J)}  # Service time per passenger for a specific aircraft [hrs]
        self.C = {t: self.parameter_settings['C'] for t in range(self.N)}  # Maximum (for dynamic) of desks available per interval
        self.s_open = {t: self.parameter_settings['s_open'] for t in range(self.N)}  # Desk opening costs for time t
        self.s_operate = {t: self.parameter_settings['s_operate'] for t in range(self.N)}  # Desk operating costs for time t
        self.h = {j: self.parameter_settings['h0'] for j in range(self.J)}  # Queue costs

        A = np.zeros((self.J, self.N))
        for key, value in self.Tj.items():
            for time in list(value):
                A[int(key), int(time)] = 1
        self.A = A
        self.l_param = self.parameter_settings['l']  # average service time per desk

    def setup_decision_variables(self):
        # Decision variables
        self.B = self.model.addVars(self.N, vtype=GRB.INTEGER, name="B")  # number of desks to be assigned in interval t
        self.q = self.model.addVars(self.J, self.N, vtype=GRB.INTEGER, name="q")
        self.x = self.model.addVars(self.J, self.N, vtype=GRB.BINARY, name="x")
        self.I = self.model.addVars(self.J, self.N, vtype=GRB.INTEGER, name="I")
        self.desk = self.model.addVars(self.parameter_settings['C'], self.N, vtype=GRB.BINARY, name="desk")  # binary variable indicating desk open status
        self.y_open = self.model.addVars(self.parameter_settings['C'], self.N, vtype=GRB.BINARY, name="y_open")  # binary variable indicating desk opening

    def add_constraints(self):
        # Initial conditions
        self.model.addConstrs((self.I[j, int(self.flight_schedule[j][0] / (self.l*60) - 4 * 12 + 1)] == self.I0[j] for j in range(self.J)), "InitialQueue")

        # Queue dynamics
        self.model.addConstrs((self.I[j, t] == (self.I[j, t - 1] + self.d[j, t] - self.q[j, t])
                               for j in range(self.J) for t in range(int(self.flight_schedule[j][0] / (self.l*60) - (4 * 12) + 2), self.N)), "QueueDynamics")

        # No passengers can ENTER queue when they are outside the check-in limits
        self.model.addConstrs((self.I[j, t] == 0
                               for j in range(self.J) for t in self.Tj[j]), "EnterQueueLimit")

        # Capacity limits -> first in static
        self.model.addConstrs((sum(self.q[j, t] * self.p[j] for j in range(self.J)) <= self.C[t]
                               for t in range(self.N)), "CapacityLimit")

        # Check-in limits -> first in static
        self.model.addConstrs((self.q[j, t] * self.p[j] <= self.C[t] * self.x[j, t]
                               for j in range(self.J) for t in range(self.N)), "CheckInLimit")

        if self.model_name == "dynamic_ACP":
            # Dynamic capacity limits
            self.model.addConstrs((sum(self.q[j, t] * self.p[j] for j in range(self.J)) <= self.l_param * self.B[t]
                                   for t in range(self.N)), "CapacityLimit_dynamic")

            # All passengers accepted in time frame -> maybe delete, because passengers can arrive too late
            self.model.addConstrs((self.A[j, t] * self.I[j, t] == 0
                                   for j in range(self.J) for t in range(self.N)), "All_pax_in_timeframe")

            # Ensure that once a desk is opened, it stays open for at least "minimum_desk_time" consecutive time intervals
            # self.model.addConstrs((self.desk[i, t] <= self.desk[i, t + 1] for i in range(self.parameter_settings['C']) for t in range(self.N - 1)), "DeskOpeningConsistency")
            for i in range(self.parameter_settings['C']):
                for t in range(1, self.N - self.parameter_settings["minimum_desk_time"]):
                    self.model.addConstr((self.y_open[i,t] == 1) >> (sum(self.desk[i, t + k] for k in range(self.parameter_settings["minimum_desk_time"])) >= self.parameter_settings["minimum_desk_time"]),
                        f"MinConsecutiveOpening_{i}_{t}")

            # Link the number of desks opened in each time interval to the binary desk variables
            self.model.addConstrs((self.B[t] == sum(self.desk[i, t] for i in range(self.parameter_settings['C'])) for t in range(self.N)), "LinkDeskToB")

            # Ensure that desks incur an opening cost when they are opened
            for i in range(self.parameter_settings['C']):
                for t in range(self.N):
                    if t == 0:
                        self.model.addConstr(self.y_open[i, t] == self.desk[i, t], f"OpeningCost_{i}_{t}")
                    else:
                        self.model.addConstr((self.desk[i, t - 1] == 0) >> (self.y_open[i, t] == self.desk[i, t]),
                                             f"OpeningCost_{i}_{t}")

            # Ensure that desks incur an operating cost while they are open
            self.model.addConstrs((self.B[t] == sum(self.desk[i, t] for i in range(self.parameter_settings['C'])) for t in range(self.N)), "OperatingCost")

    def set_objective(self):
        # Objective function
        if self.model_name == "static_ACP":
            self.model.setObjective(
                sum(self.h[j] * self.I[j, t] + self.s_open[t] * self.x[j, t]
                    for j in range(self.J) for t in range(self.N)),
                GRB.MINIMIZE
            )
        else:
            self.model.setObjective(
                sum(self.h[j] * self.I[j, t] for j in range(self.J) for t in range(self.N)) +
                sum(self.s_open[t] * sum(self.y_open[i, t] for i in range(self.parameter_settings['C'])) for t in
                    range(self.N)) +
                sum(self.s_operate[t] * self.B[t] for t in range(self.N)),
                GRB.MINIMIZE
            )

    def optimize(self):
        # Optimize the model
        self.model.setParam('OutputFlag', True)  # Enable detailed Gurobi output
        self.model.optimize()
        # Output results
        if self.model.status == GRB.OPTIMAL:
            print("Optimal solution found!")
            print(f"Objective Value = {self.model.ObjVal}")
            self.objective = self.model.ObjVal

        elif self.model.status == GRB.INF_OR_UNBD:
            print("Model is infeasible or unbounded")
        elif self.model.status == GRB.INFEASIBLE:
            print("Model is infeasible")
            self.model.computeIIS()
            print("\nThe following constraints are causing the infeasibility:\n")
            for c in self.model.getConstrs():
                if c.IISConstr:
                    print(f"{c.ConstrName}: {c}")
        elif self.model.status == GRB.UNBOUNDED:
            print("Model is unbounded")
        else:
            print("Optimization ended with status ", self.model.Status)

    def plot_queue(self):

        fig, axs = plt.subplots(3, 2, figsize=(15, 15))

        for j in range(self.J):
            q_values = [self.q[j, t].X for t in range(self.N)]  # Get the number of passengers of flight j accepted in each period t
            # Plot the number of passengers accepted for flight j over time
            axs[0, 0].plot(range(self.N), q_values, label=f'Flight {j}')
        axs[0, 0].set_xlabel('Time Interval')
        axs[0, 0].set_ylabel('Number of Passengers Accepted at Desk')
        axs[0, 0].set_title('Number of Passengers Accepted at Desk over Time for Each Flight')
        axs[0, 0].legend()
        axs[0, 0].grid(True)

        for j in range(self.J):
            I_values = [self.I[j, t].X for t in range(self.N)]  # Get the number of passengers in queue for flight j in each period t
            # Plot the number of passengers in queue for flight j over time
            axs[0, 1].plot(range(self.N), I_values, label=f'Flight {j}')
        axs[0, 1].set_xlabel('Time Interval')
        axs[0, 1].set_ylabel('Number of Passengers in Queue')
        axs[0, 1].set_title('Number of Passengers in Queue over Time for Each Flight')
        axs[0, 1].legend()
        axs[0, 1].grid(True)

        # Plots that are not per flight from here...
        q_values = [sum(self.q[j, t].X for j in range(self.J)) for t in range(self.N)]
        I_values = [sum(self.I[j, t].X for j in range(self.J)) for t in range(self.N)]
        B_values = [self.B[t].X for t in range(self.N)]

        axs[1, 0].plot(range(self.N), I_values)
        axs[1, 0].set_xlabel('Time Interval')
        axs[1, 0].set_ylabel('Number of Passengers in Queue')
        axs[1, 0].set_title('Number of Passengers in Queue over Time for all Flights Combined')
        axs[1, 0].grid(True)

        axs[1, 1].plot(range(self.N), q_values)
        axs[1, 1].set_xlabel('Time Interval')
        axs[1, 1].set_ylabel('Number of Passengers Accepted')
        axs[1, 1].set_title('Number of Passengers Accepted at Desk over Time for all Flights Combined')
        axs[1, 1].grid(True)

        axs[2, 0].plot(range(self.N), B_values)
        axs[2, 0].set_xlabel('Time Interval')
        axs[2, 0].set_ylabel('Number of Desks Opened')
        axs[2, 0].set_title('Number of Desks Opened over Time')
        axs[2, 0].grid(True)

        # Hide the last empty subplot (bottom right)
        axs[2, 1].axis('off')

        plt.tight_layout()
        plt.show()

    def get_KPI(self):
        q_values = [sum(self.q[j, t].X for j in range(self.J)) for t in range(self.N)]
        I_values = [sum(self.I[j, t].X for j in range(self.J)) for t in range(self.N)]

        # ToDo: function to determine maximum waiting time of all passengers, use q_values & I_values above
        max_waiting_time = None

        objective = self.objective
        waiting_cost = sum(self.h[j] * self.I[j, t].X for j in range(self.J) for t in range(self.N))
        opening_cost = sum(self.s_open[t] * sum(self.y_open[i,t].X for i in range(self.parameter_settings['C'])) for t in range(self.N))
        operating_cost = sum(self.s_operate[t] * self.B[t].X for t in range(self.N))


        return objective, waiting_cost, opening_cost, operating_cost, max_waiting_time




'''
model_name options: "static_ACP", "dynamic_ACP"
'''

# Example usage:
flight_schedule = {
    0: (300, 300),  # Flight 0 departs at interval X with Y passengers
    1: (800, 300),  # Flight 1 departs at interval X with Y passengers
    2: (1200, 200),  # Flight 2 departs at interval X with Y passengers
    3: (330, 100),  # Flight 3 departs at interval X with Y passengers
}

parameter_settings = {'minimum_desk_time': 4, 'p': 1, 'C': 1000, 's_open': 1000, 's_operate': 10, 'h0': 100, 'l': 1}  # 'h0' decides the costs of a waiting line, 's_open' decides the costs of opening a desk, 's_operate' decides the cost of maintaining an open desk

if __name__ == "__main__":
    '''
    STATIC APPROACH
    '''
    # acp_optimization_static = ACP(model_name="static_ACP", T=24, l=1/12, parameter_settings=parameter_settings, flight_schedule=flight_schedule)
    # acp_optimization_schiphol_static = ACP(model_name="static_ACP", T=24, l=1/12, parameter_settings=parameter_settings, data_schiphol=data(), schiphol_case=True)
    # acp_optimization_static.optimize()
    # acp_optimization_schiphol_static.optimize()
    # acp_optimization_static.plot_queue()

    '''
    DYNAMIC APPROACH
    '''

    # VERIFICATION SCENARIO
    # acp_optimization_dynamic_verification = ACP(model_name="dynamic_ACP", T=24, l=1/12, parameter_settings=parameter_settings, flight_schedule=flight_schedule)
    # acp_optimization_dynamic_verification.optimize()
    # acp_optimization_dynamic_verification.plot_queue()
    # objective, waiting_cost, opening_cost, operating_cost, max_waiting_time = acp_optimization_dynamic_verification.get_KPI()

    # SCHIPHOL SCENARIO
    acp_optimization_dynamic_schiphol = ACP(model_name="dynamic_ACP", T=24, l=1 / 12, parameter_settings=parameter_settings, data_schiphol=data(), schiphol_case=True)
    acp_optimization_dynamic_schiphol.optimize()
    acp_optimization_dynamic_schiphol.plot_queue()
    objective, waiting_cost, opening_cost, operating_cost, max_waiting_time = acp_optimization_dynamic_schiphol.get_KPI()

    # Print KPI results...
    print("KPI overview: ")
    print("Objective value = ", objective)
    print("Waiting costs = ", waiting_cost)
    print("Opening costs = ", opening_cost)
    print("Operating costs = ", operating_cost)
    print("Maximum waiting time = ", max_waiting_time)