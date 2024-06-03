from gurobipy import Model, GRB
from data import *
from Model import *

class Sensitivity:
    def __init__(self, model_name, T, l, parameter_settings):
        self.model_name = model_name
        self.T = T  # Total time window [hrs]
        self.l = l  # Length of the considered time interval [hrs]
        self.parameter_settings = parameter_settings

        # self.iterations = 5

    def sensitivity_analysis(self):
        # Define the range for sensitivity analysis
        sensitivity_range = [0.6, 1.0, 1.4]  # Adjust
        objective_list = []
        waiting_cost_list = []
        opening_cost_list = []
        operating_cost_list = []
        max_waiting_time_list = []


        for factor in sensitivity_range:
            # Apply sensitivity factor to parameter_settings
            parameter_settings_sensitivity = self.apply_sensitivity_factor(factor)

            # Initialize and optimize the model
            # acp_optimization = ACP(self.model_name, self.T, self.l, parameter_settings_sensitivity, flight_schedule=flight_schedule, data_schiphol=None, schiphol_case=False) #schiphol/own data
            acp_optimization = ACP(self.model_name, self.T, self.l, parameter_settings_sensitivity, flight_schedule=flight_schedule, data_schiphol=data(), schiphol_case=True)
            
            acp_optimization.optimize()

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
    
            # TODO: plot such that q/I are plotted for the various factors
            # acp_optimization.plot_queue()
             

    def apply_sensitivity_factor(self, factor):
        # Apply sensitivity factor to parameter_settings   >  Which parameters change?
        parameter_settings_sensitivity = {
            'minimum_desk_time': self.parameter_settings['minimum_desk_time'] * factor,
            'p': self.parameter_settings['p'] * factor,
            'C': self.parameter_settings['C'],
            's_open': self.parameter_settings['s_open'] * factor,
            's_operate': self.parameter_settings['s_operate'] * factor,
            'h0': self.parameter_settings['h0'] * factor,
            'l': self.parameter_settings['l']
        }
        return parameter_settings_sensitivity


# Param settings
parameter_settings = {'minimum_desk_time': 4, 'p': 1, 'C': 400, 's_open': 100, 's_operate': 10, 'h0': 10, 'l': 1}


if __name__ == "__main__":
    # for i in range(3):

    # Static:
    # sensitivity_analysis = Sensitivity(model_name="static_ACP", T=24, l=1/12, parameter_settings=parameter_settings)

    # Dynamic:
    sensitivity_analysis = Sensitivity(model_name="Dynamic_ACP", T=24, l=1/12, parameter_settings=parameter_settings)

    sensitivity_analysis.sensitivity_analysis()
