from gurobipy import Model, GRB
from data import *
import numpy as np
from KPI_calculations import get_longest_queue_time

class ACP:
    def __init__(self, model_name, T, l, parameter_settings, flight_schedule=None, data_schiphol=None, schiphol_case=False, passenger_scale=1):
        self.objective = None
        self.model_name = model_name
        self.model = Model(model_name)
        self.T = T  # Total time window [hrs]
        self.l = l  # Length of the considered time interval [hrs]
        self.N = int(self.T // self.l)  # Number of intervals
        self.schiphol_case = schiphol_case
        self.parameter_settings = parameter_settings
        self.passenger_scale = passenger_scale

        if self.schiphol_case is False:
            self.flight_schedule = flight_schedule  # Dictionary of flight index as key and interval index as departure time in timewindow T
        else:
            self.flight_schedule = {i: (row['ETD_minutes'], row['MAX_PAX']) for i, row in data_schiphol.flights.iterrows()}

        self.J = len(self.flight_schedule)  # Total number of flights in T
        self.d, too_early = self.create_passenger_flow()
        self.I0 = {j: too_early[j] for j in range(self.J)}  # Number of passengers waiting before desk opening per flight
        # Tj calculation
        self.early_limit = 4 / self.l  # passengers can not check-in before 4 hours in advance of departure
        self.late_limit = 0.75 / self.l  # passengers can not check-in after 45 minutes before departure
        Tj = dict()
        for j, t in self.flight_schedule.items():
            earliest_checkin_index = int(round(t[0] / (self.l*60)) - self.early_limit)
            latest_checkin_index = int(round(t[0] / (self.l*60)) - self.late_limit)
            non_checkin_intervals = set(range(earliest_checkin_index)) | set(
                range(latest_checkin_index + 1, self.N))
            Tj[j] = non_checkin_intervals
        self.Tj = Tj  # For each flight j the set of time intervals in which it is not possible to check in
        self.t_interval = 5

        self.initialize_data()
        self.setup_decision_variables()
        self.add_constraints()
        self.set_objective()



    def create_passenger_flow(self, t_interval=5, tot_m=24 * 60, mean_early_t=2 * 60, arrival_std=0.5,
                last_checkin=45, earliest_checkin=4 * 60):
    # def create_passenger_flow(self, t_interval=5, tot_m=24 * 60, mean_early_t=2 * 60, arrival_std=0.5,
    #             last_checkin=4 * 60, earliest_checkin=4 * 60 - (4 * 60 - 45)): #ALL PASSENGERS TOO EARLY - VERIFICATION
    # def create_passenger_flow(self, t_interval=5, tot_m=24 * 60, mean_early_t=2 * 60, arrival_std=0.5,
    #                           last_checkin=0, earliest_checkin=1): #ALL PASSENGERS TOO LATE - VERIFICATION
        self.t_interval = t_interval
        flight_schedule = self.flight_schedule
        d, too_early = data.flights_to_d(flight_schedule, t_interval, tot_m, mean_early_t, arrival_std, last_checkin,
                                         earliest_checkin)
        too_early = [round(self.passenger_scale * x) for x in too_early]  # Ensure correct scaling of too_early
        for key in d:
            d[key] = round(self.passenger_scale * d[key])  # Ensure correct scaling of d

        # ######### FOR VERIFICATION #############
        # too_early = [0]
        # for key, value in d.items():
        #     d[key] = 0
        # d[(0, 90)] = 10
        # ######### FOR VERIFICATION #############

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

        # Check-in limits -> first in static -> maybe delete
        # self.model.addConstrs((self.q[j, t] * self.p[j] <= self.C[t] * self.x[j, t]
        #                       for j in range(self.J) for t in range(self.N)), "CheckInLimit")

        if self.model_name == "dynamic_ACP":
            # Dynamic capacity limits
            self.model.addConstrs((sum(self.q[j, t] * self.p[j] for j in range(self.J)) <= self.l_param * self.B[t]
                                   for t in range(self.N)), "CapacityLimit_dynamic")

            # All passengers accepted in time frame -> maybe delete, because passengers can arrive too late
            # self.model.addConstrs((self.A[j, t] * self.I[j, t] == 0
            #                       for j in range(self.J) for t in range(self.N)), "All_pax_in_timeframe")

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
            print(f"Total Runtime = {self.model.Runtime} seconds")
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
        # Plot number of passengers accepted at desk for each flight
        plt.figure(figsize=(10, 6))
        for j in range(self.J):
            q_values = [self.q[j, t].X for t in range(self.N)]
            plt.plot(range(self.N), q_values, label=f'Flight {j}')
            earliest_checkin_index = int(round(self.flight_schedule[j][0] / (self.l * 60)) - self.early_limit)
            latest_checkin_index = int(round(self.flight_schedule[j][0] / (self.l * 60)) - self.late_limit)
            plt.axvline(x=earliest_checkin_index, color='r', linestyle='--', label=f'Earliest Check-in Flight {j}')
            plt.axvline(x=latest_checkin_index, color='g', linestyle='--', label=f'Latest Check-in Flight {j}')
            plt.axvline(x=round(self.flight_schedule[j][0] / (self.l * 60)), color='black', linestyle='--',
                        label=f'Departure Time of Flight {j}')
        plt.xlabel('Time Interval [5 mins]')
        plt.ylabel('Number of Passengers Accepted at Desk')
        plt.title('Number of Passengers Accepted at Desk over Time for Each Flight')
        plt.legend()
        plt.grid(True)
        plt.show()

        # Plot number of passengers in queue for each flight in one plot
        plt.figure(figsize=(10, 6))
        for j in range(self.J):
            I_values = [self.I[j, t].X for t in range(self.N)]
            plt.plot(range(self.N), I_values, label=f'Flight {j}')
            earliest_checkin_index = int(round(self.flight_schedule[j][0] / (self.l * 60)) - self.early_limit)
            latest_checkin_index = int(round(self.flight_schedule[j][0] / (self.l * 60)) - self.late_limit)
        plt.axvline(x=earliest_checkin_index, color='r', linestyle='--', label=f'Earliest Check-in')
        plt.axvline(x=latest_checkin_index, color='g', linestyle='--', label=f'Latest Check-in')
        plt.axvline(x=round(self.flight_schedule[j][0] / (self.l * 60)), color='black', linestyle='--', label=f'Departure Time')
        plt.xlabel('Time Interval [5 mins]')
        plt.ylabel('Number of Passengers in Queue')
        plt.title('Number of Passengers in Queue over Time for Each Flight')
        plt.legend()
        plt.grid(True)
        plt.show()

        # Plot number of passengers in queue for all flights combined
        I_values_combined = [sum(self.I[j, t].X for j in range(self.J)) for t in range(self.N)]
        plt.figure(figsize=(10, 6))
        plt.plot(range(self.N), I_values_combined)
        # plt.axvline(x=earliest_checkin_index, color='r', linestyle='--', label=f'Earliest Check-in')
        # plt.axvline(x=latest_checkin_index, color='g', linestyle='--', label=f'Latest Check-in')
        # plt.axvline(x=round(600 / (self.l * 60)), color='black', linestyle='--',
        #            label=f'Departure Time')
        plt.xlabel('Time Interval [5 mins]')
        plt.ylabel('Number of Passengers in Queue')
        plt.title('Number of Passengers in Queue over Time for All Flights Combined')
        #plt.legend()
        plt.grid(True)
        plt.show()

        # Plot number of passengers accepted at desk for all flights combined
        q_values_combined = [sum(self.q[j, t].X for j in range(self.J)) for t in range(self.N)]
        plt.figure(figsize=(10, 6))
        plt.plot(range(self.N), q_values_combined)
        plt.xlabel('Time Interval [5 mins]')
        plt.ylabel('Number of Passengers Accepted')
        plt.title('Number of Passengers Accepted at Desk over Time for All Flights Combined')
        plt.grid(True)
        plt.show()

        # Plot number of desks opened over time
        B_values = [self.B[t].X for t in range(self.N)]
        plt.figure(figsize=(10, 6))
        plt.plot(range(self.N), B_values)
        # plt.axvline(x=earliest_checkin_index, color='r', linestyle='--', label='Earliest Check-in Flight 2')
        # plt.axvline(x=latest_checkin_index, color='g', linestyle='--', label='Latest Check-in 2')
        # plt.axvline(x=round(600 / (self.l * 60)), color='black', linestyle='--',
        #             label='Departure Time of Flight 2')
        plt.xlabel('Time Interval [5 mins]')
        plt.ylabel('Number of Desks Opened')
        plt.title('Number of Desks Opened over Time')
        plt.grid(True)
        #plt.legend()
        plt.show()

    def get_KPI(self):
        q_values = [sum(self.q[j, t].X for j in range(self.J)) for t in range(self.N)]
        I_values = [sum(self.I[j, t].X for j in range(self.J)) for t in range(self.N)]

        print('q (number of people who leave the queue per time step) :    ', q_values)
        print('I (number of people in the queue per time step):    ', I_values)
        max_waiting_time = get_longest_queue_time(q_values, I_values)
        print('longest_queue_time in [min]:', max_waiting_time * self.t_interval)
        print()

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
    0: (600, 10)#,  # Flight 0 departs at interval X with Y passengers
    #1: (600, 500)#,  # Flight 1 departs at interval X with Y passengers
    #2: (1200, 200),  # Flight 2 departs at interval X with Y passengers
    #3: (330, 100),  # Flight 3 departs at interval X with Y passengers
}

