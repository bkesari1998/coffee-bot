import math
import random

# #Epsilon-greedy
MAX_EPSILON = 0.2
MAX_TIMESTEPS = 2000
MAX_RHO = 0.3
MIN_RHO = 0.05
EXPLORATION_STOP = 30
SCORE_TO_CHECK = 900
NO_OF_SUCCESSFUL_DONE = 96

# remains same always
UPDATE_RATE = 10 # network weights update rate
MAX_EPISODES = 100
EPS_TO_EVAL = 10
EVAL_INTERVAL = 10
NUM_HIDDEN = 18
GAMMA = 0.98
LEARNING_RATE = 1e-3
DECAY_RATE = 0.99
MIN_EPSILON = 0.05
random_seed = random.randint(0, 199)
# print ("Seed ->:", random_seed)
LAMBDA = -math.log(0.01) / EXPLORATION_STOP # speed of decay
PRINT_EVERY = 101 # logging
# convergence criteria
NO_OF_EPS_TO_CHECK = 100
NO_OF_DONES_TO_CHECK = 100

POSITIVE_REINFORCEMENT = 1000
NEGATIVE_REINFORCEMENT = -350
NORMAL_REINFORCEMENT = -1

SAVE_EVERY = 5