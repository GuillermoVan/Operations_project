from gurobipy import Model, GRB
from data import *
from Model import *

class Sensitivity:
    def __init__(self, model_name, T, l, parameter_settings):
        self.model_name = model_name
        self.T = T  # Total time window [hrs]
        self.l = l  # Length of the considered time interval [hrs]
        self.parameter_settings = parameter_settings

    def sensitivity_analysis(self):
        # Define the range for sensitivity analysis
        sensitivity_range = [0.8, 1.0, 1.2]  # You can adjust this range as needed

        for factor in sensitivity_range:
            # Apply sensitivity factor to parameter_settings
            parameter_settings_sensitivity = self.apply_sensitivity_factor(factor)

            # Initialize and optimize the model
            acp_optimization = ACP(self.model_name, self.T, self.l, parameter_settings_sensitivity, data_schiphol=data(), schiphol_case=True)
            acp_optimization.optimize()

    def apply_sensitivity_factor(self, factor):
        # Apply sensitivity factor to parameter_settings
        parameter_settings_sensitivity = {
            'p': self.parameter_settings['p'] * factor,
            'C': self.parameter_settings['C'],
            'I0': self.parameter_settings['I0'],
            's0': self.parameter_settings['s0'] * factor,
            'h0': self.parameter_settings['h0'] * factor
        }
        return parameter_settings_sensitivity

# Example usage:
parameter_settings = {'p': 1.5/60, 'C': 15, 'I0': 30, 's0': 100, 'h0': 5}

if __name__ == "__main__":
    sensitivity_analysis = Sensitivity(model_name="static_ACP", T=24, l=1/12, parameter_settings=parameter_settings)
    sensitivity_analysis.sensitivity_analysis()