import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import make_interp_spline

class data:
	def __init__(self, airline = 'KLM', t_interval = 5, tot_m = 24*60, mean_early_t = 120, arrival_std = 2, last_checkin = 45, earliest_checkin = 4*60, data_loc = 'data 30_04_2024.xlsx'):
		self.airline = airline
		self.t_interval = t_interval
		self.tot_m = tot_m
		self.mean_early_t = mean_early_t
		self.last_checkin = last_checkin
		self.earliest_checkin = earliest_checkin
		self.arrival_std_dev = last_checkin / arrival_std
		self.data_loc = data_loc

		self.df = None #dataframe for data processing
		self.flights = None #Flights for the selected airline

		self.prep_data()
		self.d = self.get_d()
		self.T = self.get_T()

	def prep_data(self):
		self.organize_rows()
		self.add_capacity()
		self.set_time_to_minutes()
		self.select_airline(self.airline)


	def organize_rows(self):
		df = pd.read_excel(self.data_loc)
		df = df[['AIRCRAFT', 'AIRLINE', 'ETD', 'CARGO']]
		df = df.dropna(subset=['ETD'])
		df = df[df['CARGO'].isna()]
		df['AIRCRAFT'] = df['AIRCRAFT'].str.replace(' WINGLET', '', regex=False)
		df = df[~df['AIRCRAFT'].str.contains('FREIGHTER')]
		df.drop(columns=['CARGO'], inplace=True)
		self.df = df

	def add_capacity(self):
		max_pax_dict = {
			'BOEING 737-800S': 176,
			'AIRBUS A321 NEO': 220,
			'Embraer E190-E2 (ERJ190-300)': 114,
			'BOEING 737-700 Winglets': 149,
			'B737-900/Winglets': 189,
			'Embraer 190 (IGW)': 100,
			'Boeing 737MAX-8': 200,
			'AIRBUS A320 NEO': 194,
			'AIRBUS A319-111': 160,
			'Boeing 737MAX-9': 220,
			'EMBRAER ERJ-195-E2 (190-400STD)': 146,
			'EMBRAER175(170-200 STD)': 88,
			'Airbus A220-300': 160,
			'AIRBUS A321-100/200': 220,
			'BOMBARDIER CRJ900(CL-600-2D24)': 90,
			'EMBRAER170': 76,
			'AIRBUS A330-300': 440,
			'Embraer 195 ERJ 190-200': 124,
			'BOEING B-767-400': 304,
			'EMBRAER145': 50,
			'BOEING 777-200': 396,
			'Boeing 787-10 Dreamliner': 330,
			'BOEING 777-300ER': 396,
			'AIRBUS A350-900': 325,
			'Airbus A330-900neo': 287,
			'Boeing 787-8 Dreamliner': 242,
			'Boeing 767-300 winglet': 261,
			'AIRBUS A350-1000': 400,
			'Boeing 787-9 Dreamliner': 290,
			'AIRBUS A330-200': 406,
			'Airbus A380-800': 520
		}

		self.df['MAX_PAX'] = self.df['AIRCRAFT'].map(max_pax_dict)

		unique_aircraft_list = self.df['AIRCRAFT'].unique()
		# print("Unique Aircraft Types:", unique_aircraft_list)
		if len(unique_aircraft_list) != len(max_pax_dict):
			print(f'{len(unique_aircraft_list)} != {len(max_pax_dict)}')

	def set_time_to_minutes(self):
		self.df['ETD_minutes'] = self.df['ETD'].apply(lambda x: x.hour * 60 + x.minute)


	def select_airline(self, airline = 'KLM'):
		flights = self.df[self.df['AIRLINE'] == airline]
		flights = flights.reset_index(drop=True)
		self.flights = flights

	def get_d(self):
		d = {}
		count = 0
		for index, flight in self.flights.iterrows():
			etd_minutes = flight['ETD_minutes']
			total_passengers = flight['MAX_PAX']

			mean_checkin_time = etd_minutes - self.mean_early_t

			arrivals = np.random.normal(loc=mean_checkin_time, scale=self.arrival_std_dev, size=total_passengers)
			valid_arrivals = arrivals[(arrivals >= 0) & (arrivals <= self.tot_m)]
			arrivals_binned = np.floor(valid_arrivals / self.t_interval).astype(int)
			arrivals_counts, _ = np.histogram(arrivals_binned, bins=np.arange(0, self.tot_m // self.t_interval + 1))
			d[count] = arrivals_counts
			count += 1

		# Restructure d so that it works with d[i,j] instead of d[i][j]
		new_d = {}
		for i, sublist in d.items():
			for j in range(len(sublist)):
				new_d[(i, j)] = sublist[j]

		return new_d

	def get_T(self):
		T = {}
		for index, flight in self.flights.iterrows():
			etd_minutes = flight['ETD_minutes']
			no_checkin_t = set()
			for i in range(self.tot_m//self.t_interval):
				t = i * self.t_interval
				if t < etd_minutes - self.earliest_checkin:
					no_checkin_t.add(i)
				elif t > etd_minutes - self.last_checkin:
					no_checkin_t.add(i)
			T[index] = no_checkin_t
		return T

	@staticmethod
	def flights_to_d(flight_schedule, t_interval = 5, tot_m = 24*60, mean_early_t = 2*60, arrival_std = 0.25, last_checkin = 35, earliest_checkin = 4*60):
		# flight_schedule = {
		# 	0: (240, 100),  # Flight 0 departs at interval 16 (4 hours into the day)
		# 	1: (48, 100),  # Flight 1 departs at interval 48 (12 hours into the day)
		# 	2: (80, 50)  # Flight 2 departs at interval 80 (20 hours into the day)
		# }
		arrival_std_dev = last_checkin / arrival_std

		d = {}
		count = 0
		for index, (etd_minutes, total_passengers) in flight_schedule.items():
			print(index, (etd_minutes, total_passengers))

			mean_checkin_time = etd_minutes - mean_early_t

			arrivals = np.random.normal(loc=mean_checkin_time, scale=arrival_std_dev, size=total_passengers)
			print(arrivals)
			valid_arrivals = arrivals[(arrivals >= 0) & (arrivals <= tot_m)]
			arrivals_binned = np.floor(valid_arrivals / t_interval).astype(int)
			arrivals_counts, _ = np.histogram(arrivals_binned, bins=np.arange(0, tot_m // t_interval + 1))
			d[count] = arrivals_counts
			count += 1

		# Restructure d so that it works with d[i,j] instead of d[i][j]
		new_d = {}
		for i, sublist in d.items():
			for j in range(len(sublist)):
				new_d[(i, j)] = sublist[j]

		return new_d

# test_flights = {
# 	0: (600, 100),  # Flight 0 departs at interval 16 (4 hours into the day)
# 	1: (700, 100),  # Flight 1 departs at interval 48 (12 hours into the day)
# 	2: (750, 50)  # Flight 2 departs at interval 80 (20 hours into the day)
# }
#
# output = data.flights_to_d(test_flights)
# print(output)
#
# # Define colors for each flight index
# colors = ['red', 'green', 'blue']
#
# plt.figure(figsize=(10, 6))
#
# for flight_index in range(max(x for (x, _), _ in output.items()) + 1):
# 	# Extract and sort time bins and counts
# 	times, counts = zip(*sorted((time_bin, count) for (idx, time_bin), count in output.items() if idx == flight_index))
#
# 	# Scatter plot for data points
# 	plt.scatter(times, counts, color=colors[flight_index], label=f'Flight {flight_index}', alpha=0.6, edgecolors='w')
#
# 	# Interpolate and plot smooth curve if there are enough points
# 	if len(times) > 1:
# 		spline = make_interp_spline(times, counts, k=2)
# 		smooth_times = np.linspace(min(times), max(times), 300)
# 		plt.plot(smooth_times, spline(smooth_times), color=colors[flight_index])
#
# plt.legend()
# plt.title('Passenger Arrivals by Flight and Time Interval')
# plt.xlabel('Time Interval')
# plt.ylabel('Number of Passengers')
# plt.grid(True)
# plt.show()
#
# # test capcities
# capacities = [0,0,0]
# for (flight_index, time_bin), count in output.items():
# 	capacities[flight_index] += count
#
# print(capacities)


# plot the x, y, val of this output dictionary