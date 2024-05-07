from gurobipy import Model, GRB
from data import *
import numpy as np
from data import plot_data

class ACP:
    def __init__(self, model_name, T, l, parameter_settings, flight_schedule=None, data_schiphol=None, schiphol_case=False):
        self.model_name = model_name
        self.model = Model(model_name)
        self.T = T  # Total time window [hrs]
        self.l = l  # Length of the considered time interval [hrs]
        self.N = int(self.T // self.l)  # Number of intervals
        self.schiphol_case = schiphol_case
        self.parameter_settings = parameter_settings

        if self.schiphol_case is False:
            self.flight_schedule = flight_schedule  # Dictionary of flight index as key and interval index as departure time in timewindow T
            self.J = len(flight_schedule)  # Total number of flights in T
            self.d = self.create_passenger_flow()
            #Tj calculation
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
        else:
            self.d, self.Tj = data_schiphol.d, data_schiphol.T
            self.J = len(self.Tj)

        self.initialize_data()
        self.setup_decision_variables()
        self.add_constraints()
        self.set_objective()

    def create_passenger_flow(self, t_interval=5, tot_m=24 * 60, mean_early_t=2 * 60, arrival_std=2,
                 last_checkin=45, earliest_checkin=4 * 60):
        #ToDo: CREATE A FUNCTION THAT CREATES DISTRIBUTION BASED ON A SELF.FLIGHT_SCHEDULE

        # flight_schedule = {
        # 	0: (240, 100),  # Flight 0 departs at interval 16 (4 hours into the day)
        # 	1: (48, 100),  # Flight 1 departs at interval 48 (12 hours into the day)
        # 	2: (80, 50)  # Flight 2 departs at interval 80 (20 hours into the day)
        # }

        d, too_early = data.flights_to_d(self.flight_schedule, t_interval, tot_m, mean_early_t, arrival_std, last_checkin, earliest_checkin)
        plot_data(d, too_early)
        return d

    def initialize_data(self):
        # Costs and demands
        self.p = {j: parameter_settings['p'] for j in range(self.J)}  # Service time per passenger for a specific aircraft [hrs]
        if self.model_name == "static_ACP":
            self.C = {t: parameter_settings['C'] for t in range(self.N)}  # Desks available per interval
        else:
            self.st = {t: parameter_settings['s'] for t in range(self.N)}  # Desk opening costs for time t
            A = np.zeros((self.J, self.N))
            for key,value in self.Tj.items():
                for time in list(value):
                    A[int(key), int(time)] = 1
            self.A = A
            self.l_param = self.parameter_settings['l']



        self.I0 = {j: parameter_settings['I0'] for j in range(self.J)}  # Number of passengers waiting before desk opening per flight
        self.s = {j: parameter_settings['s'] for j in range(self.J)}  # Desk opening costs for flight j
        self.h = {j: parameter_settings['h0'] + j for j in range(self.J)}  # Queue costs

    def setup_decision_variables(self):
        # Decision variables
        if self.model_name == "dynamic_ACP":
            self.C =  self.model.addVars(self.N, vtype=GRB.INTEGER, name="C") #number of desks to be assigned in interval t
        self.q = self.model.addVars(self.J, self.N, vtype=GRB.INTEGER, name="q")
        self.x = self.model.addVars(self.J, self.N, vtype=GRB.BINARY, name="x")
        self.I = self.model.addVars(self.J, self.N, vtype=GRB.INTEGER, name="I")

    def add_constraints(self):
        # Initial conditions
        self.model.addConstrs((self.I[j, 0] == self.I0[j] for j in range(self.J)), "InitialQueue")

        # Queue dynamics
        self.model.addConstrs((self.I[j, t] == (self.I[j, t - 1] + self.d[j, t] - self.q[j, t])
                               for j in range(self.J) for t in range(1, self.N)), "QueueDynamics")

        #No passengers can ENTER queue when they are outside the check-in limits -> should actually be changed to I
        self.model.addConstrs((self.q[j, t] == 0
                               for j in range(self.J) for t in self.Tj[j]), "CheckIn-Times")

        if self.model_name == "dynamic_ACP":
            #Dynamic capacity limits
            self.model.addConstrs((sum(self.q[j, t] * self.p[j] for j in range(self.J)) <= self.l_param * self.C[t]
                                   for t in range(self.N)), "CapacityLimit_dynamic")

            #All passengers accepted in time frame -> maybe delete, because passengers can arrive too late
            self.model.addConstrs((self.A[j, t] * self.q[j, t] == 0
                                   for j in range(self.J) for t in range(self.N)), "All_pax_in_timeframe")
        else:
            # Capacity limits
            self.model.addConstrs((sum(self.q[j, t] * self.p[j] for j in range(self.J)) <= self.C[t]
                                   for t in range(self.N)), "CapacityLimit")
            # Check-in limits
            self.model.addConstrs((self.q[j, t] * self.p[j] <= self.C[t]
                                   for j in range(self.J) for t in range(self.N)), "CheckInLimit")




    def set_objective(self):
        # Objective function
        if self.model_name == "static_ACP":
            self.model.setObjective(sum(self.h[j] * self.I[j, t] + self.s[j] * self.x[j, t]
                                        for j in range(self.J) for t in range(self.N)), GRB.MINIMIZE)
        else:
            self.model.setObjective(sum(self.h[j] * self.I[j, t] + self.st[t] * self.C[t]
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

    def plot_queue(self):

        # ------------------------- TO DO: CHECK IF CODE BELOW IS CORRECT -------------------------

        # for j in range(self.J):
        #     q_values = [self.q[j, t].x for t in range(self.N)]  # Get the number of passengers of flight j accepted in each period t

        #     # Plot the number of passengers accepted for flight j over time
        #     plt.plot(range(self.N), q_values, label=f'Flight {j}')

        # # Add vertical lines at t = 4 hours and t = 45 minutes before departure for each flight j
        # for j in range(self.J):
        #     plt.axvline(x=self.flight_schedule[j] - 4 * 12, color='red', linestyle='--', label=f'Check-in Limit for Flight {j}')
        #     plt.axvline(x=self.flight_schedule[j] - 45, color='green', linestyle='--', label=f'Last Check-in Time for Flight {j}')

        # plt.xlabel('Time Interval')
        # plt.ylabel('Number of Passengers to be Accepted')
        # plt.title('Number of Passengers to be Accepted over Time for Each Flight')
        # plt.legend()
        # plt.grid(True)
        # plt.show()
        # ----------------------------------------------------------------------------------------

        #ToDo: plot amount of passengers in queue as function of time

        return
'''
model_name options: "static_ACP", "dynamic_ACP" -> only static works for now
'''

# Example usage:
flight_schedule = {
 	0: (500, 100),  # Flight 0 departs at interval 240 with 100 passengers
 	1: (600, 100),  # Flight 1 departs at interval 48 with 100 passengers
 	2: (700, 50),  # Flight 2 departs at interval 80 with 50 passengers
    3: (800, 100) #LAST INDEX OUR OF RANGE !!!
 }

parameter_settings = {'p': 1.5/60, 'C': 1.5 * 20, 'I0': 30, 's': 100, 'h0': 5, 'l': 1.5/60}

if __name__ == "__main__":
    '''
    STATIC APPROACH
    '''
    #acp_optimization_static = ACP(model_name="static_ACP", T=24, l=1/12, parameter_settings=parameter_settings, flight_schedule=flight_schedule)
    #acp_optimization_schiphol_static = ACP(model_name="static_ACP", T=24, l=1/12, parameter_settings=parameter_settings, data_schiphol=data(), schiphol_case=True)
    #acp_optimization_static.optimize()
    #acp_optimization_schiphol_static.optimize()

    '''
    DYNAMIC APPROACH
    '''
    acp_optimization_dynamic = ACP(model_name="dynamic_ACP", T=24, l=1/12, parameter_settings=parameter_settings, flight_schedule=flight_schedule)
    #acp_optimization_schiphol_dynamic = ACP(model_name="dynamic_ACP", T=24, l=1 / 12, parameter_settings=parameter_settings, data_schiphol=data(), schiphol_case=True)
    acp_optimization_dynamic.optimize()
    #acp_optimization_schiphol_dynamic.optimize()