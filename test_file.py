from gurobipy import Model, GRB

# Create a new model
model = Model("model_name")

# Create variables
x = model.addVar(vtype=GRB.CONTINUOUS, name="x")
y = model.addVar(vtype=GRB.CONTINUOUS, name="y")

# Set objective
model.setObjective(1.0 * x + 2.0 * y, GRB.MAXIMIZE)

# Add constraint: x + 2y <= 8
model.addConstr(x + 2 * y <= 8, "c0")

# Add another constraint: 2x + y <= 10
model.addConstr(2 * x + y <= 10, "c1")

# Optimize model
model.optimize()

# Print the solution
for v in model.getVars():
    print(f"{v.varName} {v.x}")

print(f"Obj: {model.objVal}")
