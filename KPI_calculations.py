from collections import deque
import matplotlib.pyplot as plt

class FIFOQueue:
	def __init__(self):
		self.queue = deque()
		self.waiting_times = []

	def process_time_step(self, join_count, leave_count, current_time):
		# Add new agents to the queue
		for _ in range(join_count):
			self.queue.append(current_time)

		# Remove agents from the queue and calculate their waiting time
		for _ in range(leave_count):
			if self.queue:
				entry_time = self.queue.popleft()
				waiting_time = current_time - entry_time
				self.waiting_times.append(waiting_time)

	def max_waiting_time(self):
		if self.waiting_times:
			return max(self.waiting_times)
		else:
			return None

def get_longest_queue_time(q, I):
	# Create the queue
	queue = FIFOQueue()

	join_counts = [0] * (len(I) - 1)
	for t in range(1, len(I)):
		join_counts[t - 1] = I[t] - I[t - 1] + q[t]

	# Process each time step
	for current_time in range(1, len(I)):
		join_count = int(join_counts[current_time - 1])
		leave_count = int(q[current_time])
		queue.process_time_step(join_count, leave_count, current_time)

	# Plotting part
	join_counts = [0] + join_counts
	leave_counts = q
	net_difference = [join_counts[i] - leave_counts[i] for i in range(len(leave_counts))]
	plt.figure(figsize=(12, 6))
	plt.plot(range(len(join_counts)), join_counts, label='People Joining', marker='o')
	plt.plot(range(len(leave_counts)), leave_counts, label='People Leaving', marker='x')
	plt.plot(range(len(net_difference)), net_difference, label='Net Difference', marker='s')
	plt.plot(range(len(I)), I, label='Current queue size', marker = 'v')
	plt.xlabel('Time Step')
	plt.ylabel('Number of People')
	plt.title('Queue Dynamics')
	plt.legend()
	plt.grid(True)
	plt.show()

	# Get the maximum waiting time
	max_wait = queue.max_waiting_time()
	print(f"The maximum waiting time is {max_wait} time units")
	return max_wait

# q = [0, 1, 2, 1, 3]  # Number of people leaving the queue at each time step
# I = [0, 3, 5, 4, 6]  # Current size of the queue at each time step
#
# # Run the function with the test case
# print(get_longest_queue_time(q, I))