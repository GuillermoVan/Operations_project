import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import make_interp_spline
import itertools
class data:
	def _init_(self, airline = 'KLM', t_interval = 5, tot_m = 24*60, mean_early_t = 120, arrival_std = 2, last_checkin = 45, earliest_checkin = 4*60, data_loc = 'data 30_04_2024.xlsx'):
		self.airline = airline
		self.t_interval = t_interval
		self.tot_m = tot_m
		self.mean_early_t = mean_early_t
		self.last_checkin = last_checkin
		self.earliest_checkin = earliest_checkin
		self.arrival_std_dev = last_checkin / arrival_std
		self.data_loc = data_loc

		self.df = None
		self.flights = None

		self.d = None
		self.T = None
		self.too_early = None


		self.prep_data()
		self.set_d()
		self.set_T()

	def prep_data(self):
		self.organize_rows()
		self.add_capacity()
		self.set_time_to_minutes()
		self.select_airline(self.airline)
		# self.get_pax_dist()

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
	def select_airline(self, airline='KLM'):
		flights = self.df[self.df['AIRLINE'] == airline]
		flights = flights.reset_index(drop=True)
		self.flights = flights

	def set_d(self):
		d = {}
		too_early = []
		count = 0

		for index, flight in self.flights.iterrows():
			valid_pax_dist = []
			etd_minutes = flight['ETD_minutes']
			total_passengers = flight['MAX_PAX']
			mean_checkin_time = etd_minutes - self.mean_early_t

			norm_dist = np.random.normal(loc=mean_checkin_time, scale=self.arrival_std_dev, size=total_passengers)
			valid_norm_dist = norm_dist[(norm_dist >= 0) & (norm_dist <= self.tot_m)]
			norm_binned = np.floor(valid_norm_dist / self.t_interval).astype(int)
			pax_dist, _ = np.histogram(norm_binned, bins=np.arange(0, self.tot_m // self.t_interval + 1))

			# earliest_checkin_index = (etd_minutes - self.earliest_checkin)//self.t_interval
			# latest_checkin_index = (etd_minutes - self.last_checkin)//self.t_interval

			earliest_checkin_index = max(0, (etd_minutes - self.earliest_checkin) // self.t_interval)
			latest_checkin_index = min((etd_minutes - self.last_checkin) // self.t_interval, len(pax_dist) - 1)

			print('checkin avialble from index:', earliest_checkin_index, 'to index:', latest_checkin_index)
			if earliest_checkin_index >= 0 and latest_checkin_index >= 0:
				too_early.append(sum(pax_dist[:earliest_checkin_index]))
				pax_dist[:earliest_checkin_index] = 0
				pax_dist[latest_checkin_index:] = 0
				valid_pax_dist = pax_dist
				# valid_pax_dist.append(pax_dist[earliest_checkin_index:latest_checkin_index])
				# too_early.append(sum(pax_dist[:earliest_checkin_index]))

			d[count] = valid_pax_dist
			# print(too_early_pax_dist)
			# too_early[count] = sum(too_early_pax_dist)
			count += 1

		# Restructure d so that it works with d[i,j] instead of d[i][j]
		new_d = {}
		for i, sublist in d.items():
			for j in range(len(sublist)):
				new_d[(i, j)] = sublist[j]

		self.d = new_d
		self.too_early = too_early

	def set_T(self):
		T = {}
		for index, flight in self.flights.iterrows():
			etd_minutes = flight['ETD_minutes']
			no_checkin_t = set()
			for i in range(self.tot_m // self.t_interval):
				t = i * self.t_interval
				if t < etd_minutes - self.earliest_checkin:
					no_checkin_t.add(i)
				elif t > etd_minutes - self.last_checkin:
					no_checkin_t.add(i)
			T[index] = no_checkin_t
		self.T = T

	def get_departure_times(self):
		departure_times = {}
		for index, flight in self.flights.iterrows():
			departure_times[index] = flight['ETD_minutes']
		return departure_times

	@staticmethod
	def flights_to_d(flight_schedule, t_interval = 5, tot_m = 24*60, mean_early_t = 2*60, arrival_std = 0.5, last_checkin = 45, earliest_checkin = 4*60):
		# flight_schedule = {
		# 	0: (240, 100),  # Flight 0 departs at interval 16 (4 hours into the day)
		# 	1: (48, 100),  # Flight 1 departs at interval 48 (12 hours into the day)
		# 	2: (80, 50)  # Flight 2 departs at interval 80 (20 hours into the day)
		# }
		arrival_std_dev = last_checkin / arrival_std

		#valid_pax_dist = []
		d = {}
		too_early = []
		count = 0

		for index, (etd_minutes, total_passengers) in flight_schedule.items():
			valid_pax_dist = []
			# etd_minutes = flight['ETD_minutes']
			# total_passengers = flight['MAX_PAX']
			mean_checkin_time = etd_minutes - mean_early_t

			norm_dist = np.random.normal(loc=mean_checkin_time, scale=arrival_std_dev, size=total_passengers)
			valid_norm_dist = norm_dist[(norm_dist >= 0) & (norm_dist <= tot_m)]
			norm_binned = np.floor(valid_norm_dist / t_interval).astype(int)
			pax_dist, _ = np.histogram(norm_binned, bins=np.arange(0, tot_m // t_interval + 1))

			earliest_checkin_index = max(0, (etd_minutes - earliest_checkin) // t_interval)
			latest_checkin_index = min((etd_minutes - last_checkin) // t_interval, len(pax_dist) - 1)

			print('checkin avialble from index:', earliest_checkin_index, 'to index:', latest_checkin_index)
			if earliest_checkin_index >= 0 and latest_checkin_index >= 0:
				too_early.append(sum(pax_dist[:earliest_checkin_index]))
				pax_dist[:earliest_checkin_index] = 0
				pax_dist[latest_checkin_index+1:] = 0
				valid_pax_dist = pax_dist
				# valid_pax_dist = pax_dist[earliest_checkin_index:latest_checkin_index]
				# too_early.append(sum(pax_dist[:earliest_checkin_index]))

			# print('---->', valid_pax_dist)
			# print(len(valid_pax_dist), latest_checkin_index - earliest_checkin_index)

			d[count] = valid_pax_dist
			# print(too_early_pax_dist)
			# too_early[count] = sum(too_early_pax_dist)
			count += 1

		# Restructure d so that it works with d[i,j] instead of d[i][j]
		new_d = {}
		for i, sublist in d.items():
			for j in range(len(sublist)):
				new_d[(i, j)] = sublist[j]

		return new_d, too_early


#data = data()
#print(sum(data.too_early))



# test_flights = {
#     0: (90, 100),  # Flight 0 departs at interval 16 (4 hours into the day)
#     1: (400, 100),  # Flight 1 departs at interval 48 (12 hours into the day)
#     2: (500, 50)    # Flight 2 departs at interval 80 (20 hours into the day)
# }


def plot_data(d, too_early):
	# test_flights = {
	#     0: (90, 100),  # Flight 0 departs at interval 16 (4 hours into the day)
	#     1: (400, 100),  # Flight 1 departs at interval 48 (12 hours into the day)
	#     2: (500, 50)    # Flight 2 departs at interval 80 (20 hours into the day)
	# }
	# d, too_early = data.flights_to_d(test_flights)
	colors = itertools.cycle(['red', 'green', 'yellow', 'blue', 'purple', 'pink', 'cyan','orange'])

	plt.figure(figsize=(10, 6))

	for flight_index in range(max(x for (x, _), _ in d.items()) + 1): #used CHATCPT for plotting function
		# Check if there are any data points for the current flight_index
		data_points = [(time_bin, count) for (idx, time_bin), count in d.items() if idx == flight_index]
		if not data_points:
			continue  # Skip this iteration if no data points

		# Extract and sort time bins and counts
		times, counts = zip(*sorted(data_points))

		# Scatter plot for data points
		color = next(colors)
		plt.scatter(times, counts, color=color, label=f'Flight {flight_index}', alpha=0.6, edgecolors='w')

		# Interpolate and plot smooth curve if there are enough points
		#if len(times) > 1:
		#	spline = make_interp_spline(times, counts, k=2)
		#	smooth_times = np.linspace(min(times), max(times), 300)
		#	plt.plot(smooth_times, spline(smooth_times), color=colors[flight_index])

	plt.legend()
	plt.title('Passenger Arrivals by Flight and Time Interval')
	plt.xlabel('Time Interval')
	plt.ylabel('Number of Passengers')
	plt.grid(True)
	plt.show()

	print('too early', too_early)

def plot_total_passengers(d, too_early):
    """
    Plot the total number of passengers per time bin for all flights combined.

    Parameters:
    d (dict): A dictionary where the key is a tuple (flight_index, time_bin) and the value is the count of passengers.
    too_early (int): An integer representing the number of passengers that arrived too early.
    """
    # Aggregate the passenger counts for each time bin across all flights
    total_passengers_per_time_bin = {}
    for (_, time_bin), count in d.items():
        if time_bin not in total_passengers_per_time_bin:
            total_passengers_per_time_bin[time_bin] = 0
        total_passengers_per_time_bin[time_bin] += count

    # Extract and sort time bins and total counts
    sorted_time_bins = sorted(total_passengers_per_time_bin.keys())
    total_counts = [total_passengers_per_time_bin[time_bin] for time_bin in sorted_time_bins]

    # Plot the total number of passengers per time bin
    plt.figure(figsize=(10, 6))
    plt.plot(sorted_time_bins, total_counts, marker='o', linestyle='-', color='blue', alpha=0.6, label='Total Passengers')

    plt.legend()
    plt.title('Total Passenger Arrivals by Time Interval')
    plt.xlabel('Time Interval')
    plt.ylabel('Number of Passengers')
    plt.grid(True)
    plt.show()
    print('too early', too_early)

# need to fix indices, add time or something, because now we rearanged. Could keep same indices but set all too early to 0.
def tester():
	test_data = data()
	#print(test_data.too_early)
	too_early = test_data.too_early
	d = test_data.d
	#plot_data(d, too_early)
	plot_total_passengers(d, too_early)

# tester()

#print('hello')