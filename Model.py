from gurobipy import Model, GRB
from data import *
import numpy as np

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
        else:
            self.flight_schedule = {i: (row['ETD_minutes'], row['MAX_PAX']) for i, row in data_schiphol.flights.iterrows()}

        self.J = len(self.flight_schedule)  # Total number of flights in T
        self.d, too_early = self.create_passenger_flow()
        self.I0 = {j: too_early[j] for j in
                   range(self.J)}  # Number of passengers waiting before desk opening per flight
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
        self.p = {j: parameter_settings['p'] for j in range(self.J)}  # Service time per passenger for a specific aircraft [hrs]
        self.C = {t: parameter_settings['C'] for t in range(self.N)}  # Maximum (for dynamic) of desks available per interval
        self.st = {t: parameter_settings['s'] for t in range(self.N)}  # Desk opening costs for time t
        A = np.zeros((self.J, self.N))
        for key,value in self.Tj.items():
            for time in list(value):
                A[int(key), int(time)] = 1
        self.A = A
        self.l_param = self.parameter_settings['l']

        self.s = {j: parameter_settings['s'] for j in range(self.J)}  # Desk opening costs for flight j
        self.h = {j: parameter_settings['h0'] for j in range(self.J)}  # Queue costs

    def setup_decision_variables(self):
        # Decision variables
        self.B =  self.model.addVars(self.N, vtype=GRB.INTEGER, name="B") #number of desks to be assigned in interval t
        self.q = self.model.addVars(self.J, self.N, vtype=GRB.INTEGER, name="q")
        self.x = self.model.addVars(self.J, self.N, vtype=GRB.BINARY, name="x")
        self.I = self.model.addVars(self.J, self.N, vtype=GRB.INTEGER, name="I")

    def add_constraints(self):
        # Initial conditions
        self.model.addConstrs((self.I[j, int(self.flight_schedule[j][0]/(self.l*60) - 4 * 12 + 1)] == self.I0[j] for j in range(self.J)), "InitialQueue")

        # Queue dynamics
        self.model.addConstrs((self.I[j, t] == (self.I[j, t - 1] + self.d[j, t] - self.q[j, t])
                               for j in range(self.J) for t in range(int(self.flight_schedule[j][0]/(self.l*60) - (4 * 12) + 2), self.N)), "QueueDynamics")

        # No passengers can ENTER queue when they are outside the check-in limits
        self.model.addConstrs((self.I[j, t] == 0
                               for j in range(self.J) for t in self.Tj[j]), "CheckIn-Times")

        # Capacity limits -> first in static
        self.model.addConstrs((sum(self.q[j, t] * self.p[j] for j in range(self.J)) <= self.C[t]
                             for t in range(self.N)), "CapacityLimit")

        # Check-in limits -> first in static
        self.model.addConstrs((self.q[j, t] * self.p[j] <= self.C[t] * self.x[j, t]
                              for j in range(self.J) for t in range(self.N)), "CheckInLimit")

        if self.model_name == "dynamic_ACP":
            #Dynamic capacity limits
            self.model.addConstrs((sum(self.q[j, t] * self.p[j] for j in range(self.J)) <= self.l_param * self.B[t]
                                   for t in range(self.N)), "CapacityLimit_dynamic")

            #All passengers accepted in time frame -> maybe delete, because passengers can arrive too late
            self.model.addConstrs((self.A[j,t] * self.I[j, t] == 0
                                   for j in range(self.J) for t in range(self.N)), "All_pax_in_timeframe")




    def set_objective(self):
        # Objective function
        if self.model_name == "static_ACP":
            self.model.setObjective(sum(self.h[j] * self.I[j, t] + self.s[j] * self.x[j, t]
                                        for j in range(self.J) for t in range(self.N)), GRB.MINIMIZE)
        else:
            self.model.setObjective(sum(self.h[j] * self.I[j, t] + self.st[t] * self.B[t]
                                        for j in range(self.J) for t in range(self.N)), GRB.MINIMIZE)

    def optimize(self):
        # Optimize the model
        self.model.setParam('OutputFlag', True)  # Enable detailed Gurobi output
        self.model.optimize()
        # Output results
        if self.model.status == GRB.OPTIMAL:
            #for v in self.model.getVars():
            #    print(f"{v.VarName} = {v.x}")
            print("Optimal solution found!")
            print(f"Objective Value = {self.model.ObjVal}")
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

        print("HERE: ", self.I[0, 20 - 1].x, '+', self.d[0, 20], '-', self.q[0, 20].x)

        for j in range(self.J):
            q_values = [self.q[j, t].x for t in range(self.N)]  # Get the number of passengers of flight j accepted in each period t
            # Plot the number of passengers accepted for flight j over time
            plt.plot(range(self.N), q_values, label=f'Flight {j}')

            # FOR VALIDATION: Add vertical lines at t = 4 hours and t = 45 minutes before departure for each flight j
            #plt.axvline(x=self.flight_schedule[j][0]/(self.l*60) - 4 * 12, color='black', linestyle='--', label=f'First Check-in Limit for Flight {j}')
            #plt.axvline(x=self.flight_schedule[j][0]/(self.l*60) - 0.75 * 12, color='black', linestyle='--', label=f'Last Check-in Time for Flight {j}')

        plt.xlabel('Time Interval')
        plt.ylabel('Number of Passengers to be Accepted')
        plt.title('Number of Passengers to be Accepted over Time for Each Flight')
        plt.legend()
        plt.grid(True)
        plt.show()


        for j in range(self.J):
            I_values = [self.I[j, t].x for t in range(self.N)]  # Get the number of passengers in queue for flight j in each period t
            # Plot the number of passengers in queue for flight j over time
            plt.plot(range(self.N), I_values, label=f'Number of passengers in queue for Flight {j}')

            # FOR VALIDATION: Add vertical lines at t = 4 hours and t = 45 minutes before departure for each flight j
            #plt.axvline(x=self.flight_schedule[j][0]/(self.l*60) - 4 * 12, color='black', linestyle='--', label=f'First Check-in Limit for Flight {j}')
            #plt.axvline(x=self.flight_schedule[j][0]/(self.l*60) - 0.75 * 12, color='black', linestyle='--', label=f'Last Check-in Time for Flight {j}')

        plt.xlabel('Time Interval')
        plt.ylabel('Number of Passengers in Queue')
        plt.title('Number of Passengers in Queue over Time for Each Flight')
        plt.legend()
        plt.grid(True)
        plt.show()

        return

