# from gurobipy import Model, GRB
# from data import *
# from Model import *

# class Sensitivity:
#     def __init__(self, model_name, T, l, parameter_settings, passenger_scale):
#         self.model_name = model_name
#         self.T = T  # Total time window [hrs]
#         self.l = l  # Length of the considered time interval [hrs]
#         self.parameter_settings = parameter_settings
#         self.passenger_scale = passenger_scale

#         # self.iterations = 5

#     def sensitivity_analysis(self):
#         # Define the range for sensitivity analysis
#         sensitivity_range = [0.5, 0.75, 1.0, 1.25, 1.50]  # Adjust
#         objective_list = []
#         waiting_cost_list = []
#         opening_cost_list = []
#         operating_cost_list = []
#         max_waiting_time_list = []


#         for factor in sensitivity_range:
#             # Apply sensitivity factor to parameter_settings
#             parameter_settings_sensitivity = self.apply_sensitivity_factor(factor)

#             # Initialize and optimize the model
#             # acp_optimization = ACP(self.model_name, self.T, self.l, parameter_settings_sensitivity, flight_schedule=flight_schedule, data_schiphol=None, schiphol_case=False) #schiphol/own data
#             acp_optimization = ACP(self.model_name, self.T, self.l, parameter_settings_sensitivity, flight_schedule=flight_schedule, data_schiphol=data(), schiphol_case=True, passenger_scale=self.passenger_scale)
            
#             acp_optimization.optimize()
#             # acp_optimization.plot_queue()

#             objective, waiting_cost, opening_cost, operating_cost, max_waiting_time = acp_optimization.get_KPI()
#             objective_list.append(objective)
#             waiting_cost_list.append(waiting_cost)
#             opening_cost_list.append(opening_cost)
#             operating_cost_list.append(operating_cost)
#             max_waiting_time_list.append(max_waiting_time)

        
        

#         print('KPI values for factors:', sensitivity_range, 'when changing')
#         print('objective:', objective_list)
#         print('waiting time:', waiting_cost_list)
#         print('opening cost:', opening_cost_list)
#         print('operating cost:', operating_cost_list)
#         print('max waiting time:', max_waiting_time_list)
    
#             # TODO: plot such that q/I are plotted for the various factors
#             # acp_optimization.plot_queue()
             

#     def apply_sensitivity_factor(self, factor):
#         # Apply sensitivity factor to parameter_settings   >  Which parameters change?
#         parameter_settings_sensitivity = {
#             'minimum_desk_time': self.parameter_settings['minimum_desk_time'],      # Keep as interger (dont multiply with float type factor)
#             'p': self.parameter_settings['p'] * factor,
#             'C': self.parameter_settings['C'],
#             's_open': self.parameter_settings['s_open'],
#             's_operate': self.parameter_settings['s_operate'],
#             'h0': self.parameter_settings['h0'],
#             'l': self.parameter_settings['l']
#         }
#         return parameter_settings_sensitivity


# # Param settings
# parameter_settings = {'minimum_desk_time': 4, 'p': 1, 'C': 400, 's_open': 100, 's_operate': 10, 'h0': 10, 'l': 1}


# if __name__ == "__main__":
#     # for i in range(3):

#     # Static:
#     # sensitivity_analysis = Sensitivity(model_name="static_ACP", T=24, l=1/12, parameter_settings=parameter_settings)

#     # Dynamic:

#     passenger_scale = 1.0  # Define passenger_scale 
#     sensitivity_analysis = Sensitivity(model_name="dynamic_ACP", T=24, l=1/12, parameter_settings=parameter_settings, passenger_scale=passenger_scale)

#     sensitivity_analysis.sensitivity_analysis()





# --------------------------------------------------------------------------------------------------------------
# VERBETERD:



from gurobipy import Model, GRB
from data import *
from Model import *

class Sensitivity:
    def __init__(self, model_name, T, l, parameter_settings, passenger_scale):
        self.model_name = model_name
        self.T = T  # Total time window [hrs]
        self.l = l  # Length of the considered time interval [hrs]
        self.parameter_settings = parameter_settings
        self.passenger_scale = passenger_scale

    def sensitivity_analysis(self):
        # Define the range for sensitivity analysis
        # sensitivity_range = [0.5, 0.75, 1.0, 1.25, 1.50]  # Adjust
        sensitivity_range = [0.5, 1.0, 1.5]
        # parameters_to_test = ['p', 'C', 's_open', 's_operate', 'h0', 'l']
        # parameters_to_test = ['p', 's_open', 's_operate', 'h0', 'l']
        parameters_to_test = ['s_open', 's_operate', 'h0']     # THE ONLY PARAMETERS THAT CAN BE CHANGED

        for param in parameters_to_test:
            print(f"\nPerforming sensitivity analysis for parameter: {param}")
            objective_list = []
            waiting_cost_list = []
            opening_cost_list = []
            operating_cost_list = []
            max_waiting_time_list = []

            for factor in sensitivity_range:
                # Apply sensitivity factor to the current parameter
                parameter_settings_sensitivity = self.apply_sensitivity_factor(param, factor)

                # Initialize and optimize the model
                acp_optimization = ACP(self.model_name, self.T, self.l, parameter_settings_sensitivity, flight_schedule=flight_schedule, data_schiphol=data(), schiphol_case=True, passenger_scale=self.passenger_scale)
                
                acp_optimization.optimize()
                # acp_optimization.plot_queue()

                objective, waiting_cost, opening_cost, operating_cost, max_waiting_time = acp_optimization.get_KPI()
                objective_list.append(objective)
                waiting_cost_list.append(waiting_cost)
                opening_cost_list.append(opening_cost)
                operating_cost_list.append(operating_cost)
                max_waiting_time_list.append(max_waiting_time)

            print('KPI values for factors:', sensitivity_range)
            print('objective:', objective_list)
            print('waiting time:', waiting_cost_list)
            print('opening cost:', opening_cost_list)
            print('operating cost:', operating_cost_list)
            print('max waiting time:', max_waiting_time_list)
    
    def apply_sensitivity_factor(self, parameter, factor):
        # Create a copy of the original parameter settings
        parameter_settings_sensitivity = self.parameter_settings.copy()
        
        # Apply sensitivity factor to the specified parameter
        if parameter != 'minimum_desk_time':
            parameter_settings_sensitivity[parameter] = self.parameter_settings[parameter] * factor
        
        return parameter_settings_sensitivity

# Param settings
parameter_settings = {'minimum_desk_time': 4, 'p': 1, 'C': 400, 's_open': 100, 's_operate': 10, 'h0': 10, 'l': 1}

if __name__ == "__main__":
    passenger_scale = 1.0  # Define passenger_scale 
    sensitivity_analysis = Sensitivity(model_name="dynamic_ACP", T=24, l=1/12, parameter_settings=parameter_settings, passenger_scale=passenger_scale)

    sensitivity_analysis.sensitivity_analysis()
