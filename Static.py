from gurobipy import Model, GRB

# Create a new model
m = Model("static_ACP")

# Indices and Parameters (these need to be defined based on your specific data)
T = 24 # Total time window (usually a day, but model as needed)
l = 2 # Length of the considered time interval (e.g., 2 hours)
J = 3 # Total number of flights
N = T // l # Number of intervals
s = {j: 100 + 10 * j for j in range(J)}  # Costs for opening desks, increasing with flight index
h = {j: 5 + j for j in range(J)}  # Costs for passenger queuing, slightly increasing with flight index
C = {t: 5 for t in range(N)}  # Constant maximum number of desks available in each interval
p = {j: 2 for j in range(J)}  # Constant service time of 2 minutes per passenger for all flights
d = {(j, t): max(0, 25 - 5 * abs(t - 6) + j * 3) for j in range(J) for t in range(N)} # Demand d[j, t]: simulate some variation in passenger arrival

# Decision Variables
q = m.addVars(J, N, vtype=GRB.INTEGER, name="q")  # passengers in the queue for flight j at the end of period t
x = m.addVars(J, N, vtype=GRB.BINARY, name="x")  # if passengers are checked in during interval t for flight j
g = m.addVars(J, N, vtype=GRB.INTEGER, name="g")  # number of passengers of flight j to be checked in during t

# Objective function: Minimize the total cost associated with desk operation and queue management
m.setObjective(sum(h[j]*q[j,t] + s[j]*x[j,t] for j in range(J) for t in range(N)), GRB.MINIMIZE)

# Constraints
# (2) Queue dynamics
m.addConstrs((q[j, t] == (q[j, t-1] + d[j, t] - g[j, t]) for j in range(J) for t in range(1, N)), "QueueDynamics")
# (3) Limit check-ins by available desks
m.addConstrs((p[j]*g[j, t] <= C[t]*x[j, t] for j in range(J) for t in range(N)), "CheckInLimit")
# (4) Sum of passengers across all flights does not exceed total capacity at any time
m.addConstrs((sum(p[j]*g[j, t] for j in range(J)) <= C[t] for t in range(N)), "CapacityLimit")
# (5) Initial queue is zero
m.addConstrs((q[j, 0] == 0 for j in range(J)), "InitialQueue")
# (6) x_jt is binary and is defined already by variable type
# (7) g_jt should be non-negative, already defined by variable type as integer

# Optimize the model
m.optimize()

# Output results
for v in m.getVars():
    print(f"{v.VarName} = {v.x}")

# Check model status
if m.Status == GRB.OPTIMAL:
    print("Optimal solution found!")
elif m.Status == GRB.INF_OR_UNBD:
    print("Model is infeasible or unbounded")
elif m.Status == GRB.INFEASIBLE:
    print("Model is infeasible")
elif m.Status == GRB.UNBOUNDED:
    print("Model is unbounded")
else:
    print("Optimization ended with status ", m.Status)
