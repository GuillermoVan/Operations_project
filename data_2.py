import pandas as pd
import numpy as np
import datetime




# OLD CODE ---- DONT USE




# Used chat_gpt to help write parts of this class since it is just used for data generation
def get_d_and_T():
	data_loc = 'data 30_04_2024.xlsx'
	df = pd.read_excel(data_loc)
	df = df[['AIRCRAFT', 'AIRLINE', 'ETD', 'CARGO']]
	df = df.dropna(subset=['ETD'])
	df = df[df['CARGO'].isna()]
	df['AIRCRAFT'] = df['AIRCRAFT'].str.replace(' WINGLET', '', regex=False)
	df = df[~df['AIRCRAFT'].str.contains('FREIGHTER')]
	df.drop(columns=['CARGO'], inplace=True)

	# Mapping passenger capacity
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

	unique_aircraft_list = df['AIRCRAFT'].unique()
	# print("Unique Aircraft Types:", unique_aircraft_list)
	if len(unique_aircraft_list) != len(max_pax_dict):
		print(f'{len(unique_aircraft_list)} != {len(max_pax_dict)}')

	df['MAX_PAX'] = df['AIRCRAFT'].map(max_pax_dict)


	# Set time to miniutes
	df['ETD_minutes'] = df['ETD'].apply(lambda x: x.hour * 60 + x.minute)
	# print(df[['ETD', 'ETD_minutes']])
	flights = df[df['AIRLINE'] == 'KLM']
	flights = flights.reset_index(drop=True)

	last_check_in_time = 45
	t_interval = 5  # min
	total_hours = 24  # total number of hours to consider
	def get_d():
		# Define constants
		mean_arrival_time_before_departure = 120  # minutes before departure
		scaler_not_full = 1 # already do the 0.95 with the 2 STD
		# last_check_in_time = 45  # minutes before departure #TODO: can make 90 min for international flights
		arrival_std_dev = last_check_in_time / 2 #99.7 pax arrived between 3 STD, 95%
		# arrival_std_dev = 30
		# t_interval = 5 #min
		# total_hours = 24  # total number of hours to consider


		# Filter the DataFrame to only include KLM flights
		# flights = df[df['AIRLINE'] == 'KLM']


		# Initialize an array to store passenger count per time interval
		pax_per_t = np.zeros((total_hours * 60) // t_interval)  # considering a 24-hour period
		# Iterate over each flight

		d = {}
		count = 0
		for index, flight in flights.iterrows():
			# Get the departure time of the flight in minutes
			# pax_per_t = np.zeros((total_hours * 60) // t_interval)  # considering a 24-hour period
			etd_minutes = flight['ETD_minutes']

			# Calculate mean check-in time
			mean_checkin_time = etd_minutes - mean_arrival_time_before_departure

			# Get the total number of passengers arriving for this flight
			total_passengers = flight['MAX_PAX']

			# Generate arrival times centered around mean_checkin_time using a normal distribution
			arrivals = np.random.normal(loc=mean_checkin_time, scale=arrival_std_dev, size=total_passengers)

			# Filter arrivals to keep only those within the valid time range
			valid_arrivals = arrivals[(arrivals >= 0) & (arrivals <= (total_hours * 60))]

			# Convert arrivals to 5-minute bins and count the number of arrivals per bin
			arrivals_binned = np.floor(valid_arrivals / t_interval).astype(int)
			arrivals_counts, _ = np.histogram(arrivals_binned, bins=np.arange(0, (total_hours * 60) // t_interval + 1))
			d[count] = arrivals_counts
			#print(arrivals_counts)

			# Update pax_per_t array
			pax_per_t[:len(arrivals_counts)] += arrivals_counts #dont do anything with this now
			count += 1
		#print(d)

		new_d = {}
		for i, sublist in d.items():
			for j in range(len(sublist)):
				new_d[(i, j)] = sublist[j]

		return new_d

	d = get_d()

	def get_T():
		earliest_checkin = 4*60 # 4 hours before departure
		T = {}
		for index, flight in flights.iterrows():
			etd_minutes = flight['ETD_minutes']
			no_checkin_t = set()
			for i in range(total_hours*60//t_interval):
				t = i * t_interval
				if t < etd_minutes - earliest_checkin:
					no_checkin_t.add(i)
				elif t > etd_minutes - last_check_in_time:
					no_checkin_t.add(i)
			T[index] = no_checkin_t

		return T

	T = get_T()
	return d, T

d, T = get_d_and_T()
print(d)
#print(T)