parameter_settings = {'minimum_desk_time': 4, 'p': 1, 'C': 400, 's_open': 100, 's_operate': 10, 'h0': 10, 'l': 1}  # 'h0' decides the costs of a waiting line, 's_open' decides the costs of opening a desk, 's_operate' decides the cost of maintaining an open desk

if __name__ == "__main__":
    # VERIFICATION SCENARIO
    # acp_optimization_dynamic_verification = ACP(model_name="dynamic_ACP", T=24, l=1/12, parameter_settings=parameter_settings, flight_schedule=flight_schedule)
    # acp_optimization_dynamic_verification.optimize()
    # acp_optimization_dynamic_verification.plot_queue()
    # objective, waiting_cost, opening_cost, operating_cost, max_waiting_time = acp_optimization_dynamic_verification.get_KPI()

    # SCHIPHOL SCENARIO
    schiphol = True
    if schiphol == True:
        amount_simulations = 1
        total_passengers_lst = []
        objective_lst, waiting_cost_lst, desk_cost_lst, max_waiting_time_lst = [], [], [], []
        for passenger_scale in np.linspace(0.5, 1.5, amount_simulations):
            print("Currently at passenger scale ", passenger_scale)
            acp_optimization_dynamic_schiphol = ACP(model_name="dynamic_ACP", T=24, l=1 / 12, parameter_settings=parameter_settings, data_schiphol=data(), schiphol_case=True, passenger_scale=passenger_scale)
            acp_optimization_dynamic_schiphol.optimize()
            acp_optimization_dynamic_schiphol.plot_queue()
            objective, waiting_cost, opening_cost, operating_cost, max_waiting_time = acp_optimization_dynamic_schiphol.get_KPI()
            total_desk_cost = opening_cost + operating_cost
            total_passengers = sum(acp_optimization_dynamic_schiphol.q[j, t].X for j in range(acp_optimization_dynamic_schiphol.J) for t in range(acp_optimization_dynamic_schiphol.N))

            total_passengers_lst.append(total_passengers)
            objective_lst.append(objective)
            waiting_cost_lst.append(waiting_cost)
            desk_cost_lst.append(total_desk_cost)
            max_waiting_time_lst.append(max_waiting_time*5)


            # Print KPI results...
            print(f"KPI overview for scale {passenger_scale}: ")
            print("Objective value = ", objective)
            print("Waiting costs = ", waiting_cost)
            print("Opening costs = ", opening_cost)
            print("Operating costs = ", operating_cost)
            print("Total desk costs = ", total_desk_cost)
            print("Maximum waiting time = ", max_waiting_time*5)


        #Present overview of test results Schiphol case -> not sure yet how
        print("ALL LISTS NECESSARY FOR PLOTTING: ")
        print("total_passengers_lst = ", total_passengers_lst)
        print("objective_lst = ", objective_lst)
        print("waiting_cost_lst = ", waiting_cost_lst)
        print("desk_cost_lst = ", desk_cost_lst)
        print("max_waiting_time_lst = ", max_waiting_time_lst)

        # Plot total_passengers_lst vs objective_lst
        plt.figure(figsize=(10, 6))
        plt.plot(total_passengers_lst, objective_lst, marker='o')
        plt.xlabel('Total Passengers')
        plt.ylabel('Objective Value')
        plt.title('Passenger Load vs Objective Value')
        plt.grid(True)
        plt.show()

        # Plot total_passengers_lst vs waiting_cost_lst/objective_lst and desk_cost_lst/objective_lst
        waiting_fraction = [w/o for w, o in zip(waiting_cost_lst, objective_lst)]
        desk_fraction = [d/o for d, o in zip(desk_cost_lst, objective_lst)]

        plt.figure(figsize=(10, 6))
        plt.plot(total_passengers_lst, waiting_fraction, marker='o', label='Waiting Cost Fraction')
        plt.plot(total_passengers_lst, desk_fraction, marker='o', label='Desk Cost Fraction')
        plt.xlabel('Total Passengers')
        plt.ylabel('Cost Fraction of Objective')
        plt.title('Passenger Load vs Cost Fraction of Objective')
        plt.legend()
        plt.grid(True)
        plt.show()

        # Plot total_passengers_lst vs max_waiting_time_lst
        plt.figure(figsize=(10, 6))
        plt.plot(total_passengers_lst, max_waiting_time_lst, marker='o')
        plt.xlabel('Total Passengers')
        plt.ylabel('Max Waiting Time (minutes)')
        plt.title('Passenger Load vs Maximum Waiting Time')
        plt.grid(True)
        plt.show()
