from gurobipy import Model, GRB
from sympy import plot
from data import *
from Model import *
import matplotlib.pyplot as plt
import numpy as np

class Sensitivity:
    def __init__(self, model_name, T, l, parameter_settings, passenger_scale):
        self.model_name = model_name
        self.T = T  # Total time window [hrs]
        self.l = l  # Length of the considered time interval [hrs]
        self.parameter_settings = parameter_settings
        self.passenger_scale = passenger_scale

    def sensitivity_analysis(self):
        # Define the range for sensitivity analysis
        # sensitivity_range = [0.5, 0.75, 1.0, 1.25, 1.5]   # range for factors for cost
        sensitivity_range = [0.7, 0.9, 1.1, 1.3]            # range for F


        # Choose parameters for sensitivity
        # parameters_to_test = ['s_open', 's_operate', 'h0']  # COST PARAMETERS
        parameters_to_test = ['C']

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

            self.plot_stacked_bar(factors=sensitivity_range, waiting_cost=waiting_cost_list, opening_cost=opening_cost_list, operating_cost=operating_cost_list, parameter=param)

            plt.plot(sensitivity_range, objective_list)
            plt.xlabel(f"Factor of: {param}")
            plt.ylabel('Objective Value')
            plt.title(f"Sensitivity analysis for parameter: {param}")
            plt.grid(True)
            plt.show()
            

        if param == 'C':
            plt.plot(sensitivity_range, objective_list)
            plt.axvline(0.67, color='black', linestyle='--', label=f'Minimum C value')
            plt.xlabel('Factor of C')
            plt.ylabel('Objective Value')
            plt.title('Sensitivity analysis of C')
            plt.grid(True)
            plt.show()

    
    def apply_sensitivity_factor(self, parameter, factor):
        # Create a copy of the original parameter settings
        parameter_settings_sensitivity = self.parameter_settings.copy()
        
        if parameter == 'C':
            parameter_settings_sensitivity['C'] = int(self.parameter_settings[parameter] * factor)
                    
        # Apply sensitivity factor to the specified parameter
        if parameter != 'minimum_desk_time' and parameter != 'C':
            parameter_settings_sensitivity[parameter] = self.parameter_settings[parameter] * factor
        
        return parameter_settings_sensitivity
    
    def plot_stacked_bar(self, factors, waiting_cost, opening_cost, operating_cost, parameter):
        # Create the plot
        fig, ax = plt.subplots()

        # Define bar width and positions with spaces between them
        bar_width = 0.4
        positions = np.arange(len(factors)) * (bar_width + 0.2)

        # Custom colors TU Delft template
        color_waiting = (12/255, 35/255, 64/255)  # RGB=(12, 35, 64)
        color_opening = (0/255, 184/255, 200/255)  # RGB=(0, 184, 200)
        color_operating = (0/255, 118/255, 194/255)  # RGB=(0, 118, 194)

        bars1 = ax.bar(positions, waiting_cost, width=bar_width, label='Waiting Cost', color=color_waiting)
        bars2 = ax.bar(positions, opening_cost, width=bar_width, bottom=waiting_cost, label='Opening Cost', color=color_opening)
        bars3 = ax.bar(positions, operating_cost, width=bar_width, bottom=[i + j for i, j in zip(waiting_cost, opening_cost)], label='Operating Cost', color=color_operating)

        # Adding the percentage and value text on the bars
        for bar1, bar2, bar3, wait_cost, open_cost, op_cost in zip(bars1, bars2, bars3, waiting_cost, opening_cost, operating_cost):
            height1 = bar1.get_height()
            height2 = bar2.get_height()
            height3 = bar3.get_height()
            total_height = height1 + height2 + height3
            wait_pct = wait_cost / total_height * 100
            open_pct = open_cost / total_height * 100
            op_pct = op_cost / total_height * 100
            ax.text(bar1.get_x() + bar1.get_width() / 2, height1 / 2,
                    f'{wait_pct:.1f}%\n({wait_cost})', ha='center', va='bottom', color='white')
            ax.text(bar2.get_x() + bar2.get_width() / 2, height1 + height2 / 2,
                    f'{open_pct:.1f}%\n({open_cost})', ha='center', va='bottom', color='black')
            ax.text(bar3.get_x() + bar3.get_width() / 2, height1 + height2 + height3 / 2,
                    f'{op_pct:.1f}%\n({op_cost})', ha='center', va='bottom', color='white')

        # Add labels and legend
        ax.set_xlabel('Factors')
        ax.set_ylabel('Total Objective Cost')
        ax.set_title(f'Stacked Bar Plot with Percentages for {parameter}')
        ax.set_xticks(positions)
        ax.set_xticklabels(factors)
        ax.legend()

        # Show the plot
        plt.show()


# Param settings
parameter_settings = {'minimum_desk_time': 4, 'p': 1, 'C': 400, 's_open': 100, 's_operate': 10, 'h0': 10, 'l': 1}

if __name__ == "__main__":
    passenger_scale = 1.0  # Define passenger_scale 
    sensitivity_analysis = Sensitivity(model_name="dynamic_ACP", T=24, l=1/12, parameter_settings=parameter_settings, passenger_scale=passenger_scale)

    sensitivity_analysis.sensitivity_analysis()