'''
model_name options: "static_ACP", "dynamic_ACP" -> only static works for now
'''

# Example usage:
flight_schedule = {
 	0: (300, 300),  # Flight 0 departs at interval X with Y passengers
 	1: (800, 300),  # Flight 1 departs at interval X with Y passengers
 	2: (1200, 200),  # Flight 2 departs at interval X with Y passengers
    3: (330, 100),  # Flight 3 departs at interval X with Y passengers
 }

parameter_settings = {'p': 1, 'C': 500, 's': 100, 'h0': 0.1, 'l': 1} #'h0' decides the costs of a waiting line, 's' decides the costs of opening a desk

if __name__ == "__main__":
    '''
    STATIC APPROACH
    '''
    #acp_optimization_static = ACP(model_name="static_ACP", T=24, l=1/12, parameter_settings=parameter_settings, flight_schedule=flight_schedule)
    #acp_optimization_schiphol_static = ACP(model_name="static_ACP", T=24, l=1/12, parameter_settings=parameter_settings, data_schiphol=data(), schiphol_case=True)
    #acp_optimization_static.optimize()
    #acp_optimization_schiphol_static.optimize()
    #acp_optimization_static.plot_queue()

    '''
    DYNAMIC APPROACH
    '''

    # flight_schedule_schiphol = {0: (407, 114), 1: (407, 114), 2: (407, 114), 3: (409, 189), 4: (410, 100), 5: (413, 176), 6: (414, 114), 7: (415, 149), 8: (419, 100), 9: (420, 114), 10: (425, 146), 11: (426, 146), 12: (426, 176), 13: (428, 149), 14: (429, 100), 15: (433, 176), 16: (434, 114), 17: (441, 189), 18: (443, 176), 19: (447, 176), 20: (462, 146), 21: (472, 100), 22: (475, 100), 23: (477, 146), 24: (478, 176), 25: (479, 189), 26: (481, 100), 27: (484, 176), 28: (487, 100), 29: (494, 100), 30: (496, 114), 31: (499, 146), 32: (501, 176), 33: (501, 146), 34: (501, 149), 35: (502, 100), 36: (508, 100), 37: (510, 176), 38: (510, 114), 39: (513, 100), 40: (519, 176), 41: (520, 114), 42: (524, 114), 43: (525, 100), 44: (531, 149), 45: (533, 100), 46: (533, 100), 47: (535, 176), 48: (540, 100), 49: (542, 176), 50: (542, 100), 51: (545, 100), 52: (546, 176), 53: (551, 100), 54: (553, 189), 55: (557, 100), 56: (559, 100), 57: (560, 149), 58: (560, 146), 59: (564, 149), 60: (564, 100), 61: (565, 100), 62: (566, 176), 63: (568, 100), 64: (569, 100), 65: (573, 189), 66: (573, 146), 67: (573, 100), 68: (575, 100), 69: (575, 114), 70: (576, 114), 71: (578, 146), 72: (579, 176), 73: (579, 100), 74: (580, 220), 75: (580, 146), 76: (580, 100), 77: (582, 176), 78: (584, 176), 79: (585, 440), 80: (586, 146), 81: (588, 146), 82: (589, 176), 83: (591, 146), 84: (592, 114), 85: (592, 114), 86: (593, 176), 87: (596, 100), 88: (598, 176), 89: (599, 396), 90: (599, 176), 91: (601, 176), 92: (601, 330), 93: (606, 114), 94: (610, 396), 95: (610, 176), 96: (616, 176), 97: (616, 396), 98: (617, 176), 99: (618, 440), 100: (618, 100), 101: (622, 396), 102: (622, 176), 103: (629, 176), 104: (635, 100), 105: (639, 396), 106: (642, 396), 107: (645, 114), 108: (646, 396), 109: (660, 114), 110: (662, 176), 111: (670, 100), 112: (670, 146), 113: (680, 330), 114: (690, 440), 115: (695, 176), 116: (695, 100), 117: (695, 100), 118: (700, 100), 119: (700, 146), 120: (700, 114), 121: (705, 100), 122: (710, 146), 123: (711, 176), 124: (715, 100), 125: (715, 149), 126: (716, 176), 127: (720, 100), 128: (722, 100), 129: (723, 114), 130: (725, 100), 131: (725, 100), 132: (730, 114), 133: (730, 114), 134: (731, 146), 135: (735, 396), 136: (735, 176), 137: (735, 176), 138: (735, 100), 139: (740, 100), 140: (740, 146), 141: (740, 189), 142: (745, 100), 143: (745, 176), 144: (746, 100), 145: (749, 146), 146: (750, 396), 147: (750, 330), 148: (750, 100), 149: (751, 176), 150: (755, 100), 151: (755, 330), 152: (760, 396), 153: (760, 100), 154: (760, 396), 155: (760, 100), 156: (765, 100), 157: (770, 396), 158: (775, 100), 159: (775, 100), 160: (785, 176), 161: (795, 114), 162: (795, 406), 163: (795, 100), 164: (800, 149), 165: (800, 100), 166: (800, 149), 167: (800, 290), 168: (805, 330), 169: (805, 100), 170: (815, 189), 171: (815, 114), 172: (825, 176), 173: (825, 406), 174: (825, 114), 175: (830, 114), 176: (830, 100), 177: (840, 146), 178: (840, 176), 179: (845, 100), 180: (845, 114), 181: (850, 176), 182: (850, 146), 183: (850, 330), 184: (850, 176), 185: (850, 100), 186: (850, 176), 187: (855, 176), 188: (855, 406), 189: (855, 176), 190: (855, 176), 191: (855, 176), 192: (855, 114), 193: (860, 114), 194: (865, 146), 195: (865, 176), 196: (865, 114), 197: (865, 100), 198: (865, 146), 199: (870, 290), 200: (870, 149), 201: (870, 406), 202: (880, 396), 203: (880, 100), 204: (895, 146), 205: (900, 176), 206: (900, 189), 207: (905, 176), 208: (905, 146), 209: (905, 146), 210: (905, 396), 211: (915, 396), 212: (920, 149), 213: (925, 396), 214: (935, 114), 215: (940, 176), 216: (945, 100), 217: (950, 146), 218: (955, 100), 219: (960, 100), 220: (960, 290), 221: (960, 146), 222: (960, 176), 223: (965, 176), 224: (965, 100), 225: (965, 146), 226: (970, 176), 227: (970, 100), 228: (970, 100), 229: (970, 114), 230: (975, 100), 231: (975, 176), 232: (980, 100), 233: (985, 100), 234: (985, 100), 235: (985, 176), 236: (985, 114), 237: (985, 100), 238: (985, 100), 239: (985, 176), 240: (985, 176), 241: (985, 100), 242: (990, 176), 243: (990, 176), 244: (990, 100), 245: (990, 114), 246: (995, 114), 247: (995, 100), 248: (1000, 100), 249: (1000, 440), 250: (1005, 100), 251: (1005, 176), 252: (1005, 220), 253: (1005, 100), 254: (1005, 149), 255: (1005, 189), 256: (1005, 100), 257: (1010, 396), 258: (1010, 146), 259: (1015, 146), 260: (1020, 100), 261: (1020, 114), 262: (1020, 146), 263: (1020, 176), 264: (1025, 330), 265: (1025, 100), 266: (1035, 176), 267: (1040, 396), 268: (1040, 146), 269: (1050, 114), 270: (1055, 100), 271: (1060, 176), 272: (1090, 100), 273: (1105, 114), 274: (1105, 100), 275: (1115, 114), 276: (1120, 114), 277: (1125, 114), 278: (1130, 146), 279: (1155, 114), 280: (1155, 100), 281: (1165, 114), 282: (1175, 114), 283: (1190, 100), 284: (1205, 176), 285: (1210, 100), 286: (1215, 146), 287: (1215, 100), 288: (1215, 176), 289: (1215, 176), 290: (1215, 149), 291: (1220, 176), 292: (1220, 146), 293: (1220, 146), 294: (1220, 100), 295: (1220, 290), 296: (1220, 100), 297: (1220, 100), 298: (1220, 100), 299: (1220, 176), 300: (1225, 176), 301: (1225, 146), 302: (1225, 176), 303: (1225, 100), 304: (1230, 100), 305: (1230, 176), 306: (1235, 149), 307: (1235, 100), 308: (1235, 114), 309: (1235, 100), 310: (1235, 146), 311: (1235, 176), 312: (1235, 290), 313: (1235, 176), 314: (1235, 176), 315: (1235, 396), 316: (1240, 176), 317: (1245, 189), 318: (1245, 100), 319: (1245, 189), 320: (1245, 146), 321: (1245, 176), 322: (1245, 114), 323: (1250, 176), 324: (1250, 176), 325: (1250, 220), 326: (1250, 176), 327: (1255, 100), 328: (1255, 176), 329: (1260, 100), 330: (1260, 176), 331: (1265, 146), 332: (1265, 100), 333: (1265, 189), 334: (1270, 114), 335: (1275, 146), 336: (1275, 100), 337: (1275, 100), 338: (1275, 100), 339: (1280, 100), 340: (1280, 114), 341: (1280, 114), 342: (1280, 100), 343: (1280, 100), 344: (1285, 176), 345: (1285, 149), 346: (1290, 290), 347: (1290, 146), 348: (1295, 100), 349: (1305, 100), 350: (1345, 100), 351: (1345, 149), 352: (1345, 176), 353: (1345, 189), 354: (1360, 114), 355: (1360, 146)}
    # last_aircraft = 3
    # flight_schedule = {}
    # for key, value in flight_schedule_schiphol.items():
    #     flight_schedule[key] = value
    #     if key == last_aircraft:
    #         break
    #
    #acp_optimization_dynamic = ACP(model_name="dynamic_ACP", T=24, l=1/12, parameter_settings=parameter_settings, flight_schedule=flight_schedule)
    acp_optimization_schiphol_dynamic = ACP(model_name="dynamic_ACP", T=24, l=1 / 12, parameter_settings=parameter_settings, data_schiphol=data(), schiphol_case=True)
    #acp_optimization_dynamic.optimize()
    #acp_optimization_dynamic.plot_queue()
    acp_optimization_schiphol_dynamic.optimize()
    acp_optimization_schiphol_dynamic.plot_queue()